# Contributing to LeafRoute

Thank you for helping improve compiled hierarchical retrieval.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,api]'
pytest -q
```

## Pull requests

Keep changes focused and add tests for behavior changes. Retrieval changes should include at least one regression case showing the intended evidence node/page.

For performance changes, include a benchmark configuration and report machine/runtime details. Do not submit unqualified speed or accuracy claims.

## Architecture principles

Contributions should preserve these defaults:

1. No mandatory vector database.
2. No mandatory remote LLM for compilation or retrieval.
3. Evidence generation is separate from answer generation.
4. Retrieval decisions should remain inspectable.
5. Optional intelligence should degrade gracefully when absent.

## New parsers

Implement `DocumentParser` and return normalized `ParsedDocument` blocks. Preserve page numbers and layout signals whenever the source format exposes them.

## New routing features

Expose new ranking contributions in candidate `reasons` so developers can debug why a result moved.

## Tests

```bash
python -m compileall -q leafroute
pytest -q
```
