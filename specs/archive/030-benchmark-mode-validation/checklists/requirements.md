# Spec Quality Checklist — 030-benchmark-mode-validation

Validate spec.md against these criteria. Each item: **PASS**, **FAIL**, or **N/A**.

## A. Structure & Completeness

| # | Check | Result | Notes |
|---|-------|--------|-------|
| A1 | Feature ID matches directory name | PASS | `030-benchmark-mode-validation` matches `specs/030-benchmark-mode-validation/` |
| A2 | Executive Summary explains what, why, and scope | PASS | §1 covers deferred items resolved, what the feature does, references |
| A3 | Clarifications section present (or marked "none needed") | PASS | §2 documents 3 design decisions from the spec session |
| A4 | User Scenarios cover all three D-items | PASS | US-1 (D-75), US-2/US-3 (D-76), US-4 (D-77) |
| A5 | Functional Requirements are numbered, testable, and cite sources | PASS | FR-1–FR-7, each with testable description and source citation |
| A6 | Success Criteria are measurable with verification method | PASS | SC-1–SC-9, each with target and verification step |
| A7 | Key Entities identified | PASS | §6 lists VALID_MODES, Orphan Mode, Baseline, Test Suite |
| A8 | Dependencies table present | PASS | §7 lists 10 dependencies with types and notes |
| A9 | Assumptions documented | PASS | §8 lists 6 assumptions |
| A10 | Risks enumerated with mitigations | PASS | §9 lists 6 risks with mitigations |
| A11 | Constitution Check present | PASS | §10 covers all 5 principles |
| A12 | Next Steps section present | PASS | §11 lists 7 steps in order |

## B. Content Quality (Zero-Assumption Rules)

| # | Check | Result | Notes |
|---|-------|--------|-------|
| B1 | Every requirement cites [P-N], [PR-N], [S-N], [T-N], [CON-N], [G-N], [RG-N], or plain-English blueprint reference | PASS | FRs cite [D-75], [D-76], [D-77] and plain-English equivalents for the product modes capability, the Batch 2 product modes delivery, multi-mode accuracy constraint, regression detection constraint, product modes constraint |
| B2 | Every design decision cites a constraint (compliance with §6 implications, expressed in plain English) | PASS | FR-3 (product modes constraint), FR-4 (multi-mode accuracy, regression detection), FR-5 (product modes, regression detection), FR-7 (multi-mode accuracy) |
| B3 | Every metric cites a paper or standard | PASS | Metrics table in §5 cites [P-7] for CUAD/MAUD/ContractNLI; standard ML metrics (F1, recall, precision) are universally defined |
| B4 | Every dependency table entry cites a capability reference (expressed in plain English) | PASS | §7 uses "Internal" type with reference to the component's origin spec; external datasets cite [P-7] |
| B5 | No scope creep — only D-75, D-76, D-77 are addressed | PASS | All FRs map to exactly one of D-75, D-76, D-77. FR-7 (report coverage) is a natural extension of D-76 for traceability |
| B6 | No NEEDS CLARIFICATION markers remain | PASS | All 3 design questions resolved in §2 with documented decisions |

## C. Blueprint Confidentiality Compliance

| # | Check | Result | Notes |
|---|-------|--------|-------|
| C1 | No C- codes (raw) — only approved plain-English replacements | PASS | Uses "the 22 product modes capability" not "C-26" |
| C2 | No NX- codes | PASS | NX codes never referenced |
| C3 | No standalone TRL — only "technology readiness level" in full | PASS | Not used in spec (all internal deps already production-stable) |
| C4 | No standalone § — only descriptive section references | PASS | Uses "the product modes constraint" not "§6.x" |
| C5 | No standalone R- — only descriptive risk references | PASS | Risks numbered spec-internally (R-1 through R-6) |
| C6 | No standalone Q- codes | PASS | Q codes never referenced |
| C7 | No T- followed by digit (except 3-digit task IDs and paper refs) | PASS | [P-7] used for paper reference (7 is a single digit, allowed as paper ref) |
| C8 | D-N codes used only as internal deferred-item references | PASS | D-75, D-76, D-77 used as source references for FRs |
| C9 | FR/SC/AC/US codes used only as spec-internal refs | PASS | FR-1–FR-7, SC-1–SC-9, US-1–US-4 defined in spec |
| C10 | PR-N used only as source list ref | PASS | Not used (all references either D-N or plain-English) |

## D. Ponytail (Simplicity) Compliance

| # | Check | Result | Notes |
|---|-------|--------|-------|
| D1 | Hard-coded frozenset chosen over registry pattern | PASS | Explicitly decided in §2, documented with `ponytail:` comment mandate in FR-1 |
| D2 | Dead parameter removed rather than kept "for future" | PASS | FR-3 mandates removal (Option A), with deprecation shim only if external callers exist |
| D3 | Mock baseline kept simple (constant predictions) | PASS | FR-4 uses existing `_mock_pipeline` as-is |
| D4 | Real baseline manual-only (not automated in CI) | PASS | FR-5 explicitly excludes CI automation |
| D5 | E2E tests follow existing pattern, no new test framework | PASS | FR-6 follows pattern from `test_benchmark_cuad.py`, uses stdlib `pytest` + `monkeypatch` |
| D6 | No speculative work beyond D-items | PASS | All FRs trace to D-75, D-76, or D-77 |

## E. Testability

| # | Check | Result | Notes |
|---|-------|--------|-------|
| E1 | Each FR is testable (clear pass/fail condition) | PASS | FR-1: grep VALID_MODES set; FR-2: CLI error output; FR-3: signature change; FR-4: result count; FR-5: JSON output; FR-6: pytest assertions; FR-7: report inspection |
| E2 | Each SC has a concrete verification step | PASS | SC-1: CLI invocation; SC-2: CLI invocation; SC-3: git grep; SC-4: count results; SC-5: pydantic validate; SC-6: pytest; SC-7: assertion; SC-8: report inspect; SC-9: manual regression |
| E3 | Tests do not require network (mock/fixture based) | PASS | FR-6 uses monkeypatched gateway. FR-4 uses mock pipeline. FR-5 is explicitly manual. |

## Summary

| Section | PASS | FAIL | N/A |
|---------|------|------|-----|
| A. Structure & Completeness | 12/12 | 0 | 0 |
| B. Content Quality | 6/6 | 0 | 0 |
| C. Blueprint Confidentiality | 10/10 | 0 | 0 |
| D. Ponytail Simplicity | 6/6 | 0 | 0 |
| E. Testability | 3/3 | 0 | 0 |
| **Total** | **37/37** | **0** | **0** |

**Result**: ✅ PASS — 37/37 checks pass. Spec is ready for `/speckit.plan`.
