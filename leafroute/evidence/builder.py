from __future__ import annotations

from leafroute.models import Candidate, Evidence, EvidencePack, TreeIR


def build_evidence_pack(tree: TreeIR, query: str, candidates: list[Candidate], confidence: float, max_chars: int = 5000) -> EvidencePack:
    evidence: list[Evidence] = []
    for candidate in candidates:
        node = tree.nodes[candidate.node_id]
        text = node.text.strip()
        if not text:
            text = "\n".join(node.important_sentences)
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + "..."
        evidence.append(
            Evidence(
                document_id=tree.document_id,
                node_id=node.id,
                page_start=node.page_start,
                page_end=node.page_end,
                section=" > ".join(node.path),
                text=text,
                score=candidate.score,
                reasons=candidate.reasons,
            )
        )
    return EvidencePack(
        query=query,
        document_ids=[tree.document_id],
        evidence=evidence,
        confidence=confidence,
    )
