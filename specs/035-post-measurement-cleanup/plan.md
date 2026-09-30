# Master plan — post-measurement cleanup (spec 035)

**Status:** APPROVED 2026-09-30. This in-repo copy (`specs/035-post-measurement-cleanup/plan.md`) is the canonical, approved plan for spec 035; the working copy lived at `~/.commandcode/plans/035-master-plan-cleanup.md` and was revised after review (see §12). Nothing implemented.
**Companion record:** `draft/measurement-decisions-2026-09-29.md` (gitignored) — the 14 decisions, 12 warnings, the reranker measurement, the paper leads.
**Spec folder:** `specs/035-post-measurement-cleanup/`. 035 is the next free number (`023` is a permanently unused gap and must not be reused). The spec-kit tooling would auto-pick `001` because it scans only `specs/` top level, so the number is passed explicitly.

---

## 0. How to use this plan

This is the **master plan**: target state, four phases, ordering, verification. It is the source for `specs/035-post-measurement-cleanup/plan.md`.

**Per-item sub-plans** (the user's master → per-item approach) exist only for the two items with real design content, live where this repo already keeps plan documents, and are **both written up front in Phase 0**, while the measurement evidence is fresh — accepted with the known trade-off that the graph sub-plan may drift if Phase 1 changes the TUI's retrieval screen (re-check it at the start of Phase 2):
- `docs/specs/plans/2026-09-30-graph-tui-build-tree-design.md` — the graph build + tree screen.
- `docs/specs/plans/2026-09-30-grounding-accuracy-harness-design.md` — the grounding harness.

Each sub-plan passes the same review gate the master plan did (`/caveman-review` + `/ponytail-audit`) before its phase starts. The mechanical steps get no sub-plan; they are checklist lines in `tasks.md`.

**Start sequence after approval:** (1) create the git worktree **based on `feat/slm-measurement`** — the user's current, not-yet-merged branch, which is where the measurement work lives; `main` is not touched — ; (2) write the five spec artifacts; (3) write both sub-plans; (4) run Phase 1 → 2 → 3 → 4, one fresh sub-agent per task with a second independently dispatched sub-agent reviewing each.

Everything else is mechanical with a known file list and lives as checklist items in `specs/035-…/tasks.md`.

**Artifact workflow (stated plainly, because §0 and §8 conflicted in the previous revision):** the spec-kit commands target OpenCode and AGENTS.md records that harness as superseded by Command Code; there is no `.specify/feature.json`, so the scripts cannot resolve a feature. We therefore **hand-write** `spec.md`, `plan.md`, `research.md` and `tasks.md`, and **do not** create `feature.json`. Nothing else is generated.

**Review gates before any code:**
1. This plan passed `/caveman-review` + `/ponytail-audit`; the dispositions are in §12.
2. Work in a git worktree (`/using-git-worktrees`). Never touch `main` during branch work.
3. TDD inside every task: failing test first. A test written after its code gets deleted, not flagged.
4. A fresh sub-agent implements each task; a second, independently dispatched sub-agent reviews it. TUI tasks additionally get `/impeccable audit` + `/polish` + `/harden`.

---

## 1. Why (evidence)

From one measurement run; numbers and file:line proofs are in the companion record. In short:

- The shipped reader measured **0/10 with 11 timeouts** (4,016 s) versus `granite4:3b` at **9/10, 0 failures** (280 s).
- Keyword search beat meaning-based search on the decisive corpus (the committed CUAD benchmark, 4,042 queries); `porter unicode61` beat plain `unicode61` by **+1.24 hit@1 / +6.58 hit@5 / +2.73 MRR@5** on the committed harness `scripts/measure_retrieval_accuracy.py` (receipts under `docs/benchmarks/results/`). The earlier **+1.7 / +2.1 / +1.9** over **1,536** queries came from a harness that was never committed and is not citable; the committed pair confirms the direction of the choice, not the old magnitudes.
- No local reranker works: a cheap lexical rerank and a local cross-encoder both made ordering **worse** than BM25's order.
- The `reasoning` slot has **no caller**; the `graph` feature is rule-based and calls no model; `balanced` and `performance` differ only by the embedding rule (which dies).
- Grounding **removed nothing** in the measured run (7 in, 7 out) and cannot be scored by the existing metrics function.

## 2. Target state

| Area | Now | After |
|---|---|---|
| Slots | 6 (`reasoning, extraction, embedding, reranking, graph, grounding`) | **3** — `extraction` (reader), `reasoning` (checker), `grounding` (fact-checker) |
| Checker's slot | `qa_model` defaults to `extraction_model` | **`reasoning`** (structural change: the checker gets its own slot — see T1.6 for what that does and does not change today) |
| Privacy modes | `maximum`, `balanced`, `performance` (last two identical) | **`maximum`, `balanced`**; an old `performance` value keeps working as `balanced` |
| Shipped defaults | `qwen3:4b` (reader), `qwen3:8b` (rest) | **`ollama/granite4:3b`** for all three slots |
| Search | `sparse`/`dense`/`hybrid`, default `hybrid`, `unicode61` | **`sparse` only**, `porter unicode61` |
| Graph | CLI-only `build`/`view`; TUI shows 5 numbers | **the `graph` CLI is unchanged** + TUI build + foldable tree |
| Grounding | unmeasured; strict mode removes claims silently | **scored harness** (local + cloud) with known-good/known-bad claims |

## 3. Constitution check (gate for Phase 0)

| Principle | Verdict | Justification |
|---|---|---|
| P-I Privacy First | **Pass** | Removes cloud-capable slots; nothing new leaves the machine; the harness sends only public benchmark clause text and strips PII by default. |
| P-II Local-First, CLI-Only | **Pass** | No server, daemon or telemetry. |
| P-III Hardware-Bounded (<100 MB) | **Pass** | Net negative: one fewer model class, no new runtime deps; the graph screen parses in a worker thread like the existing one. |
| P-IV Dependency Minimalism | **Pass** | **No new dependencies** (verified: `porter unicode61` is built into the shipped SQLite, `Tree` is in the pinned `textual>=8.2.8`, the harness reuses existing modules). `sentence-transformers` stays absent. |
| P-V Spec-Driven, YAGNI | **Pass** | `specs/035-…` + this plan is the tracked artifact; every non-trivial change gets a runnable check (T-items below name them). Nothing speculative is added — dead slots, dead retrieval modes and dead config are deleted. |

Grounding rules: `research.md` anchors every claim to `.specify/memory/verified-sources.md`, which is therefore **mandatory**, not optional.

---

## 4. Phase 1 — mechanical cleanup + config

**One re-index** covers the tokenizer change and the dense deletion: both invalidate the same per-document index.

**T1.1 — Tokenizer.** `retrieval/storage.py:79` → `tokenize='porter unicode61'`. Update every inline DDL that hardcodes `unicode61` in tests (found by grepping `unicode61`, e.g. `tests/unit/test_retrieval_offline.py:59`, `tests/unit/test_retrieval_engine.py`). Rewrite `docs/ARCHITECTURE.md:88` **wholesale** — it currently documents "hybrid BM25 + dense + RRF" *and* `unicode61`; both die. Test in `tests/unit/test_retrieval_storage.py`: assert the created FTS table's tokenizer.
*(Decision 2.)*

**T1.2 — Delete meaning-based search.** Remove `retrieval/dense.py`, `retrieval/rrf.py`; make `retrieval/engine.py:129-138` dispatch `sparse` only (delete `_retrieve_dense`, `_retrieve_hybrid`, `_search_dense_candidates`); `retrieval/models.py:8`; drop the embedding step from `retrieval/ingest.py`; drop `chunk_embeddings`, `index_meta.embedding_model`/`embedding_dim`, `insert_embedding` and `idx_embeddings_model_id` from `retrieval/storage.py:51-52,100-108,163-175`; remove `--method` (`app.py:2174`, `:2313-2314`) and the `Method:` prints (`app.py:2248`, `:2569`); remove `retrieval.default_method` and `embedding_dimension` from `config/loader.py:65,69,214,218`.
**Tests — 14 files reference dense/hybrid; mark each:**
- *Edit in place:* `tests/unit/test_retrieval_storage.py`, `test_retrieval_ingest.py`, `test_retrieval_offline.py`, `test_retrieval_models.py`, `test_retrieval_engine.py`, `tests/unit/tui/test_retrieval_domain.py`, `tests/integration/test_retrieval_offline.py`, `test_retrieval_ingest.py`, `test_retrieve_command.py`, `test_retrieval_index.py`, `tests/fuzz/test_fuzz_sqlite.py`, `tests/integration/tui/test_retrieve_screen.py`.
- *Delete:* `tests/unit/test_retrieval_dense.py`, `tests/unit/test_retrieval_rrf.py`, `tests/integration/test_retrieval_fusion.py`, `tests/integration/test_retrieval_performance.py`, `tests/integration/test_retrieval_benchmark.py` (all dense/hybrid-specific).
- *Incidental (touch only if they break):* `tests/unit/test_retrieval_rerank.py`, `tests/unit/test_skill_p3_anti_pattern.py`.
**Check before listing it:** `docs/ARCHITECTURE.md:94` says `RetrieveScreen` already pins `method="sparse"` and never renders `method`/`embedding_model`, so "update the TUI retrieve screen" may be a no-op — verify, and if so drop that line from the task.
*(Decision 13.)*

**T1.3 — Remove the three slots.** `slots.py:9,12`; `gateway/wizard.py:15,64`; the TUI settings (`tui/tabs/settings.py:24` `SLOT_ORDER`, rendered as the "Model Slots" list at `:184-200`) and the Ollama discovery path (`gateway/registry.py:159`, the hard-coded discovered-model `"slots"` list); **`gateway/models.json`** — remove the `embedding`/`reranking`/`graph` tokens from the per-model `slots` lists and the matching provider `capabilities` flags (27 models across 17 providers; find them by grepping `"slots"` and `capabilities`), plus the `qwen3-reranker-0.6b` model entry; `gateway/router.py:120-127` `_SLOT_METHOD_MAP` plus `embed()`/`rerank()` (`:783`, `:819`); the slot defaults in `config/loader.py:31-41`; `app.py:1748-1764` (`gateway test` branches) and the capability flags at `app.py:1808-1810` / `:1827-1832`; `.github/workflows/ci-ollama-smoke.yml:82-87,98,109` and **delete** the now-moot reranking exclusion block `:117-127`; `scripts/measure_slm_slots.py:36-37` (drop `graph` from the tuple); `scripts/measure_retrieval_slots.py:53` (drop the embedding override); tests.
**Acceptance check for the docs sweep** (instead of enumerating ~40 prose lines): after the change, `grep -rn "embedding\|reranking\|qwen3-reranker\|--method\|performance" docs/ skill/SKILL.md` returns **only** intentional historical references (e.g. the honest-limitations note about Ollama reranking), and a reviewer confirms each survivor is deliberate. `skill/SKILL.md` in particular documents `retrieve --method` (`:182`) and cites the tier code (`:391,:398`).
*(Decisions 8, 11b; W3 is the checklist; W8.)*

**T1.4 — Two privacy modes.** Remove `PERFORMANCE` from `gateway/tier_config.py:13-15`, from the `valid` set in `PrivacyTier.parse` (`:23`), from the pydantic `Literal` at `config/loader.py:176`, and from `VALID_TIERS` in `tui/domain/privacy.py:10` — **four sites, and they must change together**.
**Compatibility (corrected after review):** the config loader validates against the pydantic model *before* `PrivacyTier.parse` runs, so simply deleting `performance` from the `Literal` would make an existing `privacy.tier: performance` **raise a validation error and crash the CLI** — the warning/fallback path would never execute. Per decision 9 in the record, an old `performance` must **keep working and behave as it did (= `balanced`)**. So keep the value accepted (literal entry or a normalizing validator) and map it to `balanced`. No other shim is added.
*(Decision 9 corrected; W1.)*

**T1.5 — Ship `granite4:3b`.** `config/loader.py:22` (reasoning), `:27-29` (extraction), `:42-45` (grounding) → `ollama/granite4:3b`. Test: assert the shipped defaults.
*(Decision 12.)*

**T1.6 — Wire the checker to the `reasoning` slot.** Default the QA slot to `reasoning` at `review/pipeline.py:97`, `review/runner.py:96-97`, `bilateral/__init__.py:153-154`, `app.py:2039`.
**What this does and does not change (corrected after review):** the checker gains its **own independently configurable slot** — previously it silently borrowed the reader's. With T1.5 both slots ship the *same* default model (`granite4:3b`), so the out-of-the-box behaviour is unchanged; the point is that the checker can now be pointed at a stronger model without touching the reader. Test: assert `qa_model` resolves to the `reasoning` slot's primary, and that setting the reasoning slot to a different model changes only the checker.
*(Decision 10, wording corrected.)*

**T1.7 — Delete the orphan fixture.** `tests/fixtures/grounding/seeded_claims.json` — verified zero consumers.
*(W7b.)*

**T1.8 — Re-index documentation.** One explicit sentence in the retrieval section of `docs/ARCHITECTURE.md` (next to the `:88` rewrite) and in `docs/specs/plans/…-design.md`: indexes built before this release must be re-created with `openreview ingest`. **No detection code, no migration** — there are no users yet, and the word rules are baked in at table-creation time regardless.
*(Decision 9/13 consequence.)*

**Product docs that are now false:** `PRODUCT.md` claims *"6 task-specific model slots"*, *"local embeddings + cloud reasoning"* and lists three tiers; `docs/ARCHITECTURE.md` repeats the slot table. Update the facts — **not** a regeneration (impeccable's `init`/`document` must not be re-run without approval).

**Phase 1 verification**
```
uv run pre-commit run --all-files          # ruff --fix, ruff-format, mypy, pytest-fast collect
uv run pytest -m "fast or slow" -q         # all offline except memory/network
uv run pytest -m memory -q                 # SOLO — never pooled (AGENTS.md)
uv run openreview --help                   # command surface still loads
uv run openreview gateway test extraction  # one slot smoke (3 slots exist now)
```
Targeted checks this phase must add (one per non-trivial change, per P-V):
- `VALID_SLOTS == {"extraction", "reasoning", "grounding"}`
- shipped defaults are `ollama/granite4:3b` for all three
- `TierConfig` accepts `performance` and yields `balanced`'s rules
- `retrieval` creates an FTS table with `porter unicode61` and exposes no dense/hybrid method

---

## 5. Phase 2 — graph

**T2.1 — The missing test.** `link_parent_ids` (`parsing/clause_detector.py:170-193`) has **no tests anywhere**; the graph unit tests build `Clause` objects by hand with `parent_id` already set, so they prove nothing about the real path. Add **one** direct unit test: numbered clause text through the detector → parents linked. (One test, not two: the direct test already proves the chain through to graph edges, so a separate end-to-end duplicate is dropped — see §12.)
*(Decision 11c.)*

**T2.2 — One source of truth for annotations.** `graph/view.py:render_tree` computes `[N refs out]`, `[DEF-REF: n]`, `[DEFINES: "term"]`, `[ORPHAN]` inline (`:21-66`). Extract `compute_annotations(graph) -> dict[str, list[str]]` and have `render_tree` call it.
**Justification required by the review:** this is only worth doing if it has **two** callers — the CLI renderer *and* the new TUI tree (which labels its nodes from it). If the screen ends up formatting its own labels, drop the extraction and the helper's unit test. Confirm the second caller exists before writing it.

**T2.3 — Expose the built graph (no second build path).** `tui/domain/graph.py` already runs `parse_document` → `ClauseHierarchyBuilder().build` inside `graph_summary_via_tui` and then throws the graph away. Extend that module so the built `ContractGraph` is available to the screen — **do not** add a near-duplicate second entry point that repeats the same parse+build. Keep `openreview_cli.graph.*` / `parsing.*` imports function-local (`tui/domain/graph.py:60-64`).

**T2.4 — The screen.** New `src/openreview_cli/tui/screens/graph_build.py` — **one screen that builds and shows the tree**, reached by `(B)`:

- **Mode:** Operate. Job: see this contract's clause structure without leaving the TUI.
- **Layout:** header (filename + node/edge counts) · `1fr` central `Tree` widget · single status line · docked action bar; `padding: 1 2` (`DESIGN.md:144`).
- **Rendering:** Textual `Tree` with folding; node labels via Rich `Text` with **`markup=False`** (Literal Text Rule, `DESIGN.md:135`) so contract brackets survive; annotations from `compute_annotations` (T2.2). Progress glyphs `○ ● ✓ ✗` (`DESIGN.md:158`).
- **Keys:** `(Esc)` back, `(S)` save `<name>.graph.json`; keys in parentheses, never `[A]` (`DESIGN.md:167`).
- **Work:** parse + build on a worker thread, one status voice, buttons disabled while busy — **reuse** the `RetrieveScreen` pattern (`tui/screens/retrieve.py:404-443`) rather than inventing one.
- **Input:** the document path in hand, parsed in-process. **No file is written unless `(S)` is pressed.**
- **States:** working → tree; **no hierarchy detected** (flat document — the NDA case; say so plainly); parse failure → single-line message, no traceback (`DESIGN.md:194`); save → status + path, or a one-line error. The parse-failure handling is the same code path the existing graph screen already uses — reuse it; assert it once.
- **Reach:** `tui/screens/result.py` (a binding/button beside the existing `g` summary, with `check_action` guarding on `_document_path_for_active_report`, `:292-335`) and `tui/screens/retrieve.py`.
- **Considered and rejected (review suggestion):** fold this into the existing `GraphSummaryScreen` instead of a new module. Rejected because that screen's docstring and contract promise *read-only* metrics, and the user chose a single build-and-show screen. The two do share one thing and that is taken: the domain build path (T2.3).

**T2.5 — Tests.** `tests/integration/tui/test_graph_build_screen.py`, covering what the existing screen's tests do **not**: the tree renders expected labels and folds; `(S)` writes a file whose content matches the CLI's graph JSON; a flat document shows the no-hierarchy note; the save action is the **only** writer (assert no file exists otherwise). Pattern: `app.run_test(size=(120, 40))` + `pilot`, await the screen's task, assert rendered text (as `tests/integration/tui/test_graph_screen.py` does). `slow` is applied automatically by `tests/integration/tui/conftest.py:4-13`.

**Phase 2 verification**
```
uv run pytest tests/unit/test_clause_detector*.py -q        # T2.1
uv run pytest tests/unit/test_graph_view.py -q              # T2.2 helper (only if kept)
uv run pytest -m slow -q                                    # TUI suite + the new screen
uv run openreview graph build <parsed.json> -o /tmp/g.json   # CLI path unchanged
uv run openreview graph view /tmp/g.json | head              # CLI path unchanged
```

---

## 6. Phase 3 — grounding accuracy harness

**Goal:** make grounding's accuracy knowable. Today it is not: strict mode *removes* unsupported claims before the report, so the surviving counts can never show a miss (measured 7 in, 7 out).

**T3.1 — Make the negatives honest.** `grounding/corruption.py` cannot supply correct labels as written (W12): `clause_swap`/`anachronism` edit the **claim text** with `claim.replace(clause_id, …)`, which no-ops on prose claims and returns them unchanged; `category_swap` keeps the clause text unchanged so the claim stays supported; `hallucination` draws from 10 fixed sentences, one of which (indemnification) is genuinely supported by an indemnity clause. Fix:
- add `unsupported_claim(clause_a, clause_b)` — the claim is a sentence from **another** clause, asserted against `clause_a` → a genuine negative with no string surgery;
- keep `hallucination`, subject to the guard;
- **exclude** `category_swap` from grounding (classification case, not support);
- **reclassify** `anachronism` as *citation validity* and exclude it from grounding accuracy;
- **guard (mandatory):** for every generated negative assert its text does not appear verbatim in the cited clause text, and **record how many negatives the guard dropped** — never silently keep a mislabelled one.

**T3.2 — The harness (extend, don't fork).** `scripts/measure_slm_slots.py` already owns the slot-override plumbing, `init_database`, the JSON receipt and the markdown summary, and already counts grounding verdicts. **Add a grounding-accuracy mode there** (reusing its receipt/report helpers) rather than creating a 12th top-level script with its own argument parsing and output format. If that file becomes unwieldy, split helpers out later — not now.
- **Source:** real clauses from `data/legalbenchrag/corpus/**cuad**/*.txt` (462 contracts in the `cuad` subdirectory; the parent `corpus/` also holds `contractnli`, `maud`, `privacy_qa` — the harness must target `cuad`). Skip gracefully when the corpus is absent so CI stays green.
- **Positives:** a verbatim sentence from the clause (trivially supported — a weaker positive set than human-labelled, and stated as such).
- **Negatives:** `unsupported_claim` (cross-clause) and `hallucination`, both through the T3.1 guard.
- **Call:** `CitationGroundingDiscriminator.ground_claim(claim_text, cited_clause_id, clause_text)` (`grounding/discriminator.py:65-123`) — it takes the clause text directly.
- **Score — a real confusion matrix, and nothing else:** bad claims caught (TN / all negatives), good claims wrongly rejected (false rejects / all positives), and per-call latency. **Do not** use `compute_cg_metrics` as a signal: it computes *structural* CP/CR/CL over grounded verdicts only and returns **1.0 for everything when nothing is grounded** (`grounding/metrics.py:100-105`) — the exact failure mode the harness exists to expose (a grounding that rejects everything would score perfect). It is production-used (`grounding/discriminator.py:219`, exported at `grounding/__init__.py:14,40`), so **leave its behaviour untouched**.
- **Arms:** local (`ollama/granite4:3b`, the shipped default) and cloud (OpenRouter; needs the key).
- **Output:** the repo's benchmark convention — JSON receipt + markdown report under `docs/benchmarks/results/`, with sample size, model IDs, and the corpus/guard caveats stated in the report itself.

**T3.3 — Tests.** Offline: the guard rejects a no-op corruption; the metric arithmetic is exact on a hand-built confusion matrix — when the guard leaves zero negatives (`N == 0`), `bad_caught == 0` and `caught_rate is None` (never `1.0`); when the discriminator rejects every claim, `bad_caught == N` and `false_reject_rate == 1.0`; the harness runs end-to-end on a tiny fixture set with the gateway stubbed.

**Phase 3 verification**
```
uv run pytest tests/unit/test_grounding_corruption.py -q
uv run pytest tests/unit/test_grounding_harness*.py -q
uv run python scripts/measure_slm_slots.py --grounding-accuracy --limit 20 --arm local
```

---

## 7. Phase 4 — re-measure and regenerate

1. **CI slot matrix** — dispatch the manual workflow (`gh workflow run ci-ollama-smoke.yml`), now three slots.
2. **CUAD retrieval measurement** — **now a committed harness.** `scripts/measure_retrieval_accuracy.py` loads `data/legalbenchrag/corpus/cuad/*.txt`, takes the committed 4,042 CUAD queries and answer spans, builds the FTS index with `porter unicode61` (and, via `--tokenizer`, the `unicode61` comparison arm), and scores hit@1 / hit@5 / MRR with the ground-truth rule "the chunk overlapping the CUAD answer span is relevant"; its two receipts are `docs/benchmarks/results/cuad-retrieval-{porter,unicode61}.json` and the summary is the new "CUAD keyword retrieval" section of `docs/BENCHMARKS.md`. (The **1,536**-query CUAD run it replaces lived in session scratch space only and is not citable.) Re-run it after the change lands to confirm `porter` on the full set and that no dense path remains.
3. **The grounding harness**, both arms.
4. **Regenerate the parity matrix**: `scripts/parity/inventory_cli.py`, `inventory_tui.py`, then `build_parity_matrix.py` (exact commands in `docs/cli-tui-parity-matrix.md:13-17`), and commit the regenerated `docs/cli-tui-parity-matrix.md`. Remember "CERTAIN" rows are name-token joins, not proof of coverage (W11).
5. Roll the results into `docs/benchmarks/results/` beside the existing per-slot measurement.

```
gh workflow run ci-ollama-smoke.yml
uv run python scripts/measure_slm_slots.py --grounding-accuracy --arm local
uv run python scripts/measure_slm_slots.py --grounding-accuracy --arm cloud
uv run python scripts/parity/inventory_cli.py --out draft/parity/cli-inventory.json
uv run python scripts/parity/inventory_tui.py --out draft/parity/tui-inventory.json
uv run python scripts/parity/build_parity_matrix.py --cli-json draft/parity/cli-inventory.json --tui-json draft/parity/tui-inventory.json
```

---

## 8. Spec artifacts (Phase 0, before any code)

Shrunk after the over-engineering audit — the deletion half does not need the full spec-kit set:

| File | Why it earns its keep |
|---|---|
| `specs/035-post-measurement-cleanup/spec.md` | The tracked artifact P-V requires: what changes, why, success criteria. |
| `specs/035-post-measurement-cleanup/plan.md` | This master plan + the Constitution Check (§3). |
| `specs/035-post-measurement-cleanup/research.md` | **Mandatory** — the companion decisions record is gitignored, so this is the only *tracked* home for the measurement evidence and the paper leads (§6 of the record). Each claim anchors to `verified-sources.md`. |
| `specs/035-post-measurement-cleanup/tasks.md` | The single home of the `T1.1…T3.3` checklist (the plan references it rather than duplicating). |
| `.specify/memory/verified-sources.md` | Required by the constitution's Research Grounding Rule. |

**Deliberately dropped:** `data-model.md` (034's earned its keep because it *added* a model; ours only deletes columns), `quickstart.md` (no new user flow), `checklists/requirements.md` (034 shipped without one), `contracts/` (the surface change is "one flag removed" — captured in `spec.md`), and `.specify/feature.json` (feeds a superseded toolchain; see §0). The two design docs in `docs/specs/plans/` carry the real interface detail.

Also: repoint the `<!-- SPECKIT START/END -->` block in `AGENTS.md:424-428` (currently pointing at an archived plan) at the new `plan.md`.

## 9. Risks and things I could not verify

| # | Item | Label |
|---|---|---|
| R1 | `granite4:3b`'s 9/10 came from **5 documents** — may be noise; the `qwen3:4b` failure is unambiguous. If the full sample disagrees, revisit in Phase 4. | Fact + Inference |
| R2 | Wiring the checker gives it its **own slot**; with the shipped defaults it is the *same model* as the reader, so nothing about out-of-the-box quality changes (corrected — the previous revision overstated this). No A/B was run; the user declined one. | Fact |
| R3 | An old `privacy.tier: performance` keeps working as `balanced` (mapping required — see T1.4). No other compatibility code. | Decision 9 |
| R4 | The `Tree` widget is a second renderer beside `render_tree`; mitigated by T2.2 **only if** the annotations helper genuinely has two callers. | Inference |
| R5 | The harness's positives are verbatim clause sentences, so the positive set is easier than a human-labelled one; bad-claim detection is the meaningful signal. Do not claim real-world false-positive rates from this. | Fact |
| R6 | `data/legalbenchrag` is gitignored, so the harness cannot run on the full sample in CI; it must skip cleanly. | Fact |
| R7 | Spec-kit scripts cannot resolve a feature (no `feature.json`) and the commands target OpenCode; artifacts are hand-written. A reviewer may expect `/speckit.analyze` output. | Fact |
| R8 | `compute_cg_metrics` **is** consumed — `grounding/discriminator.py:219` (`ground_report`), exported at `grounding/__init__.py:14,40`. Its behaviour must be left untouched. (Corrected from UNKNOWN.) | Fact |
| R9 | TUI rules: no module-level gateway/litellm imports, no `sys.exit`, `markup=False` on literal text, keys in parentheses (`DESIGN.md:192-196`, `AGENTS.md:247,313`). | Fact |

## 10. Explicitly out of scope

- Replacing the reranker (measured: removal is correct).
- The reader-vs-checker model-size A/B (declined by the user).
- A human-labelled grounding corpus (a separate annotation task).
- Retrieval schema versioning/migration (no users; a rebuild is required regardless).
- `NOTICE.md`'s audience mention (standing, tolerated flag).
- Any new dependency.

## 11. Files expected to change (roll-up)

- **Retrieval:** `retrieval/{storage,engine,models,ingest,__init__}.py`; delete `retrieval/{dense,rrf}.py`.
- **Gateway/config:** `slots.py`; `gateway/{wizard,router,tier_config}.py`; `gateway/models.json`; `config/loader.py`.
- **Review/CLI:** `review/{pipeline,runner}.py`; `bilateral/__init__.py`; `app.py`.
- **Graph/TUI:** `graph/view.py`; `tui/domain/graph.py`; new `tui/screens/graph_build.py`; `tui/screens/{result,retrieve}.py`.
- **Grounding:** `grounding/corruption.py`; `scripts/measure_slm_slots.py` (new accuracy mode).
- **CI/scripts:** `.github/workflows/ci-ollama-smoke.yml`; `scripts/measure_retrieval_slots.py`.
- **Docs:** `docs/ARCHITECTURE.md`; `docs/cli-tui-parity-matrix.md` (regenerated); `docs/benchmarks/results/*`; `PRODUCT.md`; `skill/SKILL.md`; `AGENTS.md` (spec pointer); the two new files in `docs/specs/plans/`.
- **Tests:** delete `tests/fixtures/grounding/seeded_claims.json`; add the clause-detector, annotation-helper (conditional), graph-screen, corruption-guard and harness tests; update or delete the dense/hybrid, slot, tier and default tests listed in T1.2.

## 12. Review log (Plan-stage gate)

Two fresh sub-agents audited the previous revision. Dispositions:

**`/caveman-review` (terse pass) — 23 findings: 4 blocking, 15 risks, 2 nits, 2 questions.**
- 🔴 *Blocking, all fixed above:* (1)+(2) the `performance` removal would have crashed the CLI instead of warning, contradicting decision 9 → T1.4 now keeps the value and maps it to `balanced`; (3) R2/T1.5 contradicted each other (all three slots ship the same model, so "the checker gets its own model" was wrong) → T1.6 and R2 reworded to "its own slot, same default model today"; (4) Phase 4's CUAD retrieval measurement was unbuildable (the committed script scores a 5-query fixture) → §7 item 2 now specifies the loader, ground-truth rule and scope.
- 🟡 *Accepted and fixed:* corpus path → `corpus/cuad/*.txt`; R8 → answered (it *is* consumed); `app.py` capability-flag line numbers; `models.json` described as per-model `slots` tokens + provider flags rather than "entries"; `skill/SKILL.md` → an acceptance grep instead of enumerating ~40 lines; `ARCHITECTURE.md:88` rewritten wholesale, not just the tokenizer; the 14 test files listed with delete-vs-edit; the TUI retrieve change flagged as possibly a no-op to verify; T1.8 given an exact home; runnable commands added to §7; design docs moved to the repo's `docs/specs/plans/` convention and listed in §11; `verified-sources.md` made mandatory; targeted per-change tests added to Phase 1; the tier site count corrected from two to four; §2 "CLI unchanged" scoped to the `graph` CLI.
- 🔵 *Accepted:* brace-expansion fix for `models.json`; named test path for T1.1.
- ❓ *Answered:* §0/§8 artifact workflow stated plainly; §2 "CLI unchanged" scoped.
- *Confirmed correct, unchanged:* all other spot-checked citations (`storage.py:79`, `slots.py:9,12`, loader defaults, `tier_config` lines, `metrics.py:100-105`, the CI slot lines, `measure_*_slots.py` lines, `retrieve.py:404-443`, `result.py:292-335`, `clause_detector.py:170-193`, `graph/view.py:21-66`, the DESIGN/AGENTS line refs) and every number in §1.

**`/ponytail-audit` (over-engineering) — 10 findings.**
- *Accepted:* drop five of the nine spec artifacts + `feature.json` (§8); drop the `compute_cg_metrics` secondary signal; drop the duplicated end-to-end graph test; collapse the verification block to `pre-commit run --all-files` + `pytest -m "fast or slow"` + targeted checks; make `views.md`'s `tasks.md` the single home of the T-list; **extend** `scripts/measure_slm_slots.py` rather than adding a 12th script; fix the near-duplicate domain helper by exposing the built graph from the existing function.
- *Partially accepted:* §8 keeps `research.md` (its point was that the evidence already exists — but in a **gitignored** file, so a tracked copy is required) and `plan.md`/`spec.md`; `verified-sources.md` stays (constitution).
- *Rejected with reason:* folding the graph screen into `GraphSummaryScreen` — that screen's contract is read-only and the user chose a separate build-and-show screen; the shared domain path is taken instead. *Also rejected:* dropping the annotations helper unconditionally — it is kept **only if** it acquires the second caller (the TUI tree), which T2.2 now states as a condition rather than an assumption.
- *Verified:* the "no new dependencies" claim holds (`porter unicode61` is in the shipped SQLite; `Tree` is in the pinned Textual); the deletion half is proportionate and must not be trimmed; `dense.py`/`rrf.py` used only `math`/`struct`, so no dependency becomes droppable (numpy/torch/transformers remain in use elsewhere).

**Post-review omissions folded in (2026-09-30, external review).** Two slot-removal sites were named in no artifact — `src/openreview_cli/tui/tabs/settings.py:24` (`SLOT_ORDER`, rendered as the "Model Slots" list) and `src/openreview_cli/gateway/registry.py:159` (the discovered-Ollama `"slots"` list) — and both are now named in T1.3 above, in `spec.md` FR-008, and as the new Foundational task T008 in `tasks.md`. The same review pass also disambiguated the grounding success criterion (SC-009 / T3.3) for the case where the guard leaves no negatives and corrected the `models.json` count to 27 models across 17 providers.
