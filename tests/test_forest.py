from leafroute import LeafRoute
from leafroute.corpus import DocumentForest


def test_document_forest(sample_md, tmp_path):
    a = LeafRoute.compile(sample_md, output=tmp_path / "a.leaf")
    other = tmp_path / "other.md"
    other.write_text("# Beta Manual\n\n## Safety\n\nEmergency shutdown time is 12 seconds.", encoding="utf-8")
    b = LeafRoute.compile(other, output=tmp_path / "b.leaf")
    forest = DocumentForest([a, b])
    pack = forest.search("What was revenue in FY2025?", document_k=2, evidence_k=4)
    assert any("Revenue" in e.section for e in pack.evidence)
    forest.close()
