# Quickstart: PII-to-Chunk Pipeline Bridge

**Date**: 2026-07-01

## Prerequisites

```bash
uv sync                     # Install all dependencies
python -m spacy download en_core_web_lg  # PII detection model
```

## Validation Scenarios

### 1. Unit test: strip_pii_clauses preserves clause metadata

```bash
uv run pytest tests/unit/test_pii_engine.py::test_strip_pii_clauses_preserves_metadata -v
```

Expected: All clause metadata fields (id, title, level, parent_id) unchanged after stripping.

### 2. Unit test: PII replaced in clause text

```bash
uv run pytest tests/unit/test_pii_engine.py::test_strip_pii_clauses_replaces_pii -v
```

Expected: Clause text contains placeholders (e.g., `[PARTY_1]`) instead of raw PII.

### 3. Unit test: empty input returns empty

```bash
uv run pytest tests/unit/test_pii_engine.py::test_strip_pii_clauses_empty_input -v
```

Expected: `([], PiiResult)` with empty mapping.

### 4. Integration test: End-to-end PII-safe chunking (T014)

```bash
uv run pytest tests/integration/test_chunking_cli.py::test_pii_safe_chunking -v
```

Expected: Full pipeline (parse → strip_pii_clauses → stream_chunks) produces zero chunks containing raw PII strings.

### 5. Regression: Existing PII tests still pass

```bash
uv run pytest tests/unit/test_pii_engine.py -v
```

Expected: All existing tests pass with zero changes.

## Manual Smoke Test

```bash
uv run python -c "
from openreview_cli.parsing.stream import parse_document
from openreview_cli.pii.engine import strip_pii_clauses
from openreview_cli.chunking.stream import stream_chunks

doc, clauses = parse_document('tests/fixtures/nda_with_pii.pdf')
stripped, result = strip_pii_clauses(clauses, doc)
chunks = list(stream_chunks(stripped))
print(f'Parsed {len(clauses)} clauses')
print(f'Detected {len(result.entities)} PII entities')
print(f'Generated {len(chunks)} chunks')
print(f'All chunks PII-safe: {all(\"[PARTY\" in c.text for c in chunks)}')
"
```

Expected: Script runs without error, prints entity count and chunks summary.
