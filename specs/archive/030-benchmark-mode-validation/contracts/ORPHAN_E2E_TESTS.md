# Interface Contract: Orphan E2E Tests (FR-6)

**Spec ref**: spec 030 FR-6
**New file**: `tests/integration/test_benchmark_orphan_modes.py`

## Test Contract

```python
@pytest.mark.parametrize("mode", [
    "licensecheck", "leasecheck", "privacycheck", "indemnitycheck",
    "consultcheck", "workcheck", "loicheck", "subcheck", "settlementcheck",
])
def test_orphan_mode_e2e(mode, monkeypatch, fixtures_dir):
    """End-to-end pipeline test for one orphan mode.

    Asserts:
    1. Fixture document loads and parses
    2. PII is stripped
    3. ReviewReport is returned with non-empty assessments
    4. Each assessment has a three-color verdict
    """
```

## Fixture Locations

| Mode | Fixture Path | Exists |
|------|-------------|--------|
| licensecheck | `tests/fixtures/benchmark/licensecheck/doc_1.pdf` | ✔ |
| leasecheck | `tests/fixtures/benchmark/leasecheck/doc_1.pdf` | ✔ |
| privacycheck | `tests/fixtures/benchmark/privacycheck/doc_1.pdf` | ✔ |
| indemnitycheck | `tests/fixtures/benchmark/indemnitycheck/doc_1.pdf` | ✔ |
| consultcheck | `tests/fixtures/benchmark/consultcheck/doc_1.pdf` | ✔ |
| workcheck | `tests/fixtures/benchmark/workcheck/doc_1.pdf` | ✔ |
| loicheck | `tests/fixtures/benchmark/loicheck/doc_1.pdf` | ✔ |
| subcheck | `tests/fixtures/benchmark/subcheck/doc_1.pdf` | ✔ |
| settlementcheck | `tests/fixtures/benchmark/settlementcheck/doc_1.pdf` | ✔ |

## Mock Gateway Pattern

```python
def mock_gateway_chat(messages, **kwargs):
    """Return pre-determined assessment matching the mode's playbook."""
    return {
        "clause_id": "clause_1",
        "clause_text": "...",
        "category": "confidentiality",
        "position": "preferred",
        "confidence": 0.85,
        "citation": "Section 2.1",
        "qa_verdict": "confirmed",
    }
```

## Assertion Contract (reconciled with actual model)

```python
# Use actual model — not spec pseudocode
report = reports[0]  # run_review returns list[ReviewReport]

assert len(report.assessments) > 0, f"No assessments for mode {mode}"

for assessment in report.assessments:
    assert assessment.color is not None, \
        f"Mode {mode}: clause {assessment.clause_id} has no color verdict"
    assert assessment.color in (
        AssessmentColor.green,
        AssessmentColor.amber,
        AssessmentColor.red,
    ), f"Mode {mode}: unexpected color '{assessment.color}'"
```

## Memory Budget

Each test parses a single PDF (5-10 pages), processes through PII + review.
Peak should stay under 110 MB (NLP model exempt). Tests run sequentially.
