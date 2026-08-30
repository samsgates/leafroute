import pymupdf

from leafroute import LeafRoute


def test_pdf_layout_parser(tmp_path):
    pdf = tmp_path / "simple.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Financial Results", fontsize=20)
    page.insert_text((72, 110), "Revenue", fontsize=16)
    page.insert_text((72, 140), "Revenue in 2025 was $42 million.", fontsize=11)
    doc.save(pdf)
    doc.close()

    engine = LeafRoute.compile(pdf)
    assert engine.tree.page_count == 1
    result = engine.search("What was revenue in 2025?")
    assert result.evidence_pack.evidence
    assert "42 million" in " ".join(e.text for e in result.evidence_pack.evidence)
    engine.close()
