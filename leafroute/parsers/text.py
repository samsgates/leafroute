from __future__ import annotations

import re
from pathlib import Path

from leafroute.models import ParsedBlock, ParsedDocument, ParsedPage
from leafroute.parsers.base import DocumentParser
from leafroute.utils import normalize_text


class TextParser(DocumentParser):
    extensions = (".txt", ".md", ".markdown")

    def parse(self, path: str | Path) -> ParsedDocument:
        source = Path(path)
        raw = source.read_text(encoding="utf-8", errors="replace")
        if source.suffix.lower() in {".html", ".htm"}:
            raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<[^>]+>", "\n", raw)
        chunks = [normalize_text(c) for c in re.split(r"\n\s*\n", raw) if normalize_text(c)]
        blocks = [
            ParsedBlock(id=f"p1_b{i}", page=1, text=chunk, source_order=i)
            for i, chunk in enumerate(chunks)
        ]
        return ParsedDocument(
            source_path=str(source),
            source_type=source.suffix.lower().lstrip("."),
            title=source.stem,
            pages=[ParsedPage(number=1, blocks=blocks)],
            metadata={},
        )
