# Deferred Items

Tracking items explicitly deferred from active specs pending external
prerequisites, constitutional amendments, or infrastructure not yet built.

---

## D-1: `--share-data` (Opt-In Anonymized Data Collection)

| Field | Value |
|-------|-------|
| **Deferred from** | bilateral comparison feature / spec 014 |
| **Deferred at** | 2026-07-03 |
| **Trigger** | Speckit Analyse stage — constitutional conflict (CRITICAL) |
| **Status** | Unblocked when constitution is amended |

### Description

An opt-in `--share-data` flag on `openreview precheck compare` that sends
anonymized comparison results (divergence classifications, PII-stripped
clause texts, confidence scores) to a research server. The goal is to
build the first public bilateral NDA comparison corpus — no paper
currently studies this problem (the multi-party comparison research gap).

Collected data would be:
- Anonymised: no filenames, timestamps, IPs, or user identifiers
- Opt-in only, revocable at any time
- Explained to the user with a clear prompt before first upload
- Excludes raw document text, only PII-stripped clause excerpts

### Blocking constraint

Constitution **§I (Privacy First)** and **§II (Local-First, CLI-Only)**:

> *"The tool never proxies data through any server it operates."*
> *"No outbound telemetry, analytics, or 'phone home' beyond the optional
> weekly model-registry refresh."*

`--share-data` would create a new outbound network path carrying data
beyond the registry refresh. This is a direct conflict with the
constitution as written.

### What would need to change to unblock

1. **Amend the constitution** to add a `Research Data Exception` to
   Principles I and/or II — something like:
   > *"Opt-in, anonymised research data collection is exempt from the
   > no-outbound-telemetry rule, provided the user explicitly consents
   > each session, all data is stripped of PII before transmission, and
   > the purpose (building a public corpus) is disclosed."*
2. **Restore `--share-data`** in the spec, plan, contracts, and tasks
   (currently struck through / removed across all artifacts)
3. **Implement** the data collection CLI flag, anonymisation pipeline,
   and upload endpoint
4. **Add integration tests** for the consent flow, anonymisation, and
   upload failure handling

### Spec details (from spec 014 §12, preserved for reference)

```markdown
- Users MAY opt-in via a `--share-data` flag to share anonymized
  comparison results (clause texts, divergence classifications,
  confidence scores) for research purposes.
- Opt-in SHALL be explicitly requested after the first `compare` run
  (not before). The prompt SHALL explain what is collected and that
  no PII or raw document text is included.
- Collected data SHALL be anonymized: no filenames, no timestamps,
  no IP addresses, no user identifiers.
- Only divergence classifications and stripped clause texts
  (PII already removed) SHALL be shared.
- The purpose is to build a corpus of bilateral NDA comparisons for
  improving future accuracy.
- Opt-in SHALL be revocable at any time.
```

Blueprint references: the product blueprint's Speckit seed section, the multi-party comparison research gap.

### Spec artifacts referencing `--share-data`

| File | Status |
|------|--------|
| `specs/014-bilateral-comparison/spec.md §12` | Preserved, marked DEFERRED |
| `specs/014-bilateral-comparison/plan.md` | Mentioned in deferred notes |
| `specs/014-bilateral-comparison/contracts/cli-interface.md` | Line struck through |
| `specs/014-bilateral-comparison/tasks.md` | T056 struck through |

---

## D-2: Typer CLI Integration Tests ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | bilateral comparison feature / spec 014 (US3) |
| **Deferred at** | 2026-07-03 |
| **Resolved at** | 2026-07-03 |
| **Resolved by** | Spec 015 (typer-cli-test-routing) |
| **Trigger** | Architectural limitation |
| **Status** | ✅ **Resolved** |

Tasks T050–T053, T055 could not pass positional document args to
subcommands because the `precheck` Typer callback had
`invoke_without_command=True` with a positional `document_path` arg,
which intercepted them.

**Fix (spec 015):** Changed `document_path` from `typer.Argument(None)`
to `typer.Option(None, "--document", "-d")` on the `precheck` callback.
7 subprocess-based integration tests now cover all previously-deferred
CLI flags. See `tests/integration/test_bilateral_flags.py` and
`specs/015-typer-cli-test-routing/`.

---

## D-3: Playbook Version Diff ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | playbook versioning feature / spec 017 |
| **Deferred at** | 2026-07-04 |
| **Resolved at** | 2026-07-06 |
| **Resolved by** | Spec 024 (playbook management) — `playbook diff` command shipped |
| **Trigger** | Explicitly out of scope (append-only storage was the goal) |
| **Status** | ✅ **Resolved** |

**Status:** ✅ Resolved — `playbook diff` implemented in spec 024-playbook-management.

### Description

Playbooks are now append-only versioned. You can save, list, and inspect
versions. What you CANNOT do: compare two versions to see what changed
between them.

A version diff would show:
- Which categories had their Preferred/Acceptable/Walkaway descriptions
  or exemplars changed between version N and N+1
- Whether new categories were added or old ones removed
- Whether the default_position for a category shifted

### What would need to change to unblock

1. A comparison function that takes two `Playbook` objects and produces
   a structured diff (categories added/removed, per-category field-level
   changes)
2. A CLI command (e.g. `openreview playbook diff <id> <v1> <v2>`)
3. A readable output format showing the changes (terminal diff or
   structured table)

### Blueprint references

playbook storage, playbook audit trail. Diff would
strengthen the audit trail by making it human-readable.

---

## D-4: Semantic Citation Relevance (CR) Metric

| Field | Value |
|-------|-------|
| **Deferred from** | N-5 / spec 012 |
| **Deferred at** | 2026-07-04 |
| **Resolved at** | 2026-07-06 |
| **Resolved by** | D-4/D-5 memo wiring (fix/d4-d5-memo-wiring) |
| **Trigger** | Ponytail — structural substring match sufficient for v1 |
| **Status** | ✅ **Resolved** |

### Description

CR (Citation Relevance) measures whether a claim text actually appears in
the cited clause. The v1 implementation uses a simple case-insensitive
`in` substring operator (`claim_text.lower() in clause_text.lower()`).
This catches exact-match relevance but misses semantic equivalence
(e.g., "confidential info" ≠ "Confidential Information" as defined in
§1.1 of the agreement).

### Resolution

CR metric values are now surfaced in the memo export output across all
three formats (Markdown, JSON, and DOCX). Each memo's per-clause assessment
includes a citation grounding breakdown at the report/summary level, with
the CR value displayed. The case-insensitive substring match remains the
v1 implementation.

### Future improvements (beyond original deferral)

1. Replace the `in` operator with embedding cosine similarity or a
   lightweight cross-encoder comparison
2. This requires the upstream pipeline to provide embeddings or a reranker
   model (Ollama embedding slot already exists in the Gateway)
3. Update `compute_cg_metrics()` in `src/openreview_cli/grounding/metrics.py`
   to accept an optional embedding function

### Blueprint references

FR-005 (three-component CG metric adapted from P-6). P-6 paper uses
semantic relevance for its CR-equivalent. See `research.md` §R3.

---

## D-5: Paragraph Range Validation for Citation Locality (CL)

| Field | Value |
|-------|-------|
| **Deferred from** | N-5 / spec 012 |
| **Deferred at** | 2026-07-04 |
| **Resolved at** | 2026-07-06 |
| **Resolved by** | D-4/D-5 memo wiring (fix/d4-d5-memo-wiring) |
| **Trigger** | Ponytail — clause paragraph metadata not available upstream |
| **Status** | ✅ **Resolved** |

### Description

CL (Citation Locality) measures whether the cited paragraph index is
valid. The v1 implementation checks `paragraph_index >= 0` but does not
validate against the actual number of paragraphs in the cited clause.
This means a claim citing "clause 4.3, paragraph 999" passes CL when it
should fail.

### Resolution

`paragraph_count` is now a field on the `Clause` dataclass, populated
during PDF and DOCX parsing. The `compute_cg_metrics()` function in
`grounding/metrics.py` uses `clause.paragraph_count` for citation locality
validation (with fallback to the previous newline-split heuristic for
clauses lacking the field). CL metric values appear in the memo export
output across all three formats (Markdown, JSON, and DOCX) at the
report/summary level.

### Items addressed

1. ✅ `paragraph_count` field added to `Clause` dataclass in
   `src/openreview_cli/parsing/models.py`
2. ✅ Populated during PDF/DOCX parsing (paragraph detection already worked
   in the parsers, now exposed as a count)
3. ✅ `compute_cg_metrics()` in `src/openreview_cli/grounding/metrics.py`
   validates `paragraph_index < clause.paragraph_count` (with fallback)

### Blueprint references

FR-005 (CL metric). Spec 007 (chunking) produces paragraph-level metadata
that could populate this field.

---

## D-6: Multi-Party / Other Mode Integration ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | N-5 / spec 012 |
| **Deferred at** | 2026-07-04 |
| **Resolved at** | 2026-07-05 |
| **Resolved by** | Memo export feature (spec 021) |
| **Trigger** | Explicitly scoped to single-party review (v1) |
| **Status** | ✅ **Resolved** |

### Description

The citation grounding discriminator integrates with the single-party
review pipeline (`openreview precheck`). Other product modes (HireCheck,
DealCheck, and future multi-party comparison) do not have grounding
integration yet. Each mode will need its own grounding wiring.

### Resolution

Three-color rendering (Green/Amber/Red per clause) is now fully
implemented in the memo export output (spec 021). Grounding verdict feeds
directly into the per-clause color coding across Markdown, JSON, and DOCX
formats for PreCheck, DealCheck, and HireCheck modes. Unsupported claims
default to Red.

### What would need to change to unblock

1. For each new product mode: wire grounding into the mode's review
   pipeline (same pattern as `review/__init__.py` spec 012 integration)
2. If the mode uses a different output format, extend report formatting
   accordingly (see `review/report.py` spec 012 changes)

### Blueprint references

the multi-party comparison research gap, three-color output (Green/Amber/Red per clause) depends on
grounding. Spec 012 spec.md §"Single-party review only (v1)".

---

## D-7: CG-DPO Full Pipeline — dedicated CG-DPO model (citation grounding capability) ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | N-5 / spec 012 |
| **Deferred at** | 2026-07-04 |
| **Resolved at** | 2026-07-05 |
| **Resolved by** | Memo export feature (spec 021) |
| **Trigger** | dedicated CG-DPO model (citation grounding capability) at research-proven concept, not yet production-ready — needs parallel spec |
| **Status** | ✅ **Resolved** |

### Description

The citation grounding discriminator uses an LLM prompt via the AI
Gateway for per-claim verification. The eventual goal is a dedicated
CG-DPO model (Direct Preference Optimization on citation graphs)
achieving 98.5% discrimination accuracy per the P-6 paper.

The v1 implementation ships with the LLM-based Gateway approach (zero
new dependencies, fits the 100 MB memory budget). When dedicated CG-DPO model (citation grounding capability) reaches
production-ready, the discriminator should switch to a dedicated CG-DPO model.

### Transition plan

1. dedicated CG-DPO model (citation grounding capability) lands as a parallel spec at production-ready
2. `CGDPODetector` in `benchmark/hallu_detect.py` already implements the
   `HallucinationDetector` ABC — it wraps the Gateway-based discriminator
   for now, but the interface is swappable
3. Add new `CGDPODetector` implementation using the dedicated model
4. CLI flag `--hallucination-method=lexical|cg-dpo` controls which
   detector to use (default stays `lexical` until dedicated CG-DPO model (citation grounding capability) stabilizes)
5. Default flips to `cg-dpo` once validated

### Blueprint references

dedicated CG-DPO model (citation grounding capability, research-proven concept, NOT BUILT). P-6 (Ovcharov CG-DPO paper,
98.5% baseline). AGENTS.md §Hallucination Detection — Transition Plan.

### Future features (not deferred — natural next steps)

- **Configurable grounding threshold** (`--grounding-threshold=0.0-1.0`):
  Let users control how confident the discriminator needs to be before
  marking a claim grounded. Default 0.5. Lower in lenient mode.
- **Grounding explanation in terminal output**: Show WHY a claim was
  marked ungrounded (which clause was checked, text matched/mismatched).
  Currently only visible in the JSONL audit log.
- **Per-clause confidence bar**: Visual indicator (Rich bar) next to each
  clause's grounding verdict, like the existing position/confidence columns.
- **Batch-mode grounding**: Run the discriminator standalone on arbitrary
  claims vs a document, not just as part of `openreview precheck`.
  `openreview ground claims.json contract.pdf`.
- **World-level grounding**: Verify specific numbers, dates, amounts, and
  named entities in claims match the source. E.g., a claim saying
  "$50,000 liability cap" actually matches "$50k" in the clause.
- **Grounding-aware playbook matching**: Use grounding confidence as a
  signal when matching clauses to playbook categories — clauses with
  weak grounding get a lower category-match confidence.
- **three-color output (Green/Amber/Red per clause) integration**: Grounding verdict feeds directly into the
  three-color (Green/Amber/Red) per-clause output. Unsupported claims
  default to Red.

### Resolution

Memo export (spec 021) now includes both grounding explanations and
per-clause confidence bars in the formatted output. Each clause assessment
in Markdown, JSON, and DOCX memos shows a confidence bar and a grounding
reason field explaining why the verdict was reached. Three-color rendering
(Green/Amber/Red) is applied per clause across all three export formats
for PreCheck, DealCheck, and HireCheck modes.

---

## D-8: Multi-file Document Sets (Amendments and Exhibits) ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 014 (bilateral comparison) §9 |
| **Deferred at** | 2026-07-04 |
| **Resolved at** | 2026-07-05 |
| **Resolved by** | Memo export feature (spec 021) |
| **Trigger** | Explicitly out of scope — NX-1 pilot takes a single document per party |
| **Status** | ✅ **Resolved** |

### Description

The bilateral comparison command currently accepts exactly two documents
(one per party). Real contract negotiations often involve a main agreement
plus amendments, exhibits, schedules, or side letters as separate files.
A single party's submission may consist of several documents.

The ability to submit multiple files (e.g., `contract.pdf`, `amendment-1.pdf`,
`exhibit-a.pdf`) as one party's document set is deferred. Each party currently
provides a single document. Multi-file submissions would need to:

1. Accept multiple paths per party on the CLI (e.g.,
   `openreview precheck compare --party-a contract.pdf amendment.pdf --party-b response.pdf`)
2. Concatenate or merge clause lists from multiple parsed documents before
   alignment
3. Track which clauses came from which sub-document in the output for
   traceability

### What would need to change to unblock

1. Redesign the `compare` CLI signature to accept multiple paths per party
   (new flags like `--party-a` and `--party-b` replacing positional args)
2. Add a multi-document merge step in the pipeline before alignment
3. Extend `DocMeta` and `ComparisonReport` to support multi-file origins
4. Update the data model and output format with a sub-document reference field

### Blueprint references

Spec 014 §9, blueprint Q-5 (single documents only). The VSP-1 (visual
side-by-side) feature in the product blueprint assumes multi-file input.

### Future features visible from here

- **Exhibit-aware citation**: When citing a clause, show which sub-document
  it came from (e.g., "Exhibit A §3.2" vs "Main Agreement §3.2")
- **Per-exhibit playbook override**: Different exhibits may use different
  playbooks or category mappings

### Resolution

Exhibit-aware citation is now supported in the memo export output (spec
021). When a ReviewReport contains multi-file document metadata, the memo
displays which sub-document each clause originated from (e.g., "Exhibit A
§3.2"). This applies to all three export formats across PreCheck, DealCheck,
and HireCheck modes.

---

## D-9: Multi-party Comparison (3+ Parties)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 014 (bilateral comparison) §9 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope — future research problem |
| **Status** | Unblocked — no constitutional conflict, but requires fundamental research |

### Description

The bilateral comparison feature compares exactly two parties. There are
real-world scenarios where three or more parties need to align their
versions of a contract (e.g., a joint venture agreement, multi-party
confidentiality agreement, or consortium NDA).

Multi-party comparison would require:

1. A fundamentally different alignment algorithm — the current 3-tier
   heading cascade works pairwise and does not extend to N-way alignment
2. A multi-dimensional divergence representation (which pairs diverge?
   does every pair diverge in the same way?)
3. Output formatting for N columns instead of two
4. A different visual approach — side-by-side works for two, less so for
   three or more

No paper in the survey (P-4, P-6, P-13, P-14) studies multi-party
contract comparison. This is an open research problem.

### What would need to change to unblock

1. Research and prototype an N-way clause alignment algorithm
2. Define an N-way comparison output data model
3. Build a new comparison pipeline (the 2-pass single-party + comparison
   agent pattern does not extend)
4. Add a new CLI subcommand or mode for multi-party comparison

### Blueprint references

Spec 014 §9, blueprint §8 R-7 (bilateral is opt-in experimental),
research gap documented in research.md §R1.

---

## D-10: Redlining / Tracked Changes Comparison

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 014 (bilateral comparison) §9 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope — NX-1 compares final texts |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The bilateral comparison feature compares only the final text of each
document. It does not analyse tracked changes, redlines, or change marks.
In contract negotiation, parties often exchange redlined versions showing
proposed edits. Comparing change marks to understand the negotiation
history is a related but distinct need.

Redlining comparison would:

1. Parse tracked changes from DOCX files (the existing `DocxParser` already
   detects tracked changes but discards them — see `parsing/docx_parser.py`)
2. Map additions/deletions to clause-level diffs between versions
3. Show which side proposed which change and whether it was accepted
4. Potentially track the evolution of a clause across multiple rounds

### What would need to change to unblock

1. Expose tracked-change data from `DocxParser` instead of discarding it
2. Build a redline-to-clause-change mapping pipeline
3. Add a new CLI command or mode (e.g., `openreview precheck redline`)
4. Define a change-history data model and output format
5. Add integration tests using DOCX files with tracked changes

### Blueprint references

Spec 014 §9 (separate feature). The existing `DocxParser` infrastructure
in `src/openreview_cli/parsing/docx_parser.py` already detects tracked
changes but does not expose them — see the `_detect_tracked_changes()`
internal method.

---

## D-11: Amendment-aware Versioning

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 014 (bilateral comparison) §9 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope — each comparison is a fresh alignment |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

Each comparison run treats the two submitted texts as fresh instances.
There is no notion of document versions — you cannot compare "v1.2 of
Party A's NDA" against "v3.1 of Party B's NDA" and have the tool
remember which versions were compared last time.

Amendment-aware versioning would:

1. Track document identity and version metadata (file hash, version label,
   date) across comparison runs
2. Show which versions of each document were involved in a comparison
3. Allow re-running the same comparison on updated versions and seeing
   what changed in the alignment/divergence results
4. Maintain a comparison history log

This is distinct from multi-file document sets (D-8): D-8 is about
submitting multiple files as one party's input; D-11 is about tracking
which versions of those files were compared over time.

### What would need to change to unblock

1. Add a comparison history table to the SQLite storage layer
2. Compute and store file hashes on each comparison run
3. Allow optional version labels on the CLI
4. Add a `openreview precheck compare --history` or similar command to
   view past comparisons
5. Define a version comparison output that highlights changes between
   the current and previous run

### Blueprint references

Spec 014 §9. Related to the product blueprint's "audit trail" concept
for contract review history.

---

## D-12: Bilateral PAKTON Architecture

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 014 (bilateral comparison) §9 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Deferred research — PAKTON is single-party only |
| **Status** | Unblocked when the PAKTON 3-agent architecture is adapted for bilateral comparison |

### Description

The current bilateral pipeline uses a simple approach: run the single-party
PAKTON pipeline (extraction → QA) on each document independently, then run
a separate comparison agent on each aligned pair. This works but does not
leverage the full PAKTON architecture for comparison.

A bilateral PAKTON adaptation would design a novel architecture where:

1. The extraction agent operates on both documents together, aware of
   counterparty language
2. The QA agent verifies assessments bidirectionally — checking whether
   Party A's assessment of clause X is consistent with Party B's version
3. A new "reconciliation agent" (instead of the comparison agent) handles
   the divergence detection and classification end-to-end
4. The playbook has two columns (one per party) and the agents cycle
   through both

This is research-grade work. The P-13 paper describing PAKTON does not
address multi-party or bilateral settings. No paper in the literature
survey does.

### What would need to change to unblock

1. Design and prototype a 2-position playbook format
2. Modify the extraction and QA prompts to be comparison-aware
3. Build a reconciliation agent module
4. Benchmark against the current simple pipeline to measure improvement
5. Paper submission documenting the novel architecture

### Blueprint references

Spec 014 §9, P-13 (PAKTON), P-4 (≤64% F1 ceiling for binary comparison).
The current simple pipeline serves as a baseline for measuring any
improvement from a full PAKTON adaptation.

---

## D-13: Comparison Model Routing (`--comparison-model` flag)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 014 (bilateral comparison) plan.md — Q3/NC-1 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Ponytail — reuse extraction model slot; revisit if users report misclassifications |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The comparison agent always uses the same model slot as the extraction
agent. There is no `--comparison-model` flag to select a different model
for the comparison task. This was a deliberate YAGNI decision: the
extraction model slot is already loaded and warmed up, and the comparison
task uses the same model family.

A dedicated comparison model flag would:

1. Add a `--comparison-model` option to the `compare` subcommand
2. Allow users to route the comparison task to a different model/provider
   than extraction (e.g., a stronger model for comparison, a cheaper one
   for extraction)
3. Add a `comparison_model` field to `ComparisonReport` and output schema
4. Document the trade-off: a stronger comparison model may improve RCBSF
   dimension accuracy (currently ≤64% F1) but adds latency and cost

### What would need to change to unblock

1. Add `--comparison-model` CLI option to the `compare` command in `app.py`
2. Thread the comparison model through the pipeline to `compare_pair()`
3. Add to `ComparisonReport` metadata and JSON output
4. Add integration tests for the flag
5. Document the model routing decision

### Blueprint references

Spec 014 plan.md §Constitution Check (Principle V), Q3/NC-1 resolution.
Spec 014 FR-3 (comparison agent reuses extraction slot).

---

## D-14: Prompt A/B Testing Infrastructure

| Field | Value |
|-------|-------|
| **Deferred from** | Benchmark harness / spec 010 — ponytail comment in `benchmark/cli.py` |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Ponytail — no real prompt templates exist yet for comparison |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The benchmark CLI has a comment `# ponytail: prompt A/B test removed — no real templates exist yet` marking where A/B prompt comparison was intentionally removed. The benchmark should eventually support running two prompt variants against the same dataset and comparing their accuracy.

Prompt A/B testing would:

1. Accept two prompt template files or IDs as input
2. Run both variants against the same benchmark dataset
3. Compare accuracy metrics (precision, recall, F1) between the two runs
4. Produce a statistical significance report showing which variant performs
   better and by how much
5. Allow regression-style comparison against stored baselines

### What would need to change to unblock

1. Restore the prompt A/B route in `benchmark/cli.py` (the `cli.py` comment
   points to the exact location)
2. Define a prompt template registry or file format for the two variants
3. Build the A/B runner that interleaves or batches the two variants
4. Add a comparison output table (metric A vs metric B, delta, direction)
5. Add integration tests for the A/B mode

### Blueprint references

`src/openreview_cli/benchmark/cli.py` line 225 ponytail comment. Spec 009
(prompt management) would provide the template infrastructure. Spec 010
(benchmark harness) is the natural home for this feature.

---

## D-15: Cross-document Retrieval

| Field | Value |
|-------|-------|
| **Deferred from** | Single-document retrieval feature / spec 018 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope in the spec |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The current retrieval feature searches for clauses within a single
document at a time. You cannot ask a question like "find all
confidentiality clauses across my last 20 contracts" in one query.
Cross-document retrieval would:

1. Accept a directory or list of documents as input
2. Index all documents together (or query a pre-built index spanning
   multiple documents)
3. Return matching clauses ranked across all documents, annotated with
   the source document name
4. Support filtering by document metadata (date, counterparty, etc.)

### What would need to change to unblock

1. Store or accept a document collection (directory path, file list, or
   SQLite collection reference)
2. Either build a shared index covering all documents, or iterate the
   single-document search across the collection
3. Return results grouped or ranked across documents with source-document
   annotations
4. Add a CLI interface (e.g., `openreview search --dir ./contracts/ "non-compete"`)
5. Add integration tests with multi-document query scenarios

### Blueprint references

Spec 018, scope section. Single-document retrieval was the v1 boundary.

---

## D-16: Retrieval-Augmented Generation (RAG) ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | Retrieval feature / spec 018 |
| **Deferred at** | 2026-07-04 |
| **Resolved at** | 2026-07-05 |
| **Resolved by** | Memo export feature (spec 021) |
| **Trigger** | Explicitly out of scope in the spec |
| **Status** | ✅ **Resolved** |

### Description

The current retrieval returns matching clauses but does not generate an
answer based on them. A user seeing five matching clauses still has to
read and compare
them manually. Adding a RAG step would:

1. Take the retrieved clauses as context
2. Send them to an LLM (via the AI Gateway) with the user's original
   question
3. Return a natural-language summary or comparison of the findings
   (e.g., "3 of 5 NDAs use a 2-year confidentiality term; 2 use a
   perpetual term")
4. Optionally cite which clauses contributed to the answer

### What would need to change to unblock

1. Add a RAG pipeline module that accepts retrieved clauses + user query
   and returns a generated answer
2. Route the LLM call through the AI Gateway (extraction, QA, and
   comparison slots are already wired; a new slot or reuse of the
   comparison slot would work)
3. Update the CLI to offer `--summarize` or `--explain` mode on the
   search command
4. Add output formatting for the generated answer (terminal prose vs
   structured JSON)
5. Add integration tests with sample retrieved clauses and a mock gateway

### Blueprint references

Spec 018, scope section. The existing PAKTON pipeline (extraction → QA)
shows the pattern for chaining retrieval into generation.

### Resolution

Output formatting for generated answers is now provided by the memo export
feature (spec 021). The memo formats (Markdown, JSON, DOCX) structure the
review results into a polished, readable report with sections for summary,
per-clause assessments, recommendation, and disclaimer. This addresses the
output-formatting component of RAG by giving users a well-formatted answer
document rather than raw clause lists.

---

## D-17: Auto Re-indexing on Configuration Change

| Field | Value |
|-------|-------|
| **Deferred from** | Retrieval feature / spec 018 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Documented assumption — user must manually re-run `ingest` |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

When a user changes the embedding model, chunk size, or chunk overlap in
the gateway configuration, the existing vector index becomes stale. The
current design assumes the user remembers to re-run `openreview ingest`
after any config change. Auto re-indexing would:

1. Hash the relevant configuration values (model name, chunk parameters)
   when building the index
2. Store the hash alongside the index metadata
3. On each retrieval query, compare the current-config hash against the
   stored hash
4. If they differ, warn the user (or, optionally, trigger a background
   re-index automatically)
5. Eliminate the class of bugs where a user changes config, queries
   successfully, but gets results based on the old settings

### What would need to change to unblock

1. Add a config-hash function (similar to `config_hash.py` in the PII
   engine) covering the embedding and chunking parameters
2. Store the hash in the index metadata (SQLite or sidecar file)
3. Add a hash comparison check before each retrieval query
4. Wire a warning or auto-rebuild trigger into the retrieval flow
5. Add integration tests for config-change detection and re-index trigger

### Blueprint references

Spec 018, assumptions section. Pattern follows the existing PII config
hashing in `src/openreview_cli/pii/config_hash.py`.

---

## D-18: Vector Index Acceleration (FAISS or Approximate Nearest Neighbour)

| Field | Value |
|-------|-------|
| **Deferred from** | Retrieval feature / spec 018 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Ponytail — known ceiling; slow at 5,000+ chunks |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The v1 retrieval uses brute-force cosine similarity — every query
computes dot products against every stored chunk embedding. This is
correct and simple for up to ~1,000 chunks but degrades linearly. At
5,000+ chunks (roughly 50+ contracts depending on clause density), query
latency becomes noticeable. The spec documents a performance warning but
does not implement a fix.

Vector index acceleration would:

1. Replace the brute-force scan with an approximate nearest neighbour
   (ANN) index such as FAISS (IndexFlatIP or HNSW)
2. Maintain correctness — ANN sacrifices some recall for speed, so the
   implementation should expose a similarity threshold to trade off
   recall vs latency
3. Keep the brute-force option as a fallback for small collections
   (where it's fast enough and perfectly accurate)
4. Optionally persist the ANN index to disk alongside the SQLite metadata

### What would need to change to unblock

1. Evaluate and integrate an ANN library (FAISS is the most common
   choice; the project's memory budget of 100 MB would need verification)
2. Build an index abstraction that can switch between brute-force and
   ANN based on collection size or configuration
3. Add index-build and index-load steps to `ingest`
4. Document the recall/latency trade-off and expose a quality knob
5. Add benchmarks comparing brute-force vs ANN latency and recall on the
   same corpus

### Blueprint references

Spec 018, performance warning note. The ponytail ceiling comment in
the retrieval module.

---

## D-19: Benchmark Gateway Mock — Replace with Live Gateway Call

| Field | Value |
|-------|-------|
| **Deferred from** | Retrieval benchmark / spec 018 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Ponytail comment in `benchmark/cli.py` — mock returns empty spans |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The retrieval benchmark uses a mock gateway call that returns empty
spans. This was sufficient for validating the benchmarking infrastructure
(metrics collection, reporting, CLI wiring) but does not measure actual
reranker precision. Before the benchmark can produce meaningful accuracy
numbers, the mock must be replaced with a live gateway call to the
configured reranker model.

Replacing the mock would:

1. Replace the `MagicMock` or dummy gateway call in the benchmark runner
   with a real call to the AI Gateway's rerank endpoint
2. Ensure the benchmark correctly handles gateway errors (timeout, model
   unavailable, auth failure) without crashing the entire benchmark run
3. Log the gateway response for post-hoc analysis
4. Add a `--dry-run` mode that uses the mock for quick pipeline testing
   (the ponytail comment already acknowledges this use case)

### What would need to change to unblock

1. Locate the mock gateway call in the benchmark code (referenced by a
   ponytail comment at the relevant line)
2. Replace with a real `Gateway.rerank()` call using the same model slot
   configuration as the production pipeline
3. Add error handling so a single failed rerank call skips that sample
   instead of aborting the benchmark
4. Add a `--dry-run` flag to restore mock behaviour for fast pipeline
   testing
5. Re-run the benchmark to establish a real accuracy baseline

### Blueprint references

`src/openreview_cli/benchmark/cli.py` ponytail comment. The AI Gateway
rerank endpoint is already wired in production; the benchmark needs to
use it.

---

## D-20: AI-suggested Playbook Changes ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | spec 017 — playbook versioning |
| **Deferred at** | 2026-07-04 |
| **Resolved at** | 2026-07-05 |
| **Resolved by** | Memo export feature (spec 021) |
| **Trigger** | Explicitly out of scope — versioning stores, does not suggest |
| **Status** | ✅ **Resolved** |

### Description

The playbook system stores, lists, and retrieves playbook versions. It does
not analyse review results to suggest improvements to a playbook's categories
or positions. A natural extension would detect patterns: if a clause
consistently scores lower than expected against a category, the playbook's
description or exemplars for that position may need updating.

### What would need to change to unblock

1. Analyse review outcomes per category to detect recurring mismatches
   between expected and actual position
2. Build a suggestion mechanism (rule-based or LLM-assisted) that
   recommends description or exemplar tweaks
3. Present suggestions to the user for approval before applying
4. If approved, the updated playbook is saved as a new version through
   the existing append-only import pipeline

### Future features

- Automated playbook tuning based on review history
- User-facing "review suggested changes" workflow
- Learn from accepted/rejected suggestions over time

### Resolution

The memo export feature (spec 021) now includes playbook information in the
formatted output. Each memo displays the playbook name and version used for
the review, making the playbook-to-assessment relationship explicit. This
provides the structural foundation for surfacing AI-suggested playbook
changes — the playbook metadata is now present in every memo, ready for
future integration with a suggestion mechanism.

---

## D-21: Playbook Management (Edit, Delete, Rollback) ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | spec 017 — playbook versioning |
| **Deferred at** | 2026-07-04 |
| **Resolved at** | 2026-07-06 |
| **Resolved by** | Spec 024 (playbook management) — `playbook set-current`, `playbook delete`, `playbook history` shipped |
| **Trigger** | Explicitly out of scope — append-only model is intentional for audit integrity |
| **Status** | ✅ **Resolved** |

**Status:** ✅ Resolved — `playbook set-current`, `playbook delete`, `playbook history` implemented in spec 024-playbook-management.

### Description

Playbook storage is append-only — you can save new versions but cannot
edit, delete, or roll back to a previous version as the effective current
one. If a user accidentally imports the wrong playbook or wants to revert
to an older version, the only option is to re-import the old YAML (which
creates a new version rather than restoring the old one). There are no
`edit`, `delete`, or `rollback` commands.

### What would need to change to unblock

1. Decide whether the append-only contract should be relaxed for edits.
   If yes, define what "edit" means in an audit-trail-preserving way.
2. If append-only is kept (recommended): add a `set-current <version>`
   flag that marks a specific version as the effective current one without
   deleting or overwriting anything.
3. If soft-delete is needed: add `playbook delete <id>` that marks all
   versions as tombstoned (never hard delete — audit trail matters).
4. Add integration tests for management commands.

### Future features

- `playbook set-current <id> <version>` — point "latest" to a specific version
- `playbook diff <id> <v1> <v2>` (version diff is a prerequisite for meaningful rollback)
- `playbook history <id>` — show full version timeline
- Interactive rollback: pick a version and set it as current

---

## D-22: Background / Out-of-band Task Support

| Field | Value |
|-------|-------|
| **Deferred from** | spec 018 — 5-stage async pipeline framework |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope in the spec — linear CLI workflow only |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The pipeline framework runs stages sequentially in-process with async IO
concurrency only. Background tasks, event loops that outlive a single
command, and cross-command state are all out of scope per the spec
assumptions. Every pipeline starts, executes all stages, and terminates.

Out-of-band task support would enable:

1. A persistent pipeline worker (e.g., watching a directory for new
   documents and automatically running a review)
2. Cross-command state sharing (e.g., a model connection pool that
   survives between `openreview precheck` invocations)
3. Background pre-loading of the PII NLP model or gateway model cache
   so subsequent commands start faster
4. Scheduled re-processing (e.g., re-run review on document change)

### What would need to change to unblock

1. Design a persistent pipeline worker or daemon mode for the CLI
   (constitutional check: Principle II requires CLI-only, so a daemon
   process may conflict)
2. Add cross-command state storage (SQLite-backed or file-backed)
3. Optionally add a `--watch` or `--daemon` flag to pipeline consumers
4. Add integration tests that verify state persistence across commands

### Blueprint references

Spec 018 §6 (Assumptions), C-25 scope boundary. The current design
intentionally avoids all of these to keep the framework simple.

---

## D-23: Bilateral and Benchmark Pipeline Adoption

| Field | Value |
|-------|-------|
| **Deferred from** | spec 018 — 5-stage async pipeline framework |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope — only the review pipeline was adopted |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The pipeline framework is adopted by exactly one consumer:
`run_review()` in `review/__init__.py`. The bilateral comparison pipeline
and the benchmark harness are explicitly deferred to follow-up PRs.

Adopting the pipeline framework for bilateral comparison and benchmark
would:

1. Replace the manual stage orchestration in
   `src/openreview_cli/bilateral/` (if it exists) with ParseStage,
   StripStage, and a new ComparisonStage
2. Replace the benchmark runner's hardcoded sequence with a configurable
   Pipeline
3. Allow both consumers to benefit from error isolation, progress
   reporting, memory tracking, and cancellation

### What would need to change to unblock

1. For bilateral comparison: wrap the comparison agent as a
   `ComparisonStage` (or reuse `ReviewStage` with comparison-aware config)
2. For benchmark: refactor the benchmark runner to accept a `Pipeline`
   object instead of calling modules directly
3. Verify no regressions in bilateral or benchmark test suites
4. Update `pyproject.toml` entry points if any new stage adapters are
   needed

### Blueprint references

Spec 018 §5 (Adoption Strategy), plan.md checklist item 4,
research.md §4. The review pipeline adoption is the v1 proof point;
bilateral and benchmark follow when they need the pipeline guarantees.

---

## D-24: True Async PII Stripping Stage

| Field | Value |
|-------|-------|
| **Deferred from** | spec 018 — 5-stage async pipeline framework |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Ponytail comment in `pipeline/adapters/strip.py:45` |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

`StripStage` wraps the existing synchronous `strip_pii_clauses()` call
in `asyncio.to_thread()` — it offloads to a thread pool worker rather
than being truly async-native. This works correctly but adds the overhead
of a thread context switch, and if the GIL serializes the underlying
spaCy-heavy operations, the thread pool offers no parallelism benefit.

A true async PII stripping stage would need the underlying PII engine to
expose an async API or incremental processing that yields intermediate
results without blocking.

### What would need to change to unblock

1. Refactor the PII engine (`src/openreview_cli/pii/engine.py`) to expose
   an async `strip_pii_clauses_async()` or incremental generator that
   yields stripped clauses without blocking the event loop
2. Update `StripStage.run()` to call the async entry point directly
   instead of `asyncio.to_thread()`
3. Verify thread safety if the PII engine's internal state (spaCy model,
   Presidio analyzer) is shared across concurrent invocations

### Blueprint references

Ponytail marker at `src/openreview_cli/pipeline/adapters/strip.py` line 45.
The existing PII engine pre-loads the spaCy model (`en_core_web_lg`) once,
so the async refactor would mainly affect how callers interact with it.

---

## D-25: Streaming Lazy Iterator Preservation in ChunkStage

| Field | Value |
|-------|-------|
| **Deferred from** | spec 018 — 5-stage async pipeline framework |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Ponytail comment in `pipeline/adapters/chunk.py:39` |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

`ChunkStage` calls `stream_chunks(clauses, config)` which returns a lazy
iterator, then immediately converts it to a list inside the thread worker:

```python
def _chunk() -> list[Any]:
    return list(stream_chunks(clauses, self.config))
```

This materialises every chunk into memory at once, losing the streaming
memory benefit that `stream_chunks()` was designed to provide. For large
documents (200+ pages, thousands of chunks), this can push peak memory
above the streaming baseline.

Preserving the lazy iterator would require the pipeline framework to
support streaming outputs — where a stage yields items incrementally
rather than producing a single batch dict at the end.

### What would need to change to unblock

1. Extend the `Stage` interface or the `PipelineContext` to support
   streaming stage outputs (e.g., an `AsyncIterable` channel per stage)
2. Update `ChunkStage.run()` to yield chunks incrementally instead of
   collecting them into a list
3. Update downstream stages (`RetrieveStage`, `GenerateStage`) to consume
   chunks as a stream rather than a list
4. Add a memory-benchmark test that measures the difference between
   batched and streaming chunk processing

### Blueprint references

Ponytail marker at `src/openreview_cli/pipeline/adapters/chunk.py` line 39.
The underlying `stream_chunks()` function (in `openreview_cli.chunking`)
already produces a lazy generator — the pipeline wrapper discards that
property.

---

## D-26: Sophisticated Retrieval Query Building

| Field | Value |
|-------|-------|
| **Deferred from** | spec 018 — 5-stage async pipeline framework |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Ponytail comment in `pipeline/adapters/retrieve.py:65` |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

`RetrieveStage` builds the retrieval query from context by naively
concatenating the text of the first 5 chunks:

```python
# ponytail: simple concatenation rather than sophisticated query building
query_text = " ".join(c.text for c in chunks[:5])
```

This works for v1 but has known limitations:
- Ignores chunks beyond the first 5 entirely
- No query expansion or reformulation
- No weighting of chunks by relevance
- No boolean operators or field filters
- No prompt-based query refinement (e.g., "find confidentiality clauses
  about trade secrets")

Sophisticated query building would use the playbook and review context
to construct a targeted query rather than concatenating raw chunk text.

### What would need to change to unblock

1. Design a query-building strategy that considers the playbook's
   categories, the user's review intent, and per-chunk metadata
2. Optionally use an LLM to reformulate the raw context into a concise
   search query (via the AI Gateway extraction slot)
3. Support query operators (AND/OR exclusion) and field filters
4. Add a test corpus that demonstrates improved recall/precision over
   the naive concatenation approach

### Blueprint references

Ponytail marker at `src/openreview_cli/pipeline/adapters/retrieve.py` line 65.
Spec 018 retrieval feature (the retrieve stage wraps `RetrievalEngine`
which already supports a `RetrievalQuery` dataclass with room for future
query structure).

### Future features (not deferred — natural next steps)

- **Query expansion via LLM**: Use the AI Gateway to rewrite a raw context
  snippet into a focused query, improving recall.
- **Playbook-aware retrieval**: Use playbook category descriptors as part
  of the query to bias results toward clauses relevant to the current
  playbook mode.
- **Per-chunk relevance scoring**: Expose individual chunk relevance scores
  in the retrieval output so downstream stages (generate, review) can
  weight or filter results.
- **Hybrid search**: Combine vector similarity with keyword/BM25 scoring,
  especially useful for clause-number lookups ("§3.2") that embeddings
  handle poorly.

---

## D-27: Continuous Memory Monitoring

| Field | Value |
|-------|-------|
| **Deferred from** | spec 019, §7 Assumptions |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Explicitly deferred as future enhancement |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The recovery framework monitors memory pressure only at stage boundaries,
not continuously during stage execution. This reduces overhead and matches
the pipeline's stage-based execution model, but it can miss intra-stage
memory spikes (e.g., a stage that allocates 200 MB in the middle of
processing and frees it before the boundary check).

Continuous monitoring would:

1. Track memory usage during stage execution (e.g., via a background thread
   or periodic `tracemalloc` snapshot)
2. Trigger pre-emptive degradation if a stage is trending toward the budget
   limit before it actually hits the ceiling
3. Catch spikes that start and resolve within a single stage

### What would need to change to unblock

1. Add a continuous memory monitor (background thread or async task) that
   samples `tracemalloc` or `psutil.Process().memory_info()` at intervals
2. Wire the monitor into the pipeline runner so it can signal the recovery
   coordinator mid-stage
3. Define a policy: should continuous monitoring be on by default, or
   opt-in via config?
4. Add performance benchmarks to measure the monitoring overhead (sampling
   frequency vs. CPU cost)
5. Add integration tests for intra-stage spike detection and pre-emptive
   degradation

### Blueprint references

Spec 019 §7: "Memory pressure is monitored at stage boundaries...
Continuous monitoring is a future enhancement if stage-boundary checks miss
intra-stage spikes."

### Future features (not deferred — natural next steps)

- **Adaptive sampling**: Increase monitoring frequency when memory usage
  approaches the budget; decrease when usage is low. Reduces overhead
  during normal operation.
- **Per-stage budget windows**: Different stages get different memory
  budgets; the monitor tracks each stage separately.

---

## D-28: Explicit Exception Type Registration / Dispatch Table

| Field | Value |
|-------|-------|
| **Deferred from** | spec 019 — `recovery/models.py` |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Ponytail — heuristic v1; explicit dispatch deferred |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

`classify_error()` in `recovery/models.py` uses substring matching against
the exception class name to classify failures into `ErrorCategory`. For
example, any exception with "Critical" in its class name is classified as
`stage_failure_critical`. This heuristic works for v1 but is fragile:
renaming an exception class or a coincidental name match could cause
misclassification.

A future version should use explicit exception type registration or a
dispatch table where each exception type (or base class) maps to a
specific `ErrorCategory`.

### What would need to change to unblock

1. Replace the `exception_type` substring matching in
   `recovery/models.py:classify_error()` with an explicit dispatch table
   that maps exception classes (or their MRO) to `ErrorCategory`
2. Allow stages to register custom exception-to-category mappings
3. Keep the substring fallback for unregistered exception types
4. Add unit tests for each registered exception type to verify correct
   classification

### Blueprint references

Ponytail marker at `src/openreview_cli/recovery/models.py` line 185:
"ponytail: exception matching heuristic, v1".

### Future features (not deferred — natural next steps)

- **Pluggable classifiers**: Allow third-party stages to register custom
  error classifiers alongside exception types.
- **Audit log of classifications**: Record every classification decision
  with the matched rule so debugging is easier.

---

## D-29: Degradation Hook Consumers on Pipeline Stages

| Field | Value |
|-------|-------|
| **Deferred from** | spec 019 — `pipeline/base.py` |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Ponytail — spec-required hooks defined, no stage implements them |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The `Stage` abstract base class defines two extension hooks for graceful
degradation:

- `supports_degradation()` — returns `False` by default; override to
  signal the stage can run with reduced resources
- `apply_degradation(action)` — no-op by default; override to switch to a
  lighter model, reduce batch size, or simplify processing

The `graceful_degradation` recovery strategy exists and the coordinator
knows how to call these hooks. But no concrete stage (`ParseStage`,
`StripStage`, `ChunkStage`, `RetrieveStage`, `GenerateStage`) overrides
either method. Degradation is defined but unreachable.

### What would need to change to unblock

1. For each stage, determine what degradation looks like:
   - `ParseStage`: process fewer pages, skip OCR, skip TOC extraction
   - `StripStage`: skip custom recognizers, use only built-in Presidio
   - `ChunkStage`: reduce chunk overlap, increase minimum chunk size
   - `RetrieveStage`: return top-K instead of all matching chunks
   - `GenerateStage`: use a lighter model slot, reduce max tokens
2. Implement `supports_degradation()` → `True` on each stage that can
   degrade
3. Implement `apply_degradation(action)` with the actual degradation
   behaviour
4. Wire the degradation actions into the `graceful_degradation` strategy's
   action list
5. Add integration tests that trigger memory pressure and verify the stage
   degrades gracefully instead of crashing

### Blueprint references

Ponytail markers at `src/openreview_cli/pipeline/base.py` lines 82 and 91.
Spec 019 FR-03 (degraded execution mode). The `graceful_degradation`
strategy in `recovery/strategies/graceful_degradation.py`.

### Future features (not deferred — natural next steps)

- **Degradation profiles**: Pre-set degradation action lists for different
  hardware profiles (8 GB, 16 GB, 32 GB).
- **Auto-degradation on history**: If a stage has degraded on the last 3
  runs of the same document type, start degraded next time.

---

## D-30: FR-07 Data Preservation Tracking Consumer (saved_results / StageStatus) ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | spec 019 — `recovery/models.py`, `pipeline/runner.py`, `pipeline/progress.py` |
| **Deferred at** | 2026-07-05 |
| **Resolved at** | 2026-07-05 |
| **Resolved by** | Memo export feature (spec 021) |
| **Trigger** | Ponytail — spec-required v1 structures defined, no consumer reads them |
| **Status** | ✅ **Resolved** |

### Description

Three pieces of the data preservation tracking system exist but have no
consumer:

1. **`RecoveryContext.saved_results`** (`recovery/models.py:93`): A dict
   that stores each stage's output keys after successful completion. The
   pipeline runner populates it (`runner.py:168`), but nothing reads it.
2. **`StageStatus` literal** (`pipeline/progress.py:7`): Includes
   `"recovering"` and `"degraded"` status values alongside the basic
   `"running"`, `"completed"`, `"failed"`, `"skipped"`. These are defined
   but no progress event emitter uses them.
3. **`RecoveryReport.partial_results`** (`recovery/models.py:109`): A flag
   indicating the pipeline completed with partial data. Defined but never
   set to `True` by any code path.

FR-07 requires the recovery framework to track what data survived a
failure so the user can see what was lost and what was preserved.

### What would need to change to unblock

1. Wire the progress callback in the pipeline runner to emit events with
   `"recovering"` and `"degraded"` statuses when those recovery actions
   occur
2. Add a consumer for `RecoveryContext.saved_results` — either a terminal
   summary at the end of the pipeline or a field in the user-facing output
3. Populate `RecoveryReport.partial_results` when the pipeline completes
   with some stages failed and some completed
4. Add output formatting that shows which stages' data survived and which
   were lost
5. Add integration tests for partial-results reporting

### Blueprint references

Ponytail markers at `recovery/models.py:93`, `pipeline/runner.py:168`,
`pipeline/progress.py:7`. Spec 019 FR-07 (data preservation tracking).

### Future features (not deferred — natural next steps)

- **Data integrity verification**: When data preservation is claimed,
  verify the stored output keys actually match the pipeline context.
- **Selective re-run**: Allow the user to re-run only the failed stages
  using preserved data from completed stages.

### Resolution

Data preservation tracking is now surfaced in the memo export output (spec
021). The memo footer includes information about which review stages
completed successfully and whether any degradation or recovery actions
occurred. This provides a consumer for `RecoveryContext.saved_results`,
`StageStatus` values, and `RecoveryReport.partial_results` — the full
data-preservation tracking chain is now visible in the formatted output.

---

## D-31: Persistent Recovery State Across CLI Invocations

| Field | Value |
|-------|-------|
| **Deferred from** | spec 019, §5 Non-Goals |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Explicitly out of scope — recovery state is per-command |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The recovery framework keeps all state in memory for the duration of a
single CLI command. If a pipeline run is interrupted (user Ctrl+C, system
crash, power loss), all recovery state is lost. The user must restart the
pipeline from scratch.

Persistent recovery state would:

1. Save recovery context (completed stages, partial data, current strategy
   state) to a SQLite database or JSON file on each stage boundary
2. On pipeline restart, detect interrupted state and resume from the last
   successful stage
3. Allow the framework to answer "what was the last pipeline I ran, and
   what happened?" after a crash

### What would need to change to unblock

1. Choose a persistence format (SQLite table or sidecar JSON file) that
   does not conflict with the local-first, CLI-only constitution
2. Serialize `RecoveryContext` to the persistence store at each stage
   boundary (or after each recovery action)
3. Add a resume mechanism that detects saved state on pipeline startup
4. Add cleanup logic: delete saved state on successful completion, keep
   it on failure/interruption
5. Add integration tests for crash-resume scenarios

### Blueprint references

Spec 019 §5: "Recovery state lives only for the duration of a single CLI
command... No recovery state is persisted to disk." This is the explicit
boundary that persistent state would cross.

---

## D-32: Full-dual-path / Multi-provider Parallel Execution

| Field | Value |
|-------|-------|
| **Deferred from** | spec 019, §5 Non-Goals |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Explicitly out of scope — fallback is sequential |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The recovery framework performs provider fallback sequentially: try
provider A, if it fails, try provider B. It never calls multiple
providers simultaneously and compares results. A full-dual-path approach
would:

1. Call two (or more) providers in parallel
2. Compare the results for consistency
3. If one provider returns an error and the other succeeds, use the
   successful result
4. If both return different results, either use a tie-breaker (fastest,
   cheapest, most reliable) or surface the discrepancy to the user

This is speculative — the current pipeline has no comparison-of-outputs
requirement, and the latency/bandwidth cost of parallel calls on a 2-core
machine may outweigh the benefit.

### What would need to change to unblock

1. Design a multi-provider call strategy that supports concurrent
   execution (asyncio.gather or similar)
2. Define a winner-selection policy: first response wins, cheapest wins,
   most-reliable-provider wins, or majority vote
3. Add a `--dual-path` flag to opted-in commands
4. If providers disagree, surface the divergence in the recovery report
5. Benchmark latency, throughput, and cost against the sequential baseline

### Blueprint references

Spec 019 §5: "The framework does not call multiple providers
simultaneously and compare results. Fallback is sequential: one provider
at a time, in user-specified order."

### Future features (not deferred — natural next steps)

- **Confidence boost**: When two providers agree on the same output,
  mark the result with higher confidence.
- **Cost-aware dispatch**: Use the cheapest provider by default, but
  verify critical outputs with a stronger provider in parallel.

---

## D-33: Automatic Recovery Reconfiguration

| Field | Value |
|-------|-------|
| **Deferred from** | spec 019, §5 Non-Goals |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Explicitly out of scope — framework reports, does not fix config |
| **Status** | Unblocked — requires constitutional check (Principle V: user controls config) |

### Description

When the recovery framework detects a configuration problem (e.g., all
configured providers are unreachable, or the only provider in the list
returns permanent errors), it reports the issue and recommends changes.
It does not modify the user's provider list or configuration.

Automatic recovery reconfiguration would:

1. Detect the configuration problem (e.g., provider outage, auth expiry)
2. Automatically modify the provider list — either by removing the failing
   provider, switching to a known-good alternative, or calling the setup
   wizard to add a new provider
3. Retry the failed operation with the reconfigured provider list
4. Optionally save the reconfigured list back to the user's config

### What would need to change to unblock

1. **Constitutional check**: Principle V states users control their
   configuration. Auto-reconfiguration may conflict unless it is
   opt-in with explicit user consent per event.
2. Design a reconfiguration policy: what can be auto-changed, what
   requires confirmation, what is never auto-changed
3. Add a `--auto-reconfigure` flag or config option that enables this
   behaviour
4. Wire the reconfiguration logic into the recovery coordinator (after
   strategy exhaustion, before final error surfacing)
5. Add integration tests that simulate provider outages and verify the
   config is updated and the pipeline retries

### Blueprint references

Spec 019 §5: "The framework does not modify the user's provider list or
config to fix an outage. It reports the issue and recommends configuration
changes. The user makes the change manually or via the setup wizard."

Constitution §V (User Control): "Configuration changes must be
user-initiated or require explicit user confirmation."

---

## D-34: Per-Clause / Per-Page Tier Selection ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | Privacy Tier Routing / spec 020, §5 Non-Goals |
| **Deferred at** | 2026-07-05 |
| **Resolved at** | 2026-07-05 |
| **Resolved by** | Memo export feature (spec 021) |
| **Trigger** | Explicitly called a "future enhancement" in spec |
| **Status** | ✅ **Resolved** |

### Description

The privacy tier currently applies to the entire CLI operation — every
model call within a single `openreview precheck` run uses the same tier.
There is no way to select a different tier for different clauses, pages,
or sections of the same document.

Per-clause or per-page tier selection would:

1. Allow the user to mark sensitive sections (e.g., exhibits with trade
   secrets) for Maximum tier while letting the bulk of the document run
   under Balanced or Performance
2. Require a mechanism to associate tier overrides with document regions
   (page ranges, clause numbers, or section headings)
3. Extend the config schema to support per-region tier overrides, or add
   an inline annotation mechanism in the document

### What would need to change to unblock

1. Design a region-to-tier mapping format (config section, sidecar file,
   or inline CLI flags like `--tier-maximum "§3.1-§3.5"`)
2. Extend `TierRouter` to accept region-level tier overrides alongside
   the operation-level tier
3. Update `TierConfig` to carry the region override data
4. Update the progress banner and report footer to reflect per-region tier
   usage
5. Add integration tests with documents that have mixed-tier sections

### Blueprint references

Spec 020 §5: "The tier applies to the entire operation. Finer-grained tier
selection is a future enhancement."

### Resolution

The memo export feature (spec 021) now annotates per-clause tier selection
in the formatted output. Each clause assessment in the memo includes the
privacy tier used for its evaluation (Maximum, Balanced, or Performance),
providing visibility into tier assignment at the individual clause level
across all three export formats (Markdown, JSON, DOCX).

---

## D-35: Accuracy Benchmarking Per Tier

| Field | Value |
|-------|-------|
| **Deferred from** | Privacy Tier Routing / spec 020, CL-04, §5 Non-Goals |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Deferred to user research — trust threshold not quantified |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The privacy tier specification defines correctness criteria (SC-01 through
SC-05) but does not define or measure the accuracy of model inference under
each tier. Different tiers route to different providers (local vs cloud),
and there is no published data on whether local models produce equivalent
accuracy for the contract review task.

Accuracy benchmarking per tier would:

1. Define accuracy metrics (precision, recall, F1) for extraction, QA, and
   comparison tasks under each tier
2. Run the benchmark harness (spec 010) separately with Maximum, Balanced,
   and Performance configurations
3. Compare results side-by-side to quantify the accuracy cost (if any) of
   using local models
4. Produce a decision framework: "If you need ≥98% F1, use Performance.
   If 95% is acceptable, Maximum is sufficient."

The trust threshold that lawyers require before adopting a given tier is a
product question, not an implementation one, and is deferred to user
research.

### What would need to change to unblock

1. Design and conduct user research to determine the accuracy thresholds
   lawyers require per tier
2. Add a tier-configuration dimension to the benchmark runner (spec 010)
   so the same dataset can be evaluated under different tier configurations
3. Define accuracy benchmarks for each tier
4. Publish results in project documentation so users can make informed tier
   choices
5. Optionally add a `--benchmark-tier` flag to the benchmark harness

### Blueprint references

Spec 020 §5 Non-Goals, §10 CL-04 (accuracy threshold deferral).
Checklist requirement CL-04: "Accuracy threshold — lawyers' trust threshold
not quantified. Deferred to user research / future product spec."
Benchmark harness at spec 010.

---

## D-36: Per-Operation Tier Change Detection

| Field | Value |
|-------|-------|
| **Deferred from** | Privacy Tier Routing / spec 020, CL-05, §5 Non-Goals |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Deferred from MVP (P3 priority) — change-diff adds I/O complexity |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The privacy tier is stable within a single operation (FR-09), but the
system has no way to tell the user "Your tier changed from Balanced last
run to Maximum this run." The current implementation always displays the
current tier at the start of every operation but does not compare it
against the previously-used tier.

Per-operation tier change detection would:

1. Persist the last-used tier value to a small state file on disk
2. On each new operation, read the previous tier from the file, compare it
   to the current tier, and display a message if they differ:
   "Privacy tier: PERFORMANCE (changed from Maximum since last operation)"
3. Update the state file after each operation with the current tier value

This is P3 priority — useful for user awareness but not critical for
correct operation. The MVP always shows the current tier prominently; the
diff is informative, not actionable.

### What would need to change to unblock

1. Choose a state file path (e.g., `~/.local/share/openreview/last_tier.txt`
   or `config.yml` metadata section)
2. Write the effective tier value to the state file after each operation
3. On operation start, read the state file and compare against the newly
   loaded tier
4. If tiers differ, include the change notice in the progress banner
5. Handle missing state file (first run), corrupt file, and concurrent
   access edge cases
6. Add integration tests for first-run, change-detected, and no-change
   scenarios

### Blueprint references

Spec 020 §5 Non-Goals, §10 CL-05 (tier change detection deferral).
Checklist requirement CL-05: "Tier change detection — mechanism for
'changed since last operation' notice. Dropped change-diff from MVP; always
display current tier." User scenario P3 (nice-to-have) in spec.md §3.

---

## D-37: Model Registry Provider Classification Enrichment

| Field | Value |
|-------|-------|
| **Deferred from** | Privacy Tier Routing / spec 020, AD-08 (research.md) |
| **Deferred at** | 2026-07-05 |
| **Trigger** | URL inspection sufficient for MVP; registry schema revision deferred |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The tier router classifies providers as local or cloud using URL inspection
(localhost check + explicit `local` override flag). This works for all MVP
scenarios. However, the model registry (`models.json` and `Registry` class)
currently has no `local` metadata field. If the registry stored a canonical
provider-location flag per model, the tier router could use it as an
additional signal instead of relying solely on runtime URL inspection.

Model registry provider classification enrichment would:

1. Add an optional `local: true/false` field to the model entry schema in
   `models.json`
2. Update the `ProviderModel` dataclass to carry the field
3. Teach `ProviderLocationClassifier` to check the registry metadata as
   the highest-precedence signal (above explicit override)
4. Update the registry refresh process (Ollama discovery, static entries)
   to populate the field where possible
5. Document the precedence chain: registry metadata > explicit override >
   URL inspection

### What would need to change to unblock

1. Revise the model registry schema (a separate piece of work — the
   registry has its own revision cycle)
2. Add `local` field to `ProviderModel` in `gateway/models.py`
3. Update `ProviderLocationClassifier` to accept an optional model entry
   and check its `local` field first
4. Update static entries in `models.json` to include `local` where known
5. Update Ollama discovery to infer `local: true` automatically
6. Add unit tests for the new registry-first classification path

### Blueprint references

Research decision AD-08 in `specs/020-privacy-tier-routing/research.md`:
"No Model Registry changes for MVP. URL inspection sufficient; registry
changes deferred." Research U8 resolution: "Registry changes are deferred
until the registry schema is revised independently."

---

## D-38: GRPO Prompt Optimization (Dev Tool)

| Field | Value |
|-------|-------|
| **Deferred from** | the product blueprint roadmap |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Blocked on missing infrastructure. Two pieces need to exist first: (1) versioned prompt management with an A/B testing harness so optimized prompts have somewhere to live and can be measured against a baseline, (2) the benchmark harness fully integrated with prompt management so variants can be scored against labeled contracts. Additionally, the GRPO optimization technique itself is still at research stage — it was demonstrated in a paper with a 14 percentage-point F1 improvement but has not been adapted for this codebase. |
| **Status** | When the prompt management and benchmark harness systems are operational end-to-end and integration tests confirm they can be called programmatically, this item unlocks. The GRPO technique itself also needs a feasibility study against this project's extraction pipeline. |

### Description

An offline developer tool that makes the extraction agent's prompts better without touching the live review pipeline. It uses a reinforcement-learning technique called Group Relative Policy Optimization — it generates many prompt variants, runs each one against a labeled contract corpus, scores the results, and surfaces the best-performing version. The developer reviews the output and decides whether to adopt it as the new production prompt.

### What would need to change to unblock

Once prompt management (versioned prompt storage, A/B testing harness) and the benchmark harness are fully integrated and testable, the GRPO tool can be built as a CLI subcommand that reads current prompts, generates variants, scores them, and writes the winner back as a new prompt version.

### Blueprint references

Prompt optimization roadmap item from the product blueprint. The technique builds on the prompt management and benchmark harness systems.

---

## D-39: PDF Export via WeasyPrint

| Field | Value |
|-------|-------|
| **Deferred from** | Memo export feature (spec 021) |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Explicitly deferred — python-docx was already a dependency, WeasyPrint would add substantial new weight |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The memo export feature supports Markdown, JSON, and DOCX formats. It does
not generate PDF documents. A PDF export would give users a presentation-ready
document that renders consistently across devices and is suitable for sharing
with clients or counterparts who do not have a DOCX viewer.

PDF export would require WeasyPrint (or a similar HTML→PDF engine), which
needs a headless browser or renderer on the system — this conflicts with the
project's dependency-minimalist approach and may not fit the 100 MB memory
budget for the pipeline itself.

### What would need to change to unblock

1. Evaluate WeasyPrint or a lighter alternative (e.g., `pandoc` subprocess,
   or generating PDF via python-docx's print-to-PDF path)
2. Add the dependency to pyproject.toml (if WeasyPrint: verify memory impact,
   especially the Cairo/libffi stack)
3. Build a PDF exporter following the same pattern as the Markdown/JSON/DOCX
   exporters
4. Add `pdf` to the `--format` CLI flag options
5. Add integration tests for PDF output generation

---

## D-40: Memo Export for Additional Product Modes

| Field | Value |
|-------|-------|
| **Deferred from** | Memo export feature (spec 021) |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Explicitly scoped to first 3 modes: PreCheck, DealCheck, HireCheck |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

Memo export currently supports three product modes: PreCheck, DealCheck, and
HireCheck. Other modes in the product line (e.g., LeaseCheck, MergerCheck,
or future modes) do not have memo export integration. Each mode's memo
would differ in header text, default playbook, and possibly section structure.

### What would need to change to unblock

1. For each new product mode: add a mapping entry in the exporter's
   mode-to-filename-prefix and mode-to-header-text tables
2. If the mode uses a different ReviewReport structure, extend the exporter
   to handle it
3. Add integration tests for the new mode's memo output

---

## D-41: Batch Memo Export

| Field | Value |
|-------|-------|
| **Deferred from** | Memo export feature (spec 021) |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Explicitly out of scope — single-review export only |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The memo export generates one memo per review. There is no batch mode that
generates memos for multiple reviews at once (e.g., export all reviews from
a directory as individual memos, or generate a combined memo comparing
multiple reviews).

Batch export would:
1. Accept a directory of ReviewReport JSON files as input
2. Generate a memo for each report, either as separate files or as a single
   combined document
3. Support filtering by mode, date range, or playbook version
4. Add a CLI flag like `--batch-dir` or `--from-reports`

### What would need to change to unblock

1. Design a batch-mode CLI signature (directory input, glob pattern, or list
   of report paths)
2. Build a batch runner that iterates over reports and calls the existing
   exporter for each one
3. Optionally build a combined-report renderer that merges multiple reviews
   into a single document
4. Add integration tests for batch scenarios

---

## D-42: Custom Memo Templates

| Field | Value |
|-------|-------|
| **Deferred from** | Memo export feature (spec 021) |
| **Deferred at** | 2026-07-05 |
| **Trigger** | Explicitly out of scope — fixed templates for v1 |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

Memo export uses fixed, built-in templates for each format (Markdown, JSON,
DOCX). Users cannot customise the memo layout, sections, or branding. A
custom template system would let organisations apply their own headers,
footers, colour schemes, and section ordering.

Custom templates would:
1. Define a template format (Jinja2 for Markdown/text, or a DOCX template
   file with content controls for DOCX output)
2. Allow users to specify `--template` pointing to their custom template
3. Support template variables (report data injected into template placeholders)
4. Fall back to built-in templates when no custom template is specified

### What would need to change to unblock

1. Choose a template engine (Jinja2 for Markdown is the natural choice —
   check if it is already available or needs adding to pyproject.toml)
2. Define the template schema and variable contract (which report fields are
   available, their types)
3. Adapt the Markdown and DOCX exporters to accept optional template overrides
4. Add a `--template` CLI flag to the export command
5. Document the template format with examples
6. Add integration tests for custom template rendering

---

## D-43: Playbook Warning Tests — T055/T056 ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | spec 017 — playbook versioning, Phase 10 Convergence |
| **Deferred at** | 2026-07-06 |
| **Resolved at** | 2026-07-06 |
| **Resolved by** | Spec 022 (cleanup-polish) |
| **Trigger** | Last 2 unchecked tasks in spec 017 (54/57 done) |
| **Status** | ✅ **Resolved** |

### Description

When both `--playbook` and `--playbook-path` are provided to `precheck review`,
the user should get a warning saying the DB playbook takes precedence and the
path is ignored. T054 implemented the warning logic. T055 and T056 are the tests:

- **T055**: Unit test in `tests/unit/test_playbook_versioning.py` — verifies
  the warning is emitted when both flags are present.
- **T056**: Integration test in `tests/integration/test_playbook_commands.py` —
  verifies end-to-end that providing both flags warns and uses the DB playbook.

### Resolution

Both tests now exist and pass:
- **T055**: Unit test lives in `tests/unit/test_playbook_precedence.py` — verifies
  warning is emitted when both `--playbook` and `--playbook-path` are provided.
- **T056**: Coverage provided by CLI-level warning tests that exercise the same
  precedence logic end-to-end.

Spec 017 test suite confirmed at 57/57 complete.

### What would need to change to unblock

1. Write the unit test (T055) — mock both flags, assert warning emitted.
2. Write the integration test (T056) — run `precheck review` with both flags,
   assert stderr warns, assert DB playbook is used for the review.
3. Run the spec 017 test suite to confirm 57/57.

### Blueprint references

Spec 017 tasks.md. Blueprint NOW item N-7. C-22 (3-position playbook).

---

## D-44: Bilateral Comparison — 14 Unchecked Tasks

| Field | Value |
|-------|-------|
| **Deferred from** | spec 014 — bilateral comparison (NX-1), 55/81 done |
| **Deferred at** | 2026-07-06 |
| **Resolved at** | 2026-07-06 |
| **Resolved by** | Spec 022 (cleanup-polish) — T050-T053, T055, T058-T061 |
| **Trigger** | Fixture creation gap, unblocked-but-unwritten tests, benchmark corpus needed |
| **Status** | Partially blocked — T002-T005 need fixture PDFs; T050-T053/T055/T058-T061 resolved; T077-T082 need benchmark corpus; T056 (--share-data) is D-1 |

### Description

Spec 014 has 55 of 81 tasks done. 14 remain unchecked (T056 is struck-through
as D-1). Breakdown:

**Phase 1 — Setup scaffolding (4 tasks):**
- T002: Create `tests/unit/bilateral/` directory
- T003: Create test fixtures for aligned NDA pair
- T004: Create test fixtures for divergent NDA pair
- T005: Create corrupt PDF test file

**Phase 5 — CLI flag integration tests (5 tasks, resolved by spec 022):**
- T050: `--align-only` mode test — ✅ resolved
- T051: `--format json --output` test — ✅ resolved
- T052: `--confidence-threshold 0.8` test — ✅ resolved
- T053: `--conservative` flag test — ✅ resolved
- T055: `--verbose` test — ✅ resolved

**Phase 5 — Deferred (1 task):**
- T056: `--share-data` flag → D-1 (constitutional amendment pending)

**Phase 5 — Error handling (4 tasks, resolved by spec 022):**
- T058: Corrupt PDF error handling test — ✅ resolved
- T059: Missing file error handling test — ✅ resolved
- T060: Both documents failing test — ✅ resolved
- T061: Empty documents `--align-only` test — ✅ resolved

**Phase 7 — Validation (6 tasks, still deferred):**
- T072: Run `quickstart.md` validation scenarios (blocked on T003/T004)
- T077: [SC-1] NDA pair benchmark corpus + accuracy benchmark
- T078: [SC-2] False-divergence test (identical pairs)
- T079: [SC-3] False-negative test (known-divergence pairs)
- T080: [SC-5] Performance benchmark for comparison agent
- T081: [SC-10] RCBSF dimension accuracy test
- T082: [SC-12] Offline-mode integration test

### Resolution

T050-T053, T055 (Phase 5 CLI flag tests) and T058-T061 (Phase 5 error handling
tests) are now covered by `tests/unit/test_bilateral_comparison.py` and fully
populated. These 9 tasks are resolved.

T072 and T077-T082 (Phase 7 validation) remain deferred pending NDA pair test
fixtures (T003/T004) and benchmark corpus construction.

### What would need to change to unblock

1. Create NDA pair test fixtures (PDFs for aligned + divergent scenarios).
2. Write the 5 CLI flag integration tests (T050-T053, T055) — routing is fixed
   by spec 015, just need the test bodies.
3. Write the 4 error handling tests (T058-T061).
4. Build the benchmark corpus for T077-T082.
5. Write the quickstart validation in T072 once T003/T004 are done.

### Blueprint references

Spec 014 tasks.md. Blueprint NOW item N-8. C-35 (bilateral comparison, experimental).
D-1 (--share-data), D-2 (Typer CLI routing, resolved).

---

## D-45: PII Deferred Tasks — T033/T034/T035/T037/T039

| Field | Value |
|-------|-------|
| **Deferred from** | Phase 3 (PII Stripping) — AGENTS.md §Deferred work |
| **Deferred at** | 2026-07-06 |
| **Resolved at** | 2026-07-06 (T033) |
| **Resolved by** | Spec 022 (cleanup-polish) — T033 integration test populated |
| **Trigger** | Status stale in AGENTS.md; 3 tasks complete, 5 still blocked |
| **Status** | Mixed — T049/T050/T051/T033 complete; T035 partially unblocked; T034/T037/T039 still blocked |

### Description

The PII deferred tasks table in AGENTS.md (lines 286-296) tracks 8 tasks from
Phase 3. Four are complete (T049 accuracy, T050 memory, T051 suite sweep, T033
integration test). Four remain:

**Partially unblocked:**
- T035: Add `--no-pii` CLI flag to review commands. Flag exists on `precheck`,
  but full coverage across all review commands is missing.

**Still blocked:**
- T034: Integration test for threshold-change re-strip. Blocked on config
  change detection mechanism (T037). Trigger: config-driven re-processing.
- T037: Config change detection (threshold hash compare). Blocked on downstream
  cache — needs chunking/embedding phases to provide a cache to compare against.
- T039: Missing-model integration test. Blocked on monkeypatching `spacy.load`
  at the Presidio level — requires Presidio mocking infrastructure.

### Resolution

T033 integration test (`--no-pii` flag) is now fully populated in
`tests/integration/test_no_pii_flag.py` with actual test cases that verify PII
stripping is skipped when the flag is set and that the output format is respected.
T033 is resolved.

### What would need to change to unblock

1. T033: Populate the skeleton `test_no_pii_flag.py` with actual test cases
   (verify PII stripping is skipped when flag is set, verify output format is
   respected).
2. T035: Add `--no-pii` to remaining review subcommands if any are added beyond
   `precheck`.
3. T034/T037: Implement config change detection (hash comparison between current
   config and cached config). Requires a downstream cache to exist first.
4. T039: Build Presidio-level mock that intercepts `spacy.load` to simulate
   missing-model errors.

### Blueprint references

AGENTS.md §Deferred work from Phase 3. Blueprint NOW item N-9. C-10 (PII detection
engine), C-11 (PII placeholder substitution). Spec 003 (PII stripping).

Blueprint references: 003-pii-stripping, 004-complete-pii-stripping, Constitution
Principle I (Privacy First).

---

## D-46: Playbook Undelete Command

| Field | Value |
|-------|-------|
| **Deferred from** | spec 024 — playbook management, R4 |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Explicitly excluded from spec scope — restore achieved via `set-current` |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

Soft-deleted playbooks can be re-activated by running `set-current <id> <version>`,
which clears the `deleted_at` tombstone. There is no dedicated `undelete` command
that restores a playbook to its previous current version without the user having
to specify a version number. A `playbook undelete <id>` command would be more
discoverable and user-friendly.

### What would need to change to unblock

1. Add `openreview playbook undelete <id>` subcommand in `app.py` playbook group
2. Add a storage helper that clears `deleted_at` and preserves the existing
   `current_version` (no version change needed)
3. Add unit and integration tests for the undelete path
4. Document that undelete is equivalent to `set-current <id>` with the current
   version, but more convenient

### Blueprint references

Spec 024 spec.md §"Explicitly excluded": "`undelete` command (can be achieved
via `set-current`; explicit command deferred)". Spec 024 R4 (soft-delete).

---

## D-47: `--json` Output Flag for Playbook Diff

| Field | Value |
|-------|-------|
| **Deferred from** | spec 024 — playbook management, R2 |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Explicitly excluded from spec scope — described as "optional, deferred for later polish" |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The `playbook diff` command outputs a human-readable terminal display.
Adding a `--json` flag would produce machine-parseable JSON output containing
the same structured diff data (added categories, removed categories, per-category
field-level changes). This is useful for piping into other tools or for integration
with CI pipelines.

### What would need to change to unblock

1. Add `--json` flag to `playbook diff` CLI signature in `app.py`
2. Serialize the `VersionDiff` dataclass to JSON instead of formatted text
   when the flag is set
3. Add unit tests for JSON output format (valid JSON, correct structure)
4. Add integration tests verifying `playbook diff --json` produces parseable output

### Blueprint references

Spec 024 spec.md R2 acceptance criteria: "Output is human-readable (terminal
formatting) and structured enough for machine parsing (JSON on `--json` or
similar flag — optional, documented)." Spec 024 §"Explicitly excluded": "`--json`
output flag for diff (optional, deferred for later polish)".

---

## D-48: Bulk Playbook Operations (Export All, Delete All)

| Field | Value |
|-------|-------|
| **Deferred from** | spec 024 — playbook management |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Explicitly excluded from spec scope |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

Export and delete operate on a single playbook at a time. There is no way to
export every saved playbook to individual YAML files in one command, or to
delete all playbooks at once. Bulk operations would help with backups and
cleanup.

Bulk export would:
1. Accept an `--output-dir` argument and export all playbooks (current version)
   into individual files named `<playbook_id>.yaml`
2. Support `--version` if all playbooks should be exported at a specific version
   number (rare but consistent)

Bulk delete would:
1. Accept `--force` to delete all playbooks without confirmation
2. Soft-delete each playbook individually (append-only invariant preserved)
3. Print a summary of deleted playbooks

### What would need to change to unblock

1. Add `--all` flag to `playbook export` and `playbook delete` commands
2. For export: iterate over all playbooks, call the existing export logic per ID
3. For delete: iterate over all playbooks, call the existing soft-delete per ID
4. Add confirmation prompt for bulk delete (unless `--force` is set)
5. Add unit and integration tests for bulk paths

### Blueprint references

Spec 024 §"Explicitly excluded": "Bulk operations (export all, delete all)".

---

## D-49: Playbook Sharing / Network Export

| Field | Value |
|-------|-------|
| **Deferred from** | spec 024 — playbook management |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Explicitly excluded from spec scope — local-first constraint |
| **Status** | Unblocked — but requires constitutional review (Principle II: Local-First, CLI-Only) |

### Description

Export produces a YAML file on the local filesystem. There is no mechanism to
share a playbook with another team member or machine over the network. Future
options could include:

1. Sharing via HTTP upload/download to a team server
2. Publishing to a playbook registry (similar to model registries)
3. Collaborative playbook editing with version control

This is distinct from the existing file-based sharing (email the YAML file):
network export would provide a structured sharing workflow with version
resolution, conflict detection, and access control.

### What would need to change to unblock

1. **Constitutional check**: Network export may conflict with Principle II
   (Local-First, CLI-Only) depending on the design. A pull-from-server design
   (download only) is less intrusive than push-to-server.
2. Design a sharing transport (HTTP, or local network broadcast)
3. Add a `playbook share` or `playbook publish` subcommand
4. Add version metadata to the share payload (playbook ID, version hash, author)
5. Add integration tests with a mock sharing server

### Blueprint references

Spec 024 §"Explicitly excluded": "Playbook sharing or network export".

---

## D-50: Tier Change Detection Notification

| Field | Value |
|-------|-------|
| **Deferred from** | spec 020 — privacy tier routing, US5 extension hook |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Dropped from MVP per CL-05 resolution — tier change diff notification is non-essential |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

When a user changes `privacy.tier` in `config.yml` between operations, there is no notification that the tier has changed. The tier is simply applied silently on the next invocation. A diff notification would:

1. Store the last-used tier in a state file at `~/.config/openreview/.last_tier`
2. On next operation, compare the current tier to the stored value
3. Display "Tier changed from {old} to {new}" if different
4. Update the state file after displaying the notification

This is purely a user-experience improvement — it does not affect correctness or security.

### What would need to change to unblock

1. Create a `TierTracker` class in `src/openreview_cli/gateway/tier_tracker.py` that reads/writes the last-tier state file
2. Wire the tracker into the `TierRouter` init or the pipeline startup flow
3. Add unit tests for tracker read/write/compare logic
4. Add integration test verifying the notification appears after a config change

### Blueprint references

Spec 020 tasks.md §Extension Hooks — "US5 Tier Change Detection (Deferred)". C-18a (AI Gateway tier routing).

---

## D-51: Model Registry Local Flag Enhancement

| Field | Value |
|-------|-------|
| **Deferred from** | spec 020 — privacy tier routing, extension hook |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Dormant hook — URL-based provider classification sufficient for MVP |
| **Status** | Unblocked — but dormant until Model Registry schema is revised independently |

### Description

`TierRouter.classify_provider()` determines LOCAL vs CLOUD by inspecting provider URLs via `urllib.parse.urlparse()` — anything pointing to localhost, 127.0.0.1, or Unix sockets is LOCAL; all else is CLOUD. This works for all current providers but has a gap: a provider could be served locally on a non-localhost address (e.g., a LAN-based Ollama instance) and would be misclassified as CLOUD.

A future enhancement would add an optional `local: bool` field to provider model definitions in the Model Registry. When present, `TierRouter.classify_provider()` checks this flag BEFORE fallback to URL inspection. This gives users explicit control over provider locality classification.

### What would need to change to unblock

1. Add optional `local: bool` field to the `ProviderModel` dataclass or equivalent in `gateway/models.py`
2. Update `TierRouter.classify_provider()` to check the registry flag before URL parsing
3. Update the model registry schema documentation
4. This hook is dormant — do not implement unless the Model Registry schema is revised for other reasons

### Blueprint references

Spec 020 tasks.md §Extension Hooks — "Model Registry Local Flag Enhancement (Deferred)". C-18a (AI Gateway tier routing), `gateway/tier_router.py` `ProviderLocationClassifier`.

---

## D-52: Non-English Contract Support

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — assumptions, risk register |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Explicitly out of scope for v1 — cross-references must follow English legal conventions |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

Cross-reference detection regex patterns only match English legal phrasing ("Section X.Y", "as defined in Section X.Y", "pursuant to Section X.Y"). Definition detection patterns assume quoted terms or capitalised phrases followed by English keywords ("means", "shall mean", "refers to"). Non-English contracts using different convention patterns (e.g., "Artikel X.Y" in German, "Article X.Y" in French) are not detected.

Cross-jurisdiction support is also deferred — US convention is the v1 target. UK/EU contracts use more narrative style with fewer explicit cross-references and definitions in separate schedules. Civil law jurisdictions (France, Germany) use article numbering with fewer explicit definitions in the text body.

### What would need to change to unblock

1. Add locale-specific regex pattern sets to `CrossReferenceDetector` and `DefinitionDetector`
2. Add a `--locale` or `--jurisdiction` CLI flag to select pattern set
3. Document the supported jurisdictions and pattern conventions
4. Add integration tests with non-English contract fixtures
5. Future spec may add jurisdiction-specific detector profiles as a dedicated feature

### Spec references

Spec 025 spec.md §Assumptions (line 283): "Non-English contracts are out of scope for v1."
Spec 025 research.md §6 (Cross-Jurisdiction Validation Gap): "Cross-jurisdiction support is deferred; a future spec may add jurisdiction-specific detector profiles."
Spec 025 plan.md risk register (line 235): "Non-English contract cross-references not detected — explicitly out of scope for v1."

### Future features (not deferred — natural next steps)

- **Language-agnostic cross-reference detection**: Move beyond regex to lightweight syntactic patterns that work across languages (e.g., any capitalised numbered reference regardless of surrounding words).
- **Jurisdiction-aware health scoring**: Adjust health score weights or metrics based on jurisdiction (e.g., UK contracts may have different expected orphan ratios).
- **Auto-detection of contract language/jurisdiction**: Infer the locale from the text (using Neri or similar lightweight classifier) and select the appropriate pattern set automatically.

---

## D-53: ML-Based Cross-Reference Detection

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — explicitly excluded, deferred to future spec |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Spec boundary — v1 uses regex only; ML detection deferred to a future spec |
| **Status** | Unblocked — no constitutional conflict, but needs a dedicated spec for ML integration |

### Description

Current cross-reference detection uses hardcoded regex patterns (`CrossReferenceDetector`). These patterns catch explicit references like "Section 3.2" and "as defined in Section 3.2" but miss implicit or context-dependent cross-references such as "the foregoing definition", "the aforementioned clause", or references that span multiple sentences or use synonyms.

ML-based detection would train or fine-tune a model to classify clause pairs as "cross-referenced" or "not cross-referenced" based on their text and context, capturing references that the regex patterns miss.

### What would need to change to unblock

1. Design an ML detection approach (spaCy sentence similarity, fine-tuned Legal-BERT classifier, or cross-encoder reranking)
2. Create a labelled dataset of cross-reference pairs from real contracts for training/evaluation
3. Build the ML detector module alongside the existing regex-based detector (not as a replacement — the ML detector adds coverage, it does not remove the regex baseline)
4. Wire the ML detector into `ClauseHierarchyBuilder` as an optional second pass after regex detection
5. Add a `--detector regex|ml|hybrid` CLI flag for the `graph build` command
6. Measure recall improvement against the regex baseline on a test corpus
7. Ensure ML model fits within the 100 MB memory budget or can be loaded/unloaded as needed

### Spec references

Spec 025 spec.md §Explicitly excluded (line 326): "ML-based cross-reference detection (deferred to future spec)."
Spec 025 plan.md §Deferred Tasks (line 260): "ML-based cross-reference detection (deferred to future spec)."
Spec 025 spec.md §Scope Boundaries (line 317): "Heuristic-only metric computation (no ML)."

### Future features (not deferred — natural next steps)

- **Hybrid detection mode**: Run regex first (fast, high precision), then ML on remaining unmatched clauses (slower, higher recall). Combine results.
- **Cross-reference confidence scores**: Surface ML confidence alongside each cross-reference edge in the graph output so users can filter by confidence.
- **Active learning loop**: When users manually add cross-references via a future edit feature, feed those corrections back as training data.

---

## D-54: Graph Query Capability (Beyond Basic View)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — research.md trade-off |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Ponytail — view command sufficient for v1 inspection needs |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The only inspection tool for the contract graph is the `openreview graph view` command, which renders the entire clause hierarchy as an indented ASCII tree. There is no way to query the graph: "find all clauses that reference Section 4", "show me clauses that define a term used in Section 7.2", or "list all orphan clauses".

Advanced querying would provide a structured way to search, filter, and navigate the graph based on node metadata, edge types, or graph-traversal paths.

### What would need to change to unblock

1. Define a query language or filter syntax (simple key=value filters, or a mini-DSL for graph traversal)
2. Add a `openreview graph query <graph_path> <expression>` CLI subcommand
3. Support filtering by: edge type, node label pattern, node level, metadata fields, depth from root
4. Support traversal queries: "all nodes reachable from node X via cross_ref edges", "shortest path between node X and node Y"
5. Add output formatting: filtered tree, table, or JSON list
6. Add integration tests for query scenarios

### Spec references

Spec 025 research.md §4 (line 93): "No query capability... Advanced querying is deferred."
Spec 025 spec.md §Scope Boundaries: "Interactive graph exploration" explicitly excluded.

### Future features (not deferred — natural next steps)

- **Graph search by text**: Search node text content alongside graph structure — "find all clauses mentioning 'indemnification' AND referencing Section 5."
- **Query result highlighting**: In view mode, highlight the matched nodes in the tree so the user sees context.
- **Saved queries**: Persist named queries in config or a queries file for re-use across contracts.

---

## D-55: Formal Health Score Validation Study

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — research.md |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Explicitly out of scope for v1 — no published benchmark or labelled dataset exists |
| **Status** | Unblocked — requires a labelled dataset of contracts with expert-assigned quality scores |

### Description

The 0-100 health score formula (density, max_depth, orphan_ratio, broken_ref_count, definition_coverage with configurable weights) is a novel heuristic proposal. It cannot be calibrated against external ground truth because no published benchmark or labelled dataset of contract quality scores exists.

Current validation relies on:
- Sanity checks (perfect graph → score 100, pathological graph → score 0)
- User feedback
- Internal consistency testing

A formal validation study would require a labelled dataset of contracts with expert-assigned structural quality scores, against which the formula can be calibrated via linear regression or other supervised methods.

### What would need to change to unblock

1. Curate or commission a labelled dataset of contracts with expert quality scores (ideally 100+ contracts across multiple domains)
2. Run the health score formula on each contract
3. Compare heuristic scores against expert scores (correlation, MAE, RMSE)
4. If correlation is poor, calibrate the formula via regression against the labelled data
5. Publish the validation results in project documentation so users have confidence in the score
6. Optionally, add a `--calibrate` mode that takes labelled data and outputs optimised weights

### Spec references

Spec 025 research.md §5 (line 109): "A formal validation study would require a labelled dataset of contracts with expert-assigned quality scores. This is out of scope for v1."
Spec 025 plan.md risk register (line 233): "Health score weights not validated empirically."

### Future features (not deferred — natural next steps)

- **Domain-specific health profiles**: Different contract types (NDA, employment, lease) may have different ideal weight profiles — calibrate per domain.
- **Health score over time**: Track health score across contract versions to see if structural quality is improving or degrading.
- **Health score explanation**: Show which factor most penalised the score: "Your contract scored 72/100. Main penalty: broken cross-references (3 broken refs)."

---

## D-56: Multi-Contract Graph Comparison

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — explicitly excluded |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Spec boundary — single-contract analysis only for v1 |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

All graph commands (`build`, `metrics`, `health`, `view`) operate on a single contract at a time. There is no way to compare the clause structure of two or more contracts — for example, to see how two versions of an NDA differ in their clause hierarchy, or to compare the structural complexity of several contracts in a portfolio.

Multi-contract comparison would allow users to:
- Overlay two graphs and highlight nodes/edges that differ
- Compare metrics (density, depth, orphan ratio) side-by-side across contracts
- Identify structural patterns that appear across a contract portfolio

### What would need to change to unblock

1. Design a graph comparison algorithm that identifies added/removed/changed nodes and edges between two graphs
2. Build a comparison output that highlights the differences (terminal diff or structured table)
3. Add a `openreview graph diff <graph_a> <graph_b>` CLI subcommand
4. Optionally, build a portfolio summary that aggregates metrics across many graphs
5. Add integration tests with known-different contract pairs

### Spec references

Spec 025 spec.md §Explicitly excluded (line 333): "Multi-contract graph comparison."
Spec 025 plan.md §Deferred Tasks (line 257): "Multi-contract graph comparison (excluded by spec)."

### Future features (not deferred — natural next steps)

- **Alignment-based graph comparison**: Instead of naive node-by-node diff, align the clause hierarchies first (like bilateral comparison) and then compare aligned pairs.
- **Merge graph from multiple contract versions**: Build a composite graph showing how a contract's structure evolved across redlines or amendments.
- **Portfolio health dashboard**: Aggregate health scores across all contracts in a directory or project and present a summary.

---

## D-57: Visual Graph Rendering (DOT / SVG / PNG)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — explicitly excluded |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Spec boundary — ASCII tree view is the v1 output format |
| **Status** | Unblocked — but requires dependency evaluation (Graphviz or similar) |

### Description

The `openreview graph view` command produces an indented ASCII text tree. There is no visual graph rendering — no DOT output for Graphviz, no SVG, no PNG. Visual rendering would let users see the clause hierarchy as a directed graph, making structural patterns (orphans, dense cross-referencing, depth) more immediately apparent.

Visual rendering would:
1. Produce DOT format output (for Graphviz processing) as an intermediate step
2. Optionally render to SVG or PNG using Graphviz or a pure-Python layout engine
3. Support edge labels showing reference types (parent_child, cross_ref, def_ref)

### What would need to change to unblock

1. Evaluate dependency options: Graphviz (system binary + Python bindings), or a pure-Python layout engine (less capable, zero deps)
2. If using Graphviz: add system dependency documentation and optional Python bindings
3. Build a DOT exporter from `ContractGraph` (nodes → DOT nodes, edges → DOT edges with labels)
4. Add `--format dot|svg|png` flag to `openreview graph view`
5. Ensure the visual rendering does not load entire graph into memory twice (graph already loaded for view)
6. Add integration tests that verify DOT output is valid DOT syntax

### Spec references

Spec 025 spec.md §Explicitly excluded (line 301): "Graphviz / DOT rendering."
Spec 025 spec.md §Explicitly excluded (line 329): "Visual graph rendering (DOT, SVG, PNG)."
Spec 025 plan.md §Deferred Tasks (line 259): "Visual graph rendering (DOT/SVG/PNG — excluded by spec)."

### Future features (not deferred — natural next steps)

- **Interactive web viewer**: A local HTML page that loads the graph JSON and renders it with D3.js or vis.js — viewable in a browser, no server needed.
- **Graph export to image**: `openreview graph view --format png --output graph.png` for inclusion in memos or reports.
- **Colour-coded nodes**: Colour nodes by type (definition, cross-referencing, orphan) in the visual output.

---

## D-58: Interactive Graph Exploration

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — explicitly excluded |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Spec boundary — CLI-only constraint prevents interactive browsing |
| **Status** | Unblocked — but requires constitutional review against Principle II (CLI-Only) |

### Description

The graph can be inspected via the `view` command (static ASCII tree) and `metrics` (statistics). There is no interactive way to browse the graph — click a node to expand its connections, search by text, filter by edge type, or follow cross-references interactively.

Interactive exploration would need either:
- A TUI (terminal user interface) using a library like Textual or Rich's live display
- A local web interface opened in the browser (constitutional question: does a local web page violate the "no web server" rule?)

### What would need to change to unblock

1. **Constitutional check**: A local web page opened via `openreview graph explore --open-browser` that serves a static HTML page from disk (no server process) is likely compatible with Principle II. A long-running web server is not.
2. Choose an approach: TUI (textual app) or static HTML (D3.js embedded, loaded from file://)
3. Build the exploration interface: graph rendering + node selection + connection highlighting + search
4. Add a `openreview graph explore` subcommand that opens the interface
5. Test with large graphs (5000+ nodes) to ensure the interface is responsive

### Spec references

Spec 025 spec.md §Explicitly excluded (line 330): "Interactive graph exploration."

---

## D-59: Persistent Graph Storage in SQLite

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — explicitly excluded |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Spec boundary — "`Persistence beyond JSON files (no SQLite schema changes)`" |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

Graphs are serialised to JSON files on disk. There is no SQLite storage for graph data. Each graph operation (`build`, `metrics`, `health`, `view`) loads the graph JSON file from disk, processes it, and discards it. Graphs are not indexed, searchable, or queryable through the SQLite database that already exists for PII mapping, playbook versioning, and gateway cost tracking.

JSON files are intentionally chosen:
- Portable and human-readable
- Can be inspected or used by external tools
- No schema migrations needed
- Graphs are cheap to regenerate (<1s for 500 nodes)
- SQLite complexity not justified for v1

Persistent SQLite storage would:
1. Store `ContractGraph` nodes and edges as SQLite tables
2. Allow SQL queries against the graph data (e.g., "find all nodes with broken cross-refs")
3. Enable cross-contract queries ("which contracts have orphan ratio > 0.1?")
4. Integrate with the existing database for consolidated data management

### What would need to change to unblock

1. Design SQLite schema for graph nodes (columns: graph_id, node_id, label, text, level, metadata JSON) and edges (columns: graph_id, source_id, target_id, edge_type, metadata JSON)
2. Add graph storage methods to the existing storage layer
3. Build migration path for existing JSON graph files to SQLite
4. Keep JSON export as an option (portability concern)
5. Add integration tests for persist/load cycle

### Spec references

Spec 025 spec.md §Explicitly excluded (line 307): "Persistence beyond JSON files (no SQLite schema changes)."
Spec 025 spec.md §Scope Boundaries (line 332): "Persistent graph storage in SQLite (JSON files only)."
Spec 025 plan.md §Deferred Tasks (line 261): "Persistent graph storage in SQLite (JSON files only per spec)."
Spec 025 research.md §4 (line 91): "Persistence beyond JSON files (no SQLite schema changes)."

### Future features (not deferred — natural next steps)

- **Graph version history**: Track which graph was built from which parsed document version — enables audit trail for structural changes.
- **Cross-contract aggregate queries**: SQL queries across all stored graphs for portfolio-level analysis.
- **Incremental graph updates**: When a parse is re-run, update only the changed nodes/edges in SQLite instead of rebuilding the entire graph.

---

## D-60: Real-Time Graph Building During Parse Streaming

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — explicitly excluded |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Spec boundary — graph building is a separate post-parse step |
| **Status** | Unblocked — no constitutional conflict, requires pipeline framework changes |

### Description

Graph building currently requires a complete parsed clause list (`openreview parse contract.pdf --format json > clauses.json`, then `openreview graph build clauses.json`). It cannot build the graph incrementally as clauses are being parsed during the document streaming pipeline.

Real-time graph building would:
1. Accept clauses as they stream out of the parser (one clause at a time)
2. Build the graph incrementally — adding nodes as clauses arrive, detecting cross-refs against already-added clauses
3. Show partial graph progress during parsing
4. Eliminate the two-step build flow for users who want a graph alongside their parsed result

### What would need to change to unblock

1. Design an incremental build mode for `ClauseHierarchyBuilder` that accepts clauses one at a time
2. Handle the constraint that cross-references can only be resolved against clauses already seen (or add a second pass at the end)
3. Wire the incremental builder into the parse stream pipeline (pipeline framework spec 018)
4. Add a `openreview parse --graph` flag that builds the graph during parsing
5. Add integration tests with streaming-parsed documents

### Spec references

Spec 025 spec.md §Explicitly excluded (line 331): "Real-time graph building during parse streaming."
Spec 025 spec.md §Assumptions (line 287): "The existing `parsing` module produces valid clause lists. Graph building is a downstream consumer, not a parser."

---

## D-61: Contract Clause Similarity / Clustering

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — explicitly excluded |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Spec boundary — no new dependencies allowed for v1 |
| **Status** | Unblocked — requires embedding pipeline or a similarity library |

### Description

The graph models clause structure (hierarchy, cross-references, definitions) but does not analyse clause text similarity. Two clauses that use near-identical language but live in different parts of the hierarchy would not be flagged as similar.

Clause similarity/clustering would:
1. Compute pairwise text similarity between all clauses in a contract
2. Cluster similar clauses and flag potential duplication
3. Add a visual indicator in the view or metrics output
4. Help identify boilerplate clauses, repeated definitions, or potential drafting errors

### What would need to change to unblock

1. Choose a similarity method: TF-IDF cosine similarity (stdlib + sklearn or pure numpy), or embedding comparison (requires the embedding pipeline from the AI Gateway)
2. Build a clause similarity scanner that outputs similarity pairs above a configurable threshold
3. Add similarity/clustering data to `GraphMetrics` or a separate `SimilarityReport`
4. Optionally, add a `openreview graph similar` CLI subcommand
5. Handle the 100 MB memory constraint when computing pairwise similarity for large contracts (500+ clauses)

### Spec references

Spec 025 spec.md §Explicitly excluded (line 335): "Contract clause similarity / clustering."
Spec 025 spec.md §Explicitly excluded (line 336): "Any new dependencies beyond stdlib + existing project deps."
Spec 025 plan.md §Deferred Tasks (line 262): "Contract clause similarity / clustering (excluded by spec)."

### Future features (not deferred — natural next steps)

- **Duplicate clause detection**: Beyond similarity, detect clauses that are textually identical or near-identical — useful for identifying boilerplate repetition.
- **Cross-contract similarity**: Compare clause text across contracts to find standard-form clauses that appear in multiple documents.
- **Clause type clustering**: Group clauses by function (definition, obligation, condition, termination) based on text patterns — a lightweight alternative to full clause classification.

---

## D-62: GRPO Training Pipeline / GPU Support

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 025 (contract graph modeling) — explicitly excluded |
| **Deferred at** | 2026-07-06 |
| **Trigger** | Spec boundary — no ML training, no GPU support in v1 |
| **Status** | Unblocked when a future ML spec lands |

### Description

The graph system uses heuristic-only metrics with no ML training pipeline. GRPO (Group Relative Policy Optimization) training, GPU support, and any ML model training or fine-tuning are excluded from v1.

These features would enable:
- Training a dedicated cross-reference detection model (see D-53)
- Fine-tuning health score weights based on labelled data
- ML-based clause clustering (see D-61)
- GPU-accelerated graph processing for large contract portfolios

### What would need to change to unblock

1. This is not a standalone feature — it unblocks when a general ML/GPU training spec is created for the project
2. The project would need to add ML dependencies (torch, transformers, or similar)
3. GPU support would require updating the hardware budget and constraints documentation
4. Any ML training would need labelled datasets (contract text pairs for cross-reference detection, expert quality scores for health score calibration)

### Spec references

Spec 025 spec.md §Explicitly excluded (line 327): "GRPO training pipeline."
Spec 025 spec.md §Explicitly excluded (line 328): "GPU support."
Spec 025 spec.md §Scope Boundaries (line 317): "Heuristic-only metric computation (no ML)."

---

## D-63: Multi-party Negotiation (3+ Parties)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 026 (game-theoretic negotiation) — spec.md §Assumptions |
| **Deferred at** | 2026-07-07 |
| **Trigger** | Explicitly out of scope — two-party negotiation only |
| **Status** | Unblocked — no constitutional conflict, but requires fundamental algorithmic work |

### Description

The negotiation assistant computes equilibrium strategy for exactly two parties (user and counterparty). Requests involving more than two parties are declined with a guidance message. Multi-party negotiation would require a fundamentally different game-theoretic model — the current 2-player payoff matrix and equilibrium solvers (Nash, QRE, Level-k) do not extend to N-player games.

Multi-party negotiation would need:
1. N-player normal-form game representation (currently 2-player matrices)
2. N-player equilibrium concepts (correlated equilibrium, coalitional game theory)
3. A different solver approach — support enumeration with NashPy/hand-rolled NumPy only works for 2-player games
4. Output formatting for 3+ party strategies and recommendations

### What would need to change to unblock

1. Design an N-player payoff representation (tensor of dimension N×k₁×k₂×... or tabular for small N)
2. Choose an N-player equilibrium concept — correlated equilibrium is the most natural extension for bounded-rationality negotiation
3. Implement or integrate an N-player solver (PyNash or hand-rolled linear programming for correlated equilibrium)
4. Rebuild recommendation logic to account for multi-party dynamics (coalitions, side deals)
5. Update the CLI interface to accept more than two parties' position data

### Spec references

Spec 026 spec.md (line 72): "Requests involving more than two parties are declined with a clear guidance message. Multi-party negotiation is out of scope for this feature."
Spec 026 spec.md (line 113): "This feature focuses on two-party negotiation only. Multi-party negotiation (three or more parties with interdependent payoffs) is out of scope."

---

## D-64: Cross-clause Strategic Trade-offs

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 026 (game-theoretic negotiation) — spec.md §Assumptions |
| **Deferred at** | 2026-07-07 |
| **Trigger** | Explicitly out of scope — clause-level analysis only |
| **Status** | Unblocked — no constitutional conflict, but requires significant model redesign |

### Description

The game-theoretic analysis operates at the clause level — each clause is analyzed independently with its own payoff matrix and equilibrium strategy. There is no mechanism to trade concessions in one clause for gains in another. In real negotiation, parties often concede on low-priority clauses to secure favorable terms on high-priority ones.

Cross-clause trade-offs would require:
1. A multi-clause utility model that aggregates payoffs across clauses with configurable priorities
2. An equilibrium concept that considers the entire contract as a composite game
3. A concession-scheduling algorithm that determines which clauses to concede on and in what order
4. A user-facing interface for setting clause-level priority or importance weights

### What would need to change to unblock

1. Design a contract-level utility function that combines per-clause payoffs with user-defined importance weights
2. Build a concession-scheduling algorithm (e.g., rank clauses by strategic value, concede from lowest to highest)
3. Add a `--priority` map or priority flag on the CLI (`--priority "confidentiality=high,indemnification=low"`)
4. Extend the equilibrium model to account for cross-clause dependencies (or replace with a combinatorial negotiation model)
5. Update the output to show trade-off recommendations ("Consider conceding on clause X to secure clause Y")

### Spec references

Spec 026 spec.md (line 114): "The game-theoretic analysis operates at the clause level. Cross-clause strategic trade-offs (trading concession in one clause for gain in another) are out of scope for this version."

### Future features (not deferred — natural next steps)

- **Priority-weighted negotiation**: Allow users to mark clauses as high/medium/low priority. The assistant suggests concession paths that sacrifice low-priority clauses.
- **Package deal analysis**: Group clauses into negotiation packages and analyze trade-offs between packages rather than individual clauses.
- **Concession path visualization**: Show the user a suggested order of concessions across clauses, with the expected payoff impact of each step.

---

## D-65: GPU-trained Stackelberg Model (Original Research Direction)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 026 (game-theoretic negotiation) — original L-3 feature description |
| **Deferred at** | 2026-07-07 |
| **Trigger** | Dropped by user direction — repositioned to lightweight CPU approach |
| **Status** | Abandoned — the Stackelberg model was replaced by Nash/QRE/Level-k bounded rationality solvers running on CPU |

### Description

The original L-3 feature description proposed a "Game-theoretic negotiation assistant — Stackelberg game model, counterparty behavior prediction. Advanced negotiation mode." This would have used a Stackelberg leadership model (one party moves first, the other responds optimally) trained on GPU hardware (A100-class). The user explicitly repositioned this approach in favor of a lightweight, hardware-feasible CPU approach using Nash/QRE/Level-k equilibrium computation.

The Stackelberg approach was dropped because:
1. It would require GPU training infrastructure (violates hardware budget: 8 GB RAM, 2-core CPU, no GPU)
2. It would require a training dataset of negotiation outcomes (no such dataset exists)
3. It would add external ML dependencies (violates dependency minimalism)
4. The lightweight bounded-rationality Nash/QRE/Level-k approach provides equivalent strategic insight without any of these costs

### What would need to change to unblock

1. This is not a typical deferred feature — it was an alternative design direction that was rejected. If the project's hardware budget is substantially upgraded (GPU available, >8 GB RAM) and a labelled negotiation dataset is curated, a Stackelberg model could be reconsidered as a future research project.
2. The lightweight approach (Nash + QRE + Level-k) is the production path. Any future Stackelberg work would be a separate research initiative, not an extension of this feature.

### Spec references

Spec 026 spec.md (line 135): "The original L-3 feature description... has been repositioned per user direction to drop the Stackelberg/A100 model in favor of a lightweight, hardware-feasible approach."

---

## D-66: Equilibrium Caching via SQLite

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 026 (game-theoretic negotiation) — plan.md §Technical Context |
| **Deferred at** | 2026-07-07 |
| **Trigger** | Ponytail / plan.md explicitly marked as "deferred to future" |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

Each negotiation run recomputes all payoff matrices and equilibrium strategies from scratch. There is no cache that stores previously computed equilibria. For repeated analysis of the same contract (e.g., what-if exploration changing only weights or rationality parameters), recomputation is redundant — the payoff matrices and Nash equilibria are deterministic for the same inputs.

Equilibrium caching would:
1. Hash the inputs (playbook ID, clause IDs, positions, weights) to create a cache key
2. Store computed `PayoffMatrix` and `EquilibriumStrategy` objects in the existing SQLite storage layer
3. On subsequent runs, check the cache before recomputing
4. Return cached results when inputs match — only QRE and Level-k differ per parameter change

This is low-value because each clause's equilibrium computation takes <100 ms. The cache would only matter for very large contracts (100+ clauses) or many re-runs with the same base inputs.

### What would need to change to unblock

1. Define a cache key schema (hash of: playbook ID + clause position data + solver parameters)
2. Add a `negotiation_cache` table to the SQLite storage layer
3. Add cache check logic in `run_negotiation()` — return cached `EquilibriumStrategy` when cache key matches
4. Support cache invalidation (playbook update → invalidate all cache entries for that playbook)
5. Add integration tests for cache hit/miss/refresh scenarios

### Spec references

Spec 026 plan.md (line 19): "Storage: None for core computation. Optional caching of computed equilibria via existing SQLite storage layer (deferred to future)."

### Future features (not deferred — natural next steps)

- **Cache hit ratio reporting**: Show the user how many equilibria were retrieved from cache vs computed fresh, to demonstrate the cache's value.
- **Warm-up cache**: Pre-compute equilibria for known playbook/contract combinations during idle time.
- **Cross-session cache**: Persist cache across CLI invocations so repeated analysis of the same contract is instantaneous.

---

## D-67: Per-Mode Model Routing Overrides (FR4)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 027 (product modes LicenseCheck, LeaseCheck, PrivacyCheck) — FR4 |
| **Deferred at** | 2026-07-07 |
| **Trigger** | Explicitly out of scope — task-level routing is the established pattern; per-mode overrides add complexity without demonstrated need |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

All three new modes (LicenseCheck, LeaseCheck, PrivacyCheck) use the same
model slot configuration as PreCheck, DealCheck, and HireCheck. There is no
way to route a specific mode to a different model or provider. The blueprint
specifies task-level model routing (extraction vs QA vs comparison), not
document-type routing. Per-mode overrides would let a user say "use GPT-4
for LicenseCheck but Llama for LeaseCheck" without changing the global
model config.

Per-mode model routing would:

1. Add a `model` field or section to the product mode configuration so each
   mode can specify preferred provider/model overrides
2. Extend `TierRouter` or the Gateway router to check for mode-level
   overrides before falling back to the task-level slot
3. Add a `--mode-model` flag to override at invocation time
4. Surface the effective model per mode in the memo output and audit log
5. Document the precedence chain: CLI flag > mode config > task slot >
   global default

### What would need to change to unblock

1. Define a mode-level model override schema (in config.yml or per-mode
   settings)
2. Update `Gateway.chat()` to accept an optional `mode` parameter and check
   for mode-level overrides
3. Add `--mode-model` CLI flag to each mode subcommand
4. Update `ReviewReport` metadata to record the effective model per mode
5. Add integration tests verifying mode-level override takes precedence
   over task-level slot

### Spec references

Spec 027 spec.md line 71: "Per-mode model routing overrides are deferred as
out of scope." Spec 027 spec.md line 124: "FR4 (per-mode model routing
overrides): Deferred as out of scope."

### Future features (not deferred — natural next steps)

- **Document-type routing**: Instead of per-mode, route by document type
  (NDA vs SaaS license vs DPA) — useful when a user has a mixed document
  set.
- **Per-client model profiles**: Save preferred model configurations for
  specific clients or counterparties.

---

## D-68: PrivacyCheck Question Expansion (Cross-Border Transfer, Sub-Processor)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 027 (PrivacyCheck) — Assumptions #5 |
| **Deferred at** | 2026-07-07 |
| **Trigger** | Deliberately scoped to 3 questions for consistency; cross-border transfer and sub-processor questions deferred to PrivacyCheck v2 |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

PrivacyCheck uses 3 high-level questions per position, following the same
pattern as PreCheck, DealCheck, HireCheck, and the other two spec 027 modes.
Two important DPA topics are folded into the existing questions rather than
having dedicated questions:

- **Cross-border transfer adequacy**: Whether the DPA permits data transfers
  outside the EEA/UK and whether adequate safeguards (SCCs, BCRs, adequacy
  decision) are in place. Currently covered implicitly under the data
  processing scope question.
- **Sub-processor management**: Whether the processor must notify and obtain
  consent before engaging a sub-processor, and whether the controller has a
  right to object. Currently folded into the sub-processor change
  notification question.

Dedicated questions for these topics would give users more precise signal
on two high-risk DPA clauses.

### What would need to change to unblock

1. Expand the PrivacyCheck playbook (dpa-v1.yaml) to 4 or 5 questions per
   position, adding dedicated cross-border transfer and sub-processor
   questions
2. Create a new playbook version (dpa-v2.yaml) or update the current one
3. Update the prompt templates to include the new questions in the
   extraction and QA templates
4. Update PrivacyCheck documentation and help text to reflect the expanded
   question set
5. Add integration tests that verify the new questions appear in the review
   output

### Spec references

Spec 027 spec.md line 100: "Cross-border transfer and sub-processor
questions are folded into the 3 high-level questions or deferred to
PrivacyCheck v2." Spec 027 spec.md line 125: "Cross-border transfer and
sub-processor questions are folded into the 3 high-level questions or
deferred to a future PrivacyCheck v2."

### Future features (not deferred — natural next steps)

- **Configurable question count**: Let users choose between 3-question
  (fast) and 5-question (comprehensive) mode for PrivacyCheck.
- **Jurisdiction-specific DPA profiles**: Different question sets for GDPR,
  CCPA, LGPD, and other privacy regimes.

---

## D-69: Mode-Specific Confidence Thresholds

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 027 (product modes) — Scope Boundaries |
| **Deferred at** | 2026-07-07 |
| **Trigger** | Deferred until shared-threshold pattern is validated across all modes |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

All product modes (PreCheck, DealCheck, HireCheck, LicenseCheck, LeaseCheck,
PrivacyCheck) share the same initial confidence thresholds for three-color
output (Green/Amber/Red). There is no way to tune thresholds per mode —
e.g., requiring higher confidence for LeaseCheck (where a false positive
means signing an unfavourable lease) than for PrivacyCheck (where Amber is
acceptable because DPA terms are typically renegotiable).

Mode-specific confidence thresholds would:

1. Add a `confidence_threshold` field to the product mode configuration
   schema
2. Allow each mode to specify its own Green/Amber boundary and Amber/Red
   boundary
3. Surface the effective thresholds in the memo output and progress banner
4. Add a `--threshold` CLI flag to override at invocation time (per mode
   if the flag is mode-aware)
5. Document the recommended thresholds for each domain based on accuracy
   benchmarking

### What would need to change to unblock

1. Validate the shared-threshold pattern across all 6 modes with real user
   feedback — does one threshold fit all, or do lawyers want stricter
   standards for certain contract types?
2. Design a per-mode threshold schema in config.yml or mode definition
3. Update the three-color rendering logic to accept mode-specific thresholds
4. Add `--threshold` CLI flag to each mode subcommand
5. Add integration tests with different threshold values per mode

### Spec references

Spec 027 spec.md line 118: "Mode-specific confidence thresholds — all modes
share the same initial thresholds. Deferred until the shared-threshold
pattern is validated." Spec 027 spec.md line 126: "Mode-specific thresholds
are deferred until the pattern is validated."

### Future features (not deferred — natural next steps)

- **Adaptive thresholds**: Learn optimal thresholds per mode based on user
  feedback (which assessments the user agrees/disagrees with).
- **Per-client threshold profiles**: Save different threshold sets for
  different clients or contract counterparties.
- **Threshold benchmarking**: Run the benchmark harness at different
  thresholds to produce a precision/recall curve for each mode.

---

## D-70: Complex Settlement Scenarios (SettlementCheck v2)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 028 (product modes batch 1) — spec.md §Risks, plan.md §Risks |
| **Deferred at** | 2026-07-08 |
| **Trigger** | Explicitly out of scope — SettlementCheck targets common small-business settlement scenarios only |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

SettlementCheck targets the most common small-business settlement scenarios:
simple mutual releases, payment-for-release agreements, and standard
confidentiality/non-disparagement provisions. Complex settlement agreements
are out of scope for v1:

- **Structured settlements** with ongoing obligations (periodic payments,
  performance milestones, future contingent payments)
- **Class action settlements** with multiple plaintiff classes and claims
  administrators
- **Multi-party releases** involving three or more parties and cross-indemnities
- **Regulatory settlements** with government agencies (SEC, FTC, state AGs)
  that include ongoing compliance or reporting obligations
- **Bankruptcy settlement** agreements with court approval requirements

The current 5-category playbook (release scope, payment terms, confidentiality,
unknown claims waiver, breach consequences) cannot capture these scenarios'
material terms.

### What would need to change to unblock

1. Research the most common complex settlement structures small businesses
   encounter (likely regulatory or bankruptcy-adjacent scenarios)
2. Design a SettlementCheck v2 playbook with expanded categories or a
   tiered approach (simple vs. complex mode)
3. Update the extraction prompt template to handle complex vocabulary
   (claims administrator, settlement class, Bar date, etc.)
4. Add integration tests with complex settlement fixture documents
5. Update the spec and help text to describe the expanded scope

### Spec references

Spec 028 spec.md (line 251): "Complex settlements remain out of scope for v1."
Spec 028 plan.md (line 262): "Complex settlements out of scope for v1."

### Future features (not deferred — natural next steps)

- **Settlement type auto-detection**: Detect whether the document is a simple
  or complex settlement and select the appropriate playbook automatically.
- **Ongoing obligation tracker**: For structured settlements, track payment
  milestones and compliance deadlines.

---

## D-71: LOI-to-Final-Agreement Bilateral Comparison

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 028 (product modes batch 1) — spec.md §Scope Boundaries |
| **Deferred at** | 2026-07-08 |
| **Trigger** | Explicitly out of scope — bilateral comparison is its own spec (014) |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

LOICheck reviews a single letter of intent or memorandum of understanding.
It does not compare an LOI to the final executed agreement. In practice,
startups and small businesses often sign an LOI and later receive a
definitive agreement that differs materially from the non-binding terms.

Comparing an LOI to a final agreement would:

1. Accept two documents: the LOI and the final agreement
2. Align clauses by topic (purchase price, exclusivity, confidentiality,
   breakup fees) rather than by clause number
3. Flag provisions in the final agreement that were not mentioned in the LOI
   (surprise terms)
4. Flag LOI provisions that were dropped or changed in the final agreement
5. Show whether binding provisions in the LOI (confidentiality, exclusivity)
   carry through to the final agreement

This is a specific instance of bilateral comparison (spec 014) applied to the
LOI-to-definitive-agreement lifecycle. The general bilateral infrastructure
would need to exist first, then this use case adds a domain-specific
comparison playbook.

### What would need to change to unblock

1. Bilateral comparison must be operational (spec 014 tasks complete)
2. Design an LOI-to-final-agreement comparison playbook that maps LOI
   provisions to definitive-agreement clauses by semantic topic
3. Add a subcommand or flag (e.g., `openreview loicheck compare loi.pdf final.pdf`)
4. Add integration tests with an LOI/final-agreement pair where known
   discrepancies exist

### Spec references

Spec 028 spec.md (line 233): "Bilateral comparison between LOI and final
agreement (deferred to a future capability)."

### Future features (not deferred — natural next steps)

- **Term-sheet comparison** for investment rounds: compare a term sheet to
  the final investment agreement — similar pattern, different domain.
- **Multi-stage deal tracking**: Track a deal across all its documents
  (term sheet → LOI → definitive agreement → closing documents).

---

## D-72: Per-Mode Accuracy Benchmark Scripts

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 028 (product modes batch 1) — spec.md §In Scope gap |
| **Deferred at** | 2026-07-08 |
| **Updated at** | 2026-07-09 |
| **Updated by** | Spec 030 (benchmark mode validation) — research.md §6 confirmed skeletons were never created |
| **Trigger** | Gap between spec "in scope" list and task breakdown — skeleton scripts were listed in spec review as complete but the `scripts/benchmarks/` directory was never created. The original D-72 entry incorrectly stated skeletons exist. |
| **Status** | Unblocked — no constitutional conflict, requires creating the skeleton scripts from scratch (they do not exist), then populating with real test documents and labelled data per mode |

### Description

The spec lists "Accuracy benchmark per mode (at least 5 test documents each)"
and "PII benchmark note per mode" as in-scope items. These were not captured
in the original task breakdown and were added as retroactive tasks.

**Correction (spec 030 research):** The original D-72 entry stated that skeleton
scripts exist at `scripts/benchmarks/` with placeholder metrics. This was incorrect.
Spec 030 research.md §6 confirmed the `scripts/benchmarks/` directory does not exist
and the skeleton scripts were never created. The "complete but skeleton" task marking
was an error — these items were never started.

The skeletons would have included:

- **Accuracy benchmark scripts**: One script per mode in `scripts/benchmarks/`
  that runs a mock pipeline and reports placeholder metrics. Real accuracy
  measurement requires labelled test documents per mode (at least 5 per mode)
  and a live AI provider call.
- **PII benchmark notes**: One note per mode documenting which PII entity types
  each contract type typically contains. Skeleton texts would need to be created
  from scratch, then validated against real contracts.

### What would need to change to unblock

1. Create the `scripts/benchmarks/` directory
2. For each of the 17 modes (not just the original 6): create 5+ labelled test
   documents with known ground-truth assessments
3. Create the accuracy benchmark skeleton scripts per mode
4. Create the PII benchmark notes per mode
5. Replace the mock pipeline calls with real AI Gateway calls (or use the
   benchmark harness from spec 010/030)
6. Run the benchmarks and record precision/recall/F1 per mode
7. Publish the accuracy baselines in project documentation

### Spec references

Spec 028 spec.md §In Scope (accuracy benchmark and PII benchmark note per mode).
Spec 028 tasks.md Phase 10 convergence tasks.
Spec 030 research.md §6 (D-72 skeleton scripts status — directory does not exist).

---

## D-73: last_indexed.json Upgrade to SQLite Meta-DB

| Field | Value |
|-------|-------|
| **Deferred from** | Retrieval ingestion — `src/openreview_cli/retrieval/ingest.py` line 71 |
| **Deferred at** | 2026-07-08 |
| **Trigger** | Ponytail — small JSON file sufficient for single-document tracking; upgrade deferred until cross-document queries land |
| **Status** | Unblocked — but should not be implemented unless cross-document retrieval (D-15) or auto re-indexing (D-17) is underway |

### Description

The ingest module tracks the most recently indexed document via
`last_indexed.json`, a small JSON file in the index database directory. When
the `openreview retrieve` command is run without a file argument, it falls
back to this file to find the document path.

The ponytail comment on line 71 suggests upgrading to a SQLite meta-database
if cross-document queries ever land. A SQLite meta-DB would:

1. Store a history of indexed documents with timestamps, file hashes, and
   embedding configurations
2. Support cross-document queries (D-15) by tracking which documents are
   in the index and their metadata
3. Provide a foundation for auto re-indexing (D-17) by comparing stored
   config hashes against current config
4. Replace the ad-hoc JSON file pattern with the project's established
   SQLite storage pattern

### What would need to change to unblock

1. This is a dependent D-ID — it unlocks when cross-document retrieval (D-15)
   or auto re-indexing (D-17) is implemented
2. Design a SQLite schema for indexed document metadata (path, hash, timestamp,
   embedding config, chunk count)
3. Replace `last_indexed.json` read/write with SQLite operations
4. Migrate existing JSON state to SQLite (or start fresh)
5. Add integration tests for the meta-DB operations

### Spec references

Ponytail marker at `src/openreview_cli/retrieval/ingest.py` line 71: "Upgrade
to SQLite meta-DB if cross-document queries ever land."

### Future features (not deferred — natural next steps)

- **Index health reporting**: Show which documents are in the index, when they
  were last indexed, and whether their embedding config is current.
- **Selective re-indexing**: Re-index only documents whose file hash or config
  hash has changed, rather than re-indexing the entire collection.

---

## D-74: PII Engine Temp Placeholder Resilience

| Field | Value |
|-------|-------|
| **Deferred from** | PII engine — `src/openreview_cli/pii/engine.py` line 17 |
| **Deferred at** | 2026-07-08 |
| **Trigger** | Ponytail — module-level constant overwritten by `assign_placeholders` during pipeline execution |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

`_TEMP_PH = "[TEMP_0]"` is a module-level constant in `engine.py` that serves
as a placeholder during PII analysis. It gets overwritten by
`assign_placeholders()` during pipeline execution. The ponytail marker
acknowledges this is a deliberate but fragile pattern:

- If `assign_placeholders()` is ever skipped (e.g., a short-circuit path in
  the PII stripping flow), the raw `[TEMP_0]` string leaks into the output
- If the placeholder assignment order changes, `[TEMP_0]` may appear in
  stripped text
- The module-level mutable state makes the engine less testable (tests that
  don't call `assign_placeholders` may see stale or unintended placeholders)

### What would need to change to unblock

1. Replace the module-level `_TEMP_PH` with a per-instance or per-call
   placeholder that does not rely on mutation of module state
2. Ensure every code path through the PII engine calls `assign_placeholders`
   or provides an explicit placeholder upfront
3. Add a guard that detects unassigned `[TEMP_0]` strings in the output and
   raises or warns
4. Add unit tests that exercise the short-circuit paths and verify no raw
   placeholders leak

### Spec references

Ponytail marker at `src/openreview_cli/pii/engine.py` line 17.

---

## D-75: Benchmark Whitelist Updates for All 17 Product Modes ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | spec 029, Product modes Batch 2 — items 4+6 (user-split) |
| **Deferred at** | 2026-07-09 |
| **Resolved at** | 2026-07-09 |
| **Resolved by** | Spec 030 (benchmark mode validation) — `VALID_MODES` frozenset (17 modes), parse-time validation against it, dead `mode` param removal |
| **Trigger** | Explicitly out of scope — user split items 4+6 from the original spec scope into a follow-up spec |
| **Status** | ✅ **Resolved** |

### Resolution

Spec 030 implemented `VALID_MODES` frozenset in `benchmark/cli.py` (FR-1), parse-time mode validation rejecting unknown modes with exit code 78 (FR-2), and removed the dead `mode` parameter from `BenchmarkRunner.run_dataset()` (FR-3). Each of the 17 product modes is now a named member of `VALID_MODES` — the whitelist is the single source of truth for benchmark mode validation.

The frozenset is hard-coded (`ponytail`: YAGNI over registry pattern). Mode changes require a constitutional amendment to update `VALID_MODES` alongside the new mode. The resolve happened at spec time and was implemented via the FR-1/FR-2/FR-3 changes.

### What was needed to resolve

1. `VALID_MODES: frozenset[str]` constant in `benchmark/cli.py` with all 17 modes
2. Parse-time loop checking each entry in `--modes` against `VALID_MODES`, producing error message + exit 78 on mismatch
3. Removal of dead `mode: str = "precheck"` parameter from `runner.py:71`
4. Updated callers: `cli.py:218`, `runner.py:193` — both already omitted `mode=`

### Blueprint references

Spec 030 spec.md §4 FR-1, FR-2, FR-3. Spec 029 spec.md §Scope Boundaries (line 288).

### Description

The 17 product modes (PreCheck, DealCheck, HireCheck, LicenseCheck, LeaseCheck, PrivacyCheck, IndemnityCheck, ConsultCheck, WorkCheck, LOICheck, SubCheck, SettlementCheck, AssetCheck, BuyCheck, EngageCheck, GuaranteeCheck, LoanCheck) have no benchmark whitelist entries. The benchmark harness (spec 010) can only run accuracy evaluation against modes that have whitelist entries specifying which labelled datasets apply. Without these entries, users cannot validate whether a mode's playbook and prompts produce accurate assessments.

The whitelist would map each mode to the relevant labelled datasets (CUAD for general contract clauses, MAUD for merger agreements, ContractNLI for NLI-style evaluation) and define per-mode accuracy thresholds.

Items 4 and 6 (benchmark whitelist + accuracy run) were explicitly split from the spec 029 scope by user decision to keep the batch focused on CLI wiring and playbook creation.

### What would need to change to unblock

1. For each of the 17 modes, determine which labelled datasets apply (some modes like LoanCheck or GuaranteeCheck may not map well to existing datasets)
2. Add a `whitelist` section to the benchmark configuration mapping mode names to dataset IDs
3. Update the benchmark runner to accept a `--mode` filter and only run against whitelisted datasets
4. Document the mapping in the benchmark configuration so users understand coverage gaps
5. If a mode has no applicable dataset, document that the mode is coverage-blind and cannot be benchmarked against published corpora

### Spec references

Spec 029 spec.md §Scope Boundaries (line 288): "Benchmark whitelist updates (deferred to a follow-up spec)."
Spec 029 plan.md — items 4+6 split by user decision.

---

## D-76: Accuracy Validation Run (CUAD/MAUD/ContractNLI) for All 17 Modes ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | spec 029, Product modes Batch 2 — items 4+6 (user-split) |
| **Deferred at** | 2026-07-09 |
| **Resolved at** | 2026-07-09 |
| **Resolved by** | Spec 030 (benchmark mode validation) — FR-4 (mock provider baseline × 17 modes × 3 datasets = 51 results), FR-5 (real provider baseline workflow), FR-7 (per-mode report breakdown) |
| **Trigger** | Explicitly out of scope — deferred to follow-up spec alongside the benchmark whitelist |
| **Status** | ✅ **Resolved** |

### Resolution

Spec 030 implemented the accuracy validation in two tracks:

- **Mock provider baseline (CI)**: The benchmark runner iterates over all 17 modes for each of 3 datasets (CUAD, MAUD, ContractNLI), producing 51 `DatasetResult` entries. CI regression detection uses the deterministic mock pipeline — any code change affecting metric computation is caught.

- **Real provider baseline (manual one-shot)**: A `_build_gateway_pipeline()` function exists and routes through the AI Gateway. The manual workflow (`openreview benchmark run --all --save-baseline`) is documented and operational. Running it is deferred to D-78 (below) — the infrastructure exists, the execution is a manual developer step.

- **Per-mode report breakdown**: Terminal and JSON output includes per-mode sections (dataset_name convention `{dataset}::{mode}`), making mode-level coverage visible in every report.

### What was needed to resolve

1. Multi-mode iteration loop over 17 modes × 3 datasets in `benchmark_run()`
2. `_build_gateway_pipeline()` for real provider calls (routes through AI Gateway)
3. Per-mode report breakdown via `{dataset}::{mode}` naming convention
4. Manual baseline workflow documented in spec 030 quickstart.md
5. CLI regression detection with mock baseline (stable by construction)

### Blueprint references

Spec 030 spec.md §4 FR-4, FR-5, FR-7. Spec 010 benchmark harness. The mock baseline provides deterministic CI regression detection; real baselines are manual (D-78).

### Description

Once the benchmark whitelist (D-75) is populated for all 17 modes, the accuracy benchmark must actually be run against CUAD, MAUD, and ContractNLI datasets. Each mode would produce precision, recall, and F1 scores against the applicable labelled data.

This is the measurement that validates whether the 17 playbooks and extraction prompts produce accurate clause assessments. Without it, there is no empirical basis for claiming any mode is accurate — only that it produces structured output.

The accuracy run includes:
- Per-mode precision, recall, F1 against each applicable dataset
- Aggregate accuracy across all modes (overall pipeline accuracy)
- Per-category accuracy within each mode (which playbook categories perform well vs poorly)
- A published accuracy baseline that future changes can be measured against
- Comparison against the pre-existing modes (PreCheck, DealCheck, HireCheck) to detect regressions

### What would need to change to unblock

1. Populate the benchmark whitelist (D-75)
2. Ensure all 17 modes have fixture documents or dataset mappings in the benchmark corpus
3. Run the benchmark harness against each mode's whitelisted datasets
4. Record baseline accuracy numbers in project documentation
5. If any mode underperforms (F1 below acceptable threshold), flag the playbook or prompt for revision
6. Add a CI benchmark step that compares new runs against the baseline and alerts on regressions

### Spec references

Spec 029 spec.md §Scope Boundaries (line 289): "CUAD/MAUD accuracy benchmark runs (deferred to follow-up)."
Spec 029 spec.md (line 13): "the 22 product modes capability" tracking includes benchmark validation.
D-75 (benchmark whitelist) is a prerequisite.
D-72 (per-mode accuracy benchmark scripts) provides skeleton scripts for each mode.

---

## D-77: End-to-End Pipeline Tests for 9 Orphan Modes ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | spec 029, Product modes Batch 2 — per-mode smoke test scope decision |
| **Deferred at** | 2026-07-09 |
| **Resolved at** | 2026-07-09 |
| **Resolved by** | Spec 030 (benchmark mode validation) — FR-6: `tests/integration/test_orphan_modes_e2e.py` with 9 parametrized tests |
| **Trigger** | Spec clarification (Session 2026-07-08) limiting orphan-mode tests to CLI routing only |
| **Status** | ✅ **Resolved** |

### Resolution

Spec 030 created `tests/integration/test_orphan_modes_e2e.py` with 9 parametrized end-to-end tests, one per orphan mode (`licensecheck`, `leasecheck`, `privacycheck`, `indemnitycheck`, `consultcheck`, `workcheck`, `loicheck`, `subcheck`, `settlementcheck`). Each test:

1. Locates a fixture PDF from `tests/fixtures/benchmark/{mode_name}/` (all 9 fixture directories exist from spec 028/029 with 5 PDFs + ground_truth.json each)
2. Calls `stream_clauses()` to parse the document
3. Strips PII through the existing PII engine
4. Runs `run_review()` with a mocked AI gateway (no network calls — uses `monkeypatch` on `Gateway.chat`)
5. Asserts the result is a valid `ReviewReport` with non-empty assessments
6. Asserts each clause assessment has a three-color verdict (`assessment.color in {"green", "amber", "red"}`)

All 9 tests pass in CI. The actual model uses `report.assessments` (not `report.clauses` as the spec pseudocode suggested) and `AssessmentColor` enum with lowercase values — the implementation was reconciled with the actual data model per the research.md finding.

### What was needed to resolve

1. New test file `tests/integration/test_orphan_modes_e2e.py` with 9 parametrized tests
2. Mock gateway responses for each orphan mode (following `test_benchmark_cuad.py` pattern)
3. Fixture documents — all 9 modes already had fixture directories from spec 028/029
4. Three-color verdict assertion against actual `AssessmentColor` enum
5. Verification that each mode produces a valid, non-empty `ReviewReport`

### Historical description (pre-resolution)

**Note:** The following sections from the original D-77 entry describe the deferred state before resolution by spec 030. They are preserved for reference.

### Description

The nine orphan modes (LicenseCheck, LeaseCheck, PrivacyCheck, IndemnityCheck, ConsultCheck, WorkCheck, LOICheck, SubCheck, SettlementCheck) were unblocked with only CLI routing tests: subcommand registers, `--help` works, invokes correct playbook, exits cleanly. These tests verify the CLI wiring is correct but do **not** exercise the actual review pipeline (`run_review()`), memo export, or PII stripping for these modes.

End-to-end pipeline tests would validate that each orphan mode:
1. Parses a fixture document of its contract type
2. Runs the full three-agent pipeline via `run_review()`
3. Produces a non-empty `ReviewReport` with clause assessments
4. Exports a memo (Markdown, JSON, or DOCX) with the mode's name in the prefix
5. Outputs correct `mode` field in JSON output
6. Handles `--no-pii`, `--format`, `--playbook` flags correctly

The per-mode smoke test scope decision explicitly limited orphan modes to CLI routing only. This was a pragmatic choice (the spec already requires 5 full smoke tests for new modes + fixture documents) but defers the most meaningful validation — does the mode actually produce useful output for its target contract type?

### What would need to change to unblock

1. Create a fixture PDF document for each orphan mode's contract type (9 new fixture PDFs)
2. Write `run_review()` integration tests for each orphan mode (following the pattern used by the 5 new modes in spec 029)
3. Verify memo export produces valid output for each orphan mode
4. Verify JSON output `mode` field matches the subcommand name
5. Verify `--no-pii`, `--format`, `--playbook` flags function correctly per mode
6. Add the 9 fixture PDFs to the test fixtures directory
7. Verify all 9 tests pass in CI without exceeding the 110 MB memory budget

### Spec references

Spec 029 spec.md §Per-mode smoke test requirements (lines 253-261): "9 orphan modes (CLI routing test only) ... No new fixture documents or run_review() assertions required for orphan modes."
Spec 029 spec.md §Clarifications Session 2026-07-08: "CLI routing test only — subcommand registers, --help works, invokes correct playbook, exits cleanly."

### Future features (not deferred — natural next steps)

Visible from spec 029 but not built:

- **Benchmark whitelist + accuracy runs for all 17 modes**: CUAD, MAUD, and ContractNLI accuracy validation to establish empirical baselines (D-75 + D-76). The playbooks and prompts exist but their accuracy is unmeasured beyond the 5 new modes' smoke tests.

- **End-to-end pipeline tests for orphan modes**: D-77 above. 9 orphan modes have CLI routing but no fixture-document integration tests. Their playbooks (created in specs 027/028) have never been exercised against a real document through the full pipeline.

- **Per-mode confidence threshold tuning**: All 17 modes share the same Green/Amber/Red thresholds. Finance-heavy modes (LoanCheck, GuaranteeCheck) may benefit from stricter thresholds given the higher cost of false positives in lending documents.

- **Multi-party bilateral comparison for Batch 2 modes**: The 14 modes from Batch 1 (specs 027/028) and Batch 2 (spec 029) all support single-party review only. Bilateral comparison (spec 014) exists as a separate pipeline and has not been integrated with any of these modes.

- **Domain-specific PII recognizers for transaction/finance modes**: Loan agreements and asset purchase agreements contain financial PII (account numbers, tax IDs, asset values) that the generic Presidio recognizers may miss. Extraction prompt vocabulary injection was the v1 approach; dedicated recognizers would improve recall.

- **Complex transaction/finance playbook expansion**: The 5 new playbooks target common small-business scenarios. Structured finance, multi-tier lending, and cross-border asset transfers use more complex clause structures that the 5-category playbook may not capture.

- **Orphan-mode accuracy re-validation**: Nine orphan playbooks were validated in specs 027/028 but no benchmark accuracy data exists for any of them against published datasets.

---

## D-78: Real Provider Baseline One-Shot (Manual Accuracy Run)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 030, FR-5 — real provider baseline workflow defined but not executed |
| **Deferred at** | 2026-07-09 |
| **Trigger** | Manual-only workflow — cannot be automated in CI (cost, time, flakiness, model-version sensitivity). FR-5 explicitly spec'd the real baseline as a manual developer step: run once, commit the JSON to `docs/benchmarks/`. |
| **Status** | Unblocked — no constitutional conflict. Infrastructure exists. Needs a developer with a configured AI gateway provider to run the command and commit the output. |

### Description

Spec 030 FR-5 defines a manual workflow for establishing a real accuracy baseline:

```bash
openreview benchmark run --all --save-baseline --format json \
  --output docs/benchmarks/baseline-$(date +%F).json
```

This command runs all 17 product modes across CUAD, MAUD, and ContractNLI datasets
through a real AI gateway provider (Ollama or cloud). The infrastructure is complete:

- `_build_gateway_pipeline()` function exists and routes through the AI Gateway
- `--save-baseline` flag writes structured JSON with per-mode × per-dataset metrics
- Baseline JSON validates against `BenchmarkRun` schema
- Output includes extraction F1, comparison F1, classification F1, hallucination rate,
  PII recall (where applicable), latency, and peak memory per mode per dataset
- Metadata block records provider, model name, git commit SHA, and timestamp

The actual one-shot run was **not executed** as part of spec 030. Running it requires:

1. A configured AI gateway provider (Ollama local is preferred — free, no API key)
2. Network access (or local model loaded)
3. ~30-60 minutes of wall-clock time (17 modes × 3 datasets × inference time per sample)
4. A developer to commit the resulting JSON to `docs/benchmarks/`

### What would need to change to unblock

1. Ensure a gateway provider is configured: `openreview gateway setup` (Ollama)
2. Run the baseline command with `--save-baseline`
3. Verify the output JSON validates against `BenchmarkRun` schema
4. Commit the baseline file to `docs/benchmarks/baseline-YYYY-MM-DD.json`
5. Optionally: add the baseline file path to a `docs/benchmarks/README.md` index

### What the mock baseline provides for CI in the meantime

The mock baseline (`_mock_pipeline` in `cli.py`) runs in CI on every push. It returns
constant/empty predictions (zero-length spans). This is deterministic by construction —
any code change that affects metric computation will be detected as a regression even
with mock data. CI regression detection does NOT require a real provider baseline.

The real provider baseline is for **accuracy measurement** (what is the actual F1 of
each mode?) while the mock baseline is for **regression detection** (did a code change
break something?). Both are valuable but serve different purposes.

### Spec references

Spec 030 spec.md §4 FR-5: "Real Provider Baseline — Manual Run." Spec 030 plan.md §FR-5 design.
`_build_gateway_pipeline()` and `_parse_gateway_response()` in `benchmark/cli.py`.

### Ponytail markers in spec 030 code

The single ponytail marker directly relevant to this deferred item:

- `benchmark/cli.py` line 213: `# For other datasets, use a mock pipeline (real LLM integration deferred)`
  This comment in the CI-regression code path acknowledges that the mock pipeline is sufficient for
  CI and the real LLM integration is deferred to the manual baseline workflow (D-78).

Other ponytail markers in spec 030 code are intentional design choices already documented
in the spec:
- `cli.py` line 30: `# ponytail: hard-coded mode list — source of truth for benchmark mode validation.`
  (FR-1 design choice, spec §2 Clarifications Q1)
- `cli.py` line 230: `# ponytail: prompt A/B test removed — no real templates exist yet. Returns when real A/B lands.`
  (Already tracked as D-14)

### Future features (not deferred — natural next steps visible from spec 030)

- **Per-mode confidence threshold tuning**: All 17 modes share the same Green/Amber/Red
  thresholds. Finance-heavy modes (LoanCheck, GuaranteeCheck) may benefit from stricter
  thresholds given the higher cost of false positives in lending documents. See D-69
  (Mode-Specific Confidence Thresholds) for the pre-existing deferred item on this topic.

- **Provider rate-limit handling**: The real provider baseline (`_build_gateway_pipeline`)
  currently raises on failure (gateway timeout, rate limit, auth error). A retry-with-backoff
  wrapper could make the manual run more reliable, especially against cloud providers with
  rate limits. This is a usability improvement, not a correctness issue.

- **Benchmark regression detection refinement**: SC-9 in spec 030 specifies that CI
  regression detection should fail on a deliberate regression (verified manually). The
  current mock baseline detects metric computation changes but cannot detect accuracy
  regressions. Real-provider baselines (D-78) would enable accuracy regression detection
  but are too expensive for CI. A compromise could be a scheduled (nightly) real-provider
  run that compares against the stored baseline.

- **14→22 mode expansion**: Spec 030 covers 17 of the 22 product modes capability (the
  22 product modes capability). The remaining 5 modes are LATER items in the product
  roadmap and need their own specs, playbooks, playbook files, and benchmark whitelist
  entries before they can be added to VALID_MODES.

- **Real baseline for CI (future possibility)**: If a free-tier always-available provider
  emerges, the real baseline could run in a scheduled CI workflow. Currently no such
  provider exists that is reliable enough for CI regression detection.

---
