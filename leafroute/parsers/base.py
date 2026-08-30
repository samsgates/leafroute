from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from leafroute.models import ParsedDocument


class DocumentParser(ABC):
    extensions: tuple[str, ...] = ()

    def supports(self, path: str | Path) -> bool:
        return Path(path).suffix.lower() in self.extensions

    @abstractmethod
    def parse(self, path: str | Path) -> ParsedDocument:
        raise NotImplementedError
