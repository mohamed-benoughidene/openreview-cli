# Quickstart: Chunking Strategy

**Date**: 2026-07-01 | **Prerequisites**: Phase 2 (document parsing) complete

## Setup

```bash
# All dependencies already installed via `uv sync`
uv run openreview --help
```

## Validation Scenarios

### 1. Basic chunking

```bash
# Parse a contract first
uv run openreview parse tests/fixtures/sample-contract.pdf --format json > /tmp/parsed.json

# Then chunk the parsed contract (once CLI command exists)
# uv run openreview chunk /tmp/parsed.json --summary
```

**Expected outcome**: "Chunked N clauses into M chunks in Ts" (SC-001: <2s)

### 2. Clause boundary enforcement

```bash
# Chunk a contract with known hierarchy
# Verify no chunk spans multiple top-level clauses
# uv run openreview chunk /tmp/hierarchical.json --format json
```

**Expected outcome**: Every chunk's `source_clause_id` corresponds to exactly one top-level clause (SC-002)

### 3. PII compatability

```bash
# Strip PII first, then chunk
# uv run openreview pii strip contract.pdf --output /tmp/stripped.pdf --out-format json
# uv run openreview chunk /tmp/stripped.json --format json
```

**Expected outcome**: Chunks contain PII placeholders, not raw PII (SC-004)

### 4. Memory budget

```bash
# Chunk a large contract
# Monitor peak memory: `time -v uv run openreview chunk large-contract.json`
```

**Expected outcome**: Peak memory <10 MB for chunking logic (SC-005)

### 5. Config override

```bash
# With custom config.yml:
# chunk_size: 256
# chunk_overlap: 25
# uv run openreview chunk contract.json --summary
```

**Expected outcome**: Average chunk size ~256 tokens (tolerance ±10%, SC-007)

## Running Tests

```bash
# Unit tests
uv run pytest tests/unit/test_chunking_models.py -v
uv run pytest tests/unit/test_chunking_tokenizer.py -v
uv run pytest tests/unit/test_chunking_splitter.py -v
uv run pytest tests/unit/test_chunking_stream.py -v

# Integration test
uv run pytest tests/integration/test_chunking_cli.py -v

# All chunking tests
uv run pytest -k "chunking" -v
```

## Success Criteria Reference

| Criterion | How to Validate |
|-----------|-----------------|
| SC-001: <2s for 50-page contract | `time openreview chunk 50page.json` |
| SC-002: No cross-clause spanning | `openreview chunk --format json` + verify source_clause_id |
| SC-003: Hierarchy preserved | Check parent_chunk_id references in JSON output |
| SC-004: PII placeholders preserved | Check chunks contain [PARTY_N], [DATE_N] etc. |
| SC-005: <10 MB peak | `time -v openreview chunk large-contract.json` (max resident set) |
| SC-007: Chunk size ±10% | Average chunk_size across all chunks in JSON output |
| SC-008: Tests pass | `pytest -k "chunking"` green |
