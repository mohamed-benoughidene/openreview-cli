# Specification Analysis Report

**Feature**: 019-error-recovery-framework
**Date**: 2026-07-05
**Artifacts analyzed**: spec.md, plan.md, data-model.md, tasks.md, contracts/ (3 files)

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| ~~C1~~ | Constitution | CRITICAL (RESOLVED) | spec.md:§4 FR-07, data-model.md | FR-07 mandates data preservation but no data-model field tracks "data saved before failure" on RecoveryContext — only `partial_data` exists for failed stages, not saved results from completed stages | ✅ `saved_results: dict[str, Any] | None` added to RecoveryContext in data-model.md |
| ~~F1~~ | Coverage Gap | HIGH (RESOLVED) | spec.md:SC-01, tasks.md:T031 | SC-01 (90% auto-recovery rate) verification is marked "optional stress test" in T031 — a success criterion requiring buildable work should not be optional | ✅ SC-01 verification made mandatory in T031, acceptance criteria enforce 90% threshold |
| ~~F2~~ | Coverage Gap | MEDIUM (RESOLVED) | spec.md:SC-02, plan.md:Phase 2 | SC-02 requires recovery within 30 seconds; backoff formula `base * attempt²` with default base=1.0 gives 1+4+9+16+25=55s total wall time for 5 retries — exceeds 30s budget | ✅ Reduced max_attempts to 4 (1+4+9+16=30s) — fits SC-02 budget. Updated spec.md, data-model.md, tasks.md defaults |
| F3 | Coverage Gap | MEDIUM | spec.md:§5 Non-Goals, tasks.md | Non-goals section mentions "no persistent recovery state across CLI invocations" but no task verifies this invariant | Add a test in T032 or T031 that confirms recovery state is discarded after pipeline completes |
| ~~D1~~ | Data Model | MEDIUM (RESOLVED) | data-model.md:RecoveryContext, contracts:gateway-recovery-contract.md | Data-model defines `user_privacy_tier` as `str` default "maximum"; contract §4 uses `tier == "maximum"` comparison — but no spec FR defines the privacy tier enum or values | ✅ PrivacyTier enum defined (`strict`, `standard`, `none`) in data-model.md. user_privacy_tier uses PrivacyTier type, default `strict`. Contract updated |
| D2 | Data Model | LOW | data-model.md:RecoveryEvent, plan.md:Phase 2 | RecoveryEvent has `outcome` as `str` with values "resolved"/"escalated"/"exhausted"/"degraded" — plan Appendix uses "proceed"/"skip"/"degrade"/"continue_with_partial"/"retry_stage"/"halt" as decision signals | These are different concepts (event outcome vs. coordinator decision) — confirm no confusion in implementation. Consider using an enum for RecoveryEvent.outcome |
| T1 | Task Ordering | LOW | tasks.md:Phase 9, tasks.md:Phase 3-7 | Phase 9 (Config) says "depends on Phase 2, but config loading can be implemented in parallel with Phases 3-7" — yet the dependency table says Phase 9 blocks Phase 10 | Clarify: Phase 9 is a soft dependency for Phase 10 (integration tests may need config), not a hard blocker |
| T2 | Task Coverage | LOW | tasks.md:T029 | T029 adds `recovery` section to config but doesn't specify which existing config file/class to modify | Add target file path (e.g., `src/openreview_cli/config/defaults.yaml` or config dataclass) |
| ~~C2~~ | Contracts | LOW (RESOLVED) | contracts:gateway-recovery-contract.md:§4 | Contract §4 has typo "RetroRetryStrategy" — should be "AutoRetryStrategy" | ✅ Typo fixed: "RetroRetryStrategy" → "AutoRetryStrategy" |

---

## Coverage Summary Table

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-01 (Auto-Retry with Backoff) | ✅ | T013, T014 | Phase 3, fully covered |
| FR-02 (Provider Fallback) | ✅ | T015, T016 | Phase 4, fully covered |
| FR-03 (Graceful Degradation) | ✅ | T017, T018 | Phase 5, fully covered |
| FR-04 (Stage Error Isolation) | ✅ | T019, T020 | Phase 6, fully covered |
| FR-05 (User-Guided Recovery) | ✅ | T021, T022 | Phase 7, fully covered |
| FR-06 (Recovery Visibility) | ✅ | T010, T024, T027 | Phase 2 (progress ext), Phase 8 (coordinator) |
| FR-07 (User Data Preservation) | ✅ | T006, T020, T027 | RecoveryContext.saved_results tracks completed-stage outputs. T020 merges partial data, T027 updates saved_results after each stage. |
| FR-08 (Configurable Thresholds) | ✅ | T028, T029, T030 | Phase 9, fully covered |
| SC-01 (90% Auto-Recovery) | ✅ | T023, T024, T031 | T031 includes mandatory SC-01 verification test (10 scenarios, ≥9 must auto-resolve) |
| SC-02 (Transient Tolerance ≤30s) | ✅ | T013, T014 | max_attempts=4, backoff 1+4+9+16=30s fits budget (see F2 resolved) |
| SC-03 (Memory Pressure) | ✅ | T017, T018, T031 | Covered |
| SC-04 (No Silent Cloud Fallback) | ✅ | T015, T016, T031 | Covered |
| SC-05 (Recovery Visibility) | ✅ | T010, T024, T027, T031 | Covered |
| SC-06 (Stage Failure Isolation) | ✅ | T019, T020, T031 | Covered |
| SC-07 (Actionable Final Errors) | ✅ | T021, T022, T031 | Covered |

---

## Constitution Alignment

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Privacy First | ✅ Pass | Recovery events log only error codes/strategy names. Privacy guard prevents silent cloud fallback (SC-04). |
| II. Local-First, CLI-Only | ✅ Pass | All recovery runs in-process. No server, no daemon. Works fully offline. |
| III. Hardware-Bounded | ✅ Pass | Coordinator is thin (~KB). Reuses existing tracemalloc. Memory budget unchanged. |
| IV. Dependency Minimalism | ✅ Pass | Zero new runtime deps. All stdlib or already-installed. |
| V. Spec-Driven, YAGNI | ✅ Pass | Every strategy maps to a spec FR. No speculative abstractions. |

---

## Unmapped Tasks

None. All 32 tasks map to at least one FR or SC.

---

## Metrics

| Metric | Count |
|--------|-------|
| Total Requirements (FR) | 8 |
| Total Success Criteria (SC) | 7 |
| Total Tasks | 32 |
| Coverage % (FR with ≥1 task) | 100% |
| Coverage % (SC with ≥1 task) | 100% (but 2 have caveats) |
| Ambiguity Count | 0 |
| Duplication Count | 0 |
| Critical Issues | 0 (C1 resolved) |
| High Issues | 0 (F1 resolved) |
| Medium Issues | 1 (F2, D1 resolved; F3 remains) |
| Low Issues | 2 (C2 resolved; T1, T2 remain) |

---

## Next Actions

**All critical and high issues resolved.** Ready for `/speckit.implement`.

**Resolved items**:
1. ✅ **C1** — `saved_results` added to RecoveryContext data model (FR-07)
2. ✅ **F1** — SC-01 verification in T031 made mandatory
3. ✅ **F2** — max_attempts reduced to 4, backoff fits 30s SC-02 budget
4. ✅ **D1** — PrivacyTier enum defined (`strict`, `standard`, `none`)
5. ✅ **C2** — Typo "RetroRetryStrategy" fixed in gateway-recovery-contract.md

---

## Extension Hooks

No `.specify/extensions.yml` found. Skipped silently.
