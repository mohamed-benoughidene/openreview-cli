# Requirements Checklist — Privacy Tier Routing

## 1. Completeness

**Instruction**: Every functional requirement from the spec must have a corresponding checklist item that is testable. Mark each requirement as present (✓), partially covered (~), or missing (✗). Add notes for any gaps.

| # | Requirement | Source (spec §) | Present? | Testable? | Notes |
|---|---|---|---|---|---|
| 1 | Three privacy tiers with defined behavior (Maximum/Balanced/Performance) | §4 (FR-01) | ✓ | ✓ | Enumeration + behavior matrix in spec |
| 2 | Tier enforcement at Gateway call boundary | §4 (FR-02) | ✓ | ✓ | Router intercepts before provider resolution |
| 3 | PII stripping before cloud egress (Balanced/Performance) | §4 (FR-03) | ✓ | ✓ | Verify via mock capture of cloud provider input |
| 4 | Block cloud calls when PII engine unavailable | §4 (FR-04) | ✓ | ✓ | Test broken PII engine + cloud call attempt |
| 5 | Tier configuration in config.yml (privacy.tier key) | §4 (FR-05) | ✓ | ✓ | Read from config; default to maximum |
| 6 | Tier-aware provider selection (local vs cloud) | §4 (FR-06) | ✓ | ✓ | URL-based classification |
| 7 | No silent tier downgrade | §4 (FR-07) | ✓ | ✓ | Error on blocked calls, never auto-downgrade |
| 8 | Tier visibility in output | §4 (FR-08) | ✓ | ✓ | Capture output for each tier |
| 9 | Tier stability within a single operation | §4 (FR-09) | ✓ | ✓ | Change config mid-operation |
| 10 | Maximum tier: zero external network calls | §2 (S1), §6 (SC-01) | ✓ | ✓ | Intercept HTTP requests |
| 11 | Balanced tier: correct routing by model type | §2 (S2), §6 (SC-02) | ✓ | ✓ | Capture per-call provider selection |
| 12 | PII stripping failure: actionable error, no data leak | §2 (S4), §6 (SC-03) | ✓ | ✓ | Error message + no cloud HTTP call |
| 13 | Tier change takes effect on next operation | §2 (S5), §6 (SC-06) | ✓ | ✓ | Mid-operation change test |
| 14 | Missing/invalid tier defaults to Maximum with warning | §6 (SC-07) | ✓ | ✓ | Remove/corrupt config key |

**Completeness score**: 14/14 present, 14/14 testable

---

## 2. Unambiguousness

**Instruction**: Each requirement must have a single, unambiguous interpretation. Flag any requirement that could be read in multiple ways.

| # | Requirement (short) | Issue | Resolution |
|---|---|---|---|
| 1 | . | No ambiguous requirements found | — |
| 2 | . | No ambiguous requirements found | — |
| 3 | "PII stripping before cloud egress" | Could mean "stripped before any cloud call" or "stripped once and cached" | Spec §7 clarifies: caching is a performance optimization, not a correctness requirement. Stripping must have completed before the first cloud call. |
| 4 | . | No ambiguous requirements found | — |
| 5 | . | No ambiguous requirements found | — |
| 6 | "Local vs cloud determination" | Could be based on URL pattern or explicit provider type attribute | Spec §7 and §8 clarify: URL matching is primary; registry `local` flag takes precedence if present. |
| 7 | . | No ambiguous requirements found | — |
| 8 | . | No ambiguous requirements found | — |
| 9 | . | No ambiguous requirements found | — |

**Unambiguousness score**: 0 ambiguous items after resolution

---

## 3. Consistency

**Instruction**: Check that requirements do not contradict each other within this spec, and that they are consistent with existing specs and the product blueprint.

| Conflict check | Result |
|---|---|
| FR-01 (three tiers) vs FR-07 (no downgrade) | Consistent — three tiers exist; router uses the user's chosen tier, never changes it |
| FR-03 (PII before cloud) vs FR-04 (block when unavailable) | Consistent — FR-04 is the enforcement mechanism for FR-03 |
| FR-05 (config.yml) vs FR-09 (per-operation stability) | Consistent — config read at startup; mid-operation changes ignored |
| FR-06 (provider classification) vs spec-005 (Gateway provider registry) | Consistent — adds lightweight classification on top of existing registry |
| FR-08 (tier visibility) vs spec-005 (Gateway output) | Consistent — tier info is additional metadata, does not conflict with Gateway output |
| Maximum tier (all local) vs PII engine dependency | Consistent — Maximum tier does not require PII engine; PII is a local-first operation in the pipeline |
| Balanced tier (local embeddings) vs Performance tier (cloud embeddings) | Consistent — different tiers, different rules |
| This spec vs product blueprint §7 privacy tier routing | Confirm via: same three tiers, same data-flow rules, same enforcement point |

**Consistency score**: No contradictions found

---

## 4. Feasibility

**Instruction**: Assess whether each requirement can be implemented given the project's constraints (Python 3.12, uv, 100 MB budget, no forbidden deps, local CLI).

| # | Requirement | Feasibility | Constraints | Notes |
|---|---|---|---|---|
| 1 | Three privacy tiers | ✅ Feasible | Pure enum + branching logic | No external deps needed |
| 2 | Gateway call interception | ✅ Feasible | Gateway exists (spec-005); router wraps existing `chat()`/`embed()` methods | Needs one wrapper class; no new deps |
| 3 | PII stripping before egress | ✅ Feasible | PII engine exists (spec-003/004) | Call existing `strip()` method; verify completion |
| 4 | Block cloud calls on PII failure | ✅ Feasible | Error handling path | No new deps |
| 5 | Config.yml reading | ✅ Feasible | Config loader exists | Read existing YAML key |
| 6 | Provider classification | ✅ Feasible | URL matching + registry | ~20 lines of logic |
| 7 | No silent downgrade | ✅ Feasible | Design invariant, not a feature | Enforced by architecture |
| 8 | Tier visibility in output | ✅ Feasible | Uses existing Rich/click output | Add banner to existing display |
| 9 | Tier stability per operation | ✅ Feasible | Snapshot config at startup | Config already loaded once per command |
| Memory impact | — | ⬜ Acceptable | ~5-10 KB for TierConfig + routing state | Negligible vs 100 MB budget |
| Dependencies | — | ⬜ No new deps | All capabilities use existing packages | No new `uv add` needed |

**Feasibility score**: All requirements feasible within project constraints

---

## 5. Testability

**Instruction**: Every requirement must have a clear pass/fail test. Mark each requirement's test approach.

| # | Requirement | Test approach | Automated? | Edge cases covered? |
|---|---|---|---|---|
| 1 | Three tiers | Unit: enum values + behavior matrix test | ✓ | Invalid values, default |
| 2 | Gateway enforcement | Unit: mock Gateway, call with each tier | ✓ | No provider matching tier |
| 3 | PII before cloud | Integration: seeded PII doc, capture cloud input | ✓ | No PII in doc, empty doc |
| 4 | Block on PII failure | Integration: broken PII engine, assert no cloud call | ✓ | PII engine partially failed |
| 5 | Config reading | Unit: various config states | ✓ | Missing key, invalid value |
| 6 | Provider classification | Unit: known URLs → expected classification | ✓ | Unix socket, IPv6, proxy URLs |
| 7 | No silent downgrade | Integration: blocked call → error message | ✓ | All error paths |
| 8 | Output visibility | Integration: capture stdout for each tier | ✓ | Empty output, long documents |
| 9 | Tier stability | Integration: change config mid-operation | ✓ | Multiple simultaneous changes |

**Testability score**: All 9 requirement groups testable; test approaches defined

---

## 6. Traceability

**Instruction**: Every requirement must trace back to an explicit source (user story, blueprint section, resolved open question). No orphan requirements.

| # | Requirement | Source |
|---|---|---|
| FR-01 | Three tiers | Product blueprint §7 — privacy tier routing: three-tier design (Maximum/Balanced/Performance) |
| FR-02 | Gateway enforcement | Product blueprint §7 — privacy tier router intercepts before provider call |
| FR-03 | PII before cloud | Product blueprint §7 — PII stripping before external API calls |
| FR-04 | Block on PII failure | Product blueprint architecture principles — fail closed on privacy |
| FR-05 | Config in config.yml | Product blueprint §7 — user-configured privacy tier per environment |
| FR-06 | Provider classification | Product blueprint §7 — Maximum tier requires local-only detection |
| FR-07 | No silent downgrade | Product blueprint resolved open questions: user control over data flow is absolute |
| FR-08 | Output visibility | Product blueprint user-experience transparency requirement |
| FR-09 | Tier stability | Product blueprint risk assessment: runtime switching causes inconsistency |
| Edge case: no config | — | Derived from FR-05 (default to maximum) |
| Edge case: partial PII | — | Derived from FR-03 (PII engine confidence) |
| Scenario 1-5 | User scenarios | Each maps to FR-01 through FR-09 |
| SC-01 through SC-07 | Success criteria | Each maps to one or more FRs |

**Traceability score**: All requirements traceable to explicit sources

---

## 7. Quality Summary

| Criterion | Score | Threshold | Pass? |
|---|---|---|---|
| Completeness | 14/14 present | 13/14 | ✅ |
| Unambiguousness | 0 ambiguous | < 2 | ✅ |
| Consistency | No contradictions | 0 contradictions | ✅ |
| Feasibility | All feasible | All feasible | ✅ |
| Testability | 9/9 groups testable | 8/9 | ✅ |
| Traceability | All traced | All traced | ✅ |

**Overall**: ✅ **PASS** — all quality criteria met.

---

## 8. Resolved Clarifications

The following items were surfaced during the Stage 2 clarification scan and resolved against the spec. Each maps to a `CL-0N` entry in `spec.md §10 Clarifications`.

| ID | Finding | Resolution | Spec Impact |
|----|---------|------------|-------------|
| CL-01 | 8GB hardware and Maximum tier — no graceful degradation path | Let Ollama handle OOM naturally; no hardware detection in router | §7 Assumptions updated |
| CL-02 | Gateway bypass for Maximum tier — routing overhead concern | Always route through Gateway; bypass adds complexity without measurable benefit | §7 Assumptions updated |
| CL-03 | Model type detection — mechanism to distinguish embedding vs. LLM calls | Wrap individual Gateway methods (`chat()`, `embed()`) per type | §7 Assumptions updated |
| CL-04 | Accuracy threshold — lawyers' trust threshold not quantified | Deferred to user research / future product spec | §5 Non-Goals updated |
| CL-05 | Tier change detection — mechanism for "changed since last operation" notice | Drop change-diff from MVP; always display current tier | §5 Non-Goals updated |

**Status**: 5 clarifications resolved. 0 pending.

---

## 9. Validation Checklist (per spec-template)

- [x] Spec title matches feature ID and directory name
- [x] Executive summary explains what problem this solves
- [x] User scenarios are concrete, prioritized, with acceptance criteria
- [x] Dependencies are listed with versions/relationships
- [x] Functional requirements are complete and testable
- [x] Non-goals are explicit
- [x] Success criteria are measurable and technology-agnostic
- [x] Assumptions are documented
- [x] Key entities are named and described
- [x] No blueprint codes (C-10, §6.1, R-10, Q-3 etc.) in public spec text
- [x] Plain-English source names used in traceability
- [x] Requirements checklists exist and validate against spec
- [x] Edge cases covered
- [x] Uses "must" / "must not" / "should" consistently (RFC 2119 style)
