from __future__ import annotations

from pathlib import Path
from typing import Literal

from leafroute.compiler import DocumentCompiler
from leafroute.config import LeafRouteConfig
from leafroute.evidence import build_evidence_pack
from leafroute.errors import OfflineViolationError
from leafroute.incremental import TreeDiff, diff_trees
from leafroute.index import SQLiteIndex
from leafroute.models import AnswerResult, Candidate, SearchResult, TreeIR
from leafroute.providers.base import ReasoningProvider
from leafroute.query import QueryCompiler, RetrievalPlanner
from leafroute.runtime.confidence import compute_confidence
from leafroute.runtime.router import TreeRouter
from leafroute.telemetry import TraceCollector


class LeafRoute:
    """Compiled hierarchical retrieval engine.

    A LeafRoute instance owns TreeIR plus a local SQLite/FTS index. Retrieval can be
    fully deterministic or optionally escalate to a configured reasoning provider.
    """

    def __init__(
        self,
        tree: TreeIR,
        index: SQLiteIndex,
        config: LeafRouteConfig | None = None,
        reasoning_provider: ReasoningProvider | None = None,
    ):
        self.tree = tree
        self.index = index
        self.config = config or LeafRouteConfig()
        self.reasoning_provider = reasoning_provider
        self.query_compiler = QueryCompiler()
        self.planner = RetrievalPlanner()
        self.router = TreeRouter(tree, index, self.config)

    @classmethod
    def compile(
        cls,
        source: str | Path,
        *,
        output: str | Path | None = None,
        config: LeafRouteConfig | None = None,
        reasoning_provider: ReasoningProvider | None = None,
    ) -> "LeafRoute":
        config = config or LeafRouteConfig()
        tree = DocumentCompiler(config).compile(source)
        if output:
            index = SQLiteIndex.create(output, tree)
        else:
            index = SQLiteIndex.memory(tree)
        return cls(tree, index, config=config, reasoning_provider=reasoning_provider)

    @classmethod
    def open(
        cls,
        artifact: str | Path,
        *,
        config: LeafRouteConfig | None = None,
        reasoning_provider: ReasoningProvider | None = None,
    ) -> "LeafRoute":
        index = SQLiteIndex.open(artifact)
        tree = index.load_tree()
        return cls(tree, index, config=config, reasoning_provider=reasoning_provider)

    def save(self, artifact: str | Path) -> Path:
        target = Path(artifact)
        persisted = SQLiteIndex.create(target, self.tree)
        persisted.close()
        return target

    def inspect(self) -> dict:
        root = self.tree.root()
        return {
            "document_id": self.tree.document_id,
            "title": self.tree.title,
            "source_type": self.tree.source_type,
            "pages": self.tree.page_count,
            "nodes": len(self.tree.nodes),
            "numeric_facts": len(self.tree.numeric_facts),
            "entities": len(self.tree.entity_mentions),
            "tables": len(self.tree.tables),
            "root_hash": root.subtree_hash,
            "format_version": self.tree.format_version,
            "compiler_version": self.tree.compiler_version,
        }

    def search(
        self,
        query: str,
        *,
        mode: Literal["fast", "balanced", "deep", "offline"] | None = None,
        top_k: int | None = None,
        debug: bool = False,
        proof: bool = False,
    ) -> SearchResult:
        trace = TraceCollector()
        mode = mode or self.config.mode
        top_k = top_k or self.config.retrieval.top_k
        effective = self.config.model_copy(deep=True)
        effective.mode = mode
        if mode == "offline":
            effective.offline = True
        budget = effective.effective_budget()

        with trace.stage("query_compile") as detail:
            query_ir = self.query_compiler.compile(query)
            detail["query_type"] = query_ir.query_type.value
            detail["metrics"] = query_ir.metrics
            detail["entities"] = query_ir.entities
            detail["periods"] = query_ir.periods + query_ir.dates

        with trace.stage("query_plan") as detail:
            plan = self.planner.plan(query_ir, top_k=top_k)
            detail["operators"] = [op.name.value for op in plan.operators]

        with trace.stage("tree_route") as detail:
            self.router.config = effective
            candidates, route_stats = self.router.route(query_ir, max(top_k, 8 if query_ir.requires_multiple_evidence else top_k), plan=plan)
            trace.trace.nodes_examined = int(route_stats["nodes_examined"])
            trace.trace.nodes_pruned = int(route_stats["nodes_pruned"])
            trace.trace.route_cache_hit = bool(route_stats["cache_hit"])
            detail.update(route_stats)
            detail["candidate_count"] = len(candidates)

        with trace.stage("confidence") as detail:
            confidence, components = compute_confidence(candidates, query_ir)
            detail.update(components)
            detail["confidence"] = confidence

        should_verify = (
            mode in {"balanced", "deep"}
            and confidence < effective.retrieval.lightweight_threshold
            and budget.max_llm_calls > 0
        )
        if should_verify:
            if effective.offline:
                raise OfflineViolationError("Reasoning escalation is prohibited in offline mode")
            if self.reasoning_provider is not None:
                with trace.stage("llm_verify") as detail:
                    before = [c.node_id for c in candidates]
                    verified = self.reasoning_provider.verify(query_ir, before, self.tree)
                    trace.trace.llm_calls += 1
                    order = {node_id: pos for pos, node_id in enumerate(verified)}
                    candidates.sort(key=lambda c: (order.get(c.node_id, 10_000), -c.score))
                    candidates = candidates[:top_k]
                    confidence = min(1.0, confidence + 0.12)
                    detail["verified_nodes"] = verified
            elif mode == "deep":
                # Deep mode remains usable without a provider, but records that escalation was unavailable.
                trace.trace.events.append(
                    __import__("leafroute.models", fromlist=["TraceEvent"]).TraceEvent(
                        stage="llm_verify_skipped",
                        duration_ms=0.0,
                        detail={"reason": "no_reasoning_provider"},
                    )
                )

        if query_ir.requires_multiple_evidence:
            candidates = candidates[: max(top_k, 4)]
        else:
            candidates = candidates[:top_k]

        with trace.stage("evidence_build") as detail:
            pack = build_evidence_pack(self.tree, query, candidates, confidence)
            detail["evidence_count"] = len(pack.evidence)
            if proof:
                detail["proof"] = True

        return SearchResult(
            query_ir=query_ir,
            plan=plan,
            evidence_pack=pack,
            trace=trace.finish(),
            mode=mode,
        )

    def ask(
        self,
        query: str,
        *,
        mode: Literal["fast", "balanced", "deep", "offline"] | None = None,
        top_k: int | None = None,
    ) -> AnswerResult:
        search = self.search(query, mode=mode, top_k=top_k, proof=True)
        if self.reasoning_provider is None:
            return AnswerResult(
                answer=self._extractive_answer(search),
                search=search,
                model=None,
            )
        if (mode or self.config.mode) == "offline" or self.config.offline:
            raise OfflineViolationError("Answer generation provider is prohibited in offline mode")
        answer = self.reasoning_provider.answer(query, search.evidence_pack)
        return AnswerResult(answer=answer, search=search, model=getattr(self.reasoning_provider, "model", None))

    def update(self, new_source: str | Path, *, output: str | Path | None = None) -> tuple["LeafRoute", TreeDiff]:
        new_tree = DocumentCompiler(self.config).compile(new_source)
        diff = diff_trees(self.tree, new_tree)
        if output:
            new_index = SQLiteIndex.create(output, new_tree)
        else:
            new_index = SQLiteIndex.memory(new_tree)
        return LeafRoute(new_tree, new_index, self.config, self.reasoning_provider), diff

    @staticmethod
    def _extractive_answer(search: SearchResult) -> str:
        if not search.evidence_pack.evidence:
            return "No sufficiently relevant evidence was found."
        parts: list[str] = []
        for item in search.evidence_pack.evidence[:3]:
            snippet = " ".join(item.text.split())[:700]
            page = f"p. {item.page_start}" if item.page_start == item.page_end else f"pp. {item.page_start}-{item.page_end}"
            parts.append(f"[{page}] {snippet}")
        return "\n\n".join(parts)

    def close(self) -> None:
        self.index.close()


def compile_document(source: str | Path, output: str | Path | None = None, config: LeafRouteConfig | None = None) -> LeafRoute:
    return LeafRoute.compile(source, output=output, config=config)


def open_index(artifact: str | Path, config: LeafRouteConfig | None = None) -> LeafRoute:
    return LeafRoute.open(artifact, config=config)
