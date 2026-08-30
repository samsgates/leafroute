from __future__ import annotations

import re

from leafroute.compiler.enrich import COMMON_METRICS
from leafroute.models import QueryIR, QueryType
from leafroute.utils import meaningful_terms, normalize_key

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
PERIOD_RE = re.compile(r"\b(?:Q[1-4]|FY)\s*[-/]?\s*(?:19|20)?\d{2}\b", re.I)
PERCENT_RE = re.compile(r"\b(?:percent|percentage|margin|rate|%)\b", re.I)
MONEY_RE = re.compile(r"\b(?:revenue|income|sales|cost|expense|cash|debt|assets?|liabilities?|ebitda|profit)\b", re.I)
ENTITY_RE = re.compile(r"\b[A-Z][A-Za-z0-9&'’.\-]+(?:\s+[A-Z][A-Za-z0-9&'’.\-]+){0,4}\b")


class QueryCompiler:
    def compile(self, query: str) -> QueryIR:
        normalized = normalize_key(query)
        lower = query.lower()
        periods = list(dict.fromkeys(PERIOD_RE.findall(query)))
        dates = list(dict.fromkeys(YEAR_RE.findall(query)))
        entities = [e.strip() for e in ENTITY_RE.findall(query) if e.lower() not in {"what", "how", "when", "where", "compare", "show"}]
        metrics = sorted({m for m in COMMON_METRICS if m in normalized})

        comparison = any(w in lower for w in ("compare", "compared", "versus", " vs ", "change between", "difference between", "changed from"))
        contradiction = any(w in lower for w in ("contradict", "conflict", "inconsistent", "disagree"))
        global_scope = any(w in lower for w in ("summarize", "major themes", "main themes", "overall", "all risks", "key risks", "major risks"))
        causal = any(w in lower for w in ("why", "cause", "caused", "driver", "driven", "because", "impact", "affect"))
        citation = any(w in lower for w in ("cite", "citation", "supporting pages", "source pages", "show the pages", "evidence"))
        table = any(w in lower for w in ("table", "row", "column"))
        numeric_cues = (
            "how much", "how many", "what was", "what is the value", "amount", "number of",
            "margin", "revenue", "income", "sales", "cost", "expense", "cash flow", "debt",
            "rate", "percentage", "percent", "ebitda", "eps",
        )
        numeric = bool(metrics or dates or periods or PERCENT_RE.search(query) or MONEY_RE.search(query)) and any(
            w in lower for w in numeric_cues
        )
        multi = causal or (len(metrics) >= 2) or (comparison and len(dates) >= 2)

        if contradiction:
            qtype = QueryType.CONTRADICTION
        elif global_scope:
            qtype = QueryType.GLOBAL
        elif comparison:
            qtype = QueryType.COMPARISON
        elif table:
            qtype = QueryType.TABLE
        elif citation:
            qtype = QueryType.CITATION
        elif multi:
            qtype = QueryType.MULTIHOP
        elif numeric:
            qtype = QueryType.NUMERIC_LOOKUP
        elif dates or periods:
            qtype = QueryType.TEMPORAL
        else:
            qtype = QueryType.DIRECT_LOOKUP

        topic_terms = meaningful_terms(query)
        reserved = set(meaningful_terms(" ".join(metrics + dates + periods + entities)))
        topics = [t for t in topic_terms if t not in reserved][:16]

        return QueryIR(
            query=query,
            normalized_query=normalized,
            query_type=qtype,
            entities=list(dict.fromkeys(entities))[:8],
            topics=topics,
            metrics=metrics,
            dates=dates,
            periods=periods,
            units=["%"] if "%" in query or PERCENT_RE.search(query) else [],
            requires_numeric=numeric,
            requires_table=table,
            requires_multiple_evidence=multi or comparison or contradiction or global_scope,
            requires_comparison=comparison,
            requires_global_coverage=global_scope,
            requires_reasoning=multi or contradiction or global_scope,
        )
