# Single-Party Review — PAKTON 3-Agent Pipeline for Legal Contract Review

**Feature ID**: 011-single-party-review
**Status**: Draft Specification
**Created**: 2026-07-02

## 1. Executive Summary

Single-party review brings contract analysis to the CLI: a user uploads a contract and receives a structured, per-clause assessment scored against a 3-position playbook — favorable, neutral, or unfavorable for the reviewing party. Three agents work in sequence — extraction, QA verification, and a placeholder for future bilateral comparison — to produce citation-grounded, uncertainty-aware output.

This feature operationalises the PAKTON architecture [§6.7] for the PreCheck product mode [Q-4] as the pilot. The extraction agent matches clauses against a bundled 3-position playbook (C-22) using minimal hierarchical retrieval (C-19). The QA agent verifies every extraction. The comparison agent is a no-op in single-party mode — a structural placeholder for Phase 2 bilateral review.

Pilot scope: NDA review via `openreview precheck review` [Q-4]. Minimum 70% accuracy bar at initial release [Q-1]. Every claim cites its source clause [Q-6]. No clause defaults to "sign this" or "reject this" — uncertain assessments are surfaced as Amber [Q-6].

Blueprint references: [CON-4], [P-13], §6.7, §6.1, §6.5, Q-1, Q-4, Q-6, Q-7

## 2. User Scenarios

### Scenario 1: Single-Document NDA Review

A user receives an NDA and wants to know: which clauses favour me, which don't, and which need a lawyer's eye? They run:

```
openreview precheck review nda.docx
```

The tool parses the document, streams clauses through the extraction agent against the bundled NDA playbook, runs QA verification on each result, and produces a structured report. The report lists every clause, its position (favorable / neutral / unfavorable / uncertain), a confidence score for the assessment, and a direct citation to the source clause text. Clauses where the extraction agent and QA agent disagree are flagged as uncertain (Amber).

### Scenario 2: Custom Playbook Override

A user whose organisation has negotiated specific NDA terms wants to review against their own playbook instead of the bundled default:

```
openreview precheck review nda.docx --playbook my-terms.yaml
```

The tool loads the user's playbook, matches clauses against it, and produces the same structured report using the custom position definitions. This enables law firms and legal departments to encode institutional preferences.

### Scenario 3: Offline Review with Local SLMs

A user on a plane or in a secure facility has no internet access. They have configured local SLM model slots (Ollama). The command runs identically — no cloud call is made, no PII leaves the machine. The review completes using only local inference [§6.1].

### Scenario 4: Export Structured Results for Downstream Tools

A legal operations team wants to feed review results into a contract management system. They run:

```
openreview precheck review nda.docx --format json
```

The tool writes a structured JSON report to stdout (or a file via `--output report.json`) containing per-clause positions, confidence scores, citations, and the QA verification verdict. The JSON schema is stable for downstream automation.

### Scenario 5: Batch Review of Multiple NDAs

A legal department receives 50 NDAs in a single day. They run:

```
openreview precheck review *.docx
```

The tool processes each document sequentially, producing individual reports and a summary roll-up showing aggregate risk posture across the batch. Memory stays under the hardware budget because each document is processed, then released.

## 3. Functional Requirements

### FR-1: Extraction Agent — Clause Extraction with Playbook Matching

The extraction agent MUST, for each clause in a parsed document:

- Receive the clause text as output by `stream_clauses()` [C-08]
- Determine which playbook entry (if any) the clause maps to using minimal hierarchical retrieval (C-19)
- Assign one of four positions: favorable, neutral, unfavorable, or no-match
- Produce a confidence score (0.0–1.0) for the position assignment
- Cite the exact source clause text supporting the assessment

The extraction agent SHALL route each clause through a configurable model slot in the AI Gateway [C-12–C-18]. Per Q-7, model routing is at the task level (extraction), not per document type.

The extraction agent MUST handle clauses that don't match any playbook entry gracefully — they are reported as "no-match" with no position guess.

The extraction agent MUST NOT output "sign this" or "reject this" language. Uncertain assessments default to Amber [Q-6].

Blueprint references: [P-13], §6.7, C-19, C-22, Q-6, Q-7

### FR-2: 3-Position Playbook System (C-22)

Each product mode SHALL ship with a bundled playbook defining the 3-position taxonomy for that mode's contract type:

| Position | Meaning | Example (NDA context) |
|----------|---------|----------------------|
| Favorable | Benefits the reviewing party | One-sided confidentiality obligation on discloser only |
| Neutral | Standard market language, no material advantage | Mutual confidentiality with standard exceptions |
| Unfavorable | Harms the reviewing party's position | Indefinite confidentiality term, no termination |
| No-match | Clause doesn't correspond to any playbook entry | Recitals, definitions, boilerplate jurisdiction |

Playbooks SHALL be authored in YAML and stored under the mode's configuration directory. Users MAY override the bundled playbook with `--playbook <path>`.

Each playbook entry MUST include:
- A unique identifier
- The clause category (e.g., "confidentiality-term", "non-solicitation")
- Description of the clause in plain English (for model grounding)
- Exemplar language patterns per position (for retrieval matching)
- The default position for clauses that match the category but lack specific indicators

Blueprint references: [C-22], §6.5

### FR-3: QA Agent — Position Verification

The QA agent SHALL run after every extraction and verify:

- Does the assigned position match the clause text?
- Does the extracted playbook category match the clause?
- Is the confidence score appropriate for the clause's ambiguity level?

The QA agent SHALL receive: (a) the original clause text, (b) the extraction agent's output (position + confidence + citations), and (c) the relevant playbook entry. It SHALL output:

- A verification verdict: agree, disagree, or uncertain
- A revised position if it disagrees with the extraction agent (with supporting rationale)
- A flag: if QA disagrees with extraction, the final assessment to the user is uncertain (Amber)

The QA agent MAY be routed to a different (e.g., more accurate, larger) model slot than the extraction agent, enabling the accuracy-vs-speed trade-off: extraction runs a fast SLM, QA runs a slower but more reliable model.

Blueprint references: §6.7, Q-6

### FR-4: Comparison Agent — Structural Placeholder

The comparison agent SHALL exist as a structural placeholder in the pipeline. In single-party mode, it SHALL be a no-op — the extraction and QA results are passed through to the output formatter unchanged.

When Phase 2 (bilateral comparison) lands, the comparison agent will compare the reviewing party's position assessment against the counterparty's position (extracted from the same clause) and flag divergences.

Blueprint references: §6.7, Phase 2

### FR-5: Structured Output

The tool SHALL produce two output formats:

1. **Terminal report** (default): A summary table of all clauses with position, confidence, and citation. Clauses flagged as uncertain (Amber) are highlighted. A roll-up summary shows position distribution.

2. **JSON report** (`--format json`): A machine-readable JSON object containing:
   - Document metadata (filename, page count, parse timestamp)
   - Per-clause array: clause text, position, confidence, citation, QA verdict, Amber flag
   - Summary statistics: count per position, overall uncertainty rate

The JSON schema SHALL be versioned and documented for downstream consumers.

Blueprint references: [P-13], §6.5

### FR-6: Integration with Existing Infrastructure

The feature SHALL reuse these existing components without modification:

| Component | Integration Point | Built In |
|-----------|-------------------|----------|
| `stream_clauses()` | Input — clauses flow from parser through clause detector | C-08, Phase 2 |
| RCTS chunking | Clause text is the chunk unit; no sub-clause chunking needed | C-32, Spec 007 |
| AI Gateway | Per-task model routing for extraction and QA agents | C-12–C-18, Phase 4 |
| Prompt management | Extraction and QA prompts managed via spec 009 prompt registry | N-1, Spec 009 |
| PII stripping | Active before any cloud API call per Principle I | Phase 3 |

The feature does NOT modify any of these components. Integration is via public APIs only.

### FR-7: Task-Level Model Routing (Q-7)

The extraction agent and QA agent SHALL be independently routable to different model slots:

```
openreview precheck review nda.docx \
  --extraction-model fast-slm \
  --qa-model accurate-cloud
```

If `--qa-model` is not specified, the QA agent SHALL use the same model slot as the extraction agent. If no model slot flags are given, the gateway's default routing applies.

This enables the SLM-first architecture [§6.1]: users start with local SLMs for everything and selectively route QA to cloud models when higher accuracy is needed.

Blueprint references: [Q-7], §6.1

### FR-8: Memory and Performance Budget

The feature SHALL stay within the project's hardware budget:

- Peak memory: <100 MB (NLP model exempt per Principle III)
- Per-document processing: 50-page NDA in under 30 seconds (all-local SLMs)
- Streaming: clauses are processed one at a time — no in-memory accumulation of all clauses before processing

Processing is async and concurrent across clauses where model slot supports it. The CLI shows live progress per clause [Principle III].

## 4. Success Criteria

| Criterion | Target | Verifiable By |
|-----------|--------|---------------|
| Position accuracy vs. expert-labelled NDA corpus | ≥70% F1 (extraction + QA combined) | Benchmark run against seeded NDA corpus |
| QA agent catches extraction errors | ≥80% of extraction errors flagged | Manual review of 100 random clauses |
| Amber flag rate on clear clauses | ≤10% of clauses that experts agree on | Expert-labelled subset |
| Per-clause processing time (all-local SLM) | <5 seconds per clause (P95) | Timed run on reference machine |
| Peak memory during batch review | <100 MB (ex-model) | `test_memory` profile |
| Offline mode works end-to-end | All-local SLM slots produce same output format | Full run with all slots set to local models |
| Users can override playbook | Any YAML playbook loads and produces valid reports | Acceptance test with custom playbook |

Criteria are technology-agnostic by design — they don't reference models, frameworks, or programming languages.

Blueprint references: [Q-1] (70% accuracy bar), §6.6 (performance)

## 5. Key Entities

### ClauseAssessment
The outcome of running a single clause through the extraction + QA pipeline.

| Field | Type | Description |
|-------|------|-------------|
| clause_id | string | Unique clause identifier from stream_clauses() |
| clause_text | string | The clause text (truncated in terminal output) |
| playbook_category | string | Matching playbook entry ID, or "no-match" |
| position | enum | favorable, neutral, unfavorable, uncertain |
| confidence | float | 0.0–1.0 (extraction agent's confidence) |
| citations | string[] | Source clause excerpts supporting the assessment |
| qa_verdict | enum | agree, disagree, uncertain |
| is_amber | boolean | True if QA disagreed or extraction confidence was low |

### Playbook
A collection of clause categories with position definitions.

| Field | Type | Description |
|-------|------|-------------|
| id | string | Playbook identifier (e.g., "precheck-nda-v1") |
| mode | string | Product mode this playbook is for (e.g., "precheck") |
| categories | Category[] | Array of clause category entries |
| metadata | object | Version, description, author |

### Category
A single clause category within a playbook.

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique category ID |
| name | string | Human-readable category name |
| description | string | Plain English description of the clause type |
| favorable | PositionDef | Definition and exemplars for favorable position |
| neutral | PositionDef | Definition and exemplars for neutral position |
| unfavorable | PositionDef | Definition and exemplars for unfavorable position |
| default_position | enum | Default position when no specific indicators found |

### ReviewReport
The top-level output of a review run.

| Field | Type | Description |
|-------|------|-------------|
| document | DocMeta | Document filename, page count, timestamp |
| assessments | ClauseAssessment[] | Per-clause assessments |
| summary | ReviewSummary | Aggregate statistics |
| amber_count | int | Number of clauses flagged uncertain |
| schema_version | string | Output schema version for downstream compatibility |

## 6. Assumptions

1. **Playbook format**: Playbooks are YAML files with a flat category list (no nested hierarchy). A category can be matched by clause heading (e.g., "Confidentiality") or by semantic similarity via the retrieval pipeline. This is reasonable for NDA review where clause headings are consistent.

2. **QA runs on every clause**: QA always runs — not only on low-confidence extractions. This doubles inference cost per clause but ensures every assessment is verified. Users who want to skip QA can route both agents to the same fast model slot. If latency proves problematic, a `--skip-qa` flag can be added later.

3. **Clause = atomic unit**: The extraction agent operates on a single clause as returned by `stream_clauses()`. No sub-clause decomposition. This is reasonable for NDAs where clauses are short and self-contained. Bilateral comparison (Phase 2) may require sub-clause alignment, which is explicitly deferred.

4. **Memory budget held by streaming**: Clauses are processed one at a time, freeing extraction/QA results from memory before the next clause starts. Only the summary report accumulates, and it's bounded by clause count (typically <50 for an NDA).

5. **No-clause-caching across runs**: Each `review` invocation re-extracts and re-assesses every clause. There is no clause-level cache. This avoids stale-assessment risk and is acceptable for document counts under 100/day. A clause cache can be added in a performance iteration if batch sizes grow.

6. **Model routing defaults**: If no model slot flags are provided, both extraction and QA use the gateway's default routing. On a fresh install with no cloud provider configured, this means both agents run via the first available local SLM slot (typically Ollama).

7. **Single-party scope only**: The comparison agent is a no-op. Bilateral comparison is explicitly Phase 2 [§6.7]. This assumption bounds the entire feature scope.

8. **PII stripping is upstream**: The `precheck review` command accepts the `--no-pii` flag defined in the existing CLI. PII stripping happens at the parser level, before clauses reach the extraction agent. The extraction and QA agents never see raw PII.

## 7. Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| AI Gateway (C-12–C-18) | Runtime | Model routing and inference for both agents |
| Prompt Registry (N-1) | Runtime | Extraction and QA prompts managed via spec 009 |
| stream_clauses() (C-08) | Runtime | Clause input pipeline |
| RCTS chunking (C-32) | Runtime | Clause text is the chunk — already produced by parser |
| Bundled NDA playbook | Content | First playbook shipped with PreCheck mode |
| YAML parsing | Runtime | `pyyaml` for playbook loading (already a dep) |

## 8. Clarifications

### Session 2026-07-02

No [NEEDS CLARIFICATION] markers remain. All scope decisions have reasonable defaults documented in the Assumptions section. The two most impactful decisions — QA always runs, and playbooks are bundled YAML — are committed as assumptions. If the user disagrees with any assumption, they should flag it during the planning phase (`/speckit.plan`).

## 9. Out of Scope (Explicit)

The following are explicitly deferred to later phases or separate features:

- **Bilateral comparison**: The comparison agent is a structural no-op. Phase 2 will implement counterparty-aware comparison [§6.7].
- **Multi-playbook merging**: A single review only uses one playbook (bundled or user-supplied). Combining multiple playbooks is deferred.
- **Clause-level caching**: Each invocation re-extracts all clauses. No cache layer (see Assumptions §5).
- **Sub-clause decomposition**: The extraction agent receives whole clauses as parsed by stream_clauses(). No splitting of complex clauses into sub-parts.
- **Redlining / track-changes review**: The tool reviews the final document text. Change-tracking analysis is a separate feature.
- **Document generation**: The tool does not generate redlined documents or suggested edits. It only produces structured assessments.
- **Web UI / dashboard**: This is a CLI tool per Principle II. No web interface for review results.

Blueprint references: §6.7 (Phase 2), Principle II (local CLI only)
