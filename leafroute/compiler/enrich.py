from __future__ import annotations

import re
from collections import Counter

from leafroute.models import DateMention, EntityMention, NumericFact
from leafroute.utils import meaningful_terms, normalize_key, top_keywords

DATE_PATTERNS = [
    re.compile(r"\b(?:19|20)\d{2}\b"),
    re.compile(r"\b(?:Q[1-4]|FY)\s*[-/]?\s*(?:19|20)?\d{2}\b", re.I),
    re.compile(r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+(?:19|20)\d{2}\b", re.I),
]
NUMERIC_RE = re.compile(
    r"(?<!\w)(?P<currency>[$€£¥])?\s*(?P<number>\(?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)\s*(?P<scale>billion|million|thousand|bn|mn|m|k)?\s*(?P<percent>%|percent|percentage points?)?",
    re.I,
)
ENTITY_RE = re.compile(r"\b(?:[A-Z][A-Za-z0-9&'’.\-]+(?:\s+|$)){1,5}")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

COMMON_METRICS = {
    "revenue", "sales", "operating income", "operating margin", "gross margin", "gross profit",
    "net income", "ebitda", "free cash flow", "cash flow", "debt", "liquidity", "expenses",
    "operating expenses", "earnings per share", "eps", "assets", "liabilities", "equity",
    "headcount", "arr", "annual recurring revenue", "churn", "bookings", "backlog",
}

SCALE = {
    None: 1.0,
    "": 1.0,
    "k": 1_000.0,
    "thousand": 1_000.0,
    "m": 1_000_000.0,
    "mn": 1_000_000.0,
    "million": 1_000_000.0,
    "bn": 1_000_000_000.0,
    "billion": 1_000_000_000.0,
}


def extract_dates(text: str, page: int, node_id: str | None = None) -> list[DateMention]:
    seen: set[str] = set()
    out: list[DateMention] = []
    for pattern in DATE_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(0).strip()
            key = normalize_key(raw)
            if key in seen:
                continue
            seen.add(key)
            out.append(DateMention(raw=raw, normalized=key, page=page, node_id=node_id))
    return out


def extract_numeric_facts(text: str, page: int, node_id: str | None = None) -> list[NumericFact]:
    facts: list[NumericFact] = []
    for m in NUMERIC_RE.finditer(text):
        raw = m.group(0).strip()
        if not raw:
            continue
        number = m.group("number")
        clean = number.replace(",", "").replace("(", "-").replace(")", "")
        try:
            value = float(clean)
        except ValueError:
            value = None
        scale = (m.group("scale") or "").lower()
        if value is not None:
            value *= SCALE.get(scale, 1.0)
        unit = None
        if m.group("percent"):
            unit = "%"
        elif m.group("currency"):
            unit = m.group("currency")
        elif scale:
            unit = scale
        start, end = m.span()
        context = text[max(0, start - 80): min(len(text), end + 80)].strip()
        label = _infer_label(context, start_offset=min(80, start))
        facts.append(
            NumericFact(
                raw=raw,
                value=value,
                unit=unit,
                label=label,
                page=page,
                node_id=node_id,
                context=context,
            )
        )
    return facts


def extract_entities(text: str, page: int, node_id: str | None = None) -> list[EntityMention]:
    out: list[EntityMention] = []
    seen: set[str] = set()
    for m in ENTITY_RE.finditer(text):
        name = " ".join(m.group(0).split()).strip(" .,:;()")
        if len(name) < 3 or name.lower() in {"the", "this", "section", "table", "figure"}:
            continue
        normalized = normalize_key(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(EntityMention(name=name, normalized=normalized, page=page, node_id=node_id))
    return out


def extract_metrics(text: str) -> list[str]:
    lower = normalize_key(text)
    return sorted({metric for metric in COMMON_METRICS if metric in lower})


def important_sentences(text: str, limit: int = 4) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if len(s.strip()) >= 30]
    if not sentences:
        return [text[:600]] if text else []
    frequencies = Counter(meaningful_terms(text))
    scored: list[tuple[float, str]] = []
    for sentence in sentences:
        terms = meaningful_terms(sentence)
        score = sum(frequencies[t] for t in terms) / max(1, len(terms))
        if any(ch.isdigit() for ch in sentence):
            score += 0.5
        scored.append((score, sentence))
    return [s for _, s in sorted(scored, reverse=True)[:limit]]


def digest(text: str) -> tuple[list[str], list[str]]:
    return top_keywords(text), important_sentences(text)


def _infer_label(context: str, start_offset: int) -> str | None:
    before = context[:start_offset]
    terms = meaningful_terms(before)
    if not terms:
        return None
    return " ".join(terms[-4:])
