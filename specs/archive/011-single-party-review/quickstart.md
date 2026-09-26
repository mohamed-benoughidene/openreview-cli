# Quickstart: Single-Party Review (NDA)

**Spec**: specs/011-single-party-review/spec.md
**Date**: 2026-07-02

## Prerequisites

- Python 3.12, `uv` installed
- Project deps installed: `uv sync`
- AI Gateway configured (at least one local model slot via Ollama, or a cloud provider)
- Test NDA documents in `tests/fixtures/`

## Setup

```bash
git checkout feat/011-single-party-review
uv sync
```

Verify the CLI entrypoint:

```bash
uv run openreview --version
uv run openreview precheck --help
```

## Validation Scenarios

### Scenario 1: Basic Single-Document NDA Review

**Command**:
```bash
uv run openreview precheck review tests/fixtures/nda-sample.docx
```

**Expected outcome**:
- All clauses are printed with position, confidence, and citation
- A summary table shows position distribution
- No errors or warnings
- Exit code 0

**Verification points**:
- [ ] Every clause from the sample NDA appears in the report
- [ ] Each assessment has a valid position (favorable, neutral, unfavorable, uncertain)
- [ ] Each assessment has a confidence score 0.0–1.0
- [ ] Each assessment has a non-empty citation string
- [ ] The summary counts add up to the total clause count
- [ ] No "sign this" or "reject this" language appears anywhere

### Scenario 2: Custom Playbook Override

**Command**:
```bash
uv run openreview precheck review tests/fixtures/nda-sample.docx \
  --playbook specs/011-single-party-review/playbooks/precheck-nda-v1.yaml
```

**Expected outcome**:
- Same format as Scenario 1, but assessments may differ if the custom playbook has different category definitions
- If the custom playbook is missing a category that matches a clause, the clause appears as "no-match"

**Verification points**:
- [ ] Custom playbook loads without error
- [ ] Invalid playbook path produces exit code `PLAYBOOK_ERROR`
- [ ] Invalid YAML content produces exit code `PLAYBOOK_ERROR` with a helpful message

### Scenario 3: JSON Output

**Command**:
```bash
uv run openreview precheck review tests/fixtures/nda-sample.docx --format json
```

**Expected outcome**:
- JSON object printed to stdout
- The JSON matches the `ReviewReport` schema in `data-model.md`
- `schema_version` is `"1.0.0"`

**Verification points**:
- [ ] Output is valid JSON (`python -m json.tool` on the output)
- [ ] All fields from `data-model.md` are present
- [ ] `assessments` array has one entry per clause
- [ ] `summary` counts are consistent with assessments

### Scenario 4: JSON Output to File

**Command**:
```bash
uv run openreview precheck review tests/fixtures/nda-sample.docx \
  --format json --output /tmp/review-report.json
```

**Expected outcome**:
- No JSON output to stdout
- File `/tmp/review-report.json` contains the report
- File is parseable JSON

### Scenario 5: Separate Model Slots

**Command**:
```bash
uv run openreview precheck review tests/fixtures/nda-sample.docx \
  --extraction-model ollama/llama3.2:3b \
  --qa-model ollama/llama3.2:3b
```

**Expected outcome**:
- Same output format as Scenario 1
- Assessments include `extraction_model` and `qa_model` fields showing the specified slots

**Verification points**:
- [ ] Invalid model slot name produces exit code `MODEL_NOT_FOUND`
- [ ] Both slots are independently configurable

### Scenario 6: Batch Review

**Command**:
```bash
uv run openreview precheck review tests/fixtures/*.docx
```

**Expected outcome**:
- Each document is processed sequentially
- Each document produces its own report section
- A batch summary shows aggregate statistics

**Verification points**:
- [ ] All matching documents are processed
- [ ] Memory stays under 100 MB (verified via `test_memory` profile)

### Scenario 7: Offline Mode

**Command**:
```bash
# Disconnect from network
uv run openreview precheck review tests/fixtures/nda-sample.docx
```

**Expected outcome**:
- Review completes successfully using only local model slots
- Same output format as online mode

**Verification points**:
- [ ] No network errors (if all model slots are local)
- [ ] Equivalent JSON output to the online run

## Expected Failures

| Test case | Command | Expected exit code |
|-----------|---------|-------------------|
| Non-existent file | `uv run openreview precheck review nonexistent.pdf` | `PARSE_ERROR` |
| Corrupt file | `uv run openreview precheck review tests/fixtures/corrupt.pdf` | `PARSE_ERROR` |
| Invalid playbook path | `uv run openreview precheck review nda.docx --playbook /nonexistent.yaml` | `PLAYBOOK_ERROR` |
| Invalid playbook YAML | `uv run openreview precheck review nda.docx --playbook /etc/passwd` | `PLAYBOOK_ERROR` |
| Invalid extraction model | `uv run openreview precheck review nda.docx --extraction-model nonexistent-slot` | `MODEL_NOT_FOUND` |

## Running the Test Suite

```bash
# Unit tests only
uv run pytest tests/unit/test_review_models.py tests/unit/test_playbook.py tests/unit/test_extraction_agent.py tests/unit/test_qa_agent.py tests/unit/test_comparison_agent.py tests/unit/test_review_report.py -v

# Integration test
uv run pytest tests/integration/test_precheck_review.py -v

# Memory profile
uv run pytest -m memory -v

# Full lint + types
uv run ruff check . && uv run mypy src/ tests/
```

## Artifact References

- **CLI contract**: `specs/011-single-party-review/contracts/cli-contract.md`
- **Data model**: `specs/011-single-party-review/data-model.md`
- **Research**: `specs/011-single-party-review/research.md`
- **Spec**: `specs/011-single-party-review/spec.md`
