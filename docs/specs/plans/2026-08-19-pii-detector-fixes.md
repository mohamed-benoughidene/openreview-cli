# PII Detection Fixes (Allowlist + Phone + Passport + ACCT) Implementation Plan

> **For agentic workers:** Use tasks as checkboxes (`- [ ]`) for tracking.

**Goal:** Implement exactly four honest PII detector fixes — entity-type allowlist, 7-digit US phone pattern, passport-word pattern, and IBAN→ACCT recognizer — improving the seeded-corpus benchmark without gaming the scoring.

**Architecture:** Extend the custom Presidio recognizers in `src/openreview_cli/pii/recognizers.py` (add a US-local phone pattern recognizer, a passport-word pattern on the existing ID_DOCUMENT recognizer, and a generic ISO-13616 IBAN→ACCT recognizer), and restrict `PiiEngine.detect_on_page` to the 11 ground-truth entity types by passing `entities=[...]` to `analyzer.analyze(...)` in `src/openreview_cli/pii/engine.py`. All patterns are generic (no template-fitting to the seeded corpus); the global threshold stays 0.7.

**Tech Stack:** Python 3.12, presidio-analyzer 2.2.362 (PatternRecognizer/Pattern API), pytest, ruff, mypy.

## Global Constraints

- Only four changes, exactly as scoped: allowlist, 7-digit phone, passport-word, IBAN→ACCT.
- `entities` kwarg to `analyzer.analyze` exists in Presidio 2.2.362 (`entities: Optional[List[str]] = None`, positional #3) — verified in `.venv` source.
- Threshold stays 0.7 everywhere. Do NOT tune it.
- Do NOT touch `src/openreview_cli/benchmark/metrics_pii.py`, the test scoring, or `tests/fixtures/pii/seeded_contracts/ground_truth.json` — the scoring amendment is a separate task.
- Do NOT add template-fitting patterns for `AutoName|ManualName`, `AutoCompany`, street addresses, or `PASSPORT12345X`-specific digits.
- Keep changes minimal and surgical; follow existing code style in `recognizers.py`/`engine.py`.
- Score for every new pattern: 0.8 (above the 0.7 threshold, below the regex-phase 1.0).

---

### Task 1: Baseline confirmation (gate regression)

**Files:**
- Run only: `tests/integration/test_benchmark_pii_accuracy.py`

- [ ] **Step 1: Run the gate test at baseline**

Run: `uv run pytest tests/integration/test_benchmark_pii_accuracy.py -q`
Expected: FAIL — `test_pii_recall_above_threshold` asserts recall ≥ 0.95.

- [ ] **Step 2: Record exact baseline numbers**

Run: `uv run python <scratchpad>/pii_bench.py` (script that calls `BenchmarkRunner.run_pii` with the real `PiiEngine`, prints recall/precision/F1 + per-type recall)
Expected: recall=0.5282 (n=568), precision=0.5629 (n=533), f1=0.5450. Per-type: acct 0.0, phone 0.0, id_document 0.34, location 0.0, person 0.20, organization 0.5735, date_time 0.68, amount/email/tax_id/reg_number 1.0.

**Baseline recorded: recall 0.5282 / precision 0.5629 / f1 0.5450.**

**Post-fix (Task 4): recall 0.7060 / precision 0.6375 / f1 0.6700.**
Per-type recall post-fix: acct 0.68, id_document 0.68, phone_number 1.0, person 0.20,
organization 0.5735, location 0.0, date_time 0.68, amount/email/tax_id/reg_number 1.0.
(Note: 48/568 GT pairs — 16 DATE_TIME + 16 ACCT + 16 ID_DOCUMENT — are absent from their
document text and are undetectable by ANY detector; hard recall ceiling 520/568 = 0.9155.)

---

### Task 2: RED — failing unit tests for the four fixes

**Files:**
- Modify: `tests/unit/test_pii_recognizers.py` (new tests)
- Modify: `tests/unit/test_pii_engine.py` (new allowlist test class)

**Interfaces:**
- Consumes: `get_custom_recognizers() -> list[PatternRecognizer]` (indices: 0 AMOUNT, 1 TAX_ID, 2 ID_DOCUMENT, 3 REG_NUMBER — after Task 3, 4 PHONE_NUMBER, 5 ACCT), `PiiEngine.detect_on_page(text, ...)`.
- Produces: failing tests that define the new behavior.

- [ ] **Step 1: Add phone/passport/ACCT pattern tests to `test_pii_recognizers.py`**

Append (keeping the existing `_has_pattern` helper style):

```python
def test_phone_recognizer_local_number() -> None:
    rec = get_custom_recognizers()[4]
    assert "PHONE_NUMBER" in rec.supported_entities
    pattern = rec.patterns[0]
    assert re.search(pattern.regex, "555-0101")
    assert re.search(pattern.regex, "Call 555-1234 today")
    assert not re.search(pattern.regex, "555-010-1234")


def test_phone_recognizer_does_not_match_10_digit() -> None:
    # The 10-digit fiction range is NOT special-cased; a plain 10-digit
    # string without hyphens is not a local-number match.
    rec = get_custom_recognizers()[4]
    pattern = rec.patterns[0]
    assert not re.search(pattern.regex, "5550101234")


def test_id_document_recognizer_passport_word() -> None:
    rec = get_custom_recognizers()[2]
    assert "ID_DOCUMENT" in rec.supported_entities
    assert any(p.regex == r"\bPASSPORT\d{6,9}\b" for p in rec.patterns)


def test_id_document_passport_word_matches() -> None:
    rec = get_custom_recognizers()[2]
    pattern = next(p for p in rec.patterns if p.name == "passport_word")
    assert re.search(pattern.regex, "PASSPORT123457")
    assert re.search(pattern.regex, "PASSPORT1234567")
    assert not re.search(pattern.regex, "PASSPORT12345X")
    assert not re.search(pattern.regex, "PASSPORT12345")  # 5 digits < min


def test_id_document_keeps_existing_patterns() -> None:
    rec = get_custom_recognizers()[2]
    pattern = rec.patterns[0]  # existing passport regex
    assert re.search(pattern.regex, "AB123456")
    assert re.search(pattern.regex, "A1234567")


def test_acct_recognizer_iban() -> None:
    rec = get_custom_recognizers()[5]
    assert "ACCT" in rec.supported_entities
    pattern = rec.patterns[0]
    assert re.search(pattern.regex, "GB29NWBK60161331926801")
    assert re.search(pattern.regex, "DE89370400440532013000")
    assert not re.search(pattern.regex, "GB29 NWBK 6016 1331 9268 01")  # spaced IBAN not matched
```

- [ ] **Step 2: Add allowlist behavior test to `test_pii_engine.py`**

Append:

```python
class TestDetectOnPageAllowlist:
    """detect_on_page restricts analysis to the 11 ground-truth entity types."""

    def test_analyze_called_with_entities_allowlist(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        engine = PiiEngine(threshold=0.7)
        captured: dict[str, object] = {}

        class _RecordingAnalyzer:
            def analyze(self, **kwargs: object) -> list[object]:
                captured.update(kwargs)
                return []

        monkeypatch.setattr(engine, "_ensure_analyzer", lambda: _RecordingAnalyzer())
        engine.detect_on_page("Some contract text with $5,000.")

        assert captured["entities"] == [
            "PERSON",
            "ORGANIZATION",
            "LOCATION",
            "DATE_TIME",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "AMOUNT",
            "TAX_ID",
            "ACCT",
            "ID_DOCUMENT",
            "REG_NUMBER",
        ]
```

- [ ] **Step 3: Run the new tests, verify they fail (RED)**

Run: `uv run pytest tests/unit/test_pii_recognizers.py tests/unit/test_pii_engine.py -q`
Expected: 8 failures — IndexError for recognizer indices 4/5, no `passport_word` pattern, and `entities` kwarg absent from the recorded call.

---

### Task 3: GREEN — implement the four fixes

**Files:**
- Modify: `src/openreview_cli/pii/recognizers.py` (add 2 recognizers + 1 pattern)
- Modify: `src/openreview_cli/pii/engine.py` (entities allowlist in `detect_on_page`)

**Interfaces:**
- Consumes: `Pattern`, `PatternRecognizer` from `presidio_analyzer`; `analyzer.analyze(text=..., language=..., entities=[...], score_threshold=...)`.
- Produces: `get_custom_recognizers()` returning 6 recognizers; `detect_on_page` returning only the 11 allowlisted entity types.

- [ ] **Step 1: Add PHONE_NUMBER and ACCT recognizers, passport-word pattern**

In `src/openreview_cli/pii/recognizers.py`, add to the ID_DOCUMENT recognizer:

```python
        PatternRecognizer(
            supported_entity="ID_DOCUMENT",
            patterns=[
                Pattern("passport", r"\b[A-Z]{1,2}\d{6,9}\b", 0.8),
                Pattern("drivers_license", r"\bDL\d{7,10}\b", 0.8),
                Pattern("passport_word", r"\bPASSPORT\d{6,9}\b", 0.8),
            ],
        ),
```

and append two recognizers to the returned list (after REG_NUMBER):

```python
        PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            patterns=[
                Pattern("us_local_number", r"\b\d{3}-\d{4}\b", 0.8),
            ],
        ),
        PatternRecognizer(
            supported_entity="ACCT",
            patterns=[
                Pattern("iban", r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", 0.8),
            ],
        ),
```

- [ ] **Step 2: Restrict `analyzer.analyze` to the 11 entity types**

In `src/openreview_cli/pii/engine.py` `detect_on_page`, replace the analyze call:

```python
            results = analyzer.analyze(
                text=text,
                language="en",
                entities=[
                    "PERSON",
                    "ORGANIZATION",
                    "LOCATION",
                    "DATE_TIME",
                    "EMAIL_ADDRESS",
                    "PHONE_NUMBER",
                    "AMOUNT",
                    "TAX_ID",
                    "ACCT",
                    "ID_DOCUMENT",
                    "REG_NUMBER",
                ],
                score_threshold=threshold,
            )
```

- [ ] **Step 3: Run the unit tests, verify they pass (GREEN)**

Run: `uv run pytest tests/unit/test_pii_recognizers.py tests/unit/test_pii_engine.py -q`
Expected: all pass (existing + new). No changes to other tests needed — the allowlist is a strict subset of what the engine already returned for in-scope types.

- [ ] **Step 4: Commit**

```bash
git add src/openreview_cli/pii/recognizers.py src/openreview_cli/pii/engine.py
git add tests/unit/test_pii_recognizers.py tests/unit/test_pii_engine.py
git commit -m "fix(pii): allowlist entity types, add local phone, passport-word, and IBAN patterns"
```

---

### Task 4: Verify benchmark FAIL-but-improved

**Files:**
- Run only: `tests/integration/test_benchmark_pii_accuracy.py`, scratchpad `pii_bench.py`

- [ ] **Step 1: Re-run the gate test**

Run: `uv run pytest tests/integration/test_benchmark_pii_accuracy.py -q`
Expected: STILL FAIL (recall/precision still < 0.95 — these fixes alone don't reach 95/95). If it passes, that indicates a mistake — re-check the scope.

- [ ] **Step 2: Record exact post-fix numbers**

Run: `uv run python <scratchpad>/pii_bench.py`
Expected: recall ≈ 0.65–0.70, precision ≈ 0.58–0.62. Report exact values + per-type recall.

- [ ] **Step 3: Commit benchmark evidence (numbers only — no test changes)**

No commit needed for evidence; record numbers in the task report.

---

### Task 5: Regression checks — full PII unit + integration, lint, types

**Files:**
- Run only: `tests/unit/test_pii_*.py`, `tests/integration/test_pii_*.py`, `ruff`, `mypy`

- [ ] **Step 1: Run all PII unit tests**

Run: `uv run pytest tests/unit/test_pii_*.py -q`
Expected: all pass (recognizers, engine, engine_tier, placeholders, mapping, models, audit, cache, retention, encryption, config_hash, fail_closed).

- [ ] **Step 2: Run non-network PII integration tests**

Run: `uv run pytest tests/integration/test_pii_accuracy.py tests/integration/test_pii_strip_command.py tests/integration/test_pii_error_handling.py tests/integration/test_pii_memory.py -q`
Expected: pass (or skip where fixtures/network required).

- [ ] **Step 3: Lint and type-check changed files**

Run: `uv run ruff check src/openreview_cli/pii/recognizers.py src/openreview_cli/pii/engine.py tests/unit/test_pii_recognizers.py tests/unit/test_pii_engine.py`
Expected: clean.
Run: `uv run mypy src/openreview_cli/pii/recognizers.py src/openreview_cli/pii/engine.py`
Expected: no new errors.

- [ ] **Step 4: Commit any remaining fixes, report**

Expected: repo clean of the four changes; report exact before/after numbers.

## Self-Review

1. **Spec coverage:** Task 2+3 cover all four scoped changes (allowlist in engine.py, phone recognizer, passport_word pattern, IBAN→ACCT). Constraint checks: no template-fitting patterns (all patterns generic), metrics_pii.py/ground_truth untouched, threshold stays 0.7, minimal diffs.
2. **Placeholder scan:** No TBD/TODO — all steps carry exact code and commands.
3. **Type consistency:** Recognizer list indices used in tests (0-5) match the order returned by `get_custom_recognizers()`; `entities` kwarg matches Presidio 2.2.362 signature verified in `.venv`.
