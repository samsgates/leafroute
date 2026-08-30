from leafroute.models import OperatorName, QueryType
from leafroute.query import QueryCompiler, RetrievalPlanner


def test_comparison_query_compilation():
    q = QueryCompiler().compile("Compare operating margin in 2024 and 2025")
    assert q.query_type == QueryType.COMPARISON
    assert q.requires_comparison
    assert "operating margin" in q.metrics
    assert set(q.dates) == {"2024", "2025"}
    plan = RetrievalPlanner().plan(q)
    assert any(op.name == OperatorName.TEMPORAL_JOIN for op in plan.operators)
