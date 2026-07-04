# Feature Specification: Citation Grounding Discriminator

**Feature Branch**: `feat/citation-grounding`

**Created**: 2026-07-03

**Status**: Draft

**Input**: User description: "Citation grounding discriminator — post-hoc checker (per the Citation Grounding paper's CG-DPO design) for contract-clause grounding. Configurable strict/lenient modes. Citation provenance per claim. Integration with single-party review output. 98.5% discrimination accuracy target."

**Design context**: post-hoc CG-DPO discriminator (98.5% discrimination accuracy target, adapted from the Citation Grounding paper for contract clauses).

---

## User Scenarios & Testing

### User Story 1 — Reviewer validates review output with strict grounding (Priority: P1)

A legal professional runs a single-party review on an NDA, gets back a `ReviewReport` with clause assessments, and wants to ensure every assessment claim is actually grounded in the source document before relying on it. They run the citation grounding discriminator in strict mode. Ungrounded claims are surfaced and excluded from the final output; only claims with verified provenance survive.

**Why this priority**: Strict mode is the default safety mechanism. Without it, the discriminator does not prevent ungrounded outputs from reaching the user — the core liability mitigation is not in place. This is the primary value of the feature.

**Independent Test**: Can be fully tested by feeding a `ReviewReport` with deliberately ungrounded claims and verifying that they are excluded from output.

**Acceptance Scenarios**:

1. **Given** a `ReviewReport` containing 10 clause assessments, **When** citation grounding runs in strict mode, **Then** each surviving claim has a recorded `clause_id` and `paragraph_index` that exists in the source document.
2. **Given** a `ReviewReport` where 2 of 10 claims cite a non-existent clause, **When** citation grounding runs in strict mode, **Then** the output contains 8 claims and the 2 ungrounded claims are suppressed with a warning.
3. **Given** a `ReviewReport` where all 10 claims are correctly grounded, **When** citation grounding runs in strict mode, **Then** all 10 claims pass through unchanged.

---

### User Story 2 — Reviewer flags ungrounded claims without suppressing them (Priority: P1)

A legal professional wants to see which claims lack grounding but does not want to automatically exclude them — they may still have value as discussion points. They run in lenient mode. All claims are returned, but each carries a grounded/ungrounded flag, and ungrounded claims are visibly marked.

**Why this priority**: Lenient mode is the alternative pathway mandated by the dual-mode (strict/lenient) discriminator requirement. It matches the real-world workflow where a reviewer wants full visibility before making exclusion decisions. Both modes must ship together for the feature to be complete. Tied with P1 because the post-hoc citation-grounding discriminator design explicitly requires both.

**Independent Test**: Can be fully tested by feeding a `ReviewReport` with deliberately ungrounded claims and verifying all claims are returned with correct grounding flags.

**Acceptance Scenarios**:

1. **Given** a `ReviewReport` with 10 clause assessments, **When** citation grounding runs in lenient mode, **Then** all 10 claims are present in the output.
2. **Given** a `ReviewReport` where 2 of 10 claims cite a non-existent clause, **When** citation grounding runs in lenient mode, **Then** the 2 ungrounded claims carry a flag/marker but are not removed.
3. **Given** a `ReviewReport` where all 10 claims are correctly grounded, **When** citation grounding runs in lenient mode, **Then** all 10 claims are marked grounded.

---

### User Story 3 — Compliance officer audits citation provenance for individual claims (Priority: P2)

A compliance officer needs to verify that a specific clause assessment (e.g., the assessment of the confidentiality clause) is properly grounded. They inspect the citation provenance for a single claim and see the exact `clause_id` and `paragraph_index` it references, plus the discriminator's confidence in that grounding.

**Why this priority**: The benchmark-with-audit-log requirement and the every-claim-cites-its-source requirement together drive this story. This story is P2 because it builds on top of grounding rather than being the grounding itself — strict mode is the prerequisite.

**Independent Test**: Can be fully tested by running the discriminator on a known report and verifying per-claim provenance fields are populated and correct.

**Acceptance Scenarios**:

1. **Given** a completed citation grounding run, **When** a user inspects the provenance of a single claim, **Then** they see `clause_id`, `paragraph_index`, and a `grounding_confidence` score.
2. **Given** a completed citation grounding run, **When** a user inspects the audit log, **Then** every discrimination decision is recorded with claim text, verdict, and timestamp.
3. **Given** a completed citation grounding run, **When** a claim was marked ungrounded, **Then** the audit log records the reason (e.g., "paragraph index 12 does not exist in clause 4.3").

---

### User Story 4 — Developer validates discriminator accuracy against benchmark (Priority: P3)

A developer runs the discriminator against the Citation Grounding paper's baseline methodology (CG-DPO achieves 98.5% discrimination accuracy on a 1,000+ claim corpus) — a seeded corpus of contract clauses with known grounded/ungrounded claims using adapted corruption strategies (clause_swap, category_swap, hallucination, anachronism). The system reports discrimination accuracy, precision, and recall against ground truth.

**Why this priority**: Accuracy validation is critical for the 98.5% target but does not deliver user-facing value until the first three stories are implemented. P3 because it is a development/QA tool.

**Independent Test**: Can be fully tested by running the discriminator against the seed corpus and comparing results against known ground truth.

**Acceptance Scenarios**:

1. **Given** a seeded corpus of 1,000 contract claims with known grounded/ungrounded labels, **When** the discriminator processes the corpus, **Then** overall accuracy is ≥98.5%.
2. **Given** the seeded corpus, **When** discrimination results are compared against ground truth, **Then** precision and recall are reported as separate metrics.
3. **Given** the seeded corpus with adapted corruption strategies (clause_swap, category_swap, hallucination, anachronism), **When** accuracy is computed per corruption type, **Then** no corruption type falls below 95% accuracy.

---

### Edge Cases

- **Document has no clause structure**: When the source document has no detectable clause IDs, the discriminator must handle gracefully — grounded claims can reference paragraph indices only, with a warning about missing clause structure.
- **Claim text is longer than any single clause**: If a claim spans multiple clauses, behavior is mode-dependent: strict mode flags as uncertain (default ungrounded), lenient mode assigns all matching clause provenances with a warning.
- **Empty claims list**: When the review report has no clause assessments, the discriminator returns an empty result set with no error.
- **Duplicate clause IDs in source**: If the source document has duplicate clause IDs (e.g., two clauses numbered "4.3"), the discriminator must handle by qualifying with document section or flagging as ambiguous.
- **Corrupted or mismatched encoding**: Claims or source text with encoding issues (e.g., mojibake, non-ASCII control characters) must not crash the discriminator — degraded accuracy is acceptable with a logged warning.
- **Tie/uncertainty at threshold**: Claims where the discriminator confidence is exactly at the grounded/ungrounded boundary must default to ungrounded in strict mode and flagged as uncertain in lenient mode (the 98.5% target is a deliberate ceiling, not 100%).
- **Review report with mixed modes**: If the input `ReviewReport` contains assessments from multiple review modes (e.g., precheck and hirecheck), the discriminator must process all assessments uniformly.
- **Zero‑length claims**: A claim that is empty or whitespace-only is treated as trivially ungrounded with a logged warning. (Ponytail: empty claim is a caller bug, guard it once at the discriminator boundary instead of patching every caller.)

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST accept a set of claims with their corresponding source document text and produce a grounded/ungrounded verdict per claim. The mechanism is LLM-based via the AI Gateway, reusing existing chat routing and cost tracking. Multiple claims are batched into a single prompt to mitigate per-claim latency. (Approach per the Citation Grounding paper; near-human discrimination is achievable with RAG-augmented grounding.)
- **FR-002**: System MUST support two modes — strict mode (ungrounded claims are excluded from output) and lenient mode (ungrounded claims are flagged but retained). Multi-provenance behavior is mode-dependent: in strict mode, claims referencing multiple clauses are flagged as uncertain (default ungrounded); in lenient mode, all matching clause provenances are assigned with a warning. (Per the post-hoc-not-prompt-guard design: strict/lenient modes are the chosen discriminator architecture.)
- **FR-003**: System MUST store citation provenance for every grounded claim, comprising at minimum a `clause_id` and `paragraph_index` that exist in the source document. (Per the post-hoc grounding-discriminator design: provenance is stored at discrimination time, not generation time.)
- **FR-004**: System MUST record every discrimination decision (claim, verdict, confidence, timestamp) in an audit log that can be inspected after the run. (Per the benchmark-with-audit-log requirement.)
- **FR-005**: System MUST compute and report a three-component CG metric adapted from the Citation Grounding paper methodology: Citation Precision (CP), Citation Relevance (CR), and Citation Locality (CL).
  - **CP** (Citation Precision): percentage of grounded claims whose `clause_id` exists in the source document.
  - **CR** (Citation Relevance): percentage of grounded claims whose claim text appears within the cited clause's content.
  - **CL** (Citation Locality): average paragraph-index delta between the claim's logical position and the cited clause's position.
  - All three metrics are deterministic (no LLM required) and cheap to compute.
- **FR-006**: System MUST integrate with the existing single-party review output (`ReviewReport` / `ClauseAssessment`), adding grounding information to each assessment. The discriminator augments the existing QA `citation_valid` check: claims where QA already flagged `citation_valid=false` are skipped (already known ungrounded) and do not receive discriminator processing. (Per the 3-agent pipeline and the post-hoc-not-prompt-guard design decision.)
- **FR-007**: System MUST implement the discriminator as a post-hoc module that runs on already-generated review output, not as a prompt prefix or generation constraint. (The post-hoc design is the chosen discriminator architecture; prompt-side constraints are not used.)
- **FR-008**: System MUST adapt the four Citation Grounding paper corruption strategies from court citations to contract clauses: clause_swap, category_swap, hallucination, and anachronism.
- **FR-009**: System MUST achieve a per-corpus discrimination accuracy of ≥98.5% when measured against a seeded corpus with known ground-truth labels using the adapted corruption strategies. (Per the Citation Grounding paper's reported CG-DPO accuracy, adapted from court citations to contract clauses.)
- **FR-010**: System MUST handle edge cases (empty claims, duplicate clause IDs, no clause structure, zero-length claims, encoding errors) without crashing; degraded accuracy or warnings are acceptable.

### Key Entities

- **CitationProvenance**: A record linking a single claim to a specific location in the source document. Attributes: `clause_id` (string identifier of the clause), `paragraph_index` (integer position within the clause). A single claim may have zero provenances (ungrounded), one provenance (grounded to one clause), or multiple provenances (claim spans multiple clauses). Enables the three deterministic CG metrics: CP (clause_id existence check), CR (text overlap check), CL (position delta).
- **GroundingVerdict**: An enumeration with three values: `grounded` (provenance verified), `ungrounded` (no valid provenance), `uncertain` (provenance ambiguous or below confidence threshold).
- **CGReport**: The aggregate output of a discriminator run. Contains per-claim verdicts with provenances, the mode used (strict/lenient), the three CG metrics (CP, CR, CL), and overall accuracy against any available ground truth.
- **DiscriminationAuditEntry**: A single audit record for one discrimination decision. Attributes: claim text (or hash), verdict, confidence score, provenance (if any), timestamp, and reason (if ungrounded or uncertain).
- **ClauseAssessment integration**: Three optional fields (default `None`) added to the existing `ClauseAssessment` dataclass: `grounding_verdict: Optional[GroundingVerdict]`, `grounding_provenances: Optional[list[CitationProvenance]]`, `grounding_confidence: Optional[float]`. Backwards-compatible — existing `ClauseAssessment` instances without discriminator data remain valid.

### Integration Points

- **Input**: The discriminator accepts the output of the single-party review pipeline — a `ReviewReport` containing a list of `ClauseAssessment` objects with their `citation` fields.
- **Ordering with QA**: The discriminator runs **after** the QA agent. Claims where QA's `citation_valid=false` are skipped (the discriminator does not re-process them). This avoids redundant LLM calls and respects the existing QA verdict.
- **Output**: The discriminator produces a `CGReport` that can be merged back into the `ReviewReport` or appended as a separate artifact. Existing `ClauseAssessment` fields (`citation`, `confidence`, `qa_verdict`) are read during processing but not mutated — grounding information is stored on new fields or a companion structure.
- **Reporting**: The report formatter (from spec 011, `src/openreview_cli/review/report.py`) must be extended to display grounding verdicts and citation provenance in the terminal table and JSON output.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: The discriminator achieves ≥98.5% discrimination accuracy across a seeded corpus of at least 1,000 contract-clause claims using the four adapted corruption strategies (clause_swap, category_swap, hallucination, anachronism). Accuracy is measured as (correct grounded + correct ungrounded) / total claims. (Per the Citation Grounding paper's reported CG-DPO accuracy.)
- **SC-002**: Every grounded claim in the output carries a `clause_id` and `paragraph_index` that, when checked against the source document, exist. Zero false provenances (a claim citing a non-existent clause or paragraph) in a 500-claim audit sample. (Per the every-claim-cites-its-source requirement.)
- **SC-003**: In strict mode, ≥95% of claims identified as ungrounded by manual review are excluded from the output. Measured by running strict mode on a corpus where a domain expert has independently flagged ungrounded claims. (Per the liability-mitigation requirement.)
- **SC-004**: In lenient mode, 100% of claims in the input are present in the output. All ungrounded claims carry a visible flag distinguish them from grounded claims. (Per the strict/lenient dual-mode discriminator design.)
- **SC-005**: The audit log, when inspected after a run, contains one entry per claim with verdict, confidence, timestamp, and reason. Zero entries missing for non-trivial claims.
- **SC-006**: A `ReviewReport` passed through the discriminator in either mode produces output that can be serialized (JSON/terminal table) without errors, with grounding information included. (Per the 3-agent pipeline integration.)
- **SC-007**: The discriminator, when given a `ReviewReport` with 100 clause assessments, completes processing in under 60 seconds on the reference target machine (8 GB RAM, 2-core CPU, no GPU). This assumes gateway batching of multiple claims per LLM call — higher batch sizes reduce per-claim latency. Performance degrades gracefully (no crash) if the target machine is below spec. [§Constraints — hardware budget]
- **SC-008**: No corruption type (clause_swap, category_swap, hallucination, anachronism) causes accuracy to fall below 95% when measured independently. (Per the Citation Grounding paper's per-corruption-type accuracy.)

---

## Assumptions

- **Contract clause domain adaptation is feasible**: The Citation Grounding paper methodology (developed for court citations) can be adapted to contract clauses with no loss of accuracy. The four corruption strategies map cleanly: clause_swap (wrong clause ID), category_swap (wrong playbook category), hallucination (no support in any clause), anachronism (clause ordering or version mismatch). If this assumption fails, the 98.5% accuracy target may need revision, and new corruption strategies may be required.
- **Ground truth corpus is buildable**: A seeded corpus of ≥1,000 contract-clause claims with known grounded/ungrounded labels can be constructed for validation. The corpus requires domain-expert annotation or synthetic generation using the four corruption strategies. If corpus construction proves impractical, accuracy validation falls back to statistical sampling against a smaller expert-annotated set.
- **Post-hoc is sufficient**: The post-hoc discriminator design is adequate for achieving 98.5% discrimination accuracy. Since the discriminator operates on output text alone via the AI Gateway's chat interface (no access to generation internals needed), the post-hoc approach is well-matched to the architecture. Accuracy depends on the gateway LLM's capability, not on access to model internals.
- **Hardware budget applies to discriminator**: The discriminator processing must stay within the 100 MB peak memory budget (ex-model). The Citation Grounding paper's reference implementation uses a 7B-parameter fine-tuned model (~14 GB), which exceeds this budget by two orders of magnitude. The LLM-based Gateway approach resolves this tension: the Gateway runs the LLM externally (no local model loaded), so the discriminator's memory overhead is limited to prompt construction and response parsing — well within 100 MB. Accuracy depends on the gateway LLM's capability, not on model size loaded locally.
- **Existing review pipeline unchanged**: The discriminator reads from but does not mutate the existing `ReviewReport` / `ClauseAssessment` schema. Grounding data is added as new fields or a companion structure. This avoids breaking changes to the spec-011 pipeline. If schema mutation becomes necessary, it requires a coordinated change across spec 011 and 012.
- **Single-party review only (v1)**: The discriminator integrates with the single-party review output (spec 011). Multi-party review (future spec) and other product modes will need separate integration work.
- **Audit log is local-file based**: The audit log is written to a local file or appended to the existing report output. No audit server, no remote logging. Matches the local-first, CLI-only principle (Constitution §II).
- **Gateway LLM is sufficient for grounding discrimination**: The general-purpose LLM available through the AI Gateway (e.g., GPT-4o, Claude 3.5 Sonnet) is capable of discriminating grounded from ungrounded claims in contract clauses without fine-tuning or a dedicated model. If this assumption fails (accuracy below 98.5%), the resolution path is to improve prompt engineering, increase few-shot examples, or evaluate alternative gateway models — not to deploy a local fine-tuned model.

---

## Open Questions

The following questions are resolved by informed assumption (recorded above). They are documented here so that if implementation reveals the assumption was wrong, the resolution path is clear:

1. **Hardware vs accuracy tension**: The Citation Grounding paper achieves 98.5% with a 7B LoRA model (~14 GB). The constitution mandates <100 MB peak (ex-model). The LLM-based Gateway approach resolves this tension by running the discriminator through an external LLM, keeping local memory overhead to prompt construction and response parsing. If the Gateway LLM cannot reach 98.5%, resolution path: improve prompt engineering, increase few-shot examples, switch gateway model, or accept a documented lower ceiling.
2. **Corpus construction**: If building a 1,000+ claim ground-truth corpus proves too expensive or time-consuming, fall back to a smaller (200-claim) expert-annotated corpus with synthetic augmentation. The 98.5% accuracy target is then a target against the augmented corpus, not the raw expert set.
3. **Integration depth**: The discriminator does not need access to model internals — it operates on the output text alone via the AI Gateway chat interface. If the Gateway LLM cannot reach 98.5% without logprobs or attention patterns, resolution path: extend the gateway to expose per-token logprobs for extraction calls, or accept a documented lower accuracy ceiling.

---

## Clarifications

### Session 2026-07-03

The following five clarification answers were integrated into the spec after the initial draft:

1. **Discriminator implementation approach → B (LLM-based via Gateway)** — The discriminator uses the AI Gateway to prompt per claim ("Does the clause text support this assessment?"). Zero new dependencies; reuses existing gateway routing/cost tracking. Fits within the 100 MB budget (no new model loaded locally). Batching multiple claims in a single prompt mitigates per-claim latency.

2. **Relationship to QA `citation_valid` → B (Augment)** — QA `citation_valid` is the first-pass filter during generation. The discriminator only runs on claims that passed QA (adds provenance depth). If QA already flagged `citation_valid=false`, the discriminator skips that claim (already known ungrounded).

3. **Schema attachment → A (New fields on ClauseAssessment)** — Three optional fields (default `None`) added to `ClauseAssessment`: `grounding_verdict: Optional[GroundingVerdict]`, `provenance: Optional[list[CitationProvenance]]`, `grounding_confidence: Optional[float]`. Backwards-compatible, single model file change.

4. **CG metric definition → A (Structural mapping)** — CP = % of citations with valid `clause_id` in source; CR = % where the claim text appears in the cited clause; CL = average paragraph-index delta between claim and citation. All three are deterministic, cheap, and sufficient for v1.

5. **Multi-provenance rule → C (Mode-dependent)** — Strict mode: multi-clause claims are flagged uncertain (default ungrounded). Lenient mode: assign all matching clause provenances with a warning.
