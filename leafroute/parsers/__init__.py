from __future__ import annotations

from pathlib import Path

from leafroute.errors import UnsupportedDocumentError
from leafroute.parsers.base import DocumentParser
from leafroute.parsers.pdf import PDFParser
from leafroute.parsers.text import TextParser
from leafroute.parsers.html import HTMLDocumentParser
from leafroute.parsers.docx import DOCXParser

PARSERS: tuple[DocumentParser, ...] = (PDFParser(), HTMLDocumentParser(), DOCXParser(), TextParser())


def get_parser(path: str | Path) -> DocumentParser:
    for parser in PARSERS:
        if parser.supports(path):
            return parser
    raise UnsupportedDocumentError(f"Unsupported document type: {Path(path).suffix}")
