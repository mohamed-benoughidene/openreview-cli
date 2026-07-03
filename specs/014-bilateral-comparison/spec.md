# NX-1: Bilateral Comparison (Experimental) — Two-Party Contract Comparison for PreCheck

**Feature ID**: 014-bilateral-comparison
**Status**: Draft Specification — EXPERIMENTAL
**Created**: 2026-07-03
**Pilot Mode**: PreCheck (NDA)
**Accuracy Target**: ≥70% initial (aspirational ≥95%)
**Blueprint References**: [P-4], [P-13], [P-14], §4 (C-12, C-20, C-22), §6.4, §6.7, §8 (R-1, R-6, R-7, R-11), §9 (R-1, R-11), §10 (Q-1, Q-4, Q-5, Q-6), §11 (Speckit Seed)

---

## 1. Executive Summary

Single-party review (spec 011) answers: *"Does this clause favour me?"* Bilateral comparison answers: *"Where do my counterparty and I disagree?"* Given two versions of the same contract — one from each negotiating party — the tool identifies clause-by-clause divergences, highlights the delta, and classifies each divergence using the RCBSF 5-dimension risk taxonomy (Category, Location, Evidence, Issue, Suggestion). The output is a paired, side-by-side view with per-divergence confidence scores and a three-color (Green/Amber/Red) overall health indicator.

**This is an experimental feature.** The academic literature establishes a hard ceiling on automated contract comparison: best binary discrepancy F1 ≤ 64% (P-4), and no published study validates bilateral contract comparison at all (§6.7). NX-1 ships as opt-in, labelled EXPERIMENTAL, with explicit accuracy caveats, an Amber escape hatch for uncertain comparisons, and a mandatory disclaimer against using results as legal advice.

Pilot scope: PreCheck (NDA) only [Q-4]. Single documents only (no amendments) [Q-5]. Users compare two NDAs — Party A's version and Party B's version — and receive a divergence report showing where the counterparty's position differs from the standard (never "sign this") [Q-6].

### 1.1 What Bilateral Comparison Gives the User That Single-Party Does Not

| Capability | Single-Party (spec 011) | Bilateral (NX-1) |
|---|---|---|
| Risk to me | ✅ Per-clause position (favourable/neutral/unfavourable) | ✅ Same, plus... |
| Risk to me vs. counterparty | ❌ Not available | ✅ Side-by-side divergence per clause |
| Negotiation leverage | ❌ Not available | ✅ "Party B changed X" — surface counterparty deviations |
| Divergence taxonomy | ❌ Not available | ✅ RCBSF 5-dimension classification per delta |
| Counterparty strategy signal | ❌ Not available | ✅ Pattern analysis across all divergences (e.g., Party B systematically shortens confidentiality terms) |
| Paired confidence | ❌ Not available | ✅ Per-divergence confidence + per-clause paired color |

Blueprint references: [P-14] (RCBSF taxonomy), §6.7 (comparison is unsolved), §10 Q-1 (accuracy bar)

---

## 2. User Scenarios

### Scenario 1: Two-NDA Divergence Report (Pilot)

A legal professional at a startup receives an NDA from a potential partner. Before sending it to legal, they run:

```
openreview precheck compare my-nda.pdf their-nda.pdf
```

The tool parses both documents, aligns clauses by heading (e.g., both versions have a "Confidentiality" clause), runs the single-party extraction + QA pipeline on each aligned pair, then runs the comparison agent to detect and classify divergences. The output is a paired summary:

- Every matched clause pair shown side-by-side with the position for Party A, the position for Party B, and the divergence classification (if any).
- Each divergence tagged with one of the RCBSF 5 risk dimensions: **Category** mismatch (wrong clause type), **Location** mismatch (different sub-clause), **Evidence** mismatch (different basis/standard), **Issue** mismatch (different risk assessment), or **Suggestion** mismatch (different remedy).
- A per-divergence confidence score and a per-clause-pair three-color indicator (Green = no material divergence, Amber = uncertain / low confidence, Red = material divergence found).
- A mandatory disclaimer printed at the top of the output: "EXPERIMENTAL — comparison accuracy has known limitations. Do not rely on this tool for legal advice."
- A roll-up showing the number of divergences, the distribution across RCBSF dimensions, and the overall agreement rate.

Blueprint references: §10 Q-4 (PreCheck pilot), §10 Q-6 (no "sign this"), §9 R-1 (accuracy caveats)

### Scenario 2: Drilling into a Specific Divergence

A senior attorney sees a Red (material divergence) flag on the "Confidentiality Term" clause pair and wants the details. They re-run with verbosity:

```
openreview precheck compare my-nda.pdf their-nda.pdf --verbose
```

The expanded output shows for every divergence: the exact clause text from both sides, the RCBSF dimension and sub-type, the extraction positions for each party (favourable/neutral/unfavourable), the comparison agent's rationale for flagging a divergence, the confidence score for the divergence detection, and — if the comparison agent was uncertain — the specific reason (e.g., "heading match but semantic similarity below threshold; manual review recommended").

Blueprint references: §9 R-11 (comparison uncertainty as warning category), §8 R-6 (confidence scores)

### Scenario 3: Conservative Mode for Risk-Averse Review

A general counsel wants maximum sensitivity — they'd rather have false positives than miss a divergence. They run:

```
openreview precheck compare my-nda.pdf their-nda.pdf --confidence-threshold 0.8
```

More comparisons are flagged as divergences (including low-confidence ones), more clauses appear Amber, and fewer material divergences are missed. The user sacrifices precision for recall and manually reviews the additional flags. The output includes a prominent caveat: "Confidence threshold set to 0.8 — output includes low-confidence comparisons. Expect higher divergence count; manually verify each."

Blueprint references: §8 R-6 (generous Amber threshold), §6.4 (three-color accuracy mitigation)

### Scenario 4: Exporting a Comparison Report for Downstream Review

A legal operations team wants to feed comparison results into a contract management system or a negotiation tracker. They run:

```
openreview precheck compare my-nda.pdf their-nda.pdf --format json --output comparison.json
```

The tool writes a structured JSON report containing:
- Document metadata (filenames, page counts, parse timestamps for both)
- Clause alignment table: clause ID, heading, Party A position, Party B position, divergence classification (or "no divergence"), confidence, color
- Per-divergence detail: RCBSF dimension, Party A text excerpt, Party B text excerpt, comparison agent rationale, confidence
- Summary roll-up: total matched clauses, total divergences, divergence distribution by RCBSF dimension, overall agreement rate
- Experimental disclaimer as a top-level field
- Schema version for downstream compatibility

Blueprint references: §8 R-6 (confidence + three-color), §10 Q-1 (citation grounding)

### Scenario 5: Alignment-Only Mode

A user wants to preview how the two documents map to each other before running the full comparison pipeline:

```
openreview precheck compare my-nda.pdf their-nda.pdf --align-only
```

The tool parses both documents, runs clause alignment (heading-based fast-path), and outputs an alignment table showing which clauses map to which and which clauses are unique to each document (unmatched from Party A or Party B). No extraction, QA, or comparison is performed. This lets the user verify the alignment before committing to the full (costly) inference pipeline.

---

## 3. Functional Requirements

### FR-1: Clause Alignment Engine

The system MUST align clauses across two documents so that corresponding clauses can be compared pairwise.

- The alignment engine SHALL accept two parsed document structures (each a list of clauses with headings, text, and hierarchical position) as output by `stream_clauses()`.
- The primary alignment method SHALL be heading-based exact matching first, then heading-based similarity (fuzzy matching for minor wording differences like "Confidentiality" vs "Confidentiality Obligations"), then structural position fallback (clause N in document A aligns to clause N in document B when headings do not match).
- Unmatched clauses (present in one document but not the other) SHALL be reported as "Party A only" or "Party B only" with no comparison performed.
- The alignment engine SHALL output an alignment table: one entry per matched or unmatched clause, with the clause ID, heading, and document-side marker.
- The alignment engine SHALL be stateless — no persistent alignment cache. Each comparison invocation re-runs alignment from scratch.

Blueprint references: §6.7 (comparison is unsolved, every design choice is provisional), §10 Q-5 (single document only — no amendments)

### FR-2: Bilateral Assessment Model — Paired Assessments with Divergence

The system MUST produce a paired assessment for each aligned clause.

- Each paired assessment SHALL contain: (a) the single-party ClauseAssessment for Party A's version, (b) the single-party ClauseAssessment for Party B's version, (c) a divergence classification (one of the RCBSF 5 dimensions, or "no divergence"), (d) a per-pair confidence score (0.0–1.0) for the divergence detection, and (e) a paired three-color status.
- The single-party assessments SHALL reuse the spec 011 extraction + QA pipeline. No modification to the single-party pipeline is required — the bilateral layer wraps it.
- A paired assessment SHALL exist for every aligned clause pair. Unmatched clauses SHALL have a single-party assessment only, marked with the document-side marker.
- The paired assessment SHALL be the atomic unit of the comparison output. All downstream reporting and filtering operates on paired assessments.

### FR-3: Comparison Agent — RCBSF 5-Dimension Divergence Detection

The comparison agent SHALL detect and classify divergences between aligned clause pairs using the RCBSF 5-dimension risk taxonomy.

| Dimension | What It Detects | Example (NDA) |
|---|---|---|
| **Category** | The clause types differ between parties | Party A has "Confidentiality" clause; Party B has "Non-Disclosure" clause with different scope |
| **Location** | The same concept appears in different sub-clauses | Party A puts "exclusions" in §2.3; Party B puts them in §4.1 |
| **Evidence** | The evidentiary basis or legal standard differs | Party A uses "reasonable efforts"; Party B uses "best efforts" |
| **Issue** | The risk assessment differs between parties | Party A's position is favourable (one-sided obligation); Party B's position is unfavourable (mutual with exceptions) |
| **Suggestion** | The proposed remedy or action differs | Party A says "confidentiality survives 2 years"; Party B says "confidentiality survives 5 years" |

The comparison agent SHALL:

- Receive both clause texts plus both single-party assessments (position, confidence, citation, QA verdict) — [C-20, C-22]
- Output a divergence dimension or "no divergence"
- Output a confidence score (0.0–1.0) for the divergence classification
- Cite the exact text from both sides supporting the divergence detection — [Q-6]
- Mark the comparison as uncertain (Amber) when divergence detection confidence is below the user-configurable threshold — [FR-014 from spec 013]

The comparison agent SHALL reuse the extraction agent's model slot. No `--comparison-model` flag is provided. This decision may be revisited if users report systematic misclassifications where a larger model would improve accuracy.

The comparison agent SHALL NOT output "sign this" or "reject this" language. Output MUST always be descriptive: "differs from counterparty's standard" [Q-6].

**Known ceiling**: Binary discrepancy detection is bounded at ≤64% F1 (P-4, §6.4). The comparison agent MUST NOT claim higher accuracy. All output is provisional and labelled EXPERIMENTAL.

Blueprint references: [P-14] (RCBSF 5-dimension taxonomy), [P-4] (§6.4 binary discrepancy F1 ≤64%), §8 R-11 (comparison uncertainty), §9 R-1 (accuracy caveats)

### FR-4: Paired Three-Color Status

Each clause pair SHALL display a three-color status computed from the paired assessment:

| Color | Meaning | Trigger |
|---|---|---|
| **Green** | No material divergence | No divergence detected AND both single-party assessments have confidence ≥ threshold AND no Amber trigger on either side |
| **Amber** | Uncertain — manual review recommended | Divergence detection confidence < threshold, OR QA disagreement on either side, OR extraction confidence < threshold on either side |
| **Red** | Material divergence found | Divergence detected with confidence ≥ threshold AND no Amber trigger on either side |

The three-color computation SHALL be a pure deterministic mapping at output time (no re-run of extraction, QA, or comparison) [spec 013 FR-007]. The default confidence threshold for bilateral comparisons SHALL be 0.7 (generous, per §6.4 "set Amber threshold generously").

The Amber threshold SHALL be set more generously for bilateral comparison than for single-party review, because bilateral divergence detection is harder and less validated §6.4. The minimum Amber escape hatch SHALL be wider: any paired divergence with confidence < 0.7 is Amber (vs. < 0.5 which triggers Amber in single-party).

Blueprint references: §6.4 (three-color accuracy mitigation, binary discrepancy F1 ≤64%), §8 R-6 (generous Amber threshold), §9 R-1 (accuracy ceiling)

### FR-5: Experimental Disclaimer and Accuracy Caveats

Every comparison output — terminal and JSON — MUST include:

1. **EXPERIMENTAL badge** at the top of every output: "NX-1 BILATERAL COMPARISON — EXPERIMENTAL FEATURE"
2. **Accuracy caveat**: "Comparison accuracy has known limitations (best binary discrepancy F1 ≤64% per published research). Do not rely on this tool for legal advice. All comparisons are provisional and should be reviewed by a qualified legal professional."
3. **Per-output confidence disclosure**: The confidence threshold used and the number/percentage of Amber (uncertain) comparisons
4. **Never "sign this"** : Output language MUST always be descriptive, never prescriptive. Use "differs from counterparty's standard" instead of "Party B is wrong" [Q-6]

The disclaimer SHALL be printed to stderr on every run, not hidden behind `--verbose`.

Blueprint references: §9 R-1 (accuracy risk, HIGH/HIGH), §9 R-11 (multi-party semantics never validated), §6.4 (binary discrepancy F1 ≤64%), §10 Q-6 (never "sign this")

### FR-6: Paired Report Formatter — Side-by-Side Terminal and JSON Output

The system SHALL produce two output formats for the comparison report:

1. **Terminal report** (default):
   - Mandatory experimental disclaimer and accuracy caveat at top
   - Per-clause-pair summary: heading, Party A position, Party B position, divergence (binary: "Divergence" / "No divergence" by default), confidence, three-color status
   - Full RCBSF 5-dimension classification for each divergence shown only under `--verbose`
   - `alignment_quality` (0.0–1.0) shown per pair only under `--verbose`
   - Unmatched clauses listed separately with their side marker
   - Roll-up summary: total matched pairs, unmatched by side, divergences by RCBSF dimension (detailed under `--verbose`), overall agreement rate, Amber rate
   - Three-color visual styling (Green/Amber/Red badges in Status column) [spec 013 FR-005]

2. **JSON report** (`--format json`):
   - All terminal report information as structured JSON
   - Schema version field for downstream compatibility
   - Per-divergence detail: RCBSF dimension with rationale, paired citation excerpts, confidence, color, alignment_quality
   - `alignment_quality` always included per pair in JSON output
   - Full RCBSF 5-dimension taxonomy always present in the data model and JSON output, regardless of terminal display mode
   - Experimental disclaimer as a top-level field
   - The JSON schema SHALL be versioned and documented

### FR-7: `--align-only` Mode

The system SHALL support a `--align-only` flag that:
- Runs parsing and clause alignment on both documents
- Outputs the alignment table showing matched and unmatched clauses
- Skips all extraction, QA, and comparison inference
- Completes in under 5 seconds for typical 50-page NDAs (no model inference)
- Accepts `--format json` for machine-readable alignment output

This mode is useful for previewing alignment quality before committing to the full inference pipeline. Because clause alignment is the weakest link in the comparison chain (P-4 reports citation matching at <14% F1), allowing users to inspect alignment quality directly builds trust and avoids wasted inference cost on misaligned clauses.

Blueprint references: §6.4 (binary discrepancy F1 ≤64%), [P-4] (citation matching <14% F1)

### FR-8: Confidence Threshold on Comparison

The system SHALL accept a `--confidence-threshold` flag (float 0.0–1.0, default 0.7) on the `compare` subcommand that controls the Amber boundary for divergence detection confidence. This is independent of the single-party `--confidence-threshold` (spec 013 FR-003) — the comparison threshold SHALL default to 0.7 for bilateral mode because divergence detection is provably harder than single-party assessment (§6.4).

The system SHALL also accept a `--conservative` convenience flag that sets `--confidence-threshold 0.8` for maximum sensitivity (favours recall over precision). The `--conservative` flag SHALL be mutually exclusive with an explicit `--confidence-threshold` — using both SHALL produce an error (exit code 3).

The user-facing help text for this flag SHALL include the accuracy ceiling disclosure: "Note: Bilateral comparison accuracy is bounded at approximately 64% F1 per published research (P-4). Set this threshold generously to push uncertain comparisons to Amber rather than risking false Green or Red."

Blueprint references: §8 R-6 (generous Amber threshold), §6.4 (binary discrepancy F1 ≤64%), §9 R-1 (accuracy caveats — Amber escape hatch)

### FR-9: Opt-In Experimental Activation

The `compare` subcommand SHALL be opt-in — it MUST NOT run as part of `openreview precheck review` or any non-comparison workflow. Users explicitly invoke it via:

```
openreview precheck compare <docA> <docB>
```

The first run of `compare` on any machine SHALL print a one-time warning:

```
⚠ NX-1 Bilateral Comparison is EXPERIMENTAL.
Comparison accuracy has known limitations.
Review all results manually before relying on them.
See https://github.com/mohamed-benoughidene/openreview-specs/014 for details.
```

This warning SHALL NOT be suppressible. It reminds users on every first invocation per machine that the feature is research-grade.

Blueprint references: §8 R-7 (bilateral is opt-in experimental), §9 R-11 (never validated — experimental), §10 Q-4 (PreCheck pilot only)

### FR-10: Integration with Existing Infrastructure

The bilateral comparison SHALL reuse these existing components without modification:

| Component | Integration Point | Built In |
|---|---|---|
| `stream_clauses()` | Input — both documents parsed through the same pipeline | Phase 2, C-08 |
| Single-party extraction + QA pipeline | Per-party assessment (reused as-is from spec 011) | C-20, C-22, spec 011 |
| AI Gateway | Per-task model routing for extraction, QA, and comparison agents | C-12–C-18, Phase 4 |
| Three-color confidence (spec 013) | Per-pair color computation using the same framework | spec 013 FR-001–FR-007 |
| Prompt management | Comparison agent prompts managed via spec 009 prompt registry | N-1, spec 009 |
| PII stripping | Active before any inference call upstream of comparison | Phase 3 |
| Bundled NDA playbook | Single-party assessments on each side use the existing playbook | C-22, spec 011 |

The system SHALL NOT modify any of these components. Integration is via public APIs only.

### Processing Model

The comparison pipeline SHALL process both documents sequentially, not in parallel:

1. Document A is fully parsed → extraction → QA, then all Document A inference state is released.
2. Document B is fully parsed → extraction → QA, then all Document B inference state is released.
3. Clause alignment is performed on the two parsed clause structures.
4. The comparison agent runs on each aligned pair to detect and classify divergences.

This constraint keeps peak model-inference memory within the hardware budget by never holding both documents' inference results simultaneously.

---

## 4. Success Criteria

| Criterion | Target | Verifiable By |
|---|---|---|
| Per-clause divergence detection accuracy vs. expert-labelled NDA pair corpus | ≥70% F1 (initial), ≥95% (aspirational) | Benchmark run against seeded NDA pair corpus — [R-1], [Q-1] |
| Comparison Amber rate on clearly identical clause pairs | ≤15% false divergence flags | Expert-labelled matched-subset — [§6.4] |
| Comparison misses truly divergent clause pairs | ≤20% false negative rate on expert-identified divergences | Expert-labelled divergent-subset — [§6.4] |
| Clause alignment accuracy (heading-based fast path) | ≥90% correct alignment | Manual review of 50 random NDA document pairs |
| Per-pair processing time (all-local SLM) | <10 seconds per clause pair (P95) | Timed run on reference machine |
| Peak memory during comparison pipeline | <100 MB (ex-model, per the hardware budget) | `test_memory` profile |
| Alignment-only mode completes | Under 5 seconds for two 50-page NDAs | Timed run |
| Experimental disclaimer printed | On every `compare` invocation first time | Automated acceptance test |
| Users can override confidence threshold | Different threshold produces different Amber rate | Acceptance test with threshold=0.9 vs 0.3 |
| RCBSF dimension classification accuracy | ≥60% correct dimension assignment (initial) | Expert-labelled NDA pair subset |
| Terminal divergence display | Binary (divergence/no-divergence) by default; full RCBSF taxonomy under `--verbose` | Automated output acceptance test |
| Offline mode works end-to-end | All-local SLM slots produce same output format | Full run with all slots set to local models |

All success criteria are technology-agnostic by design.

Blueprint references: [R-1] (≥70% initial, ≥95% aspirational), §6.4 (binary discrepancy F1 ≤64% ceiling), §8 R-6 (confidence + Amber), §9 R-1 (accuracy caveats — Amber escape hatch)

---

## 5. Key Entities

### PairedAssessment
The outcome of comparing one aligned clause pair across both documents.

| Field | Type | Description |
|---|---|---|
| pair_id | string | Unique identifier for this clause pair |
| clause_heading | string | The shared clause heading (or best-match heading) |
| party_a_assessment | ClauseAssessment | Single-party assessment for Party A's version [spec 011] |
| party_b_assessment | ClauseAssessment | Single-party assessment for Party B's version [spec 011] |
| divergence | string enum | RCBSF dimension: category, location, evidence, issue, suggestion, or "no_divergence" |
<!-- divergence_dimension removed: redundant with `divergence` field which already encodes the RCBSF dimension or no_divergence -->
| confidence | float | 0.0–1.0 confidence score for the divergence detection |
| alignment_quality | float | 0.0–1.0 match score for the clause alignment (1.0 = exact heading match, lower = fuzzy/structural fallback); shown in JSON by default and in terminal under `--verbose` |
| color | string enum | green, amber, red (paired three-color status) |
| citations | string[] | Excerpts from both sides supporting the divergence detection |
| rationale | string | Comparison agent's reasoning for the divergence classification |
| is_amber | boolean | Derived: true if color == amber |

### AlignmentTable
The output of clause alignment before full comparison.

| Field | Type | Description |
|---|---|---|
| pairs | AlignmentPair[] | Array of matched or unmatched clause pairs |
| unmatched_a | string[] | Clause IDs present in Document A only |
| unmatched_b | string[] | Clause IDs present in Document B only |
| total_a | int | Total clauses in Document A |
| total_b | int | Total clauses in Document B |
| alignment_rate | float | Percentage of clauses successfully aligned |

### ComparisonReport
The top-level output of a bilateral comparison run.

| Field | Type | Description |
|---|---|---|
| experimental | boolean | Always true — marks output as experimental |
| disclaimer | string | Accuracy caveat and legal disclaimer text |
| document_a | DocMeta | Document A metadata (filename, page count, timestamp) |
| document_b | DocMeta | Document B metadata |
| alignment | AlignmentTable | Clause alignment results |
| assessments | PairedAssessment[] | Per-pair comparison results |
| summary | ComparisonSummary | Aggregate statistics |
| schema_version | string | Output schema version |

### ComparisonSummary
Aggregate statistics for a comparison run.

| Field | Type | Description |
|---|---|---|
| total_pairs | int | Number of aligned clause pairs |
| divergences | int | Number of pairs with a detected divergence |
| divergences_by_dimension | map[string, int] | Count per RCBSF dimension |
| unmatched_a | int | Clauses in Party A's document only |
| unmatched_b | int | Clauses in Party B's document only |
| agreement_rate | float | Percentage of pairs with no divergence = green_count / total_pairs |
| green_count | int | Pairs with Green (no material divergence) status |
| amber_count | int | Pairs with Amber (uncertain) status |
| red_count | int | Pairs with Red (material divergence) status |
| overall_color | string enum | green, amber, red — worst-clause-wins: Red if any pair is Red, Amber if any pair is Amber, else Green |
| avg_alignment_quality | float | Average alignment_quality across all matched pairs (0.0–1.0) |
| confidence_threshold | float | The threshold used for this run |

---

## 6. Assumptions

1. **Heading-based alignment is sufficient for NDA review**: NDA clauses have consistent headings across most commercial NDAs. Heading-based exact and fuzzy matching will achieve ≥90% alignment accuracy. Documents with heavily customised heading structures will have lower alignment quality, flagged as Amber. This assumption is provisional — alignment quality MUST be measured in the benchmark (§4 success criteria).

2. **Comparison agent runs after single-party pipeline**: The comparison agent consumes already-extracted single-party assessments. It does not re-extract. This means the comparison pipeline is extraction + QA on both documents (sequential or parallel), then alignment, then comparison. Total inference cost is approximately 2× single-party plus the comparison agent pass.

3. **RCBSF taxonomy is the right lens for divergence classification**: The 5-dimension taxonomy from P-14 is used as-is for bilateral divergence detection. This is an assumption because RCBSF was designed for risk-resolution in single-document review, not for cross-document divergence. If initial accuracy (≥60% dimension classification) is not met, a simplified binary (divergence / no divergence) output becomes the fallback.

4. **Amber threshold is wider than single-party**: Because bilateral divergence detection is harder (§6.4, P-4 F1 ≤64%), the default confidence threshold for comparison is 0.7 (generous) and the default for single-party remains 0.5 (spec 013 default). Users can override both independently.

5. **No clause-level cache**: Each `compare` invocation re-runs parsing, alignment, extraction, QA, and comparison. No caching layer. This is acceptable for typical document counts (<20 pairs/day). A cache can be added if batch sizes grow.

6. **Single-document format only**: Each party provides exactly one document. No amendments, no exhibits, no multi-file submissions. The system parses the first page to the last page of each document as a single contract [Q-5].

7. **PII stripping is upstream**: Both documents are PII-stripped before any inference. The comparison agent never sees raw PII from either party.

8. **Symmetrical comparison**: Party A and Party B are symmetric in the comparison — neither side is treated as the "standard." The output shows deltas symmetrically. If the user wants to compare against a specific standard (e.g., "my company's template"), they provide that document as one of the two inputs.

---

## 7. Dependencies

| Dependency | Type | Notes |
|---|---|---|
| Single-party review pipeline (spec 011) | Runtime | Extraction + QA for each side |
| Three-color confidence (spec 013) | Runtime | Color computation framework |
| AI Gateway (C-12–C-18) | Runtime | Model routing for all three agents |
| Prompt Registry (N-1) | Runtime | Comparison agent prompts via spec 009 |
| stream_clauses() (C-08) | Runtime | Clause input for both documents |
| Bundled NDA playbook | Content | Single-party assessments on each side |
| Clause alignment logic | New component | Heading-based exact + fuzzy matching |
| Comparison agent prompt set | New content | RCBSF 5-dimension divergence detection prompt |
| YAML parsing | Runtime | `pyyaml` for playbook loading (already a dep) |

---

## 8. Edge Cases / Failure Handling

### Document Parse Failure

If either document fails to parse (corrupt PDF, unsupported format, password-protected file, or any other parse error), the comparison SHALL fail-fast:

- Print the filename of the failed document and the specific parse error reason to stderr.
- Exit with exit code 1.
- Produce no partial output — no alignment table, no comparison report, no cached state.

Partial comparison is misleading when one document cannot be parsed. The tool SHALL NOT produce any output if either input is invalid.

---

## 9. Out of Scope (Explicit)

The following are explicitly deferred to later phases or separate features:

- **Non-NDA contract types**: NX-1 pilots with PreCheck (NDA) only. HireCheck, DealCheck, and other modes are separate features [Q-4].
- **Amendments and exhibits**: Both parties provide a single document. Multi-file submissions (contract + amendments + exhibit A) are deferred [Q-5].
- **Multi-party comparison (3+ parties)**: NX-1 compares exactly two parties. Three-way alignment is a future research problem.
- **Redlining / tracked changes comparison**: The tool compares final texts, not change marks. Track-changes analysis is a separate feature.
- **Automated pass/fail on entire contract**: The tool never says "sign this" or "reject this." Output is per-clause and descriptive [Q-6].
- **Negotiation recommendation engine**: The tool does not suggest negotiating positions or counter-offers. It only flags where and how the documents diverge.
- **Web UI / dashboard**: This is a CLI tool per Principle II. No web interface for comparison results.
- **Amendment-aware versioning**: Comparing v1.2 of Party A's document against v3.1 of Party B's document as distinct versions is deferred. Each comparison is a fresh alignment of whatever texts are provided.
- **Opt-in anonymized data collection (`--share-data`)**: Deferred to a future spec pending constitutional amendment to Principles I/II. Not included in NX-1 scope.
- **Bilateral PAKTON adaptation**: The PAKTON 3-agent architecture (P-13) is single-party. Adapting it for bilateral comparison (e.g., a 2-position playbook with a cycle) is deferred research. NX-1 uses a simple 2-pass single-party + comparison agent pipeline.

Blueprint references: §8 R-7 (bilateral is opt-in experimental), §10 Q-4 (PreCheck pilot), §10 Q-5 (single documents only), §10 Q-6 (never "sign this")

---

## 10. Research Limitations and Risks

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| R-1: Comparison accuracy ≤64% F1 ceiling (P-4) | HIGH | HIGH | Amber escape hatch, experimental disclaimer, user-configurable threshold, ≥70% aspirational not guaranteed |
| R-11: Multi-party semantics never validated in literature | HIGH | MEDIUM | Experimental badge, opt-in only, per-output caveats, research data collection |
| Clause alignment fails for non-standard headings | MEDIUM | MEDIUM | Alignment quality metric exposed in output, `--align-only` preview mode, manual alignment as escape hatch |
| RCBSF taxonomy not suited for bilateral divergence | MEDIUM | MEDIUM | Binary fallback if dimension accuracy <60%, dimension visible in JSON for research |
| Citation grounding <14% F1 (P-4) affects trust | LOW | HIGH | All comparisons cite exact text, but citation match quality is disclosed as experimental |
| Users treat output as legal advice | HIGH | MEDIUM | Non-suppressible disclaimer on every run, never "sign this" language, stderr warning |

Blueprint references: §9 R-1 (accuracy HIGH/HIGH), §9 R-11 (semantics MEDIUM/CRITICAL), [P-4] (binary discrepancy F1 ≤64%, citation matching <14% F1)

---

## 11. Relationship to Existing Specifications

| Spec | Relationship |
|---|---|
| **011** (Single-Party Review) | NX-1 wraps and extends the single-party pipeline. Single-party assessments are reused as-is; the comparison agent is added as a new stage. The no-op comparison agent from spec 011 FR-4 is replaced with a real implementation. |
| **013** (Three-Color Confidence) | NX-1 inherits the full three-color framework. The comparison adds paired color computation and its own `--confidence-threshold` (default 0.7). Single-party thresholds remain per spec 013 defaults. |
| **012** (Citation Grounding) | NX-1 cites divergence detections to exact text from both parties. The grounding discriminator from spec 012 applies to each single-party assessment independently. |
| **009** (Prompt Management) | The comparison agent requires new prompts for RCBSF dimension classification. These are added to the prompt registry following spec 009 conventions. |
| **010** (Benchmark Harness) | The bilateral benchmark requires a new dataset: NDA pairs with expert-labelled divergences. The benchmark harness from spec 010 is extended with a bilateral mode. |

---

## 12. Open Data Collection (Research) — DEFERRED

**DEFERRED**: `--share-data` is deferred to a future spec pending constitutional amendment to Principles I/II. Not included in NX-1 scope.

Because bilateral contract comparison is an unsolved research problem (§6.7), NX-1 SHALL include an opt-in anonymized data collection mechanism:

- Users MAY opt-in via a `--share-data` flag to share anonymized comparison results (clause texts, divergence classifications, confidence scores) for research purposes.
- Opt-in SHALL be explicitly requested after the first `compare` run (not before). The prompt SHALL explain what is collected and that no PII or raw document text is included.
- Collected data SHALL be anonymized: no filenames, no timestamps, no IP addresses, no user identifiers.
- Only divergence classifications and stripped clause texts (PII already removed) SHALL be shared.
- The purpose is to build a corpus of bilateral NDA comparisons for improving future accuracy.
- Opt-in SHALL be revocable at any time.

Blueprint references: §11 (Speckit Seed — "Data collection: opt-in anonymized accuracy data"), §6.7 (no paper studies bilateral contract comparison)

---

## Clarifications

### Session 2026-07-03

The following clarifications were accepted and applied to the spec above:

- **Q1: Document parse failure handling** — Fail-fast. Print which document failed and why. Exit code 1. No partial output. (Applied to new §8 Edge Cases / Failure Handling.)
- **Q2: Sequential vs parallel processing** — Sequential. Process Document A fully (parse → extract → QA), release memory, then Document B fully, then align + compare. (Applied to new Processing Model subsection under §3.)
- **Q3 (NC-1): Comparison model routing** — Reuse extraction agent's model slot. No `--comparison-model` flag. Revisit only if users report systematic misclassifications. (Applied to FR-3 Comparison Agent.)
- **Q4 (NC-2): Alignment quality disclosure** — Add `alignment_quality` (0.0–1.0) metadata field on PairedAssessment. Show in JSON by default, terminal only under `--verbose`. (Applied to §5 Key Entities and FR-6 Output Format.)
- **Q5 (NC-3): RCBSF dimension accuracy fallback** — Binary divergence/no-divergence in terminal output. Full 5-dimension RCBSF taxonomy always in data model and JSON output, visible in terminal under `--verbose`. (Applied to §4 Success Criteria and FR-6 Output Format.)
