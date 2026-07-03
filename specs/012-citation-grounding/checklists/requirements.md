# N-5 Citation Grounding Discriminator — Quality Checklist

## Structural Completeness

- [x] spec.md exists at `specs/012-citation-grounding/spec.md`
- [x] Directory structure: `specs/012-citation-grounding/checklists/` exists
- [x] Feature branch named per convention (`feat/citation-grounding`)
- [x] Date and status fields populated
- [x] Blueprint citations cross-referenced (C-21, P-6, T-7, §6.3, §8/R-5, R-2, R-9, Q-1, Q-6)
- [x] No audience references in spec text (Constitution §Audience rule)
- [x] No implementation details (languages, frameworks, APIs, libraries) in spec.md
- [x] All [NEEDS CLARIFICATION] markers resolved (zero remain)
- [x] Clarifications section added with Session 2026-07-03 covering 5 Q&A items
- [x] Feature description from blueprint §11 seed is accurately reflected

## User Stories

- [x] User stories are prioritized (P1, P2, P3)
- [x] Each story is independently testable
- [x] Each story has acceptance scenarios in Given/When/Then format
- [x] Stories cover strict mode (P1), lenient mode (P1), provenance audit (P2), and accuracy validation (P3)
- [x] Edge cases documented (no clause structure, empty claims, duplicate IDs, encoding, threshold ties, mixed modes, zero-length claims)

## Functional Requirements

- [x] FR-001: Accept claims + source text → per-claim verdict via AI Gateway with batching [P-6][T-7]
- [x] FR-002: Strict mode and lenient mode with mode-dependent multi-provenance [§6.3]
- [x] FR-003: Citation provenance (clause_id, paragraph_index) [Q-6][§6.3]
- [x] FR-004: Audit log per discrimination decision [R-9]
- [x] FR-005: Three-component CG metric (CP, CR, CL) with deterministic definitions [P-6]
- [x] FR-006: Integration with single-party review output, augments QA citation_valid [C-21][§8/R-5]
- [x] FR-007: Post-hoc design, not prompt prefix [§6.3][§8/R-5]
- [x] FR-008: Adapted corruption strategies: clause_swap, category_swap, hallucination, anachronism [P-6]
- [x] FR-009: ≥98.5% discrimination accuracy [P-6][T-7]
- [x] FR-010: Edge case handling without crash [R-9]

## Key Entities

- [x] CitationProvenance defined (clause_id, paragraph_index, enables CP/CR/CL metrics)
- [x] GroundingVerdict defined (grounded, ungrounded, uncertain)
- [x] CGReport defined (per-claim verdicts, mode, metrics, accuracy)
- [x] DiscriminationAuditEntry defined (claim, verdict, confidence, timestamp, reason)
- [x] ClauseAssessment integration defined (grounding_verdict, provenance, grounding_confidence as optional fields)
- [x] Integration points documented (ReviewReport input, CGReport output, QA ordering, report formatter extension)

## Success Criteria

- [x] SC-001: ≥98.5% accuracy on 1,000+ claim corpus [P-6]
- [x] SC-002: Every grounded claim has valid clause_id + paragraph_index
- [x] SC-003: Strict mode excludes ≥95% of ungrounded claims [R-2]
- [x] SC-004: Lenient mode retains 100% of claims with flags [§6.3]
- [x] SC-005: Audit log complete (one entry per claim) [R-9]
- [x] SC-006: Serialization works with grounding information [C-21]
- [x] SC-007: 100 claims processed in under 60 seconds on reference machine (assumes gateway batching)
- [x] SC-008: No corruption type below 95% accuracy [P-6]
- [x] All success criteria are measurable without implementation knowledge
- [x] All success criteria are technology-agnostic

## Assumptions

- [x] Contract clause domain adaptation is feasible
- [x] Ground truth corpus is buildable
- [x] Post-hoc is sufficient for 98.5% (no model internals needed)
- [x] Hardware budget applies to discriminator (resolved via Gateway — no local model loaded)
- [x] Existing review pipeline unchanged
- [x] Single-party review only (v1)
- [x] Audit log is local-file based
- [x] Gateway LLM is sufficient for grounding discrimination (no dedicated model needed)

## Blueprint Traceability

- [x] P-6 (Ovcharov CG-DPO): 98.5% accuracy, corruption strategies, CG metric → FR-001, FR-005, FR-008, FR-009, SC-001, SC-008
- [x] T-7 (Hallucination detection): discriminator interface → FR-001, FR-009
- [x] §6.3 (Architecture): post-hoc, strict/lenient, provenance → FR-002, FR-003, FR-007, SC-004
- [x] §8/R-5 (Revision): post-hoc module → FR-006, FR-007
- [x] R-2 (Liability): CG before every output → SC-003
- [x] R-9 (98.5% ≠ 100%): show citations, audit log → FR-004, FR-010, SC-005
- [x] Q-1 (Trust): source-grounding as baseline → implicit in all stories
- [x] Q-6 (Link): clause ID + paragraph → FR-003, SC-002
- [x] C-21 (Capability): CG capability → FR-006, SC-006

## Constitution Compliance

- [x] Principle I (Privacy First): No PII exposure in discriminator processing. Claims may contain PII placeholders only.
- [x] Principle II (Local-First, CLI-Only): Discriminator is a local post-hoc module, no server component.
- [x] Principle III (Hardware-Bounded): 100 MB peak budget met via Gateway approach (no local model loaded); overhead limited to prompt construction and response parsing.
- [x] Principle IV (Dependency Minimalism): No forbidden dependencies introduced. CG-DPO approach does not require langchain, FAISS, spaCy, or sentence-transformers.
- [x] Principle V (Spec-Driven, YAGNI): This spec defines the minimum viable discriminator. No speculative abstractions.

## Open Questions

- [x] Hardware vs accuracy tension: resolved via Gateway approach (no local model); fallback: improve prompt engineering / switch model
- [x] Corpus construction fallback: smaller corpus + synthetic augmentation
- [x] Integration depth: no model internals needed; fallback: extend gateway logprobs or accept lower ceiling

## File Existence

- [x] `specs/012-citation-grounding/spec.md` — written
- [x] `specs/012-citation-grounding/checklists/requirements.md` — this file
- [x] `.specify/feature.json` — updated with `"specs/012-citation-grounding"`

---

**Checklist prepared**: 2026-07-03
**Status**: All items pass — no violations, no unresolved markers.
