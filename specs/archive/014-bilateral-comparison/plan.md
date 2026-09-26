# Implementation Plan: Bilateral Comparison (NX-1) — Experimental Two-Party Contract Comparison

**Branch**: `feat/014-bilateral-comparison` | **Date**: 2026-07-03 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from `specs/014-bilateral-comparison/spec.md`

**Research**: [`research.md`](./research.md) — 4 research questions resolved
**Data Model**: [`data-model.md`](./data-model.md) — 7 entity definitions
**CLI Contract**: [`contracts/cli-interface.md`](./contracts/cli-interface.md)
**Quickstart**: [`quickstart.md`](./quickstart.md) — 6 validation scenarios

---

## Summary

Add an experimental `compare` subcommand to `openreview precheck` that
takes two documents (Party A's and Party B's), aligns clauses by heading,
runs the existing single-party extraction + QA pipeline on each side
(sequentially), then runs a comparison agent that detects and classifies
divergences using the RCBSF 5-dimension taxonomy. Output is a paired,
side-by-side view with three-color status and an experimental disclaimer.

The academic ceiling is hard: ≤64% F1 for binary discrepancy (P-4, §6.4).
NX-1 ships as opt-in, labelled EXPERIMENTAL, with Amber escape hatch, an
accuracy caveat, and a mandatory disclaimer against legal advice use.

---

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: None new. Uses existing `difflib` (stdlib),
`dataclasses`, `enum.StrEnum`, `rich`, `typer`, `json`. The comparison
agent reuses the existing extraction model slot — no new model dependency.

**Storage**: N/A — no cache (assumption 5 from spec §6). Each invocation
re-runs alignment from scratch.

**Testing**: pytest — unit tests for alignment engine, comparison agent
prompt builder, paired color assignment, report formatting; integration
tests for full pipeline, CLI flags, error handling, memory budget.

**Target Platform**: Linux/macOS/Windows (CLI tool)

**Project Type**: CLI tool (PreCheck product mode — experimental feature)

**Performance Goals**: ≤10 seconds per clause pair (P95) for comparison
agent. <5 seconds for alignment-only mode on 50-page NDAs. Sequential
processing holds peak memory at single-party levels (~25 MB ex-model).

**Constraints**: <100 MB peak memory (ex-PII-model, Constitution §III).
Zero new runtime dependencies (Constitution §IV). TDD enforced. Must
reuse existing single-party pipeline without modification (FR-10).

**Scale/Scope**: ~30 clause pairs per comparison (typical NDA). ~20
comparisons/day per user. Pilot at single contract type (NDA) [Q-4].

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Justification |
|-----------|---------|---------------|
| **I. Privacy First** | Pass | PII stripping runs upstream on both documents before any inference. Comparison agent sees only PII-stripped text and assessment dataclasses. No new PII exposure paths. Anonymized data collection is opt-in (`--share-data`) and excludes filenames, IPs, identifiers.  *(Note: `--share-data` deferred to future spec pending constitutional amendment to Principles I/II. Not in NX-1 scope.)* |
| **II. Local-First, CLI-Only** | Pass | `compare` is a CLI subcommand with the same lifetime as `review` — single invocation, no server, no daemon. All-local SLM slots produce the same output format. |
| **III. Hardware-Bounded** | Pass | Sequential processing (Q2) keeps peak memory at single-party levels (~25 MB). Alignment table is <1 MB for 60 clause texts. Comparison agent runs one pair at a time. No new heavy imports. NLP model exemption applies to PII only — no new NLP models loaded. |
| **IV. Dependency Minimalism** | Pass | Zero new runtime dependencies. `difflib.SequenceMatcher` is stdlib. The comparison agent reuses the extraction model slot — no new provider or model config. The bilateral package is a new `src/openreview_cli/bilateral/` directory with ~6 modules, no new packages to `pyproject.toml`. |
| **V. Spec-Driven, YAGNI** | Pass | Every entity and function maps to a spec requirement. No speculative abstractions: no cache (not needed yet), no factory for alignment methods (3-tier cascade is hardcoded), no plugin system. The `--comparison-model` flag is explicitly deferred (FR-3/Q3). |

---

## Project Structure

### Documentation (this feature)

```text
specs/014-bilateral-comparison/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output — 4 research questions resolved
├── data-model.md        # Phase 1 output — 7 entity definitions
├── quickstart.md        # Phase 1 output — 6 validation scenarios
├── contracts/           # Phase 1 output — CLI interface contract
│   └── cli-interface.md
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created here)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── bilateral/                          # NEW PACKAGE — comparison pipeline
│   ├── __init__.py                     # Public API: run_comparison()
│   ├── models.py                       # PairedAssessment, AlignmentPair, AlignmentTable,
│   │                                   # ComparisonReport, ComparisonSummary, RCBSFDimension,
│   │                                   # MatchingMethod
│   ├── align.py                        # AlignmentEngine — exact → fuzzy → positional cascade
│   ├── comparison.py                   # ComparisonAgent — prompt builder + divergence detection
│   ├── report.py                       # ComparisonReportFormatter — terminal + JSON output
│   ├── colors.py                       # PairedColorAssigner — three-color per paired assessment
│   └── prompts.py                      # Comparison agent prompt templates (RCBSF 5-dim)
│
├── app.py                              # Add `compare` subcommand to precheck_app
│
└── review/                             # EXISTING — reused as-is (FR-10)
    ├── __init__.py                     # run_review() — per-party pipeline
    ├── models.py                       # ClauseAssessment, DocMeta, etc.
    ├── extraction.py                   # extract_clause() — per-party extraction
    ├── qa.py                           # verify_assessment() — per-party QA
    ├── report.py                       # format_terminal(), format_json()
    └── base.py                         # ReviewCommand

tests/
├── unit/bilateral/
│   ├── test_align.py                   # AlignmentEngine — exact, fuzzy, positional, unmatched
│   ├── test_comparison.py              # ComparisonAgent — prompt builder, RCBSF classification
│   ├── test_models.py                  # PairedAssessment, AlignmentTable validation
│   ├── test_colors.py                  # PairedColorAssigner — three-color computation
│   └── test_report.py                  # Terminal + JSON formatter for comparison
│
├── integration/
│   ├── test_bilateral_compare.py       # Full pipeline CLI test (2 documents → output)
│   ├── test_bilateral_align_only.py    # --align-only mode, alignment table
│   ├── test_bilateral_flags.py         # --conservative, --confidence-threshold, --format
│   ├── test_bilateral_errors.py        # Corrupt/missing file, mutual exclusion
│   ├── test_bilateral_disclaimer.py    # Experimental disclaimer on every run
│   └── test_bilateral_memory.py        # Memory budget verification (<100 MB ex-model)
│
└── fixtures/
    ├── nda_pair_aligned/               # Two NDAs with known alignment
    │   ├── party_a.pdf
    │   ├── party_b.pdf
    │   └── expected_alignment.json
    ├── nda_pair_divergent/             # Two NDAs with known divergences
    │   ├── party_a.pdf
    │   ├── party_b.pdf
    │   └── expected_divergences.json
    └── corrupt.pdf                     # Non-PDF binary for error testing
```

**Structure Decision**: Single-project layout (Option 1). New `bilateral/`
package follows the same pattern as `review/`, `pii/`, `gateway/`. Tests
follow existing `tests/unit/` and `tests/integration/` conventions.

---

## Implementation Phases

### Phase 1 — Data Models (`src/openreview_cli/bilateral/models.py`)

Files: `src/openreview_cli/bilateral/models.py`

1. Add `RCBSFDimension(StrEnum)` with 6 values: `category`, `location`,
   `evidence`, `issue`, `suggestion`, `no_divergence`
2. Add `MatchingMethod(StrEnum)` with 5 values: `exact_heading`,
   `fuzzy_heading`, `positional`, `unmatched_a`, `unmatched_b`
3. Add `AlignmentPair` dataclass (slots=True): heading, clause_id_a,
   clause_id_b, alignment_quality, match_method, index_a, index_b
4. Add `AlignmentTable` dataclass (slots=True): pairs, unmatched_a_ids,
   unmatched_b_ids, total_a, total_b, alignment_rate (computed property)
5. Add `PairedAssessment` dataclass (slots=True): pair_id, clause_heading,
   party_a_assessment (ClauseAssessment), party_b_assessment (ClauseAssessment),
   divergence (RCBSFDimension), confidence (0.0-1.0), alignment_quality (0.0-1.0),
   color (AssessmentColor|None), citations, rationale
6. Add `ComparisonSummary` dataclass (slots=True): total_pairs, divergences,
   divergences_by_dimension, unmatched_a, unmatched_b, agreement_rate,
   green_count, amber_count, red_count, avg_alignment_quality, confidence_threshold
7. Add `ComparisonReport` dataclass (slots=True): experimental, disclaimer,
   document_a (DocMeta), document_b (DocMeta), alignment (AlignmentTable),
   assessments (list[PairedAssessment]), summary (ComparisonSummary),
   schema_version

**Tests**: `tests/unit/bilateral/test_models.py`
- PairedAssessment validation (confidence range, divergence enum)
- AlignmentTable alignment_rate computation
- ComparisonSummary agreement_rate computation
- RCBSFDimension, MatchingMethod enum values

**Blueprint references**: spec §5, data-model.md

---

### Phase 2 — Clause Alignment Engine (`src/openreview_cli/bilateral/align.py`)

Files: `src/openreview_cli/bilateral/align.py`

1. Implement `AlignmentEngine` class:
   - `align(clauses_a: list[Clause], clauses_b: list[Clause]) -> AlignmentTable`
   - Three-tier cascade: exact → fuzzy (difflib, threshold=0.8) → positional
   - Output: `AlignmentTable` with all pairs + unmatched lists
2. Static methods for each tier:
   - `_exact_match(heading_a, heading_b) -> bool`: case-insensitive `==`
   - `_fuzzy_match(heading_a, heading_b, threshold=0.8) -> bool`:
     `SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold`
   - `_structural_fallback(clauses_a, clauses_b) -> list[AlignmentPair]`:
     match by positional index, handle length mismatch
3. Alignment tracking:
   - Track which clauses in each document have been matched
   - Leftovers after all tiers = unmatched

**Tests**: `tests/unit/bilateral/test_align.py`
- Exact heading match: same heading in both docs → alignment_quality 1.0
- Fuzzy heading match: "Confidentiality" vs "Confidentiality Obligations" → ≥0.8
- Positional fallback: no heading match → position-based match
- Unmatched A + unmatched B reported correctly
- Mixed scenario: some exact, some fuzzy, some unmatched
- Empty documents → empty alignment table
- Edge case: identical documents → all matched
- Edge case: completely different headings → all unmatched

**Blueprint references**: FR-1, research.md RQ-1, §4 (≥90% alignment)

---

### Phase 3 — Comparison Agent Prompt Builder (`src/openreview_cli/bilateral/prompts.py`)

Files: `src/openreview_cli/bilateral/prompts.py`

1. Define `BUILD_COMPARISON_SYSTEM_PROMPT()` returning system message:
   - Role: contract comparison agent
   - RCBSF 5-dimension taxonomy definitions
   - Output format spec (JSON with divergence, confidence, citations, rationale)
   - Accuracy caveat (P-4 ≤64% F1 ceiling)
   - "never prescriptive" language per Q-6
2. Define `build_comparison_messages()`:
   - Input: clause_a_text, clause_b_text, assessment_a, assessment_b
   - Output: list of chat messages (system + user)
   - User message: template with both clause texts + both assessments

**Tests**: `tests/unit/bilateral/test_comparison.py`
- System prompt includes RCBSF dimension descriptions
- System prompt includes accuracy caveat
- User message contains both clause texts
- User message contains both positions and confidences
- Output format expected is valid JSON schema

**Blueprint references**: FR-3, research.md RQ-2, P-14, P-13

---

### Phase 4 — Comparison Agent (`src/openreview_cli/bilateral/comparison.py`)

Files: `src/openreview_cli/bilateral/comparison.py`

1. Implement `ComparisonAgent` class:
   - `__init__(model_slot: str)` — uses extraction model slot
   - `compare(assessment_a: ClauseAssessment, assessment_b: ClauseAssessment, clause_a_text: str, clause_b_text: str) -> PairedAssessment`
2. Pipeline:
   - Build messages using prompts.py
   - Call `call_gateway_chat()` from review._gateway
   - Parse JSON response into divergence + confidence + citations + rationale
   - Return partially-filled PairedAssessment (color set later in Phase 7)
3. Error handling:
   - If model returns invalid JSON → mark as Amber with error
   - If confidence is out of range → clamp to [0.0, 1.0]
   - If model fails → raise ComparisonError

**Tests**: `tests/unit/bilateral/test_comparison.py`
- Successful comparison → PairedAssessment with valid fields
- Model returns no_divergence → PairedAssessment with no_divergence
- Model returns each RCBSF dimension → correctly parsed
- Invalid JSON response → Amber with error
- Gateway failure → ComparisonError raised

**Blueprint references**: FR-3, Q3 (reuse extraction slot), P-4 (accuracy

---

### Phase 5 — Orchestrator (`src/openreview_cli/bilateral/__init__.py`)

Files: `src/openreview_cli/bilateral/__init__.py`

1. Implement `run_comparison()`:
   - Input: doc_a_path, doc_b_path, playbook, model slots, options
   - Output: `ComparisonReport`
2. Pipeline (sequential per Q2):
   - Parse Document A → extract clauses
   - Run single-party extraction + QA for Document A (reuse `extract_clause()` + `verify_assessment()` from review/)
   - Store A's parsed clauses + assessments
   - Release A's inference state (model output buffers, tokenizer caches)
   - Parse Document B → extract clauses
   - Run single-party extraction + QA for Document B
   - Store B's parsed clauses + assessments
   - Release B's inference state
   - Run `AlignmentEngine.align(clauses_a, clauses_b)` → AlignmentTable
   - For each aligned pair:
     - Get ClauseAssessment for A and B
     - Build comparison messages
     - Call comparison agent → PairedAssessment
   - Build ComparisonSummary from all paired assessments
   - Build ComparisonReport
   - Apply disclaimer (FR-5)
3. Export `run_comparison` in `__init__.py`'s `__all__`

**Tests**: Integration tests only (tests/integration/). Unit tests already
cover each component individually.

**Blueprint references**: FR-2, FR-10, Q2 (sequential), research.md RQ-3

---

### Phase 6 — Paired Color Assignment (`src/openreview_cli/bilateral/colors.py`)

Files: `src/openreview_cli/bilateral/colors.py`

1. Implement `assign_paired_colors(assessments: list[PairedAssessment], threshold: float = 0.7)`:
   - For each PairedAssessment:
     - If divergence confidence < threshold → Amber
     - If QA disagreed on either side → Amber
     - If extraction confidence < threshold on either side → Amber
     - If divergence detected with confidence ≥ threshold and no Amber triggers → Red
     - Otherwise (no divergence, both sides confident) → Green
2. Pure function — no side effects, no re-run of inference
3. Follows spec 013 `assign_colors()` pattern exactly

**Tests**: `tests/unit/bilateral/test_colors.py`
- No divergence, both confident → Green
- Divergence detected, confident → Red
- Divergence below threshold → Amber
- QA disagreement on one side → Amber
- Low extraction confidence on one side → Amber
- Threshold=0.9 → more Amber than threshold=0.5
- All triggers apply simultaneously → Amber (any trigger wins)
- Pure function — no mutation of input

**Blueprint references**: FR-4, spec 013 FR-001–FR-007, §6.4

---

### Phase 7 — Report Formatter (`src/openreview_cli/bilateral/report.py`)

Files: `src/openreview_cli/bilateral/report.py`

1. Implement `format_comparison_terminal(report: ComparisonReport, verbose: bool = False) -> str`:
   - Experimental disclaimer header
   - Document info block
   - Per-pair table: heading, A position, B position, divergence (binary
     unless verbose), confidence, color badge
   - Under verbose: alignment_quality, rationale, full RCBSF dimension,
     citations, truncated clause texts
   - Unmatched clauses section
   - Summary roll-up
   - Footer disclaimer

2. Implement `format_comparison_json(report: ComparisonReport) -> str`:
   - Full data model serialization
   - schema_version included
   - alignment_quality always included per Q4
   - RCBSF taxonomy always present per Q5

3. Implementation mirrors `review/report.py` `format_terminal()` and
   `format_json()` exactly.

**Tests**: `tests/unit/bilateral/test_report.py`
- Terminal output: all sections present, color badges correct
- Terminal verbose: RCBSF dimensions shown, rationale present
- JSON output: matches expected schema, validates against data model
- Disclaimer appears in both formats
- Empty comparison (no assessments) → valid empty output
- Error formatting: graceful handling of None fields

**Blueprint references**: FR-6, Q4, Q5

---

### Phase 8 — CLI Integration (`src/openreview_cli/app.py`)

Files: `src/openreview_cli/app.py`

1. Add `compare` subcommand to existing `precheck_app` Typer group:
   - Positional args: `doc_a: str`, `doc_b: str`
   - Options: `--playbook`, `--extraction-model`, `--qa-model`,
     `--confidence-threshold` (default 0.7, callback validates 0.0-1.0),
     `--format` (text|json), `--output`, `--align-only`, `--verbose`,
      `--no-pii`, `--conservative`, `--grounding-mode`, `--no-grounding`
      <!-- ponytail: --share-data deferred to future spec pending constitutional amendment -->
2. Validation:
   - Both files exist before processing either
   - Mutually exclusive: `--conservative` and `--confidence-threshold`
   - Format: `text` or `json`
3. Error handling:
   - Parse fail → exit code 1, print which file and why
   - No partial output on failure (spec §8)
4. One-time experimental warning on first `compare` invocation
   (per-machine, stored in data dir marker file)

**Tests**: `tests/integration/test_bilateral_compare.py` (full CLI test)
`tests/integration/test_bilateral_flags.py` (--conservative, --format)
`tests/integration/test_bilateral_errors.py` (corrupt, missing, mutual exclusion)
`tests/integration/test_bilateral_disclaimer.py` (first-run warning)

**Blueprint references**: FR-9 (opt-in), research.md RQ-4, existing app.py
patterns

---

### Phase 9 — First-Run Warning + Disclaimer (`src/openreview_cli/bilateral/__init__.py`)

Files: `src/openreview_cli/bilateral/__init__.py` + `src/openreview_cli/app.py`

1. First-run detection:
   - Check for marker file `{data_dir}/.bilateral_first_run`
   - If absent: print warning to stderr, create marker file
   - Warning content (spec FR-9):
     ```
     ⚠ NX-1 Bilateral Comparison is EXPERIMENTAL.
     Comparison accuracy has known limitations.
     Review all results manually before relying on them.
     See https://github.com/mohamed-benoughidene/openreview-specs/014 for details.
     ```
   - Warning is non-suppressible per spec

2. Per-run disclaimer (FR-5):
   - Always printed to stderr
   - Contains experimental badge + accuracy caveat
   - Never "sign this" language
   - Confidence threshold disclosure
   - Amber count / percentage

**Tests**: `tests/integration/test_bilateral_disclaimer.py`
- First run: warning printed
- Second run: warning NOT printed
- Disclaimer always present in output
- Disclaimer printed to stderr, not stdout

**Blueprint references**: FR-5, FR-9, §9 R-1

---

## Dependency Map

```
compare CLI (app.py)
  └─ run_comparison() (bilateral/__init__.py)
       ├─ stream_clauses() (parsing/)              ← existing, FR-10
       ├─ extract_clause() (review/)                ← existing, FR-10
       ├─ verify_assessment() (review/)             ← existing, FR-10
       ├─ AlignmentEngine.align() (bilateral/align.py)  ← NEW
       ├─ ComparisonAgent.compare() (bilateral/comparison.py)  ← NEW
       │    ├─ build_comparison_messages() (bilateral/prompts.py)  ← NEW
       │    └─ call_gateway_chat() (review/_gateway.py)  ← existing
       ├─ assign_paired_colors() (bilateral/colors.py)  ← NEW
       └─ format_comparison_terminal/json() (bilateral/report.py)  ← NEW
```

**All existing components are reused without modification.** The bilateral
pipeline is a pure composition layer on top of the single-party review
pipeline.

---

## Edge Cases / Failure Modes

| Edge Case | Handling | File |
|-----------|----------|------|
| Both documents identical | All pairs Green, agreement_rate=1.0, no divergences | align.py + comparison.py |
| One document has extra clauses | Reported as unmatched with side marker | align.py |
| No headings match at all | All pairs unmatched (0 alignment rate) | align.py |
| Model returns invalid JSON | Amber with error, rationale set to "comparison agent parse error" | comparison.py |
| Document A parses, B fails | Fail-fast — no output, exit code 1 | app.py |
| Both documents fail | Fail-fast — first failure printed, exit 1 | app.py |
| --align-only on empty document | Alignment table with 0 pairs, 0 alignment_rate | app.py |
| Single-clause NDA | Single pair processed normally | align.py |
| Threshold=0.0 | Everything is Green (no divergence) or Red (all divergences confident) | colors.py |
| Threshold=1.0 | Everything is Amber (no divergence is 100% confident) | colors.py |
| --conservative + --confidence-threshold | Mutually exclusive → error exit 3 | app.py |

---

## Complexity Tracking

> **Constitution Check has no violations — this section is informational.**

No complexity needs justification. The implementation adds:
- 1 new package (`bilateral/`) with ~6 modules — same pattern as `review/`
- 1 new CLI subcommand — mirrors existing `review` pattern
- 0 new runtime dependencies — all stdlib
- 0 new config keys — reuses existing model slots

**ponytail: this exists** — every module and data class maps directly
to a spec requirement. No speculative abstraction, no interface with one
implementation, no config for a value that never changes.

---

## File Change Summary

| File | Action | Content |
|------|--------|---------|
| `src/openreview_cli/bilateral/__init__.py` | **CREATE** | Public API: `run_comparison()` |
| `src/openreview_cli/bilateral/models.py` | **CREATE** | 7 dataclasses, 2 enums |
| `src/openreview_cli/bilateral/align.py` | **CREATE** | 3-tier alignment cascade |
| `src/openreview_cli/bilateral/comparison.py` | **CREATE** | Comparison agent |
| `src/openreview_cli/bilateral/prompts.py` | **CREATE** | RCBSF prompt templates |
| `src/openreview_cli/bilateral/colors.py` | **CREATE** | Paired color assignment |
| `src/openreview_cli/bilateral/report.py` | **CREATE** | Terminal + JSON output |
| `src/openreview_cli/app.py` | **MODIFY** | Add `compare` subcommand |
| `tests/unit/bilateral/test_models.py` | **CREATE** | Data model tests |
| `tests/unit/bilateral/test_align.py` | **CREATE** | Alignment engine tests |
| `tests/unit/bilateral/test_comparison.py` | **CREATE** | Comparison agent tests |
| `tests/unit/bilateral/test_colors.py` | **CREATE** | Paired color tests |
| `tests/unit/bilateral/test_report.py` | **CREATE** | Report formatter tests |
| `tests/integration/test_bilateral_compare.py` | **CREATE** | Full CLI pipeline test |
| `tests/integration/test_bilateral_align_only.py` | **CREATE** | `--align-only` test |
| `tests/integration/test_bilateral_flags.py` | **CREATE** | CLI flags test |
| `tests/integration/test_bilateral_errors.py` | **CREATE** | Error handling test |
| `tests/integration/test_bilateral_disclaimer.py` | **CREATE** | Disclaimer test |
| `tests/integration/test_bilateral_memory.py` | **CREATE** | Memory budget test |
| `tests/fixtures/nda_pair_aligned/` | **CREATE** | Test fixtures |
| `tests/fixtures/nda_pair_divergent/` | **CREATE** | Test fixtures |
| `AGENTS.md` | **MODIFY** | Update SPECKIT plan reference |

---

## Blueprint References

| Reference | Where Used |
|-----------|------------|
| P-4 (binary discrepancy F1 ≤64%) | spec §1, FR-3, FR-5, research.md RQ-2, plan.md (ceiling) |
| P-13 (PAKTON 3-agent) | spec §1, research.md RQ-2 (prompt pattern), plan.md (extraction reuse) |
| P-14 (RCBSF 5-dimension taxonomy) | spec §1, §3 FR-3, §5, research.md RQ-2, data-model.md |
| §4 (C-12, C-20, C-22) | spec §1, FR-3, FR-10 |
| §6.4 (three-color, Amber generous) | spec §1, FR-4, FR-8, plan.md (paired colors) |
| §6.7 (comparison unsolved) | spec §1, FR-1, research.md RQ-1 |
| §8 (R-1, R-6, R-7, R-11) | spec §1, FR-3, FR-5, FR-8 |
| §9 (R-1, R-11) | spec §1, FR-5, FR-9 |
| §10 (Q-1, Q-4, Q-5, Q-6) | spec §1, FR-5, FR-9, FR-10 (pilot scope) |
| spec 013 (three-color) | FR-4, FR-8, plan.md Phase 6 |
| spec 011 (single-party review) | FR-2, FR-10, plan.md (all phases) |
| Constitution §III (memory budget) | research.md RQ-3, plan.md (sequential processing) |
| Constitution §IV (dependency minimalism) | research.md RQ-1, plan.md (no new deps) |
