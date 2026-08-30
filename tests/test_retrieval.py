from leafroute import LeafRoute
from leafroute.config import LeafRouteConfig
from leafroute.models import QueryType


def test_numeric_query_routes_to_revenue(sample_md):
    engine = LeafRoute.compile(sample_md, config=LeafRouteConfig(domain_pack="finance"))
    result = engine.search("What was revenue in FY2025?", top_k=3)
    assert result.query_ir.query_type == QueryType.NUMERIC_LOOKUP
    assert result.trace.llm_calls == 0
    assert result.evidence_pack.evidence
    assert "Revenue" in result.evidence_pack.evidence[0].section
    assert "$120 million" in result.evidence_pack.evidence[0].text
    engine.close()


def test_causal_query_is_multihop(sample_md):
    engine = LeafRoute.compile(sample_md)
    result = engine.search("Why did operating margin decline?", top_k=4)
    assert result.query_ir.query_type == QueryType.MULTIHOP
    assert result.query_ir.requires_reasoning
    assert any("Operating Income" in e.section for e in result.evidence_pack.evidence)
    engine.close()


def test_route_cache(sample_md, tmp_path):
    artifact = tmp_path / "cached.leaf"
    engine = LeafRoute.compile(sample_md, output=artifact)
    engine.search("What was revenue in FY2025?")
    second = engine.search("What was revenue in FY2025?")
    assert second.trace.route_cache_hit
    engine.close()
