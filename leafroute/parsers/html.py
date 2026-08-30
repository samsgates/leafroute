from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from leafroute.models import ParsedBlock, ParsedDocument, ParsedPage
from leafroute.parsers.base import DocumentParser
from leafroute.utils import normalize_text


class _BlockHTMLParser(HTMLParser):
    BLOCKS = {"p", "div", "li", "blockquote", "pre", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.current: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.skip += 1
            return
        if tag in self.BLOCKS:
            self._flush()
            self.stack.append(tag)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
            return
        if tag in self.BLOCKS:
            self._flush(tag)
            if self.stack:
                self.stack.pop()

    def handle_data(self, data: str):
        if not self.skip:
            self.current.append(data)

    def _flush(self, tag: str | None = None):
        text = normalize_text(" ".join(self.current))
        self.current = []
        if text:
            active = tag or (self.stack[-1] if self.stack else "p")
            self.blocks.append((active, text))


class HTMLDocumentParser(DocumentParser):
    extensions = (".html", ".htm")

    def parse(self, path: str | Path) -> ParsedDocument:
        source = Path(path)
        parser = _BlockHTMLParser()
        parser.feed(source.read_text(encoding="utf-8", errors="replace"))
        parser._flush()
        blocks = []
        for i, (tag, text) in enumerate(parser.blocks):
            if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
                text = "#" * min(6, int(tag[1])) + " " + text
            blocks.append(ParsedBlock(id=f"p1_b{i}", page=1, text=text, source_order=i))
        return ParsedDocument(
            source_path=str(source),
            source_type="html",
            title=source.stem,
            pages=[ParsedPage(number=1, blocks=blocks)],
            metadata={},
        )
