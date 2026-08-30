# LeafRoute Architecture

## 1. System model

LeafRoute separates ingestion, retrieval, and reasoning.

```text
source document
   -> parser
   -> structural compiler
   -> TreeIR
   -> SQLite/FTS artifact

natural-language query
   -> QueryIR
   -> RetrievalPlan
   -> local runtime
   -> confidence
   -> EvidencePack
   -> optional reasoning provider
```

The separation is deliberate. TreeIR is provider-independent. EvidencePack is also provider-independent. This prevents the retrieval layer from becoming coupled to one embedding vendor or LLM.

## 2. Document compilation

### Parse

Parsers normalize multiple source formats into `ParsedDocument`, pages, and blocks.

PDF blocks include layout information such as bounding boxes, font sizes, and bold/italic ratios.

### Structure detection

The structural classifier combines features instead of relying on one rule:

- relative font size
- bold ratio
- numbering
- capitalization
- line count
- text length
- punctuation
- PDF bookmarks
- Markdown/DOCX heading markers

Every decision receives a confidence value.

### Hierarchy construction

Heading levels are used to maintain a stack of current parents. Non-heading blocks are attached to the active structural node.

Flat documents receive a fallback `Document Content` leaf so the root remains a routing container rather than the only searchable node.

### Enrichment

Each node is enriched using local algorithms:

- lexical keywords
- extractive important sentences
- named entity heuristics
- dates and periods
- numeric values and units
- common financial/business metrics

### Hashing

Each node gets a content hash. The compiler then calculates hashes bottom-up so every node also has a subtree hash.

## 3. Artifact model

The current `.leaf` format is SQLite.

The complete TreeIR is compressed in the `blobs` table. Search-specific projections are materialized into FTS and typed tables.

This is similar to a database having both canonical rows and physical indexes.

## 4. Query compilation

The Query Compiler performs low-cost intent extraction.

It detects:

- query type
- metrics
- dates
- periods
- entities
- whether numbers/tables are likely needed
- whether multiple evidence regions are required
- whether reasoning is likely needed

The compiler does not need an LLM for normal cases.

## 5. Logical retrieval plan

`RetrievalPlanner` emits a list of logical operators.

The current physical runtime fuses several logical operations into an efficient multi-index candidate-generation and ranking pass. This allows the public plan to stabilize before every operator has an independent physical implementation.

## 6. Candidate generation

Candidates can originate from:

- FTS5 lexical matches
- entity index
- date index
- numeric context index
- hierarchical beam traversal
- route cache

The router adds local tree neighborhoods around candidates to avoid the failure mode of retrieving an isolated section without relevant parent/sibling context.

## 7. Ranking

Scores are observable weighted signals rather than a single opaque similarity value.

Domain rule packs may apply small deterministic boosts.

## 8. Confidence

Confidence is a separate layer because the best-ranked node can still be ambiguous.

Current confidence factors:

- candidate strength
- top-to-second margin
- number of strong evidence candidates
- ambiguity across top candidates
- query reasoning complexity

## 9. Reasoning escalation

Fast/offline modes never use retrieval LLMs.

Balanced/deep modes may call a configured provider when confidence is low enough and the budget permits it.

Only selected candidate sections are sent to a verifier.

## 10. Evidence Pack

The retrieval result contains:

- document id
- node id
- page range
- section path
- evidence text
- score
- scoring reasons

Applications may answer, display, audit, cache, or rerank the Evidence Pack independently.

## 11. Multi-document routing

`DocumentForest` uses document metadata and a cheap lexical probe to rank document artifacts before invoking per-document retrieval.

This creates a two-stage hierarchy:

```text
corpus -> document -> section -> evidence
```

## 12. Incremental architecture

The compiler currently implements deterministic recompile plus tree diff. Path-independent node signatures make diffs resilient to a renamed source file.

The next physical optimization is to persist per-node compilation products and rewrite only affected rows/index entries.

## 13. Concurrency model

Artifacts are read-mostly. Route cache writes are serialized by a process-local lock. For scale-out API deployment, each process opens its own SQLite connection.

## 14. Extension points

Stable extension surfaces include:

- `DocumentParser`
- `ReasoningProvider`
- `RoutingRule` and `RulePack`
- logical retrieval operators
- corpus router
- benchmark cases

Future extension surfaces should include rerankers and learned route predictors.
