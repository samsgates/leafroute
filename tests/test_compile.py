from leafroute import LeafRoute
from leafroute.config import LeafRouteConfig


def test_compile_tree_and_artifact(sample_md, tmp_path):
    artifact = tmp_path / "report.leaf"
    engine = LeafRoute.compile(sample_md, output=artifact, config=LeafRouteConfig(domain_pack="finance"))
    assert artifact.exists()
    assert len(engine.tree.nodes) >= 6
    assert any("Revenue" in n.title for n in engine.tree.nodes.values())
    assert len(engine.tree.numeric_facts) >= 5
    assert engine.inspect()["root_hash"]
    engine.close()

    reopened = LeafRoute.open(artifact)
    assert reopened.tree.title == "report"
    assert len(reopened.tree.nodes) >= 6
    reopened.close()
