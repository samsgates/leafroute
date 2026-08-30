"""LeafRoute public API."""

from .engine import LeafRoute, compile_document, open_index
from .models import EvidencePack, QueryIR, SearchResult, TreeIR

__all__ = [
    "LeafRoute",
    "compile_document",
    "open_index",
    "EvidencePack",
    "QueryIR",
    "SearchResult",
    "TreeIR",
]

from .version import __version__
