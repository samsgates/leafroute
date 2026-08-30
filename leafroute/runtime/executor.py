from __future__ import annotations

from collections import defaultdict

from leafroute.index import SQLiteIndex
from leafroute.models import OperatorName, QueryIR, RetrievalPlan, TreeIR
from leafroute.utils import normalize_key


class PlanExecutor:
    """Execute the candidate-generation portion of a logical RetrievalPlan.

    Ranking remains fused with tree-aware scoring in `TreeRouter`. Keeping the
    candidate stage plan-driven means new planners can change search behavior
    without rewriting the router.
    """

    def __init__(self, tree: TreeIR, index: SQLiteIndex):
        self.tree = tree
        self.index = index

    def seed_scores(self, plan: RetrievalPlan, limit: int = 200) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
        scores: dict[str, float] = defaultdict(float)
        reasons: dict[str, dict[str, float]] = defaultdict(dict)
        q = plan.query_ir

        for op in plan.operators:
            if op.name == OperatorName.SEARCH_TEXT:
                text = str(op.args.get("query") or q.query)
                for node_id, score in self.index.lexical_search(text, limit=limit):
                    scores[node_id] += score * 0.50
                    reasons[node_id]["plan_lexical"] = max(reasons[node_id].get("plan_lexical", 0.0), score)

            elif op.name == OperatorName.SEARCH_ENTITY:
                values = op.args.get("values") or q.entities
                for node_id, count in self.index.entity_search(values).items():
                    boost = min(1.0, count / max(1, len(values)))
                    scores[node_id] += boost * 0.25
                    reasons[node_id]["plan_entity"] = boost

            elif op.name == OperatorName.SEARCH_DATE:
                values = op.args.get("values") or (q.dates + q.periods)
                for node_id, count in self.index.date_search(values).items():
                    boost = min(1.0, count / max(1, len(values)))
                    scores[node_id] += boost * 0.20
                    reasons[node_id]["plan_date"] = boost

            elif op.name == OperatorName.SEARCH_METRIC:
                values = op.args.get("values") or q.metrics
                structured = self.index.numeric_label_search(values)
                for node_id, count in structured.items():
                    boost = min(1.0, count / max(1, len(values)))
                    scores[node_id] += boost * 0.25
                    reasons[node_id]["plan_metric_numeric"] = boost
                if values:
                    for node_id, lexical in self.index.lexical_search(" ".join(values), limit=limit):
                        scores[node_id] += lexical * 0.25
                        reasons[node_id]["plan_metric_lexical"] = lexical

            elif op.name == OperatorName.SEARCH_TABLE:
                for node_id, match in self.index.table_search(q.query, limit=limit).items():
                    scores[node_id] += match * 0.25
                    reasons[node_id]["plan_table"] = match

            elif op.name == OperatorName.FILTER_DATE:
                wanted = [normalize_key(v) for v in (op.args.get("values") or q.dates + q.periods)]
                if wanted and scores:
                    for node_id in list(scores):
                        node = self.tree.nodes.get(node_id)
                        if not node:
                            scores.pop(node_id, None)
                            continue
                        hay = normalize_key(" ".join(node.dates) + " " + node.text[:5000])
                        if not any(v in hay for v in wanted):
                            scores[node_id] *= 0.35
                            reasons[node_id]["plan_date_filter_penalty"] = 0.35

            elif op.name == OperatorName.FILTER_TYPE:
                allowed = {str(x) for x in op.args.get("types", [])}
                if allowed:
                    for node_id in list(scores):
                        node = self.tree.nodes.get(node_id)
                        if node and node.node_type.value not in allowed:
                            scores[node_id] *= 0.35
                            reasons[node_id]["plan_type_filter_penalty"] = 0.35

            elif op.name == OperatorName.EXPAND_PARENT:
                levels = int(op.args.get("levels", 1))
                additions: dict[str, float] = defaultdict(float)
                for node_id, score in list(scores.items()):
                    current = self.tree.nodes.get(node_id)
                    for level in range(levels):
                        if not current or not current.parent_id:
                            break
                        parent = self.tree.nodes.get(current.parent_id)
                        if not parent:
                            break
                        additions[parent.id] = max(additions[parent.id], score * (0.45 / (level + 1)))
                        current = parent
                for node_id, boost in additions.items():
                    scores[node_id] += boost
                    reasons[node_id]["plan_parent_expansion"] = boost

            elif op.name == OperatorName.EXPAND_CHILDREN:
                additions: dict[str, float] = defaultdict(float)
                for node_id, score in list(scores.items()):
                    node = self.tree.nodes.get(node_id)
                    if not node:
                        continue
                    for child_id in node.child_ids:
                        additions[child_id] = max(additions[child_id], score * 0.50)
                for node_id, boost in additions.items():
                    scores[node_id] += boost
                    reasons[node_id]["plan_child_expansion"] = boost

            elif op.name == OperatorName.EXPAND_SIBLINGS:
                additions: dict[str, float] = defaultdict(float)
                for node_id, score in list(scores.items()):
                    node = self.tree.nodes.get(node_id)
                    if not node or not node.parent_id:
                        continue
                    parent = self.tree.nodes.get(node.parent_id)
                    if not parent:
                        continue
                    for sibling_id in parent.child_ids:
                        if sibling_id != node_id:
                            additions[sibling_id] = max(additions[sibling_id], score * 0.25)
                for node_id, boost in additions.items():
                    scores[node_id] += boost
                    reasons[node_id]["plan_sibling_expansion"] = boost

            elif op.name == OperatorName.TEMPORAL_JOIN:
                wanted = [normalize_key(v) for v in (op.args.get("periods") or q.dates + q.periods)]
                if len(wanted) >= 2:
                    for node_id in list(scores):
                        node = self.tree.nodes.get(node_id)
                        if not node:
                            continue
                        hay = normalize_key(" ".join(node.dates) + " " + node.text[:6000])
                        coverage = sum(1 for p in wanted if p in hay) / len(wanted)
                        scores[node_id] += coverage * 0.15
                        if coverage:
                            reasons[node_id]["plan_temporal_coverage"] = coverage

            # RANK, PRUNE, TOP_K and READ are finalized by TreeRouter/EvidenceBuilder.

        if not scores:
            return {}, reasons
        peak = max(scores.values()) or 1.0
        normalized = {node_id: min(1.0, value / peak) for node_id, value in scores.items()}
        return normalized, reasons
