from __future__ import annotations

from abc import ABC, abstractmethod

from leafroute.models import EvidencePack, QueryIR, TreeIR


class ReasoningProvider(ABC):
    @abstractmethod
    def verify(self, query: QueryIR, candidate_node_ids: list[str], tree: TreeIR) -> list[str]:
        """Return candidate node ids in preferred order."""
        raise NotImplementedError

    @abstractmethod
    def answer(self, query: str, evidence: EvidencePack) -> str:
        """Generate an answer using only supplied evidence."""
        raise NotImplementedError
