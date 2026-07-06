# Quickstart — Spec 022 Cleanup & Polish

**Date**: 2026-07-06 | **Spec**: `specs/022-cleanup-polish/spec.md`

## Prerequisites

- Python 3.12, `uv` installed
- Project cloned and `uv sync` completed
- Pre-commit hooks installed: `uv run pre-commit install`
- Active virtual environment (`.venv/`)

## Setup

```bash
# From repo root
uv sync
```

No additional setup needed. All test fixtures are already in `tests/fixtures/`.

---

## Scenario 1: Playbook Precedence Warning

### Validate
```bash
# Run the unit test for playbook precedence
uv run pytest tests/unit/test_playbook_precedence.py -v
```

### Expected Outcome
- Warning emitted on stderr when both `--playbook` and `--playbook-path` supplied
- Warning contains both flag names and states `--playbook-path` wins
- Command continues with exit code 0
- Tests pass (green)

### Manual Smoke Test
```bash
uv run openreview precheck \
  --playbook precheck-nda-v1 \
  --playbook-path /nonexistent/playbook.yaml \
  tests/fixtures/sample-nda.pdf
# Expect: warning on stderr, execution proceeds
```

---

## Scenario 2: Bilateral Comparison CLI

### Validate
```bash
# Run the unit test for bilateral comparison CLI
uv run pytest tests/unit/test_bilateral_comparison.py -v
```

### Test Cases (auto-verified)
| Case | Input | Expected |
|------|-------|----------|
| Missing file | `nonexistent.pdf doc2.pdf` | stderr contains "not found", exit != 0 |
| Unsupported format | `doc1.txt doc2.pdf` | stderr names format, exit != 0 |
| Unreadable file | chmod 000 doc1, then compare | stderr mentions permission, exit != 0 |
| Valid comparison | Two valid .pdf files | Exit 0, comparison output |

### Manual Smoke Test
```bash
# Valid comparison (requires two sample docs)
uv run openreview compare tests/fixtures/sample-nda.pdf tests/fixtures/sample-nda.pdf

# Error: missing file
uv run openreview compare tests/fixtures/nonexistent.pdf tests/fixtures/sample-nda.pdf
# Expected: error on stderr, exit code != 0

# Help
uv run openreview compare --help
# Expected: lists all flags
```

---

## Scenario 3: PII `--no-pii` Flag

### Validate
```bash
# Run the integration test for --no-pii flag
uv run pytest tests/integration/test_no_pii_flag.py -v
```

### Test Cases (auto-verified)
| Case | `--no-pii` | PII Engine Called | Gateway Receives |
|------|------------|-------------------|-----------------|
| Flag present | Yes | No (mock call count 0) | Raw text |
| Flag absent | No | Yes (mock call count > 0) | Stripped text |

### Manual Smoke Test
```bash
# With --no-pii (PII bypassed)
uv run openreview precheck --no-pii tests/fixtures/sample-nda.pdf

# Without --no-pii (PII stripped, default)
uv run openreview precheck tests/fixtures/sample-nda.pdf

# Verify help shows the flag
uv run openreview precheck --help | grep no-pii
```

---

## Full Validation

```bash
# Run all tests for this feature
uv run pytest tests/unit/test_playbook_precedence.py tests/unit/test_bilateral_comparison.py tests/integration/test_no_pii_flag.py -v

# Run full unit suite to check no regressions
uv run pytest tests/unit/ -q

# Run pre-commit (ruff, mypy, pytest-fast)
uv run pre-commit run --all-files
```

---

## References

- CLI interface contract: `specs/022-cleanup-polish/contracts/CLI-interface.md`
- Data model: `specs/022-cleanup-polish/data-model.md`
- Full spec: `specs/022-cleanup-polish/spec.md`
