# Research — Spec 035 Post-Measurement Cleanup

Phase 0 output. Every technical claim below is anchored to an item in
`.specify/memory/verified-sources.md` (referenced as **VS**: `<item name>`); an item whose raw
artifact is not in the repo is labelled **CONFIRMED-EXTERNAL** and is not re-verifiable here, and
claims that are reasoned rather than proven are labelled **Inference** or **UNVERIFIED** with the
reason, per the constitution's Research Grounding Rule. Numeric evidence is reproduced
in the "Measurement evidence" section.

Source of the reasoning: the 14 settled decisions and 12 warnings in the measurement
decision record `draft/measurement-decisions-2026-09-29.md` (gitignored), the tracked
receipt `docs/benchmarks/results/slot-measurement.md` / `.json`, and direct reads of the
project code listed as VS items.

---

## Research questions (one per settled decision)

### Q1 — How are grounding's known-good and known-bad claims produced? (Decision 1)

**Decision:** Generate known-bad claims from real clauses with the existing corruption
generator, but only after repairing it and adding a guard; known-good claims are verbatim
sentences from the cited clause.

**Rationale:** The generator already targets real clause text, so no new corpus is needed
(*VS: Grounding corruption generator*). But as written it cannot supply correct labels:
two functions edit the claim *text* with a string replace that no-ops on prose (returning
the claim unchanged), one leaves the clause text unchanged so the claim stays supported,
and the fabricated set is ten fixed sentences, one of which is genuinely supported by an
indemnity clause (*VS: Grounding corruption generator*; record W12). The scoring target
takes the clause text directly — `ground_claim(claim_text, cited_clause_id, clause_text)` —
so any source of real clause text works (*VS: Grounding ground_claim signature*).

**Alternatives considered:**
- *Repair and use the orphan fixture* — it has zero consumers and carries no source clause
  text, so it cannot be a label set (*VS: Orphan grounding fixture*). Rejected.
- *Commission a human-labelled corpus* — a separate annotation task, out of scope.
- *Score with the existing structural metrics* — see Q14; it returns 1.0 when nothing is
  grounded (*VS: Structural grounding metrics*). Rejected as the accuracy signal.

### Q2 — Which full-text tokenizer ships? (Decision 2)

**Decision:** `porter unicode61`.

**Rationale:** Re-measured with the committed harness `scripts/measure_retrieval_accuracy.py`
over the committed CUAD benchmark (4,042 labelled queries, 462 contracts), `porter` stemming beat
plain `unicode61` by +1.24 hit@1, +6.58 hit@5 and +2.73 MRR@5 (receipts
`docs/benchmarks/results/cuad-retrieval-porter.json` and `cuad-retrieval-unicode61.json`; see
Measurement evidence and *VS: CUAD keyword retrieval receipts*). The figures this decision was
originally recorded with (+1.7 hit@1 / +2.1 hit@5 / +1.9 MRR over 1,536 queries) came from a
harness that was never committed and are **not citable**; the committed pair reproduces the
*direction* (porter ahead on all three metrics) but not the old *magnitudes*. Both tokenizers
are built into the shipped SQLite, so this is a one-line change with **no new dependency**
(*VS: SQLite FTS5 tokenizers*; *VS: Retrieval FTS tokenizer site*).

**Alternatives:** keep `unicode61` (measurably weaker); `trigram` (supported, but no
measured gain and a larger index).

### Q3 — Keep the `embedding` slot? (Decision 3)

**Decision:** Drop it.

**Rationale:** A local dense model scored 0.104 / 0.505 / 0.238 (hit@1 / hit@5 / MRR)
against keyword search at 0.126 / 0.519 / 0.258 — worse on every metric — for about 20 minutes
of CPU and a model held in memory. That comparison came from the same harness that was never
committed and is **not citable**; the reproducible re-run on the committed benchmark covers only
the two tokenizer arms (*VS: CUAD keyword retrieval receipts*), and with the `embedding` slot
gone the dense path cannot run at all (Q13). Cloud embeddings are ruled out by the privacy
claim. The embedding store (table, columns, insert path) is project code with a known schema
(*VS: Embedding store schema*).

**Alternatives:** keep local dense (needs a bundled model or a local server); keep cloud
dense (privacy); keep hybrid (needs dense, and was not better — Q13).

### Q4 — Is `reasoning` a bug to fix or a slot to remove? (Decision 4)

**Decision:** Wire it — it is a wiring problem, not a provider problem.

**Rationale:** No product code calls the slot; only the `gateway test` branch exercises it
(*VS: No reasoning/graph model caller*). The cause is code, so the fix is
code. Decision 10 then defines what wires it.

**Alternatives:** delete the slot (Q8 keeps it because the checker needs a socket); leave it
dead (leaves a user-visible slot that does nothing).

### Q5 — Does the `graph` feature need fixing? (Decision 5)

**Decision:** No bug to fix in the feature; remove the `graph` *slot*; add TUI access (Q11).

**Rationale:** The graph is rule-based and makes no model call, so the slot has no caller at
all (*VS: Graph tree renderer and annotations* shows the renderer; the builder is regex
only). A live smoke test ran `parse → build → metrics → view → health` all at exit 0 on two
fixtures. The flat output is expected for unnumbered input, and a flat graph scoring 100/100
is documented intent (*VS: Graph health weights*).

**Alternatives:** make the graph an AI feature (new work, unsupported by any observed
breakage — record §1.7); hunt for a bug (none observed).

### Q6 — When are the measurements re-run? (Decision 6)

**Decision:** Only after these changes land.

**Rationale:** The tokenizer change and the slot removal invalidate the current numbers, and
the measurement harness itself needed a fix (it had to initialise the app database and drop
errored assessments, or every call failed and a fallback faked recall). Re-running before
the change would re-measure the surface being deleted.

**Alternatives:** re-run now (measures the old surface and spends cloud budget).

### Q7 — Replace the reranker with a local model, or remove it? (Decision 7)

**Decision:** Remove the `reranking` slot; do not swap in a local reranker.

**Rationale:** Measured on 424 labelled CUAD queries at the product's candidate depth: the
plain BM25+`porter` order scored 0.108 / 0.535 / 0.252; a cheap lexical rerank scored
0.092 / 0.448 / 0.207; a local cross-encoder scored 0.085 / 0.427 / 0.199. Both rerankers
made ordering **worse than doing nothing** (the cross-encoder −10.8 points hit@5). The
best measured configuration is simply keyword search with `porter` (Q2). The reranking slot
is also unreachable in the retrieval path under both remaining tiers (*VS: PrivacyTier members
and tier rules*).

**Alternatives:** bundle a local cross-encoder (worse); cloud rerank (privacy); keep it
opt-in and disabled (dead weight). *Why* the local rerankers lose is **Inference**
(small model / truncation / the task) — unproven, and not needed to justify removal.

### Q8 — Which slots remain? (Decision 8)

**Decision:** Three — `extraction`, `reasoning`, `grounding`.

**Rationale:** `embedding` (Q3), `reranking` (Q7) and `graph` (Q5) are all dead. The clause
clustering option loads a local legal model through the model library directly and never
touches the gateway, so it is unaffected (*VS: Clause clustering model path*). The
sentence-embedding library is not installed, so the surface stays inside the spec (*VS:
Clause clustering model path*). The slot constant to change is project code (*VS: Slot set*).

**Alternatives:** keep the `graph` slot (no caller); keep `embedding` (Q3).

### Q9 — How many privacy modes? (Decision 9)

**Decision:** Two — `maximum` and `balanced`; keep accepting an old `performance` value and
treat it as `balanced`.

**Rationale:** With the embedding work gone, the only rule distinguishing `balanced` from
`performance` disappears, so they collapse into one mode (*VS: PrivacyTier members and tier
rules* — the rules are `llm_local_only`, `embeddings_local_only`, `pii_required_before_cloud`).
The compatibility point is a real trap: the configuration loader validates the tier against a
schema **before** the tier parser runs, so narrowing the schema would make an old
`performance` value raise a validation error instead of falling back (*VS: PrivacyConfig
tier literal*). The value must stay accepted and normalize to `balanced`.

**Alternatives:** keep a third no-op name as an alias (dishonest surface); make it genuinely
distinct by keeping a slot local (would require a local text model and break the
cloud-only setup `balanced` exists to serve).

### Q10 — What is `reasoning`? (Decision 10)

**Decision:** `reasoning` is the checker (QA) socket; point `qa_model` at it.

**Rationale:** The reader (`extraction`) and the checker (QA) are two separate model calls
per clause with separate prompts and separate files; today they share one model because the
QA model defaults to the extraction slot (*VS: QA model default* — four call sites:
`review/pipeline.py:97`, `review/runner.py:96-97`, `bilateral/__init__.py:153-154`,
`app.py:2039`). Giving the checker its own slot makes it independently configurable. With
FR-012 both slots ship the same default model, so out-of-the-box behaviour is unchanged; the
point is that the checker can later be pointed at a stronger model without touching the
reader (record R2). The literature supports separating extraction from verification
(Q-lit-1, Q-lit-2 below). No fallback machinery is needed because every slot ships a default.

**Alternatives:** run a reader-vs-checker size A/B (explicitly declined by the user);
delete `reasoning` (Q8).

### Q11 — What exactly does the graph work consist of? (Decision 11)

**Decision:** Leave the feature alone; remove the slot; add the missing parent-linking test;
add TUI build/view screens.

**Rationale:** The feature works (Q5). Three real gaps: the parent-linking function that the
whole hierarchy depends on has no tests at all (*VS: Clause hierarchy bridge*); the TUI has
no build and no view, only a read-only metrics screen, and its graph wrapper builds a graph
in memory then discards it (*VS: TUI domain graph builder*); and the parity matrix reports
`graph build` / `graph view` as matched to the TUI on a shared name-token join only — a
caveat the generator itself states (*VS: CLI/TUI parity matrix graph rows*). The tree screen
is net-new UI work, reusing the existing worker/busy pattern (*VS: TUI worker/busy pattern*)
and reachable from the result screen's existing binding (*VS: TUI result graph binding*).

**Alternatives:** treat the flat output as a bug (not supported by any observed breakage);
fold the screen into the existing read-only summary screen (rejected — that screen's contract
is read-only metrics, and the chosen deliverable is a single build-and-show screen; the one
thing the two can share, the domain build path, is taken).

### Q12 — Which models ship as defaults? (Decision 12)

**Decision:** `ollama/granite4:3b` for all three remaining slots.

**Rationale:** The previously shipped reader default scored 0.0 position accuracy with 11
failures in 4,015.9 s, versus `granite4:3b` at 0.9 with 0 failures in 279.6 s (see
Measurement evidence). The code has no way to disable a model's "thinking" mode, so
"keep the old default and turn thinking off" is not available without new work.

**Alternatives:** move only the reader while the checker keeps the larger model of the same
family that produced the timeouts; leave the defaults and raise the timeout only. Both
rejected. **Caveat**: the reader comparison used five documents, so 0.9 vs 0.7 may be noise;
the old default's unusability is not (**Inference** on the ranking, per record R1).

### Q13 — Delete meaning-based search? (Decision 13)

**Decision:** Delete `dense` and `hybrid` completely.

**Rationale:** With the embedding slot gone the dense path cannot run (it calls the gateway's
embedding method); the fusion helper exists only to combine hybrid; the engine dispatches
three methods (*VS: Retrieval engine dispatch*); the method constant lists three (*VS:
Retrieval methods*); the CLI exposes a `--method` flag and prints the method (*VS:
Ingest/retrieve --method option*); the embedding store is removed with it (*VS: Embedding
store schema*). Keyword search stays as the only mode that always works.

**Alternatives:** keep hybrid (needs dense), keep dead code (violates minimalism).

### Q14 — Build a grounding-accuracy harness, and how to score it? (Decision 14)

**Decision:** Build it; score bad-claims-caught, good-claims-wrongly-rejected and latency;
run a local arm and a cloud arm.

**Rationale:** Today grounding cannot be scored: strict mode removes unsupported claims
before the report, so the surviving counts can never show a miss — measured 7 claims in, 7
grounded, 0 ungrounded (*VS: Slot measurement receipt (tracked)*). The structural metrics
function is the wrong signal: it computes structural CP/CR/CL over grounded verdicts only and
returns **1.0 for everything when nothing is grounded** (*VS: Structural grounding metrics*),
so a grounding that rejects everything would score perfect. That function is consumed in
production, so its behaviour stays untouched (*VS: Structural grounding metrics*). The
scoring target takes the clause text directly (*VS: Grounding ground_claim signature*), so no
document plumbing is needed.

**Alternatives:** score with the structural metrics (wrong signal); use the orphan fixture
(no source text); skip measurement (leaves the primary uncertainty unmeasured).

---

## Measurement evidence

Reproduced here because the decision record is gitignored; this is the tracked home.

### Reader (extraction) — position accuracy, 5 synthetic documents

| model | position accuracy | extraction failures | review seconds |
|---|---|---|---|
| `ollama/granite4:3b` | **0.9** | **0** | **279.6** |
| `ollama/gemma3:4b` | 0.7 | 0 | 554.1 |
| `ollama/phi4-mini:3.8b` | 0.7 | 0 | 486.7 |
| `openrouter/anthropic/claude-sonnet-4.6` | 0.7 | 0 | 116.0 |
| `ollama/qwen3:4b` (**previously shipped default**) | **0.0** | **11** (60 s timeouts) | **4,015.9** |

Source: *VS: Slot measurement receipt (tracked)* — `docs/benchmarks/results/slot-measurement.md`
and `.json`. Category recall is not a model metric: the category is resolved by lexical
matching before any model call, and the fixtures embed the category name; only the position
is the model's work. n = 5 documents → single samples (**Inference**; record R1).

### Retrieval — 4,042 labelled CUAD queries (committed benchmark)

Every query in the committed CUAD benchmark; each of the 462 contracts is indexed alone with the
shipped FTS5 configuration and searched with the product chunker and ingest path; retrieval is
scoped to each query's own contract; ground truth = character-span overlap between the retrieved
chunk and the query's CUAD answer span. Measured by `scripts/measure_retrieval_accuracy.py`
(~48 s per arm).

| arm | hit@1 | hit@5 | MRR@5 |
|---|---|---|---|
| plain `unicode61` (no stemming) | 0.0312 | 0.2548 | 0.1001 |
| **`porter unicode61` (shipped)** | **0.0435** | **0.3206** | **0.1274** |

`porter` − `unicode61` = **+1.24 hit@1 / +6.58 hit@5 / +2.73 MRR@5**. Source: *VS: CUAD keyword
retrieval receipts* — `docs/benchmarks/results/cuad-retrieval-porter.json` and
`cuad-retrieval-unicode61.json`; the same comparison is summarised in the "CUAD keyword
retrieval" section of `docs/BENCHMARKS.md`. **Provenance:** the decision was originally recorded
against a **1,536-query** comparison whose harness was never committed (the raw run lived in
session scratch and is gone), so the previous figures — **+1.7 hit@1 / +2.1 hit@5 / +1.9 MRR**
and the dense/hybrid rows of the old table — are **not reproducible and not citable**. This pair
is the re-derivation on the committed set: it confirms the *direction* of the shipped choice
(porter ahead on all three metrics) but not the old *magnitudes*. Both arms are weak in absolute
terms — keyword search returns the gold span first for only ~4% of queries, largely because the
benchmark queries carry a long contract-identifying preamble that BM25 matches against
title/signature blocks — so the defensible claim is that `porter unicode61` is **the better of
two weak configurations**, not that retrieval works. The dense and hybrid arms were never
re-measured (the `embedding` slot is gone and the path is deleted — Q13); the tracked
tokenizer/engine facts the decision relies on are separately anchored (*VS: Retrieval FTS
tokenizer site*, *VS: Retrieval engine dispatch*). The harness reuses the product chunker and
ingest path but not the product parser (PDF/DOCX only), so chunk boundaries approximate a real
parse (**stated in the receipts**).

### Reranking — 424 labelled CUAD queries at candidate depth 20

| arm | hit@1 | hit@5 | MRR@5 |
|---|---|---|---|
| **BM25 + `porter` (no rerank)** | **0.108** | **0.535** | **0.252** |
| + cheap lexical rerank | 0.092 | 0.448 | 0.207 |
| + local cross-encoder rerank | 0.085 | 0.427 | 0.199 |

Both rerankers made ordering worse than leaving the keyword order alone (−10.8 points hit@5
for the cross-encoder). Source: *VS: Measurement decision record (gitignored companion)*,
§1.5. *Why* is **Inference**/unproven.

### Grounding — verdicts

Strict mode: 7 claims assessed, 7 grounded, 0 ungrounded/uncertain after strict filtering;
surviving counts cannot show misses. Source: *VS: Slot measurement receipt (tracked)*. A
lenient re-run was blocked by a provider key limit; cloud re-runs are unblocked by the user's
token purchase (record W10, parked).

---

## Literature leads (record §6, searched 2026-09-30)

**Q-lit-1 — Should extraction and verification be separate steps?** Yes.
- **RCBSF** (multi-agent contract revision) runs a distinct adversarial local-verification
  agent; a single-round ablation causes a clear decline (−7.76% RRR), and it reports the
  gains are **not** from model size ("the mechanism is model-agnostic"). Supports the checker
  being its own agent/slot (*VS: RCBSF paper lead*).
- **SOLAR** is built on an explicit two-stage decomposition — knowledge acquisition separated
  from knowledge application — with inspection points between them (*VS: SOLAR paper lead*).
- **PAKTON** keeps a distinct reasoning stage that cites evidence spans, at an explicit cost
  in latency and money ("prioritizes multi-step reasoning over speed"). The traceability is
  bought with latency — the axis the local runs hit (*VS: PAKTON paper lead*).

**Q-lit-2 — What model class for those steps?** A small self-hosted model is credible for
extraction.
- **A Few Good Clauses**: a domain-trained, self-hosted small model beat every frontier
  baseline on structured contract extraction (micro F1 0.842 vs 0.820 best frontier) at
  8–25× lower cost, with caveats (high batched latency; large-scale fine-tuning). Backs the
  small/local direction and warns that the generic model's failure is not a verdict on small
  models per se (*VS: A Few Good Clauses paper lead*).
- **SOLAR**: on statutory reasoning, foundational models 18.8% vs reasoning models 87.0%,
  but reasoning models need substantially longer processing; its own two-stage structure
  lifted non-reasoning models to 76.4%. If the verifier must be reasoning-capable, expect the
  latency; structure can partly substitute for model class (*VS: SOLAR paper lead*).

**What the literature does not establish:** that the verifier must be a *larger* model than
the extractor (RCBSF says the opposite), and none of the papers prescribe per-role slots or a
size split. The size question remains a **measurement** question for our own harness.

---

## Technical Context Resolutions

- **Language/Version**: Python ≥ 3.12 (fixed by the project's packaging metadata —
  *VS: Python requires-python*).
- **Primary Dependencies**: none added. `porter unicode61` ships in the installed SQLite; the
  tree widget ships in the pinned UI library (*VS: SQLite FTS5 tokenizers*, *VS: Textual Tree
  widget*). `sentence-transformers` stays absent.
- **Storage**: the embedding table and columns are removed; the index FTS tokenizer becomes
  `porter unicode61`; existing indexes are re-created (no migration).
- **Testing**: `pytest` unit tests for the tokenizer, tier compatibility, defaults, QA-slot
  resolution, parent-linking, the corruption guard and the harness arithmetic; TUI
  integration tests for the tree screen (auto-marked `slow` — *VS: TUI integration test slow
  marker*).
- **Target Platform**: local CLI, no server (Constitution Principle II).
- **Project Type**: CLI tool, package `openreview_cli`.
- **Performance Goals**: retrieval gets faster (keyword-only, no embedding round-trips);
  no regression elsewhere.
- **Constraints**: peak memory < 100 MB; pre-commit and CI stay green; no new dependency.
- **Scale/Scope**: ~6 code areas (retrieval, gateway/config, review/CLI, graph/TUI,
  grounding, CI/scripts) plus docs and tests; the file-by-file list is the master plan §11 and
  the checklist is `tasks.md`.

## Grounding map (FR → decision)

| FR | Decision | FR | Decision |
|---|---|---|---|
| FR-001 | 2 | FR-016 | 11d |
| FR-002 | 2, 13 | FR-017 | 11d |
| FR-003 | 13 | FR-018 | 11d |
| FR-004 | 13 | FR-019 | W7b |
| FR-005 | 13 | FR-020 | 1, W12 |
| FR-006 | 13, 9 | FR-021 | W12 |
| FR-007 | 8 | FR-022 | W12 |
| FR-008 | 8, 3, 5 | FR-023 | 14 |
| FR-009 | 3, 7 | FR-024 | 14 |
| FR-010 | 9 | FR-025 | 14, W7a, R6 |
| FR-011 | 9, W1 | FR-026 | 6 |
| FR-012 | 12 | FR-027 | W11 |
| FR-013 | 4, 10 | FR-028 | R8 |
| FR-014 | 4, 10 | FR-029 | P-IV |
| FR-015 | 11c | FR-030 | 11a |

## Claims not fully verifiable in the repo (labelled, not hidden)

- The **CUAD tokenizer** numbers (Q2) are now **reproducible**: the committed harness
  `scripts/measure_retrieval_accuracy.py` and its two receipts
  (`docs/benchmarks/results/cuad-retrieval-{porter,unicode61}.json`) are the anchors, and the
  same comparison is summarised in `docs/BENCHMARKS.md`. The **dense/hybrid** rows (Q3, Q13) and
  the **reranker** numbers (Q7) still come only from the gitignored decision record and a
  session-scratch harness that no longer exists, so they remain **UNVERIFIED in repo / not
  citable**; the tracked code facts they depend on are anchored (provenance above).
- **Why** the local rerankers lose is **Inference** (small model / truncation / the task).
- The **reader ranking** (granite 0.9 vs others 0.7) is **Inference** at n = 5 documents.
- The claim that the TUI retrieve screen needs no edit is **UNVERIFIED until checked** at
  implementation time (*VS: Retrieval methods* shows the TUI pins `method="sparse"` in the
  documented architecture, but the code check is a task, not a research conclusion).
