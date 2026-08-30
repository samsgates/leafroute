from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rapidfuzz.fuzz import token_set_ratio

from leafroute.engine import LeafRoute
from leafroute.models import Evidence, EvidencePack, SearchResult
from leafroute.utils import normalize_key


@dataclass(slots=True)
class CorpusHit:
    engine: LeafRoute
    score: float


class DocumentForest:
    """A lightweight multi-document router over compiled LeafRoute artifacts."""

    def __init__(self, engines: list[LeafRoute]):
        self.engines = engines

    @classmethod
    def open_directory(cls, directory: str | Path) -> "DocumentForest":
        root = Path(directory)
        engines = [LeafRoute.open(path) for path in sorted(root.glob("*.leaf"))]
        return cls(engines)

    def route_documents(self, query: str, limit: int = 5) -> list[CorpusHit]:
        normalized = normalize_key(query)
        hits: list[CorpusHit] = []
        for engine in self.engines:
            tree = engine.tree
            metadata_text = " ".join(
                [
                    tree.title,
                    str(tree.metadata.get("author", "")),
                    str(tree.metadata.get("subject", "")),
                    " ".join(tree.root().routing_signature.keywords),
                    " ".join(tree.root().routing_signature.entities),
                ]
            )
            score = token_set_ratio(normalized, normalize_key(metadata_text)) / 100.0
            # Give every document a lexical probe so corpus routing is not title-only.
            lexical = engine.index.lexical_search(query, limit=3)
            if lexical:
                score = min(1.0, score * 0.45 + lexical[0][1] * 0.55)
            hits.append(CorpusHit(engine, score))
        return sorted(hits, key=lambda h: h.score, reverse=True)[:limit]

    def search(self, query: str, *, document_k: int = 4, evidence_k: int = 8, mode: str = "fast") -> EvidencePack:
        routed = self.route_documents(query, limit=document_k)
        evidence: list[Evidence] = []
        confidences: list[float] = []
        for hit in routed:
            result = hit.engine.search(query, mode=mode, top_k=max(2, evidence_k // max(1, document_k)))  # type: ignore[arg-type]
            confidences.append(result.evidence_pack.confidence)
            for item in result.evidence_pack.evidence:
                adjusted = item.model_copy(deep=True)
                adjusted.score = min(1.0, adjusted.score * 0.80 + hit.score * 0.20)
                evidence.append(adjusted)
        evidence.sort(key=lambda e: e.score, reverse=True)
        evidence = evidence[:evidence_k]
        return EvidencePack(
            query=query,
            document_ids=list(dict.fromkeys(e.document_id for e in evidence)),
            evidence=evidence,
            confidence=max(confidences, default=0.0),
        )

    def close(self) -> None:
        for engine in self.engines:
            engine.close()
