from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from leafroute.engine import LeafRoute


@dataclass(slots=True)
class BenchmarkCase:
    query: str
    expected_pages: list[int]
    expected_nodes: list[str] | None = None


@dataclass(slots=True)
class BenchmarkRecord:
    query: str
    latency_ms: float
    confidence: float
    recall_at_k: float
    pages_returned: list[int]
    llm_calls: int
    nodes_examined: int


class BenchmarkRunner:
    def __init__(self, engine: LeafRoute):
        self.engine = engine

    def run(self, cases: list[BenchmarkCase], top_k: int = 5) -> list[BenchmarkRecord]:
        records: list[BenchmarkRecord] = []
        for case in cases:
            start = time.perf_counter()
            result = self.engine.search(case.query, top_k=top_k)
            elapsed = (time.perf_counter() - start) * 1000
            returned_pages: set[int] = set()
            for e in result.evidence_pack.evidence:
                returned_pages.update(range(e.page_start, e.page_end + 1))
            expected = set(case.expected_pages)
            recall = len(expected & returned_pages) / max(1, len(expected))
            records.append(
                BenchmarkRecord(
                    query=case.query,
                    latency_ms=elapsed,
                    confidence=result.evidence_pack.confidence,
                    recall_at_k=recall,
                    pages_returned=sorted(returned_pages),
                    llm_calls=result.trace.llm_calls,
                    nodes_examined=result.trace.nodes_examined,
                )
            )
        return records

    @staticmethod
    def summary(records: list[BenchmarkRecord]) -> dict:
        latencies = [r.latency_ms for r in records]
        recalls = [r.recall_at_k for r in records]
        return {
            "queries": len(records),
            "recall_mean": statistics.mean(recalls) if recalls else 0.0,
            "latency_p50_ms": _percentile(latencies, 50),
            "latency_p95_ms": _percentile(latencies, 95),
            "llm_calls": sum(r.llm_calls for r in records),
            "nodes_examined_mean": statistics.mean([r.nodes_examined for r in records]) if records else 0.0,
        }

    @staticmethod
    def load_cases(path: str | Path) -> list[BenchmarkCase]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [BenchmarkCase(**item) for item in data]

    @staticmethod
    def save_report(path: str | Path, records: list[BenchmarkRecord]) -> None:
        payload = {
            "summary": BenchmarkRunner.summary(records),
            "records": [asdict(r) for r in records],
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p / 100.0
    lo = int(idx)
    hi = min(len(ordered) - 1, lo + 1)
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac
