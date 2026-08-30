from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class NodeType(StrEnum):
    ROOT = "root"
    SECTION = "section"
    SUBSECTION = "subsection"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    APPENDIX = "appendix"
    UNKNOWN = "unknown"


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class TextSpan(BaseModel):
    text: str
    page: int
    bbox: BBox | None = None
    font_size: float | None = None
    bold: bool = False
    italic: bool = False
    block_id: str | None = None


class ParsedBlock(BaseModel):
    id: str
    page: int
    text: str
    bbox: BBox | None = None
    font_size: float | None = None
    bold_ratio: float = 0.0
    italic_ratio: float = 0.0
    line_count: int = 1
    source_order: int = 0


class ParsedTable(BaseModel):
    id: str
    page: int
    bbox: BBox | None = None
    rows: list[list[str]] = Field(default_factory=list)
    header_rows: int = 1
    section_hint: str | None = None


class ParsedPage(BaseModel):
    number: int
    width: float | None = None
    height: float | None = None
    blocks: list[ParsedBlock] = Field(default_factory=list)
    tables: list[ParsedTable] = Field(default_factory=list)

    @computed_field
    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks if b.text.strip())


class ParsedDocument(BaseModel):
    source_path: str
    source_type: str
    title: str | None = None
    pages: list[ParsedPage]
    metadata: dict[str, Any] = Field(default_factory=dict)
    bookmarks: list[tuple[int, str, int]] = Field(default_factory=list)

    @computed_field
    @property
    def page_count(self) -> int:
        return len(self.pages)


class NumericFact(BaseModel):
    raw: str
    value: float | None = None
    unit: str | None = None
    label: str | None = None
    period: str | None = None
    page: int
    node_id: str | None = None
    context: str | None = None


class EntityMention(BaseModel):
    name: str
    normalized: str
    kind: str = "entity"
    page: int
    node_id: str | None = None


class DateMention(BaseModel):
    raw: str
    normalized: str | None = None
    page: int
    node_id: str | None = None


class TableCell(BaseModel):
    row: int
    column: int
    row_header: str | None = None
    column_header: str | None = None
    value: str


class CompiledTable(BaseModel):
    id: str
    node_id: str
    page: int
    cells: list[TableCell] = Field(default_factory=list)
    raw_rows: list[list[str]] = Field(default_factory=list)


class RoutingSignature(BaseModel):
    title_terms: list[str] = Field(default_factory=list)
    path_terms: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    periods: list[str] = Field(default_factory=list)
    numeric_density: float = 0.0
    table_density: float = 0.0
    importance: float = 0.0


class TreeNode(BaseModel):
    id: str
    parent_id: str | None = None
    child_ids: list[str] = Field(default_factory=list)
    depth: int = 0
    title: str
    normalized_title: str = ""
    path: list[str] = Field(default_factory=list)
    node_type: NodeType = NodeType.UNKNOWN
    page_start: int
    page_end: int
    text: str = ""
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    important_sentences: list[str] = Field(default_factory=list)
    routing_signature: RoutingSignature = Field(default_factory=RoutingSignature)
    content_hash: str = ""
    subtree_hash: str = ""
    structure_confidence: float = 1.0
    source_block_ids: list[str] = Field(default_factory=list)


class TreeIR(BaseModel):
    format_version: str = "1.0"
    compiler_version: str = "0.1.0"
    document_id: str
    title: str
    source_type: str
    page_count: int
    root_id: str
    nodes: dict[str, TreeNode]
    numeric_facts: list[NumericFact] = Field(default_factory=list)
    entity_mentions: list[EntityMention] = Field(default_factory=list)
    date_mentions: list[DateMention] = Field(default_factory=list)
    tables: list[CompiledTable] = Field(default_factory=list)
    references: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def root(self) -> TreeNode:
        return self.nodes[self.root_id]


class QueryType(StrEnum):
    DIRECT_LOOKUP = "direct_lookup"
    SECTION_RETRIEVAL = "section_retrieval"
    NUMERIC_LOOKUP = "numeric_lookup"
    TEMPORAL = "temporal"
    COMPARISON = "comparison"
    MULTIHOP = "multihop"
    CROSS_SECTION = "cross_section"
    GLOBAL = "global"
    CONTRADICTION = "contradiction"
    TABLE = "table"
    CITATION = "citation"


class QueryIR(BaseModel):
    query: str
    normalized_query: str
    query_type: QueryType = QueryType.DIRECT_LOOKUP
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    periods: list[str] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)
    section_hints: list[str] = Field(default_factory=list)
    requires_numeric: bool = False
    requires_table: bool = False
    requires_multiple_evidence: bool = False
    requires_comparison: bool = False
    requires_global_coverage: bool = False
    requires_reasoning: bool = False


class OperatorName(StrEnum):
    SEARCH_TEXT = "SEARCH_TEXT"
    SEARCH_TITLE = "SEARCH_TITLE"
    SEARCH_PATH = "SEARCH_PATH"
    SEARCH_ENTITY = "SEARCH_ENTITY"
    SEARCH_NUMBER = "SEARCH_NUMBER"
    SEARCH_METRIC = "SEARCH_METRIC"
    SEARCH_DATE = "SEARCH_DATE"
    SEARCH_TABLE = "SEARCH_TABLE"
    FILTER_DATE = "FILTER_DATE"
    FILTER_TYPE = "FILTER_TYPE"
    EXPAND_PARENT = "EXPAND_PARENT"
    EXPAND_CHILDREN = "EXPAND_CHILDREN"
    EXPAND_SIBLINGS = "EXPAND_SIBLINGS"
    INTERSECT = "INTERSECT"
    UNION = "UNION"
    TEMPORAL_JOIN = "TEMPORAL_JOIN"
    RANK = "RANK"
    PRUNE = "PRUNE"
    TOP_K = "TOP_K"
    READ = "READ"
    READ_NEIGHBORS = "READ_NEIGHBORS"
    READ_TABLE = "READ_TABLE"


class RetrievalOperator(BaseModel):
    name: OperatorName
    args: dict[str, Any] = Field(default_factory=dict)


class RetrievalPlan(BaseModel):
    query_ir: QueryIR
    operators: list[RetrievalOperator]
    estimated_llm_calls: int = 0
    estimated_nodes: int | None = None


class Candidate(BaseModel):
    node_id: str
    score: float
    reasons: dict[str, float] = Field(default_factory=dict)


class Evidence(BaseModel):
    document_id: str
    node_id: str
    page_start: int
    page_end: int
    section: str
    text: str
    score: float
    reasons: dict[str, float] = Field(default_factory=dict)
    bbox: BBox | None = None
    table_id: str | None = None


class EvidencePack(BaseModel):
    query: str
    document_ids: list[str]
    evidence: list[Evidence]
    confidence: float
    conflicting_evidence: list[Evidence] = Field(default_factory=list)


class TraceEvent(BaseModel):
    stage: str
    duration_ms: float
    detail: dict[str, Any] = Field(default_factory=dict)


class RetrievalTrace(BaseModel):
    trace_id: str
    events: list[TraceEvent] = Field(default_factory=list)
    nodes_examined: int = 0
    nodes_pruned: int = 0
    llm_calls: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    route_cache_hit: bool = False
    total_latency_ms: float = 0.0


class SearchResult(BaseModel):
    query_ir: QueryIR
    plan: RetrievalPlan
    evidence_pack: EvidencePack
    trace: RetrievalTrace
    mode: Literal["fast", "balanced", "deep", "offline"] = "fast"


class AnswerResult(BaseModel):
    answer: str
    search: SearchResult
    model: str | None = None
