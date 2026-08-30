from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from leafroute.models import QueryIR, TreeNode
from leafroute.utils import normalize_key


@dataclass(slots=True)
class RoutingRule:
    name: str
    match_metrics: set[str] = field(default_factory=set)
    match_topics: set[str] = field(default_factory=set)
    prefer_sections: set[str] = field(default_factory=set)
    score_boost: float = 0.08

    def applies(self, query: QueryIR) -> bool:
        metrics = {normalize_key(x) for x in query.metrics}
        topics = {normalize_key(x) for x in query.topics}
        return bool(metrics & {normalize_key(x) for x in self.match_metrics}) or bool(
            topics & {normalize_key(x) for x in self.match_topics}
        )

    def boost(self, node: TreeNode) -> float:
        path = normalize_key(" ".join(node.path))
        if any(normalize_key(section) in path for section in self.prefer_sections):
            return self.score_boost
        return 0.0


FINANCE_RULES = [
    RoutingRule(
        name="finance-income-statement",
        match_metrics={"revenue", "sales", "operating income", "net income", "eps", "gross margin"},
        prefer_sections={"financial statements", "results of operations", "income statement", "management discussion"},
        score_boost=0.10,
    ),
    RoutingRule(
        name="finance-liquidity",
        match_metrics={"liquidity", "cash flow", "debt", "free cash flow"},
        prefer_sections={"liquidity", "capital resources", "cash flows", "debt"},
        score_boost=0.10,
    ),
]

LEGAL_RULES = [
    RoutingRule(
        name="legal-termination",
        match_topics={"termination", "terminate", "term"},
        prefer_sections={"term", "termination", "duration"},
        score_boost=0.12,
    ),
    RoutingRule(
        name="legal-liability",
        match_topics={"liability", "indemnification", "indemnity"},
        prefer_sections={"liability", "indemnification", "limitation"},
        score_boost=0.12,
    ),
]


class RulePack:
    def __init__(self, rules: Iterable[RoutingRule] = ()): 
        self.rules = list(rules)

    @classmethod
    def finance(cls) -> "RulePack":
        return cls(FINANCE_RULES)

    @classmethod
    def legal(cls) -> "RulePack":
        return cls(LEGAL_RULES)

    @classmethod
    def combined(cls) -> "RulePack":
        return cls([*FINANCE_RULES, *LEGAL_RULES])

    def score_boost(self, query: QueryIR, node: TreeNode) -> float:
        return min(0.25, sum(rule.boost(node) for rule in self.rules if rule.applies(query)))
