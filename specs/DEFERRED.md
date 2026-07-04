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

## D-3: Playbook Version Diff

| Field | Value |
|-------|-------|
| **Deferred from** | playbook versioning feature / spec 017 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope (append-only storage was the goal) |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

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
| **Trigger** | Ponytail — structural substring match sufficient for v1 |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

CR (Citation Relevance) measures whether a claim text actually appears in
the cited clause. The v1 implementation uses a simple case-insensitive
`in` substring operator (`claim_text.lower() in clause_text.lower()`).
This catches exact-match relevance but misses semantic equivalence
(e.g., "confidential info" ≠ "Confidential Information" as defined in
§1.1 of the agreement).

### What would need to change to unblock

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
| **Trigger** | Ponytail — clause paragraph metadata not available upstream |
| **Status** | Unblocked when clause model tracks paragraph count |

### Description

CL (Citation Locality) measures whether the cited paragraph index is
valid. The v1 implementation checks `paragraph_index >= 0` but does not
validate against the actual number of paragraphs in the cited clause.
This means a claim citing "clause 4.3, paragraph 999" passes CL when it
should fail.

### What would need to change to unblock

1. Add a `paragraph_count` field to the `Clause` dataclass in
   `src/openreview_cli/parsing/models.py`
2. Populate it during document parsing (paragraph detection already works
   in the PDF/DOCX parsers but isn't exposed as a count)
3. Update `compute_cg_metrics()` in
   `src/openreview_cli/grounding/metrics.py` to validate
   `paragraph_index < clause.paragraph_count`

### Blueprint references

FR-005 (CL metric). Spec 007 (chunking) produces paragraph-level metadata
that could populate this field.

---

## D-6: Multi-Party / Other Mode Integration

| Field | Value |
|-------|-------|
| **Deferred from** | N-5 / spec 012 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly scoped to single-party review (v1) |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

### Description

The citation grounding discriminator integrates with the single-party
review pipeline (`openreview precheck`). Other product modes (HireCheck,
DealCheck, and future multi-party comparison) do not have grounding
integration yet. Each mode will need its own grounding wiring.

### What would need to change to unblock

1. For each new product mode: wire grounding into the mode's review
   pipeline (same pattern as `review/__init__.py` spec 012 integration)
2. If the mode uses a different output format, extend report formatting
   accordingly (see `review/report.py` spec 012 changes)

### Blueprint references

the multi-party comparison research gap, three-color output (Green/Amber/Red per clause) depends on
grounding. Spec 012 spec.md §"Single-party review only (v1)".

---

## D-7: CG-DPO Full Pipeline — dedicated CG-DPO model (citation grounding capability)

| Field | Value |
|-------|-------|
| **Deferred from** | N-5 / spec 012 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | dedicated CG-DPO model (citation grounding capability) at research-proven concept, not yet production-ready — needs parallel spec |
| **Status** | Unblocked when dedicated CG-DPO model (citation grounding capability) reaches production-ready |

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

---

## D-8: Multi-file Document Sets (Amendments and Exhibits)

| Field | Value |
|-------|-------|
| **Deferred from** | Spec 014 (bilateral comparison) §9 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope — NX-1 pilot takes a single document per party |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

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

## D-16: Retrieval-Augmented Generation (RAG)

| Field | Value |
|-------|-------|
| **Deferred from** | Retrieval feature / spec 018 |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope in the spec |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

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

## D-20: AI-suggested Playbook Changes

| Field | Value |
|-------|-------|
| **Deferred from** | spec 017 — playbook versioning |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope — versioning stores, does not suggest |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

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

---

## D-21: Playbook Management (Edit, Delete, Rollback)

| Field | Value |
|-------|-------|
| **Deferred from** | spec 017 — playbook versioning |
| **Deferred at** | 2026-07-04 |
| **Trigger** | Explicitly out of scope — append-only model is intentional for audit integrity |
| **Status** | Unblocked — no constitutional conflict, just not built yet |

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
