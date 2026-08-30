from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Iterator

from leafroute.models import RetrievalTrace, TraceEvent


class TraceCollector:
    def __init__(self):
        self.trace = RetrievalTrace(trace_id=f"tr_{uuid.uuid4().hex[:16]}")
        self._start = time.perf_counter()

    @contextmanager
    def stage(self, name: str, **detail) -> Iterator[dict]:
        start = time.perf_counter()
        mutable_detail = dict(detail)
        yield mutable_detail
        elapsed = (time.perf_counter() - start) * 1000
        self.trace.events.append(TraceEvent(stage=name, duration_ms=elapsed, detail=mutable_detail))

    def finish(self) -> RetrievalTrace:
        self.trace.total_latency_ms = (time.perf_counter() - self._start) * 1000
        return self.trace
