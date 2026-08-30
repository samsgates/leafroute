from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QueryBuilder:
    """Small programmatic query DSL that compiles down to natural retrieval hints."""

    _terms: list[str] = field(default_factory=list)
    _metrics: list[str] = field(default_factory=list)
    _periods: list[str] = field(default_factory=list)
    _entities: list[str] = field(default_factory=list)

    def find(self, *terms: str) -> "QueryBuilder":
        self._terms.extend(terms)
        return self

    def metric(self, *metrics: str) -> "QueryBuilder":
        self._metrics.extend(metrics)
        return self

    def period(self, *periods: str) -> "QueryBuilder":
        self._periods.extend(periods)
        return self

    def entity(self, *entities: str) -> "QueryBuilder":
        self._entities.extend(entities)
        return self

    def render(self) -> str:
        pieces = []
        if self._terms:
            pieces.append(" ".join(self._terms))
        if self._metrics:
            pieces.append("metrics " + ", ".join(self._metrics))
        if self._periods:
            pieces.append("period " + ", ".join(self._periods))
        if self._entities:
            pieces.append("entities " + ", ".join(self._entities))
        return ". ".join(pieces)
