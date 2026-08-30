from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StructureConfig(BaseModel):
    heading_confidence: float = Field(0.62, ge=0, le=1)
    max_heading_chars: int = Field(180, ge=20)
    max_leaf_chars: int = Field(18_000, ge=1000)
    merge_leaf_chars: int = Field(240, ge=0)
    llm_repair: bool = False


class RetrievalConfig(BaseModel):
    beam_width: int = Field(4, ge=1, le=32)
    top_k: int = Field(5, ge=1, le=100)
    early_stop_score: float = Field(0.88, ge=0, le=1)
    early_stop_margin: float = Field(0.20, ge=0, le=1)
    verifier_threshold: float = Field(0.60, ge=0, le=1)
    lightweight_threshold: float = Field(0.78, ge=0, le=1)
    max_nodes_examined: int = Field(500, ge=10)


class BudgetConfig(BaseModel):
    max_latency_ms: int | None = Field(default=None, ge=1)
    max_llm_calls: int = Field(0, ge=0)
    max_llm_tokens: int = Field(0, ge=0)


class LeafRouteConfig(BaseModel):
    mode: Literal["fast", "balanced", "deep", "offline"] = "fast"
    offline: bool = False
    structure: StructureConfig = Field(default_factory=StructureConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    enable_entities: bool = True
    enable_numeric: bool = True
    enable_tables: bool = True
    enable_route_cache: bool = True
    domain_pack: Literal["none", "finance", "legal", "combined"] = "none"

    def effective_budget(self) -> BudgetConfig:
        if self.offline or self.mode in {"fast", "offline"}:
            return BudgetConfig(
                max_latency_ms=self.budget.max_latency_ms,
                max_llm_calls=0,
                max_llm_tokens=0,
            )
        if self.mode == "balanced" and self.budget.max_llm_calls == 0:
            return BudgetConfig(
                max_latency_ms=self.budget.max_latency_ms,
                max_llm_calls=1,
                max_llm_tokens=max(self.budget.max_llm_tokens, 4000),
            )
        return self.budget
