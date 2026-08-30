# LeafRoute

**Compiled retrieval for RAG.**

LeafRoute is an open-source hierarchical retrieval runtime that compiles long documents into portable, searchable `.leaf` artifacts. Queries are compiled into structured intent and executed with deterministic local indexes and tree navigation. LLMs are optional for retrieval and are used only when a configured mode decides that reasoning adds value.

```text
Document                       Query
   |                             |
   v                             v
Structural compiler          Query compiler
   |                             |
   v                             v
TreeIR + indexes             QueryIR
   |                             |
   +-------------> Retrieval Plan
                         |
                         v
                 Deterministic runtime
                         |
                         v
                   Confidence gate
                    /           \
                   /             \
             sufficient        ambiguous
                 |                 |
                 |          optional verifier
                 \                 /
                  +---------------+
                         |
                         v
                    Evidence Pack
                         |
                  application / LLM
```

## Why LeafRoute?

Hierarchical RAG is attractive because real documents already have structure: chapters, sections, subsections, tables, notes, appendices, page ranges, and references. LeafRoute preserves that structure, but avoids making a generative model the default search engine.

The design follows one rule:

> **Use algorithms to search. Use LLMs to reason.**

LeafRoute is intended for long, structured documents such as financial reports, contracts, regulatory filings, technical manuals, policies, research papers, and internal documentation.

## Core ideas

### 1. TreeIR

Documents are compiled into a stable intermediate representation containing hierarchy, page ranges, text, routing signatures, keywords, entities, dates, numeric facts, tables, hashes, and provenance.

### 2. QueryIR

Natural-language questions are compiled into structured intent. For example:

```text
Compare operating margin in 2024 and 2025
```

becomes conceptually:

```json
{
  "query_type": "comparison",
  "metrics": ["operating margin"],
  "dates": ["2024", "2025"],
  "requires_numeric": true,
  "requires_multiple_evidence": true,
  "requires_comparison": true
}
```

### 3. Retrieval plans

QueryIR becomes an explainable plan such as:

```text
SEARCH_METRIC operating margin
SEARCH_DATE 2024, 2025
SEARCH_TEXT original query
TEMPORAL_JOIN
EXPAND_PARENT
RANK
TOP_K 5
READ
```

### 4. Deterministic hierarchical routing

LeafRoute combines:

- SQLite FTS5 lexical retrieval
- title and path matching
- entity lookup
- date lookup
- numeric-fact lookup
- metric matching
- structural priors
- hierarchical beam search
- domain routing rules
- version-aware hot-route caching

No vector database is required.

### 5. Evidence-first API

Retrieval returns an `EvidencePack` before answer generation. This lets applications use LeafRoute with any LLM, no LLM, or their own downstream reasoning layer.

### 6. Portable `.leaf` artifacts

A `.leaf` file is a self-contained SQLite artifact storing:

- compressed TreeIR
- node metadata
- FTS5 search data
- entity index
- numeric facts
- dates
- table payloads
- route cache
- artifact version metadata

Compile once and reopen without the original source file.

## Current capabilities

The repository currently implements:

- PDF parsing with layout and font metadata through PyMuPDF
- Markdown and plain-text parsing
- HTML parsing with heading preservation
- DOCX parsing without a mandatory DOCX library
- deterministic heading classification
- bookmark-aware PDF structure detection
- TreeIR hierarchy construction
- automatic fallback nodes for flat documents
- oversized leaf splitting
- extractive keywords and important sentences
- entity extraction
- date and period extraction
- normalized numeric fact extraction
- common business and financial metric detection
- PDF table extraction when available
- local SQLite FTS5 index
- entity, numeric, and date indexes
- QueryIR compilation
- query type detection
- retrieval-plan generation
- hierarchical beam routing
- confidence calculation
- reasoning escalation hooks
- optional OpenAI provider adapter
- route caching
- evidence packs
- proof/debug traces
- incremental structural diffing with content/subtree hashes
- multi-document `DocumentForest`
- finance and legal routing rule packs
- Python SDK
- CLI
- FastAPI server
- local browser Studio
- benchmark runner
- Docker image
- GitHub Actions test workflow

## Installation

Python 3.11+ is required.

```bash
pip install -e .
```

For the API server:

```bash
pip install -e '.[api]'
```

For OpenAI-based verification or answer generation:

```bash
pip install -e '.[openai]'
```

For development:

```bash
pip install -e '.[dev,api]'
```

## Quick start

Compile a document:

```bash
leafroute compile report.pdf -o report.leaf
```

Inspect it:

```bash
leafroute inspect report.leaf
```

Render the tree:

```bash
leafroute tree report.leaf --max-depth 5
```

Search without an LLM:

```bash
leafroute search report.leaf "What was revenue in FY2025?" --trace
```

Explain the query plan:

```bash
leafroute explain report.leaf "Compare operating margin in 2024 and 2025"
```

Produce an extractive answer:

```bash
leafroute ask report.leaf "What are the major liquidity risks?"
```

## Python SDK

```python
from leafroute import LeafRoute
from leafroute.config import LeafRouteConfig

engine = LeafRoute.compile(
    "annual-report.pdf",
    output="annual-report.leaf",
    config=LeafRouteConfig(
        mode="fast",
        domain_pack="finance",
    ),
)

result = engine.search(
    "What was operating income in FY2025?",
    top_k=5,
)

print(result.evidence_pack.confidence)
print(result.trace.total_latency_ms)
print(result.trace.llm_calls)

for evidence in result.evidence_pack.evidence:
    print(evidence.section)
    print(evidence.page_start, evidence.page_end)
    print(evidence.text)

engine.close()
```

Reopen the compiled artifact:

```python
from leafroute import LeafRoute

engine = LeafRoute.open("annual-report.leaf")
result = engine.search("What are the main risks?")
```

## Retrieval modes

### Fast

```python
engine.search(query, mode="fast")
```

Retrieval LLM budget is forced to zero. The runtime uses deterministic indexes and tree routing.

### Balanced

```python
engine.search(query, mode="balanced")
```

Allows at most one verifier call by default when a reasoning provider is configured and confidence is below the configured threshold.

### Deep

```python
engine.search(query, mode="deep")
```

Allows reasoning escalation. The current open-source runtime performs candidate verification through the provider hook. More advanced iterative operators can be built on the same interface.

### Offline

```python
engine.search(query, mode="offline")
```

Retrieval is local and provider escalation is prohibited.

A whole engine can also be configured as offline:

```python
LeafRouteConfig(mode="offline", offline=True)
```

## Optional generative answers

LeafRoute intentionally separates retrieval from generation.

The included OpenAI adapter is optional:

```python
from leafroute import LeafRoute
from leafroute.config import LeafRouteConfig
from leafroute.providers.openai_provider import OpenAIReasoningProvider

provider = OpenAIReasoningProvider(model="gpt-5-mini")

engine = LeafRoute.open(
    "annual-report.leaf",
    config=LeafRouteConfig(mode="balanced"),
    reasoning_provider=provider,
)

result = engine.ask(
    "Why did operating margin decline?",
    mode="balanced",
)

print(result.answer)
```

The provider receives only selected evidence or candidate sections. The entire document tree is not sent by default.

## Query types

The query compiler currently detects:

- direct lookup
- numeric lookup
- temporal lookup
- comparison
- multi-hop/causal queries
- global-summary queries
- contradiction queries
- table queries
- citation/evidence requests

Example:

```python
from leafroute.query import QueryCompiler

ir = QueryCompiler().compile(
    "Compare operating margin in 2024 and 2025"
)
print(ir.model_dump())
```

## Retrieval operators

Plans can use the following operator vocabulary:

```text
SEARCH_TEXT
SEARCH_TITLE
SEARCH_PATH
SEARCH_ENTITY
SEARCH_NUMBER
SEARCH_METRIC
SEARCH_DATE
SEARCH_TABLE
FILTER_DATE
FILTER_TYPE
EXPAND_PARENT
EXPAND_CHILDREN
EXPAND_SIBLINGS
INTERSECT
UNION
TEMPORAL_JOIN
RANK
PRUNE
TOP_K
READ
READ_NEIGHBORS
READ_TABLE
```

Not every operator has a dedicated standalone physical executor yet. The current planner maps the important search operators into the fused retrieval runtime while preserving the logical plan for debugging and future optimizer work.

## Tree-aware scoring

Each node receives a score assembled from observable signals:

```text
lexical
+ title similarity
+ title term overlap
+ hierarchy-path similarity
+ path term overlap
+ keyword overlap
+ entity coverage
+ metric coverage
+ temporal coverage
+ numeric density
+ table density
+ structural importance
+ structured-index boosts
+ optional domain-rule boosts
```

The response preserves these reasons:

```python
for evidence in result.evidence_pack.evidence:
    print(evidence.reasons)
```

## Confidence engine

Confidence is intentionally separate from retrieval score. The current confidence model uses:

- best candidate strength
- ranking margin
- evidence coverage
- ambiguity penalty
- reasoning-complexity penalty

This controls whether balanced/deep modes should ask a verifier for help.

## Finance and legal domain packs

Use deterministic expert rules without fine-tuning:

```python
LeafRouteConfig(domain_pack="finance")
```

or:

```python
LeafRouteConfig(domain_pack="legal")
```

Finance rules favor sections such as financial statements, results of operations, liquidity, capital resources, and cash flow when matching relevant metrics.

Legal rules boost likely sections for termination, liability, indemnification, and related concepts.

The rules system is intentionally small and inspectable. Add custom routing rules in `leafroute/rules.py` or build an application-specific pack.

## Numeric facts

LeafRoute promotes numbers into retrieval objects rather than leaving every numeric question to fuzzy text retrieval.

A fact stores fields such as:

```json
{
  "raw": "$120 million",
  "value": 120000000.0,
  "unit": "$",
  "label": "revenue fy2025 was",
  "page": 42,
  "node_id": "n_000123",
  "context": "..."
}
```

The normalized value makes it possible to build richer numeric comparison operators without replacing the document evidence.

## Tables

For PDFs, LeafRoute asks PyMuPDF for tables when supported and stores a cell-oriented representation:

```text
row index
column index
row header
column header
value
```

Table extraction is best-effort. Failure to extract a table never blocks normal text retrieval.

## Incremental updates

Every node has:

```text
content_hash
subtree_hash
```

Use:

```python
updated, diff = engine.update("annual-report-v2.pdf")

print(diff.changed_nodes)
print(diff.unchanged_nodes)
print(diff.reuse_ratio)
```

CLI:

```bash
leafroute update old.leaf annual-report-v2.pdf -o annual-report-v2.leaf
```

The current implementation performs deterministic recompilation and computes exactly which structural nodes can be reused. The hashes and diff contract are ready for a later physical incremental compiler that reuses persisted per-node indexes instead of rebuilding the final SQLite artifact.

This distinction matters: **incremental change detection is implemented; partial physical artifact rewriting is the next optimization step.**

## Multi-document retrieval

Use a document forest:

```python
from leafroute.corpus import DocumentForest

forest = DocumentForest.open_directory("./knowledge")
pack = forest.search(
    "Compare revenue growth across the companies",
    document_k=4,
    evidence_k=10,
)

for item in pack.evidence:
    print(item.document_id, item.section, item.score)

forest.close()
```

The corpus router combines document metadata and a lightweight lexical probe before searching the most likely document trees.

## Query DSL

Applications can build query text programmatically:

```python
from leafroute.query import QueryBuilder

query = (
    QueryBuilder()
    .find("growth")
    .metric("revenue")
    .period("FY2025")
    .entity("Acme")
    .render()
)
```

The DSL is intentionally small in the current release. It establishes a stable path toward a richer retrieval query language.

## API server

Start an API for one artifact:

```bash
leafroute serve report.leaf --host 127.0.0.1 --port 8000
```

Endpoints:

```text
GET  /health
GET  /v1/document
GET  /v1/document/tree
POST /v1/search
POST /v1/ask
GET  /studio
```

Example request:

```bash
curl -X POST http://127.0.0.1:8000/v1/search \
  -H 'content-type: application/json' \
  -d '{
    "query": "What was revenue in FY2025?",
    "mode": "fast",
    "top_k": 5,
    "include_trace": true
  }'
```

## LeafRoute Studio

After starting the server, open:

```text
http://127.0.0.1:8000/studio
```

The included zero-build local Studio shows:

- compiled document tree
- page ranges
- search playground
- evidence cards
- confidence
- total retrieval latency
- LLM call count
- QueryIR
- retrieval plan
- execution trace

The Studio intentionally has no external frontend dependency so it works in local and air-gapped environments.

## Docker

First create a compiled artifact and copy it to `./data/document.leaf`.

Then:

```bash
docker compose up --build
```

The container reads:

```text
LEAFROUTE_ARTIFACT=/data/document.leaf
```

and serves port 8000.

## Benchmarking

Benchmark case format:

```json
[
  {
    "query": "What was revenue in FY2025?",
    "expected_pages": [42]
  }
]
```

Run:

```bash
leafroute benchmark report.leaf cases.json -o benchmark-report.json
```

The report includes:

- mean evidence page recall
- p50 latency
- p95 latency
- total retrieval LLM calls
- average nodes examined
- per-query evidence pages

A sample benchmark file is available under `benchmarks/`.

### Important benchmark policy

LeafRoute does not claim speed, cost, or accuracy improvements over other RAG systems until those results are reproduced on public datasets under comparable settings. The repository contains the benchmark harness needed to measure those claims.

Recommended future comparisons:

- SQLite/BM25 baseline
- conventional embedding RAG
- hybrid RAG
- hierarchical reasoning RAG
- PageIndex open-source retrieval where reproducible

Recommended datasets include FinanceBench and long-document retrieval datasets with page-level ground truth.

## Artifact format

A `.leaf` artifact is currently SQLite, which gives LeafRoute:

- atomic file deployment
- mature locking and recovery
- built-in FTS5
- simple inspection
- straightforward backups
- no external database process

Main logical tables:

```text
manifest
blobs
nodes
nodes_fts
entities
numeric_facts
dates
tables_data
route_cache
```

TreeIR is compressed and stored in the artifact, so reopening does not require rebuilding the hierarchy.

## Security and offline deployment

LeafRoute's core compiler and retrieval runtime are local.

In offline mode:

- retrieval provider escalation is disabled
- remote answer generation is rejected
- document processing remains local

Applications should still implement their own controls for:

- artifact access permissions
- API authentication
- tenant isolation
- file upload validation
- audit retention
- encryption at rest

See `SECURITY.md`.

## Prompt-injection posture

Document text is evidence, not system instructions.

LeafRoute itself does not execute instructions discovered in retrieved document text. Optional answer providers are prompted to use supplied evidence as data. Applications adding tools or agents should maintain the same separation.

## Threading and concurrency

Compiled artifacts are read-mostly. The API uses SQLite with cross-thread access enabled and explicit serialization for route-cache writes.

For high-throughput multi-process deployments, prefer one SQLite connection per worker process, which is naturally achieved by launching multiple API workers.

## Design boundaries

LeafRoute is not intended to be:

- a vector database
- a general autonomous-agent framework
- a knowledge graph platform
- an OCR research suite
- an LLM hosting layer
- an enterprise identity product

Those systems can integrate with LeafRoute, but the repository stays focused on document compilation and retrieval execution.

## Project structure

```text
leafroute/
├── compiler/        structural detection, hierarchy, enrichment
├── parsers/         PDF, Markdown/text, HTML, DOCX
├── index/           SQLite artifact and FTS indexes
├── query/           QueryIR, planner, query DSL
├── runtime/         tree routing, scoring, confidence
├── evidence/        provider-neutral Evidence Packs
├── incremental/     content/subtree diffing
├── providers/       optional reasoning providers
├── benchmark/       evaluation runner
├── telemetry/       execution traces
├── api/             FastAPI and local Studio
├── corpus.py        multi-document forest
├── rules.py         domain routing packs
├── engine.py        public orchestration API
└── cli.py           command-line interface
```

## Tests

Run:

```bash
pytest -q
```

The suite covers:

- compilation
- artifact save/reopen
- numeric retrieval
- causal/multi-hop classification
- route cache
- query planning
- incremental diffing
- PDF layout parsing
- multi-document routing
- FastAPI and Studio

## Development

```bash
git clone <your-fork>
cd leafroute
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,api]'
pytest -q
```

Useful commands:

```bash
make smoke
make artifact
make benchmark
make api
```

## Roadmap

Near-term priorities:

1. Persisted partial incremental index rewriting.
2. Better table header/span reconstruction.
3. Reference-edge extraction for notes, appendices, and cross-sections.
4. A physical operator engine matching every logical RetrievalPlan operator.
5. Cross-encoder and local tiny-model reranking plugins.
6. Profile-guided route optimization from successful query traces.
7. Adaptive splitting of frequently queried large nodes.
8. Learned node-route prediction.
9. Stronger document-level corpus routing for very large forests.
10. Public benchmark results with reproducible configurations.

## Relationship to PageIndex

LeafRoute is an independent project inspired by the broader idea of structure-aware, hierarchical retrieval. It is not a fork of PageIndex.

The architectural focus is different: LeafRoute treats document structure as compiled machine-readable state and query-time retrieval as a local execution problem. Optional LLM reasoning is an escalation path rather than a mandatory routing primitive.

## Contributing

Contributions are especially welcome in:

- document parsers
- structure detection
- query planning
- benchmark datasets
- domain packs
- table reconstruction
- numeric retrieval
- local rerankers
- trace visualization
- incremental compilation

See `CONTRIBUTING.md`.

## License

Apache License 2.0.

## Optional performance extras

The core runtime uses standard-library fallbacks for compression and hashing. Install the performance extra to use Zstandard and BLAKE3 when available:

```bash
pip install -e '.[performance]'
```

This is optional. Artifacts and retrieval remain functional without the extra.

For a feature-by-feature mapping of the product specification to source files, see `docs/PRD_IMPLEMENTATION.md`.
