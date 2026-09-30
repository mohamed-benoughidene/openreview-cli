---
description: "Task list for spec 035 — Post-Measurement Cleanup"
---

# Tasks: 035 — Post-Measurement Cleanup

**Input**: Design documents from `/specs/035-post-measurement-cleanup/`

**Prerequisites**: `plan.md` (required — the approved master plan; its §8 lists the spec
artifacts and this file is the single home of the `T1.1…T3.3` checklist), `spec.md`
(FR-001…FR-030, P1/P2/P3 user stories), `research.md` (Q1–Q14 resolved).
`data-model.md` and `contracts/` were deliberately dropped (plan §8), so they are not inputs.

**Task-context note (environment gap):** `.specify/memory/task-context.md` is still spec-034
scoped, which breaks the constitution's Task Grounding Rule for every 035 path. It is **not**
regenerated here: 035's paths were grounded directly against the live worktree instead, and
regenerating `task-context.md` for 035 is a recorded follow-up.

**Tests**: Included. Tests are required here (TDD per repo `AGENTS.md`; the spec's success
criteria require new unit and integration tests).

**Grounding**: Every file path below was read from the worktree. Technical claims anchor to
`.specify/memory/verified-sources.md` (Spec 035 section) — see `research.md` for the mapping.
Plan task ids (`T1.1`, `T2.5`, …) are cross-referenced in each line so this checklist and the
plan cannot drift; the mapping table is at the end of this file.

**Organization**: Four phases of work map onto three prioritized user stories. US1 (P1) is
the cleanup; US2 (P2) is the graph screen; US3 (P3) is the grounding harness.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`US1`, `US2`, `US3`)
- Every task description names an exact file path

## Path Conventions

- Single project: `src/openreview_cli/`, `tests/`, `scripts/`, `docs/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the grounding artifacts exist and capture a green baseline before edits.

- [ ] T001 Verify the spec-035 evidence is anchored: `research.md` Q1–Q14 and Measurement
  evidence reference only verified items (CONFIRMED / CONFIRMED-EXTERNAL) in
  `.specify/memory/verified-sources.md`, and the spec-035 section is present. Do not begin edits
  until this is true (constitution Research Grounding Rule).
- [ ] T002 [P] Record the branch baseline: `uv run pre-commit run --all-files` and
  `uv run pytest -m "fast or slow" -q` green on `feat/035-post-measurement-cleanup` before any
  change (per `AGENTS.md`).

**Verification**:
```bash
grep -c "^## ITEM:" .specify/memory/verified-sources.md
uv run pre-commit run --all-files
```

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Remove the three dead slots (plan T1.3). The final slot set is the contract the
rest of the cleanup, the tests, the documentation and the Phase-4 re-measurement all read, so
it lands first. US2 and US3 do **not** depend on this phase.

**⚠️ CRITICAL**: The cleanup (US1) and the documentation sweep must not enumerate slots until
this phase is complete.

- [ ] T003 [P] (plan T1.3, decision 8) Reduce the slot sets in `src/openreview_cli/slots.py`:
  `VALID_SLOTS` (`:8-10`) to `{extraction, reasoning, grounding}` and `PRIMARY_ONLY_SLOTS`
  (`:12`) to the empty set / removed.
- [ ] T004 [P] (plan T1.3, decisions 8, 3, 7) Remove the three slots from
  `src/openreview_cli/gateway/wizard.py` (`SLOT_NAMES` at `:15` and the selection flow at
  `:64`) and from `src/openreview_cli/gateway/models.json` — remove the `embedding` /
  `reranking` / `graph` tokens from every per-model `slots` list and the matching provider
  `capabilities` flags, and delete the `qwen3-reranker-0.6b` model entry.
- [ ] T005 [P] (plan T1.3, decision 8) In `src/openreview_cli/gateway/router.py` remove
  `_SLOT_METHOD_MAP` (`:120-127`) and the `embed()` (`:783`) and `rerank()` (`:819`) methods;
  in `src/openreview_cli/config/loader.py` remove the `embedding` / `reranking` / `graph`
  entries from the shipped slot defaults (`:31-41`).
- [ ] T006 (plan T1.3) In `src/openreview_cli/app.py` remove the `gateway test` branches for
  the deleted slots (`:1748-1764`) and the matching capability flags (`:1808-1810`,
  `:1827-1832`).
- [ ] T007 [P] (plan T1.3, W8) Update the CI and measurement harnesses for the three-slot set:
  `.github/workflows/ci-ollama-smoke.yml` (slot list and loop `:82-87`, `:98`, `:109`; delete
  the now-moot reranking exclusion block `:117-127`), drop `graph` from the tuple in
  `scripts/measure_slm_slots.py:36-37`, and drop the embedding override in
  `scripts/measure_retrieval_slots.py:53`.
- [ ] T008 [P] (plan T1.3, decision 8) Remove the deleted slots from the two remaining
  slot-listing sites: narrow `SLOT_ORDER` in `src/openreview_cli/tui/tabs/settings.py:24`
  (it renders the "Model Slots" list at `:184-200`) to the three remaining slots, and
  change the hard-coded `"slots": ["reasoning", "extraction", "graph"]` in
  `src/openreview_cli/gateway/registry.py:159` (the discovered-Ollama model list) to the
  three remaining slots.

**Checkpoint**: The product advertises exactly three slots; the wizard, registry, router,
config, CLI, CI and scripts agree.

**Verification**:
```bash
uv run python -c "from openreview_cli.slots import VALID_SLOTS; assert VALID_SLOTS == frozenset({'extraction','reasoning','grounding'}), VALID_SLOTS"
uv run pytest tests/unit -q -k "slot or gateway or config or tier or privacy"
uv run openreview gateway test extraction
```

---

## Phase 3: User Story 1 - Ship an honest, working default configuration (Priority: P1) 🎯 MVP

**Goal**: Keyword-only retrieval on a `porter unicode61` index, two privacy modes with
`performance` accepted as `balanced`, `granite4:3b` defaults for all three slots, the checker
wired to the `reasoning` slot, the orphan fixture deleted, and the documentation corrected.

**Independent Test**: Assert three slots, `granite4:3b` defaults, `performance` → `balanced`,
and a `porter unicode61` index; run the retrieval, config and tier suites; run the CLI.

### Tests for User Story 1

- [ ] T009 [P] [US1] (plan T1.1, decision 2) Add a test in
  `tests/unit/test_retrieval_storage.py` asserting a freshly created FTS table's tokenizer is
  `porter unicode61`.
- [ ] T010 [P] [US1] (plan T1.4/T1.5, decisions 9, 12) Add tests in
  `tests/unit/test_config_loader.py`: the three shipped defaults are `ollama/granite4:3b`, and a
  config with `privacy.tier: performance` loads and yields `balanced`'s rules (add the
  `performance` case beside the existing tier tests, e.g. `tests/unit/test_tier_config.py`).
- [ ] T011 [P] [US1] (plan T1.6, decision 10) Add a test asserting `qa_model` resolves to the
  `reasoning` slot's primary and that changing the `reasoning` model changes only the checker
  (`tests/unit/test_config_loader.py` for the resolution; `tests/unit/bilateral/test_report.py`
  or the nearest review test for the call path).

### Implementation for User Story 1

- [ ] T012 [US1] (plan T1.1, decision 2) Change the FTS tokenizer to
  `tokenize='porter unicode61'` in `src/openreview_cli/retrieval/storage.py:79`, and update
  every inline DDL that hardcodes `unicode61` in tests (e.g.
  `tests/unit/test_retrieval_offline.py:59`, `tests/unit/test_retrieval_engine.py`).
- [X] T013 [US1] (plan T1.1, decision 2) Rewrite the tokenizer fragment of the retrieval
  section in `docs/ARCHITECTURE.md:88`: `unicode61` → `porter unicode61`. Done on
  `feat/035-post-measurement-cleanup` (the "hybrid BM25 + dense + RRF" wording is split out to
  T043 and lands with plan T1.2).
- [ ] T043 [US1] (plan T1.2, decision 13) Rewrite the retrieval section of
  `docs/ARCHITECTURE.md:88` wholesale — it currently documents "hybrid BM25 + dense + RRF";
  that wording dies with the dense path (T1.2, dense still exists today) — and add the
  re-index sentence there: indexes built before this release must be re-created with
  `openreview ingest` (no detection, no migration).
- [ ] T014 [US1] (plan T1.2, decision 13) Delete the meaning-based search path: remove
  `src/openreview_cli/retrieval/dense.py` and `src/openreview_cli/retrieval/rrf.py`; make
  `src/openreview_cli/retrieval/engine.py:129-138` dispatch `sparse` only (delete
  `_retrieve_dense`, `_retrieve_hybrid`, `_search_dense_candidates`); narrow
  `src/openreview_cli/retrieval/models.py:6,8` to `sparse`; drop the embedding step from
  `src/openreview_cli/retrieval/ingest.py`; drop `chunk_embeddings`, the `embedding_model` /
  `embedding_dim` columns, `insert_embedding` and `idx_embeddings_model_id` from
  `src/openreview_cli/retrieval/storage.py:51-52,100-108,163-175`.
- [ ] T015 [US1] (plan T1.2, decision 13) Remove `--method` from
  `src/openreview_cli/app.py:2174` (ingest) and `:2313-2314` (retrieve) and the `Method:`
  prints at `:2248` and `:2569`; remove `retrieval.default_method` and
  `retrieval.embedding_dimension` from `src/openreview_cli/config/loader.py:65,69,214,218`.
- [ ] T016 [US1] (plan T1.2, decision 13) Edit in place the dense/hybrid-referencing test
  files: `tests/unit/test_retrieval_storage.py`, `test_retrieval_ingest.py`,
  `test_retrieval_offline.py`, `test_retrieval_models.py`, `test_retrieval_engine.py`,
  `tests/unit/tui/test_retrieval_domain.py`, `tests/integration/test_retrieval_offline.py`,
  `tests/integration/test_retrieval_ingest.py`, `tests/integration/test_retrieve_command.py`,
  `tests/integration/test_retrieval_index.py`, `tests/fuzz/test_fuzz_sqlite.py`,
  `tests/integration/tui/test_retrieve_screen.py`.
- [ ] T017 [US1] (plan T1.2, decision 13) Delete the dense/hybrid-specific test files:
  `tests/unit/test_retrieval_dense.py`, `tests/unit/test_retrieval_rrf.py`,
  `tests/integration/test_retrieval_fusion.py`, `tests/integration/test_retrieval_performance.py`,
  `tests/integration/test_retrieval_benchmark.py`.
- [ ] T018 [US1] (plan T1.2) Verify whether the TUI retrieve screen needs any edit:
  `docs/ARCHITECTURE.md:94` says `RetrieveScreen` already pins `method="sparse"` and never
  renders `method`/`embedding_model`. Check `src/openreview_cli/tui/screens/retrieve.py` and
  `src/openreview_cli/tui/domain/retrieval.py`; if it is a no-op, drop the TUI change and
  record that; otherwise update those two paths.
- [ ] T019 [US1] (plan T1.4, decision 9, W1) Implement two privacy tiers: remove `PERFORMANCE`
  from `src/openreview_cli/gateway/tier_config.py:13-15` and the valid set at `:23`, remove the
  dead `embeddings_local_only` property (`:45-47`), and remove `performance` from
  `VALID_TIERS` in `src/openreview_cli/tui/domain/privacy.py:10`; in
  `src/openreview_cli/config/loader.py:176` keep `performance` accepted (literal entry or a
  normalizing pre-validator) and map it to `balanced` so an old config never raises.
- [ ] T020 [US1] (plan T1.5, decision 12) Set `ollama/granite4:3b` for `extraction` (`:26-30`),
  `reasoning` (`:21-25`) and `grounding` (`:42-46`) in `src/openreview_cli/config/loader.py`.
- [ ] T021 [US1] (plan T1.6, decision 10) Point the checker at the `reasoning` slot:
  `src/openreview_cli/review/pipeline.py:97`, `src/openreview_cli/review/runner.py:96-97`,
  `src/openreview_cli/bilateral/__init__.py:153-154`, `src/openreview_cli/app.py:2039`.
- [ ] T022 [US1] (plan T1.7, W7b) Delete the orphan fixture
  `tests/fixtures/grounding/seeded_claims.json` (verified zero consumers).
- [ ] T023 [US1] (plan T1.8) Add the re-index sentence (indexes built before this release must
  be re-created with `openreview ingest`; no detection, no migration) next to the
  `docs/ARCHITECTURE.md:88` rewrite and in the design docs under `docs/specs/plans/`.
- [ ] T024 [US1] (plan §4 "Product docs that are now false") Correct the false facts — not a
  regeneration: `PRODUCT.md` (the "6 task-specific model slots", "local embeddings + cloud
  reasoning", and three-tier claims), the slot table in `docs/ARCHITECTURE.md`, and
  `skill/SKILL.md` (`retrieve --method` at `:182`; tier code at `:391`, `:398`).

**Checkpoint**: US1 is fully functional and testable independently; the product's shipped
configuration matches what it does.

**Verification** (master plan Phase 1 block, plus the targeted checks):
```bash
uv run pre-commit run --all-files
uv run pytest -m "fast or slow" -q
uv run pytest -m memory -q          # SOLO — never pooled (AGENTS.md)
uv run openreview --help
uv run openreview gateway test extraction
# targeted checks this phase must add (one per non-trivial change, per P-V):
#   VALID_SLOTS == {extraction, reasoning, grounding}
#   shipped defaults are ollama/granite4:3b for all three
#   TierConfig accepts `performance` and yields `balanced`'s rules
#   retrieval creates an FTS table with `porter unicode61` and exposes no dense/hybrid method
grep -rn "embedding\|reranking\|qwen3-reranker\|--method\|performance" docs/ skill/SKILL.md
```

---

## Phase 4: User Story 2 - See a contract's clause structure inside the TUI (Priority: P2)

**Goal**: A screen that builds the open contract's clause graph in-process and shows its
foldable tree, with an explicit save action and plain-language states.

**Independent Test**: `tests/integration/tui/test_graph_build_screen.py` — the tree renders and
folds, save writes the CLI-matching JSON, a flat document shows the no-hierarchy note, and no
file exists unless save was pressed.

### Tests for User Story 2

- [ ] T025 [P] [US2] (plan T2.1, decision 11c) Add one direct unit test in
  `tests/unit/test_clause_detector.py`: numbered clause text through the detector →
  `link_parent_ids` links parents → graph hierarchy edges exist.
- [ ] T026 [P] [US2] (plan T2.2) Add a unit test in `tests/unit/test_graph_view.py` for the
  extracted `compute_annotations(graph)` helper — **only if** the helper is kept (i.e. the TUI
  tree is confirmed as its second caller in T028); if not, drop this task.
- [ ] T027 [P] [US2] (plan T2.5) Add `tests/integration/tui/test_graph_build_screen.py`
  covering what the existing `tests/integration/tui/test_graph_screen.py` does not: expected
  labels + folding; `(S)` output equals the CLI's graph JSON; the flat-document note; the save
  action is the only writer. Pattern: `app.run_test(size=(120, 40))` + `pilot`, await the
  screen's task, assert rendered text (`slow` is applied automatically by
  `tests/integration/tui/conftest.py:4-13`).

### Implementation for User Story 2

- [ ] T028 [US2] (plan T2.2) Extract `compute_annotations(graph) -> dict[str, list[str]]` in
  `src/openreview_cli/graph/view.py:21-66` and have `render_tree` (`:6`) call it. Confirm the
  second caller (the TUI tree, T030) exists before doing this; if the screen formats its own
  labels, drop the extraction and T026.
- [ ] T029 [US2] (plan T2.3) Extend `src/openreview_cli/tui/domain/graph.py` so the
  `ContractGraph` it already builds in `graph_summary_via_tui` is available to the screen — do
  **not** add a second parse+build entry point; keep `openreview_cli.graph.*` / `parsing.*`
  imports function-local (`:60-64`).
- [ ] T030 [US2] (plan T2.4, decisions 11d) Create `src/openreview_cli/tui/screens/graph_build.py`:
  header (filename + node/edge counts), a `1fr` central `Tree` (folding), a single status line
  and a docked action bar (`padding: 1 2`); node labels via Rich `Text` with `markup=False`;
  annotations from `compute_annotations` (T028); progress glyphs `○ ● ✓ ✗`; keys `(Esc)` back
  and `(S)` save `<name>.graph.json`; parse + build on a worker thread reusing the
  `RetrieveScreen` pattern (`src/openreview_cli/tui/screens/retrieve.py:404-443`); write no file
  unless `(S)`; handle working → tree, no-hierarchy (flat, the NDA case), parse failure
  (single line, no traceback — reuse the existing graph screen's handling).
- [ ] T031 [US2] (plan T2.4) Wire reach: add the binding/button beside the existing graph
  summary in `src/openreview_cli/tui/screens/result.py` with `check_action` guarding on
  `_document_path_for_active_report` (`:292-335`), and from
  `src/openreview_cli/tui/screens/retrieve.py`.

**Checkpoint**: US2 is functional and testable independently; the CLI `graph` feature is
unchanged.

**Verification** (master plan Phase 2 block):
```bash
uv run pytest tests/unit/test_clause_detector*.py -q         # T025
uv run pytest tests/unit/test_graph_view.py -q               # T026 (only if kept)
uv run pytest -m slow -q                                     # TUI suite + the new screen
uv run openreview graph build <parsed.json> -o /tmp/g.json    # CLI path unchanged
uv run openreview graph view /tmp/g.json | head              # CLI path unchanged
```

---

## Phase 5: User Story 3 - Know whether grounding actually works (Priority: P3)

**Goal**: A grounding-accuracy harness with honest negatives: real CUAD clauses, a mandatory
guard, a real confusion matrix, local and cloud arms.

**Independent Test**: `tests/unit/test_grounding_harness.py` — the guard rejects a no-op
corruption; the arithmetic is exact, including the guard-drained case (`N == 0` →
`caught_rate is None`) and the reject-everything case (`false_reject_rate == 1.0`); end-to-end on
a tiny fixture with the gateway stubbed.

### Tests for User Story 3

- [ ] T032 [P] [US3] (plan T3.3, W12) In `tests/unit/test_grounding_corruption.py` add: the
  guard rejects a no-op corruption (a corruption that returns the claim unchanged) and asserts
  the negative is genuinely unsupported.
- [ ] T033 [P] [US3] (plan T3.3) Create `tests/unit/test_grounding_harness.py`: the
  confusion-matrix arithmetic is exact on a hand-built matrix — when the guard leaves zero
  negatives (`N == 0`), `bad_caught == 0` and `caught_rate is None` (never `1.0`); when the
  discriminator rejects every claim, `bad_caught == N` and `false_reject_rate == 1.0`; the
  harness runs end-to-end on a tiny fixture set with the gateway stubbed.

### Implementation for User Story 3

- [ ] T034 [US3] (plan T3.1, decision 1, W12) Fix `src/openreview_cli/grounding/corruption.py`
  (98 lines): add `unsupported_claim(clause_a, clause_b)` (a sentence from another clause,
  asserted against `clause_a` — a genuine negative, no string surgery); keep `hallucination`
  subject to the guard; exclude `category_swap` (`:39-56`) from grounding; reclassify
  `anachronism` (`:84-98`) as citation validity and exclude it from grounding accuracy; add the
  **mandatory guard** that asserts each generated negative differs from the original and is
  unsupported, and records how many negatives it dropped.
- [ ] T035 [US3] (plan T3.2, decision 14) Add a grounding-accuracy mode to
  `scripts/measure_slm_slots.py` (extend, do not fork; reuse its receipt/report helpers):
  positives = a verbatim sentence from a CUAD clause under
  `data/legalbenchrag/corpus/cuad/*.txt`; negatives = `unsupported_claim` (cross-clause) and
  `hallucination`, both through the T034 guard; call
  `CitationGroundingDiscriminator.ground_claim(claim_text, cited_clause_id, clause_text)`
  (`src/openreview_cli/grounding/discriminator.py:65-123`); score bad-claims-caught,
  false-rejects and per-call latency only — **do not** use `compute_cg_metrics` as a signal
  (`src/openreview_cli/grounding/metrics.py:100-105`); run a local arm (`ollama/granite4:3b`)
  and a cloud arm; skip cleanly when the corpus is absent; emit JSON + markdown under
  `docs/benchmarks/results/` stating sample size, model IDs and the corpus/guard caveats.
- [ ] T036 [US3] (plan T3.2) Leave `compute_cg_metrics` behaviour untouched (it is consumed at
  `src/openreview_cli/grounding/discriminator.py:219` and exported at
  `src/openreview_cli/grounding/__init__.py:14,40`) — assert this via the existing
  `tests/unit/test_grounding_metrics.py`.

**Checkpoint**: US3 is functional and testable independently; grounding accuracy is knowable.

**Verification** (master plan Phase 3 block):
```bash
uv run pytest tests/unit/test_grounding_corruption.py -q
uv run pytest tests/unit/test_grounding_harness*.py -q
uv run python scripts/measure_slm_slots.py --grounding-accuracy --limit 20 --arm local
```

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Re-measure and regenerate (master plan Phase 4), then final validation.

- [ ] T037 Dispatch the manual CI slot matrix, now three slots:
  `gh workflow run ci-ollama-smoke.yml`.
- [ ] T038 Re-run the CUAD retrieval harness — **already committed** as
  `scripts/measure_retrieval_accuracy.py` (it loads `data/legalbenchrag/corpus/cuad/*.txt`,
  takes the committed 4,042 CUAD queries and answer spans, builds the FTS index with
  `porter unicode61` — and, via `--tokenizer`, the `unicode61` arm — and scores hit@1 / hit@5 /
  MRR with ground truth "the chunk overlapping the CUAD answer span is relevant"). Its receipts
  are `docs/benchmarks/results/cuad-retrieval-{porter,unicode61}.json` and the summary is the
  "CUAD keyword retrieval" section of `docs/BENCHMARKS.md`. Re-run it after the change lands to
  confirm `porter` on the full set and that no dense path remains. (The **1,536**-query CUAD run
  this replaces lived in session scratch space only and is not citable.)
- [ ] T039 Run the grounding harness on both arms:
  `uv run python scripts/measure_slm_slots.py --grounding-accuracy --arm local` and
  `--arm cloud` (skip the cloud arm cleanly if the key/limit is unavailable, and say so in the
  report). `data/` is gitignored and absent from this worktree, so before the real arms copy or
  symlink `data/legalbenchrag/corpus/cuad/` into the worktree (or run the script from the parent
  checkout) — otherwise the harness takes its graceful-skip path and this step is skipped, not
  blocked.
- [ ] T040 Regenerate the parity matrix from live source:
  `scripts/parity/inventory_cli.py`, `scripts/parity/inventory_tui.py`, then
  `scripts/parity/build_parity_matrix.py` (exact commands in
  `docs/cli-tui-parity-matrix.md:13-17`), and commit the regenerated
  `docs/cli-tui-parity-matrix.md`. Remember "CERTAIN" rows are name-token joins, not proof of
  coverage (W11).
- [ ] T041 Roll the re-run results into `docs/benchmarks/results/` beside the existing per-slot
  measurement.
- [ ] T042 [P] Final validation: `uv run pre-commit run --all-files`,
  `uv run pytest -m "fast or slow" -q`, `uv run pytest -m memory -q` (solo), and
  `uv run openreview --help`.
- [ ] T044 Deduplicate the `chunk_fts` DDL: the product copy in
  `src/openreview_cli/retrieval/storage.py:73-81` is duplicated in four test fixtures
  (`tests/unit/test_retrieval_offline.py:56`, `tests/unit/test_retrieval_engine.py:64,126,192`),
  so every schema change must be made five times. Export the FTS DDL fragment from the product
  module (or add a shared test helper that builds the table from the product's own DDL) and
  convert the four fixtures to use it, so future schema changes land in one place.

**Verification** (master plan Phase 4 block):
```bash
gh workflow run ci-ollama-smoke.yml
uv run python scripts/measure_slm_slots.py --grounding-accuracy --arm local
uv run python scripts/measure_slm_slots.py --grounding-accuracy --arm cloud
uv run python scripts/parity/inventory_cli.py --out draft/parity/cli-inventory.json
uv run python scripts/parity/inventory_tui.py --out draft/parity/tui-inventory.json
uv run python scripts/parity/build_parity_matrix.py --cli-json draft/parity/cli-inventory.json --tui-json draft/parity/tui-inventory.json
uv run pre-commit run --all-files
```

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup. Blocks US1 and the Phase-6 re-measurement
  (which reads the final slot set). Does **not** block US2 or US3.
- **US1 (Phase 3)**: depends on Foundational.
- **US2 (Phase 4)**: depends on Setup only; independent of Foundational/US1/US3.
- **US3 (Phase 5)**: depends on Setup only; independent of Foundational/US1/US2.
- **Polish (Phase 6)**: depends on US1 (retrieval + slots) and US3 (the harness); the parity
  regeneration depends on US1 + US2.

### User Story Dependencies

- **US1 (P1)**: after Foundational. No story dependencies. MVP.
- **US2 (P2)**: after Setup. No story dependencies.
- **US3 (P3)**: after Setup. No story dependencies.

### Within Each User Story

- Tests written and failing before implementation (TDD).
- US1: tokenizer/defaults/tier before the doc sweep; retrieval deletions before the test edits.
- US2: parent-linking test before the domain/screen work; `compute_annotations` before the screen.
- US3: corruption fix + guard before the harness mode.

### Parallel Opportunities

- **Phase 1**: T002 runs in parallel with T001.
- **Phase 2**: T003, T004, T005, T007, T008 touch different files and can run in parallel; T006
  (`app.py`) is independent of T004/T005.
- **US1**: T009–T011 (tests) in parallel; T012/T013, T014/T015, T019/T020/T021 are distinct files.
- **US2**: T025, T026, T027 (tests) in parallel.
- **US3**: T032, T033 (tests) in parallel.

See `plan.md` §0 for the review gates (one fresh sub-agent per task; a second independently
dispatched sub-agent reviews each task; TUI tasks additionally get the design audit).

---

## Parallel Example: User Story 2

```bash
# Tests (parallel):
Task: "T025 unit test link_parent_ids links parents in tests/unit/test_clause_detector.py"
Task: "T026 unit test compute_annotations in tests/unit/test_graph_view.py"
Task: "T027 integration test graph build screen in tests/integration/tui/test_graph_build_screen.py"
# Implementation (T028 helper, then T029 domain, then T030 screen, then T031 wiring):
Task: "T030 create src/openreview_cli/tui/screens/graph_build.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational → three slots.
3. Complete Phase 3: US1 → cleanup + docs.
4. **STOP and VALIDATE**: three slots, two tiers, `granite4:3b`, `porter unicode61`, no dense.
5. This alone repairs the false surface — a shippable increment.

### Incremental Delivery

1. Setup + Foundational → three-slot contract.
2. US1 → honest configuration (MVP).
3. US2 → TUI graph screen.
4. US3 → grounding harness.
5. Polish → re-measure, regenerate the parity matrix, final validation.

---

## Notes

- `[P]` = different files, no dependencies. `[Story]` labels give traceability to
  `spec.md`'s P1/P2/P3 stories.
- Every task names an exact file path; paths were read from the worktree.
- Nothing has been implemented yet — this file is the checklist, not a record of work done.
- Deferred with reason: the reranker swap, a reader-vs-checker size A/B, a human-labelled
  grounding corpus, and retrieval schema migration are all explicitly out of scope.

## Plan cross-reference (single source of truth)

This file is the single home of the checklist; `plan.md` references it rather than repeating it.
Every master-plan task maps here:

| Plan task | tasks.md | Plan task | tasks.md |
|---|---|---|---|
| T1.1 | T009, T012, T013 | T2.3 | T029 |
| T1.2 | T014, T015, T016, T017, T018, T043 | T2.4 | T030, T031 |
| T1.3 | T003, T004, T005, T006, T007, T008 | T2.5 | T027 |
| T1.4 | T010, T019 | T3.1 | T034 |
| T1.5 | T010, T020 | T3.2 | T035, T036 |
| T1.6 | T011, T021 | T3.3 | T032, T033 |
| T1.7 | T022 | Phase 4.1 | T037 |
| T1.8 | T023 | Phase 4.2 | T038 |
| T2.1 | T025 | Phase 4.3 | T039 |
| T2.2 | T026, T028 | Phase 4.4 | T040 |
| — | T001, T002, T024, T042, T044 | Phase 4.5 | T041 |
