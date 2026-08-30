# PRD Implementation Map

This file maps the product specification to the repository so contributors can see what is implemented physically and what is an intentional roadmap item.

## Implemented in 0.1.0

| PRD area | Implementation |
|---|---|
| Local-first compilation | `compiler/`, `parsers/` |
| PDF layout extraction | `parsers/pdf.py` |
| Markdown/TXT/HTML/DOCX | `parsers/` |
| Structural heading detection | `compiler/structure.py` |
| Hierarchical TreeIR | `models.py`, `compiler/compiler.py` |
| Extractive digests | `compiler/enrich.py` |
| Entities, dates, metrics, numbers | `compiler/enrich.py` |
| Table extraction model | `parsers/pdf.py`, `models.py` |
| Portable `.leaf` artifact | `index/sqlite_index.py` |
| FTS lexical index | `index/sqlite_index.py` |
| Entity/date/numeric/table indexes | `index/sqlite_index.py` |
| QueryIR | `query/compiler.py` |
| RetrievalPlan | `query/planner.py` |
| Plan-driven physical candidate execution | `runtime/executor.py` |
| Hierarchical beam search | `runtime/router.py` |
| Explainable scoring | `runtime/scoring.py` |
| Confidence gate | `runtime/confidence.py` |
| Fast/offline modes | `engine.py`, `config.py` |
| Balanced/deep provider escalation | `engine.py`, `providers/` |
| Evidence Pack | `evidence/` |
| Proof/debug traces | `telemetry/`, CLI explain |
| Version-aware route cache | SQLite artifact + router |
| Content/subtree hashing | compiler + incremental |
| Incremental structural diff | `incremental/` |
| Multi-document forest | `corpus.py` |
| Finance/legal domain packs | `rules.py` |
| Query builder DSL | `query/dsl.py` |
| REST API | `api/app.py` |
| Local Studio | `api/studio.py` |
| Benchmark harness | `benchmark/` |
| Docker deployment | `Dockerfile`, compose |
| CI | `.github/workflows/ci.yml` |

## Partially implemented by design

### Physical incremental rewriting

The project detects changed/unchanged structural nodes and computes subtree hashes. Version 0.1.0 still recompiles the final SQLite physical indexes. A future storage pass should copy unchanged persisted node products and rewrite only affected rows.

### Full physical operator algebra

The planner exposes the complete logical operator vocabulary. Search, metric, entity, date, table, expansion, filtering, and temporal coverage are executable. Some set/join operators remain represented at the logical layer and are currently handled by fused tree ranking or downstream reasoning.

### Table reconstruction

PDF table extraction and cell-level storage are implemented. Complex merged-header reconstruction, spanning cells, and cross-page tables remain areas for specialized improvements.

### Reference graph

TreeIR has a reference-edge field and the compiler extracts basic section/note references. More robust cross-reference resolution is planned.

## Roadmap research features

These are intentionally not presented as completed functionality:

- adaptive tree refinement from production traffic
- profile-guided physical index optimization
- learned route predictor
- distributed retrieval runtime
- artifact registry service
- fine-grained persisted incremental compiler
- MCTS/deep agent retrieval
- broad public benchmark claims

The architecture contains extension points for these features without requiring them for the core local retrieval runtime.
