from __future__ import annotations

from pathlib import Path

import pymupdf

from leafroute.models import BBox, ParsedBlock, ParsedDocument, ParsedPage, ParsedTable
from leafroute.parsers.base import DocumentParser
from leafroute.utils import normalize_text


class PDFParser(DocumentParser):
    extensions = (".pdf",)

    def parse(self, path: str | Path) -> ParsedDocument:
        source = Path(path)
        pages: list[ParsedPage] = []
        bookmarks: list[tuple[int, str, int]] = []

        with pymupdf.open(source) as doc:
            metadata = {k: v for k, v in (doc.metadata or {}).items() if v}
            toc = doc.get_toc(simple=True) or []
            for level, title, page in toc:
                bookmarks.append((int(level), str(title), max(1, int(page))))

            for page_index, page in enumerate(doc):
                data = page.get_text("dict", sort=True)
                blocks: list[ParsedBlock] = []
                order = 0
                for raw in data.get("blocks", []):
                    if raw.get("type") != 0 or "lines" not in raw:
                        continue
                    span_texts: list[str] = []
                    font_sizes: list[float] = []
                    bold_chars = 0
                    italic_chars = 0
                    total_chars = 0
                    line_count = 0
                    for line in raw.get("lines", []):
                        line_count += 1
                        line_parts: list[str] = []
                        for span in line.get("spans", []):
                            text = str(span.get("text", ""))
                            if not text:
                                continue
                            line_parts.append(text)
                            font_sizes.append(float(span.get("size", 0) or 0))
                            n = len(text)
                            total_chars += n
                            flags = int(span.get("flags", 0) or 0)
                            if flags & (1 << 4):
                                bold_chars += n
                            if flags & (1 << 1):
                                italic_chars += n
                        if line_parts:
                            span_texts.append(" ".join(line_parts))
                    text = normalize_text("\n".join(span_texts))
                    if not text:
                        continue
                    bbox_raw = raw.get("bbox")
                    bbox = BBox(x0=bbox_raw[0], y0=bbox_raw[1], x1=bbox_raw[2], y1=bbox_raw[3]) if bbox_raw else None
                    blocks.append(
                        ParsedBlock(
                            id=f"p{page_index+1}_b{order}",
                            page=page_index + 1,
                            text=text,
                            bbox=bbox,
                            font_size=max(font_sizes) if font_sizes else None,
                            bold_ratio=(bold_chars / total_chars) if total_chars else 0,
                            italic_ratio=(italic_chars / total_chars) if total_chars else 0,
                            line_count=line_count,
                            source_order=order,
                        )
                    )
                    order += 1

                tables: list[ParsedTable] = []
                try:
                    finder = page.find_tables()
                    for t_index, table in enumerate(getattr(finder, "tables", []) or []):
                        extracted = table.extract() or []
                        rows = [[str(cell or "").strip() for cell in row] for row in extracted]
                        bbox_raw = getattr(table, "bbox", None)
                        bbox = BBox(x0=bbox_raw[0], y0=bbox_raw[1], x1=bbox_raw[2], y1=bbox_raw[3]) if bbox_raw else None
                        tables.append(
                            ParsedTable(
                                id=f"p{page_index+1}_t{t_index}",
                                page=page_index + 1,
                                bbox=bbox,
                                rows=rows,
                            )
                        )
                except Exception:
                    # Table extraction is best-effort. Text retrieval must remain available.
                    pass

                pages.append(
                    ParsedPage(
                        number=page_index + 1,
                        width=float(page.rect.width),
                        height=float(page.rect.height),
                        blocks=blocks,
                        tables=tables,
                    )
                )

            title = metadata.get("title") or source.stem
            return ParsedDocument(
                source_path=str(source),
                source_type="pdf",
                title=title,
                pages=pages,
                metadata=metadata,
                bookmarks=bookmarks,
            )
