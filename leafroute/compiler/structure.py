from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from leafroute.config import StructureConfig
from leafroute.models import ParsedBlock, ParsedDocument
from leafroute.utils import normalize_key

NUMBERED_HEADING_RE = re.compile(
    r"^(?:(?:section|chapter|article|part)\s+)?(?:[A-Z]|\d+|[IVXLCDM]+)(?:[.\-)]|\s)",
    re.I,
)
MULTILEVEL_RE = re.compile(r"^(\d+(?:\.\d+){1,5})\s+\S")
MARKDOWN_RE = re.compile(r"^(#{1,6})\s+(.+)$")


@dataclass(slots=True)
class HeadingDecision:
    is_heading: bool
    level: int
    confidence: float
    title: str


class StructureDetector:
    def __init__(self, config: StructureConfig):
        self.config = config

    def detect(self, document: ParsedDocument) -> dict[str, HeadingDecision]:
        all_blocks = [b for p in document.pages for b in p.blocks if b.text.strip()]
        font_sizes = [b.font_size for b in all_blocks if b.font_size and b.font_size > 0]
        median_font = statistics.median(font_sizes) if font_sizes else 11.0
        p75 = self._percentile(font_sizes, 75) if font_sizes else median_font
        p90 = self._percentile(font_sizes, 90) if font_sizes else median_font
        decisions: dict[str, HeadingDecision] = {}
        bookmark_titles = {normalize_key(title): level for level, title, _ in document.bookmarks}

        for block in all_blocks:
            text = " ".join(block.text.split())
            decisions[block.id] = self._score_block(
                block,
                text,
                median_font=median_font,
                p75=p75,
                p90=p90,
                bookmark_titles=bookmark_titles,
                source_type=document.source_type,
            )
        return decisions

    def _score_block(
        self,
        block: ParsedBlock,
        text: str,
        *,
        median_font: float,
        p75: float,
        p90: float,
        bookmark_titles: dict[str, int],
        source_type: str,
    ) -> HeadingDecision:
        if not text or len(text) > self.config.max_heading_chars:
            return HeadingDecision(False, 0, 0.0, text)

        md = MARKDOWN_RE.match(text)
        if md:
            return HeadingDecision(True, len(md.group(1)), 0.99, md.group(2).strip())

        score = 0.0
        level = 2
        normalized = normalize_key(text)

        if normalized in bookmark_titles:
            score += 0.60
            level = min(6, max(1, bookmark_titles[normalized]))

        font = block.font_size or median_font
        if source_type == "pdf":
            if font >= p90 and font > median_font * 1.12:
                score += 0.61
                level = min(level, 1)
            elif font >= p75 and font > median_font * 1.05:
                score += 0.24
                level = min(level, 2)
            elif font > median_font * 1.01:
                score += 0.12

        if block.bold_ratio >= 0.75:
            score += 0.20
        elif block.bold_ratio >= 0.30:
            score += 0.10

        if NUMBERED_HEADING_RE.match(text):
            score += 0.25
            level = self._numbered_level(text)

        if text.isupper() and len(text.split()) <= 14:
            score += 0.16
            level = min(level, 2)

        word_count = len(text.split())
        if word_count <= 10:
            score += 0.10
        elif word_count <= 18:
            score += 0.04

        if text.endswith(('.', ';', ',')):
            score -= 0.14
        if block.line_count > 3:
            score -= 0.12
        if len(text) < 3:
            score -= 0.30

        confidence = max(0.0, min(1.0, score))
        return HeadingDecision(confidence >= self.config.heading_confidence, level, confidence, text)

    @staticmethod
    def _numbered_level(text: str) -> int:
        m = MULTILEVEL_RE.match(text)
        if m:
            return min(6, m.group(1).count(".") + 1)
        lowered = text.lower()
        if lowered.startswith(("part ", "chapter ")):
            return 1
        if lowered.startswith(("section ", "article ")):
            return 2
        return 2

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = (len(ordered) - 1) * percentile / 100
        lo = int(idx)
        hi = min(lo + 1, len(ordered) - 1)
        frac = idx - lo
        return ordered[lo] * (1 - frac) + ordered[hi] * frac
