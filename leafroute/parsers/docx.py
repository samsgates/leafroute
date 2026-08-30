from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from leafroute.models import ParsedBlock, ParsedDocument, ParsedPage
from leafroute.parsers.base import DocumentParser
from leafroute.utils import normalize_text

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DOCXParser(DocumentParser):
    extensions = (".docx",)

    def parse(self, path: str | Path) -> ParsedDocument:
        source = Path(path)
        with zipfile.ZipFile(source) as zf:
            xml = ET.fromstring(zf.read("word/document.xml"))
            blocks: list[ParsedBlock] = []
            order = 0
            for paragraph in xml.iter(W + "p"):
                texts = [node.text or "" for node in paragraph.iter(W + "t")]
                text = normalize_text("".join(texts))
                if not text:
                    continue
                style_el = paragraph.find(f"{W}pPr/{W}pStyle")
                style = style_el.get(W + "val", "") if style_el is not None else ""
                heading_level = _heading_level(style)
                if heading_level:
                    text = "#" * heading_level + " " + text
                blocks.append(ParsedBlock(id=f"p1_b{order}", page=1, text=text, source_order=order))
                order += 1
        return ParsedDocument(
            source_path=str(source),
            source_type="docx",
            title=source.stem,
            pages=[ParsedPage(number=1, blocks=blocks)],
            metadata={},
        )


def _heading_level(style: str) -> int | None:
    lowered = style.lower().replace(" ", "")
    for i in range(1, 7):
        if lowered in {f"heading{i}", f"titre{i}"}:
            return i
    return None
