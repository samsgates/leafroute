from __future__ import annotations

from leafroute.models import Candidate, QueryIR


def compute_confidence(candidates: list[Candidate], query: QueryIR) -> tuple[float, dict[str, float]]:
    if not candidates:
        return 0.0, {"candidate_strength": 0.0, "ranking_margin": 0.0, "coverage": 0.0}
    best = candidates[0].score
    second = candidates[1].score if len(candidates) > 1 else 0.0
    margin = max(0.0, best - second)
    margin_norm = min(1.0, margin / 0.30)

    required = 1
    if query.requires_multiple_evidence:
        required = 2
    strong = sum(1 for c in candidates[:5] if c.score >= max(0.25, best * 0.60))
    coverage = min(1.0, strong / required)

    ambiguity_penalty = 0.0
    if len(candidates) > 2 and abs(candidates[0].score - candidates[2].score) < 0.05:
        ambiguity_penalty = 0.12
    if query.requires_reasoning:
        ambiguity_penalty += 0.05

    confidence = (
        best * 0.55
        + margin_norm * 0.22
        + coverage * 0.23
        - ambiguity_penalty
    )
    confidence = max(0.0, min(1.0, confidence))
    return confidence, {
        "candidate_strength": round(best, 4),
        "ranking_margin": round(margin_norm, 4),
        "coverage": round(coverage, 4),
        "ambiguity_penalty": round(ambiguity_penalty, 4),
    }
