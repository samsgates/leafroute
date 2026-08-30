from __future__ import annotations

from collections import defaultdict

from leafroute.config import LeafRouteConfig
from leafroute.index import SQLiteIndex
from leafroute.models import Candidate, QueryIR, RetrievalPlan, TreeIR
from leafroute.runtime.scoring import score_node
from leafroute.runtime.executor import PlanExecutor
from leafroute.rules import RulePack
from leafroute.utils import content_hash, meaningful_terms


class TreeRouter:
    def __init__(self, tree: TreeIR, index: SQLiteIndex, config: LeafRouteConfig):
        self.tree = tree
        self.index = index
        self.config = config

    def query_signature(self, query: QueryIR) -> str:
        features = [
            query.query_type.value,
            *sorted(query.metrics),
            *sorted(query.entities),
            *sorted(query.dates),
            *sorted(query.periods),
            *meaningful_terms(query.normalized_query)[:8],
        ]
        return content_hash("|".join(features))[:24]

    def route(self, query: QueryIR, top_k: int, plan: RetrievalPlan | None = None) -> tuple[list[Candidate], dict[str, int | bool]]:
        signature = self.query_signature(query)
        root_hash = self.tree.nodes[self.tree.root_id].subtree_hash
        if self.config.enable_route_cache:
            cached = self.index.cache_get(self.tree.document_id, root_hash, signature)
            if cached:
                candidates = []
                for node_id in cached:
                    node = self.tree.nodes.get(node_id)
                    if not node:
                        continue
                    score, reasons = score_node(node, query, lexical_score=0.8)
                    candidates.append(Candidate(node_id=node_id, score=score, reasons={**reasons, "route_cache": 1.0}))
                candidates.sort(key=lambda c: c.score, reverse=True)
                if candidates:
                    return candidates[:top_k], {"nodes_examined": len(candidates), "nodes_pruned": max(0, len(self.tree.nodes) - len(candidates)), "cache_hit": True}

        lexical = dict(self.index.lexical_search(query.query, limit=min(120, self.config.retrieval.max_nodes_examined)))
        entity_scores = self.index.entity_search(query.entities)
        date_scores = self.index.date_search(query.dates + query.periods)
        numeric_scores = self.index.numeric_label_search(query.metrics) if query.requires_numeric else {}
        plan_scores: dict[str, float] = {}
        plan_reasons: dict[str, dict[str, float]] = {}
        if plan is not None:
            plan_scores, plan_reasons = PlanExecutor(self.tree, self.index).seed_scores(
                plan, limit=min(200, self.config.retrieval.max_nodes_examined)
            )

        seed_ids = set(lexical) | set(entity_scores) | set(date_scores) | set(numeric_scores) | set(plan_scores)
        if not seed_ids:
            seed_ids = set(self.tree.nodes)

        # Add tree-neighborhood candidates around high-scoring seeds.
        expanded = set(seed_ids)
        for node_id in list(seed_ids)[:80]:
            node = self.tree.nodes.get(node_id)
            if not node:
                continue
            if node.parent_id:
                expanded.add(node.parent_id)
                parent = self.tree.nodes.get(node.parent_id)
                if parent:
                    expanded.update(parent.child_ids[:30])
            expanded.update(node.child_ids[:30])

        # Hierarchical beam traversal prevents purely flat search from dominating.
        beam = [self.tree.root_id]
        examined_tree: set[str] = set()
        for _depth in range(8):
            next_candidates: list[tuple[float, str]] = []
            for node_id in beam:
                node = self.tree.nodes[node_id]
                examined_tree.add(node_id)
                for child_id in node.child_ids:
                    child = self.tree.nodes[child_id]
                    s, _ = score_node(child, query, max(lexical.get(child_id, 0.0), plan_scores.get(child_id, 0.0)))
                    next_candidates.append((s, child_id))
            if not next_candidates:
                break
            next_candidates.sort(reverse=True)
            beam = [node_id for _, node_id in next_candidates[: self.config.retrieval.beam_width]]
            expanded.update(beam)

        score_boosts: dict[str, float] = defaultdict(float)
        pack = None
        if self.config.domain_pack == "finance":
            pack = RulePack.finance()
        elif self.config.domain_pack == "legal":
            pack = RulePack.legal()
        elif self.config.domain_pack == "combined":
            pack = RulePack.combined()
        for node_id, value in entity_scores.items():
            score_boosts[node_id] += min(0.12, value * 0.05)
        for node_id, value in date_scores.items():
            score_boosts[node_id] += min(0.10, value * 0.04)
        for node_id, value in numeric_scores.items():
            score_boosts[node_id] += min(0.12, value * 0.04)

        ranked: list[Candidate] = []
        max_examined = self.config.retrieval.max_nodes_examined
        for node_id in list(expanded)[:max_examined]:
            node = self.tree.nodes.get(node_id)
            if not node or node.id == self.tree.root_id:
                continue
            score, reasons = score_node(node, query, max(lexical.get(node_id, 0.0), plan_scores.get(node_id, 0.0)))
            if node_id in plan_reasons:
                reasons.update(plan_reasons[node_id])
            if score_boosts[node_id]:
                score = min(1.0, score + score_boosts[node_id])
                reasons["structured_index_boost"] = round(score_boosts[node_id], 4)
            if pack is not None:
                domain_boost = pack.score_boost(query, node)
                if domain_boost:
                    score = min(1.0, score + domain_boost)
                    reasons["domain_rule_boost"] = round(domain_boost, 4)
            ranked.append(Candidate(node_id=node_id, score=score, reasons=reasons))

        ranked.sort(key=lambda c: c.score, reverse=True)
        result = ranked[:top_k]
        if self.config.enable_route_cache and result:
            self.index.cache_put(self.tree.document_id, root_hash, signature, [c.node_id for c in result])

        examined = min(len(expanded), max_examined)
        return result, {
            "nodes_examined": examined,
            "nodes_pruned": max(0, len(self.tree.nodes) - examined),
            "cache_hit": False,
        }
