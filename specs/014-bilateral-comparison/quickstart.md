# Quickstart — Bilateral Comparison (NX-1)

**Feature**: 014-bilateral-comparison | **Date**: 2026-07-03
**Spec Reference**: [`spec.md`](./spec.md) §2 (User Scenarios)

---

## Prerequisites

- `openreview` CLI installed and configured
- AI Gateway set up (run `openreview gateway setup` if not done)
- Two NDA documents (PDF or DOCX) — one from each party

---

## Scenario 1: Basic Two-NDA Divergence Report

Compare two NDAs and get a full divergence report:

```bash
openreview precheck compare my-nda.pdf their-nda.pdf
```

**Expected output**:
1. Experimental disclaimer printed to stderr
2. Terminal table showing all matched clause pairs
3. Per-pair: heading, Party A position, Party B position, divergence status
   (binary: "Divergence" / "No divergence" by default), confidence, color
4. Unmatched clauses listed separately
5. Roll-up summary: matched pairs, unmatched by side, divergences by type,
   agreement rate, Amber rate

**Verify**:
- [ ] Disclaimer appears
- [ ] All standard NDA clauses appear in the table
- [ ] Unmatched clauses are marked with the correct side (A-only / B-only)
- [ ] Colors are consistent with confidence scores (≥0.7 = Green/Red, <0.7 = Amber)
- [ ] Summary numbers add up (matched + unmatched = total per side)
- [ ] Agreement rate is between 0.0 and 1.0

**Blueprint references**: §2 Scenario 1, §3 FR-4 (three-color), FR-5
(disclaimer), FR-6 (terminal output)

---

## Scenario 2: Alignment-Only Preview

Before running the full comparison pipeline, preview the alignment:

```bash
openreview precheck compare my-nda.pdf their-nda.pdf --align-only
```

**Expected output**:
1. No disclaimer (no inference = no experimental warning needed)
2. Alignment table showing matched and unmatched clauses
3. Each row: heading, alignment_quality, match method, side markers
4. Complete in <5 seconds for typical 50-page NDAs
5. No inference calls — no cost incurred

```bash
# Machine-readable alignment output
openreview precheck compare my-nda.pdf their-nda.pdf --align-only --format json
```

**Verify**:
- [ ] Alignment table has correct number of rows (total_a + total_b - matched_pairs)
- [ ] alignment_quality values: 1.0 for exact matches, 0.8-0.99 for fuzzy, 0.5 for positional
- [ ] Unmatched clauses correctly attributed to the right side
- [ ] Completes quickly (<5 seconds)
- [ ] No inference calls logged

**Blueprint references**: §2 Scenario 5, §3 FR-7 (align-only mode)

---

## Scenario 3: Verbose Output with RCBSF Dimensions

Drill into a specific divergence with full detail:

```bash
openreview precheck compare my-nda.pdf their-nda.pdf --verbose
```

**Expected output**:
- Same as Scenario 1, PLUS per divergence:
- Full RCBSF dimension classification (not just binary)
- `alignment_quality` value for each pair
- Comparison agent rationale and citations
- Both clause texts (truncated)
- Divergence distribution by RCBSF dimension in summary

**Verify**:
- [ ] Divergence column shows full dimension name ("evidence", "suggestion", etc.)
- [ ] Each divergence has a rationale and at least one citation
- [ ] alignment_quality shown for every pair
- [ ] Summary includes "divergences_by_dimension" breakdown
- [ ] Clause texts are PII-free (no raw PII in output)

**Blueprint references**: §2 Scenario 2, §3 FR-3 (RCBSF), FR-6 (verbose
output), Q5 (full taxonomy in verbose)

---

## Scenario 4: JSON Export for Downstream Systems

Export comparison results for a contract management system:

```bash
openreview precheck compare my-nda.pdf their-nda.pdf --format json --output comparison.json
```

**Expected output**:
1. File `comparison.json` created
2. JSON contains: schema_version, document_a, document_b, alignment,
   assessments[], summary
3. Each assessment includes full divergence data (RCBSF dimension rationale,
   citations, confidence, alignment_quality, color)
4. Summary includes divergences_by_dimension map
5. Valid JSON (parse with `python -m json.tool comparison.json`)

**Verify schema compliance**:
- [ ] `schema_version` is `"1.0.0"`
- [ ] `experimental` is `true`
- [ ] `disclaimer` is a non-empty string
- [ ] `document_a` and `document_b` match `DocMeta` schema
- [ ] `alignment` has all fields from `AlignmentTable`
- [ ] `assessments` is a list of `PairedAssessment` objects
- [ ] `summary` has all fields from `ComparisonSummary`
- [ ] All `PairedAssessment` objects have `divergence`, `confidence`,
      `color`, `citations`, `rationale`
- [ ] RCBSF `no_divergence` is NOT in `divergences_by_dimension`
- [ ] `agreement_rate + divergence_rate = 1.0` (within rounding)

**Blueprint references**: §2 Scenario 4, §3 FR-6 (JSON output), §5 (JSON
schema)

---

## Scenario 5: Error Handling — Corrupt Document

Test fail-fast behavior when one document is invalid:

```bash
# Create a corrupt "document"
echo "not a pdf" > corrupt.pdf
openreview precheck compare my-nda.pdf corrupt.pdf
```

**Expected output**:
1. Error message printed to stderr:
   `Error: Failed to parse 'corrupt.pdf': [specific parse error]`
2. Exit code 1
3. No partial output — no alignment table, no comparison report
4. No cached state

```bash
openreview precheck compare nonexistent.pdf their-nda.pdf
```

**Expected output**:
1. Error message: `File not found: nonexistent.pdf`
2. Exit code 1

```bash
openreview precheck compare my-nda.pdf their-nda.pdf --conservative --confidence-threshold 0.8
```

**Expected output**:
1. Error message: `--conservative and --confidence-threshold are mutually exclusive`
2. Exit code 3

**Verify**:
- [ ] All three error cases produce correct exit codes
- [ ] No partial output in any error case
- [ ] Error messages are user-facing, not stack traces
- [ ] --no-partial-output guarantee: even if Party A parsed successfully,
      a Party B parse failure produces no output
- [ ] Mutually exclusive flags produce clear error

**Blueprint references**: §3.3 (Edge Cases), §8 (document parse failure
handling), Q1 (fail-fast)

---

## Scenario 6: Conservative Mode

Run with maximum sensitivity:

```bash
openreview precheck compare my-nda.pdf their-nda.pdf --conservative
```

Equivalent to:
```bash
openreview precheck compare my-nda.pdf their-nda.pdf --confidence-threshold 0.8
```

**Expected output**:
1. Caveat printed: "Confidence threshold set to 0.8 — output includes
   low-confidence comparisons. Expect higher divergence count; manually
   verify each."
2. More clauses appear Amber than with default threshold
3. Higher divergence count (some low-confidence divergences now flagged)

**Verify**:
- [ ] More Amber clauses than default (0.7) threshold
- [ ] Conservative mode produces same output as explicit `--confidence-threshold 0.8`
- [ ] Caveat is printed

**Blueprint references**: §2 Scenario 3, §3 FR-8 (confidence threshold)

---

## Running Automated Validation

```bash
# Unit tests for bilateral package
uv run pytest tests/unit/bilateral/ -q

# Integration tests
uv run pytest tests/integration/test_bilateral_compare.py -q

# Memory test
uv run pytest tests/integration/test_bilateral_memory.py -v

# Full bilateral test suite
uv run pytest tests/ -k "bilateral" -q
```

**Blueprint references**: Constitution (TDD), spec 011 test patterns,
spec §4 (success criteria)
