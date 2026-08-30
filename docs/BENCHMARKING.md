# Benchmarking LeafRoute

LeafRoute separates evidence retrieval quality from answer-model quality. Benchmarks should therefore score evidence independently whenever possible.

## Minimum metrics

- page Recall@K
- node Recall@K
- MRR where a single primary section exists
- evidence coverage for multi-hop cases
- compilation wall time
- peak compilation memory
- artifact size
- retrieval p50/p95/p99
- nodes examined and pruned
- retrieval LLM calls
- retrieval LLM input/output tokens
- fallback rate
- route-cache hit rate

## Fair comparison principles

1. Use the same source document representation where possible.
2. Separate index-construction cost from query cost.
3. Report warm and cold retrieval separately.
4. Include all LLM routing calls in token/cost measurements.
5. Do not count final answer-generation latency as retrieval latency unless every compared system includes it.
6. Publish model names, prompts, embedding models, chunking settings, top-K values, and hardware.
7. Repeat latency tests and publish percentile values rather than one best run.

## Included runner

Create a JSON case file:

```json
[
  {"query": "What was revenue?", "expected_pages": [42]}
]
```

Then:

```bash
leafroute benchmark report.leaf cases.json -o report.json
```

The built-in runner is intentionally simple so public benchmark integrations can layer dataset-specific evaluation on top.
