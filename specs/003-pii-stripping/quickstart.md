# Quickstart: PII Stripping Validation

**Date**: 2026-06-25
**Feature**: 003-pii-stripping

## Prerequisites

1. Phase 2 (Document Parsing) is complete and tests pass
2. Python 3.12 with `uv` package manager
3. Presidio and spaCy model installed:
   ```bash
   uv add presidio-analyzer presidio-anonymizer
   uv run python -m spacy download en_core_web_lg
   ```

## Validation Scenarios

### Scenario 1: Basic PII Stripping (P1 — Core)

**Goal**: Verify that known PII entities are detected and replaced with deterministic placeholders.

```bash
# Run unit tests for PII models and engine
uv run pytest tests/unit/test_pii_models.py -v
uv run pytest tests/unit/test_pii_engine.py -v
uv run pytest tests/unit/test_pii_placeholders.py -v
```

**Expected outcome**: All tests pass. PiiEntity, PiiResult, PiiAudit dataclasses are constructed correctly. Presidio detects PERSON, ORGANIZATION, EMAIL_ADDRESS, PHONE_NUMBER entities. Placeholders are assigned deterministically (alphabetical sort → sequential numbering).

### Scenario 2: PII Mapping Persistence (P1 — Core)

**Goal**: Verify that the PII mapping is written to disk (encrypted, chmod 600) and can be read back.

```bash
# Run mapping I/O tests
uv run pytest tests/unit/test_pii_mapping.py -v
```

**Expected outcome**: JSON mapping file is written with `version: 1`, `encrypted: true`, and base64-encoded AES-CBC ciphertext values. File permissions are `0o600`. Reading back with the same key produces the original mapping. Reading with a wrong key raises `PiiError`.

### Scenario 3: Privacy Tier Configuration (P2)

**Goal**: Verify that `--no-pii` flag and `privacy.strip_pii: false` correctly skip stripping with a warning.

```bash
# Run configuration tests
uv run pytest tests/integration/test_pii_config.py -v
```

**Expected outcome**: When stripping is disabled, the warning `"⚠️ PII stripping disabled. Contract text may be sent to providers as-is."` is displayed. No `pii_map.json` or `pii_audit.json` is created. Original text passes through unchanged.

### Scenario 4: Graceful Error Handling (P2)

**Goal**: Verify that PII stripping failures halt the review with an actionable error.

```bash
# Run error handling tests
uv run pytest tests/integration/test_pii_error_handling.py -v
```

**Expected outcome**: When Presidio crashes, the tool displays: `"PII detection failed while processing clause '{title}' ({phase}). Run with --no-pii to skip stripping. Report this bug."` The error message contains the clause heading and processing phase but NOT character offsets or text snippets. The review halts — unstripped text is never sent downstream.

### Scenario 5: End-to-End Strip Flow

**Goal**: Verify the full pipeline from parsed document → stripped text + mapping + audit.

```bash
# Run end-to-end integration test
uv run pytest tests/integration/test_pii_strip_command.py -v
```

**Expected outcome**: A parsed document with known PII (seeded) produces:
1. Stripped text with all PII replaced by typed placeholders
2. `pii_map.json` with encrypted mapping values
3. `pii_audit.json` with entity counts and confidence ranges (zero PII values)
4. All placeholders round-trip correctly through the mapping

### Scenario 6: Accuracy Validation

**Goal**: Verify ≥90% recall and ≥95% precision on the seeded test corpus.

```bash
# Run accuracy tests
uv run pytest tests/integration/test_pii_accuracy.py -v
```

**Expected outcome**: Against 50 seeded documents (25 auto-generated + 25 manually annotated):
- Recall ≥ 90%: at least 90% of actual PII entities are detected
- Precision ≥ 95%: at least 95% of replacements are genuine PII
- False replacement rate < 5%: legal terms like "Force Majeure" are NOT replaced

### Scenario 7: Memory Budget Validation

**Goal**: Verify processing overhead stays under 100 MB (NLP model exempt).

```bash
# Run memory tests
uv run pytest tests/integration/test_pii_memory.py -v -m memory
```

**Expected outcome**: `tracemalloc` peak memory for processing a 50-page document stays under 100 MB (excluding the NLP model baseline of ~600-800 MB).

### Scenario 8: Performance Target

**Goal**: Verify PII stripping of a 50-page document completes in <3 seconds (warm).

```bash
# Run performance test (part of integration suite)
uv run pytest tests/integration/test_pii_strip_command.py -v -k "performance"
```

**Expected outcome**: After NLP model is warm, stripping a 50-page document completes in under 3 seconds on the reference machine (8 GB RAM, 2-core CPU, no GPU).

## Full Test Suite

Run all PII stripping tests:
```bash
# Unit tests
uv run pytest tests/unit/test_pii_models.py tests/unit/test_pii_engine.py tests/unit/test_pii_recognizers.py tests/unit/test_pii_placeholders.py tests/unit/test_pii_mapping.py tests/unit/test_pii_audit.py -v

# Integration tests
uv run pytest tests/integration/test_pii_strip_command.py tests/integration/test_pii_accuracy.py tests/integration/test_pii_error_handling.py tests/integration/test_pii_config.py tests/integration/test_pii_memory.py -v
```

## Pre-commit Validation

Before committing any PII stripping code:
```bash
uvx pre-commit run --all-files
```

This runs ruff, ruff-format, mypy (strict), and the fast test subset.

## Reference

- Data model: [data-model.md](data-model.md)
- Interface contract: [contracts/strip_pii.md](contracts/strip_pii.md)
- Research findings: [research.md](research.md)
- Feature spec: [spec.md](spec.md)
