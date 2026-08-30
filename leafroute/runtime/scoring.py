from __future__ import annotations

from rapidfuzz.fuzz import token_set_ratio

from leafroute.models import QueryIR, TreeNode
from leafroute.utils import meaningful_terms, normalize_key


def score_node(node: TreeNode, query: QueryIR, lexical_score: float = 0.0) -> tuple[float, dict[str, float]]:
    q_terms = set(meaningful_terms(query.normalized_query))
    title_terms = set(node.routing_signature.title_terms)
    path_terms = set(node.routing_signature.path_terms)
    keywords = set(node.keywords)

    title = token_set_ratio(query.normalized_query, node.normalized_title) / 100.0 if node.title else 0.0
    path = token_set_ratio(query.normalized_query, normalize_key(" ".join(node.path))) / 100.0 if node.path else 0.0
    keyword = len(q_terms & keywords) / max(1, len(q_terms))
    title_overlap = len(q_terms & title_terms) / max(1, len(q_terms))
    path_overlap = len(q_terms & path_terms) / max(1, len(q_terms))

    entity = 0.0
    if query.entities:
        target = {normalize_key(e) for e in query.entities}
        present = {normalize_key(e) for e in node.entities}
        entity = sum(1.0 for e in target if any(e in p or p in e for p in present)) / max(1, len(target))

    metric = 0.0
    if query.metrics:
        present_metrics = {normalize_key(m) for m in node.metrics}
        metric = sum(1.0 for m in query.metrics if normalize_key(m) in present_metrics or normalize_key(m) in normalize_key(node.title + " " + node.text[:3000])) / max(1, len(query.metrics))

    temporal = 0.0
    requested_dates = [normalize_key(x) for x in query.dates + query.periods]
    if requested_dates:
        hay = normalize_key(" ".join(node.dates) + " " + node.text[:4000])
        temporal = sum(1.0 for d in requested_dates if d in hay) / max(1, len(requested_dates))

    numeric = node.routing_signature.numeric_density if query.requires_numeric else 0.0
    table = node.routing_signature.table_density if query.requires_table else 0.0
    structural = node.routing_signature.importance

    weights = {
        "lexical": 0.23,
        "title": 0.13,
        "title_overlap": 0.08,
        "path": 0.08,
        "path_overlap": 0.06,
        "keyword": 0.10,
        "entity": 0.08,
        "metric": 0.10,
        "temporal": 0.07,
        "numeric": 0.03,
        "table": 0.02,
        "structural": 0.02,
    }
    signals = {
        "lexical": lexical_score,
        "title": title,
        "title_overlap": title_overlap,
        "path": path,
        "path_overlap": path_overlap,
        "keyword": keyword,
        "entity": entity,
        "metric": metric,
        "temporal": temporal,
        "numeric": numeric,
        "table": table,
        "structural": structural,
    }
    score = sum(weights[k] * signals[k] for k in weights)
    return min(1.0, score), {k: round(v, 4) for k, v in signals.items() if v > 0}
