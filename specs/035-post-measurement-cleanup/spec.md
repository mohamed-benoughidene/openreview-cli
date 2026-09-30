# Feature Specification: Post-Measurement Cleanup (Spec 035)

**Feature Branch**: `feat/035-post-measurement-cleanup`

**Created**: 2026-09-30

**Status**: Approved — derived from the approved master plan (`plan.md`, approved 2026-09-30)

**Input**: The 14 settled decisions and 12 warnings in the measurement decision record (`draft/measurement-decisions-2026-09-29.md`, gitignored) and the measurement receipt (`docs/benchmarks/results/slot-measurement.md` / `.json`). Every functional requirement below traces to a numbered decision; the numeric evidence lives in `research.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ship an honest, working default configuration (Priority: P1)

The product shipped six AI slots, three privacy modes, and a meaning-based search path. Measurement showed most of that surface is dead, duplicated, or worse than the alternative. After this change the product ships a smaller configuration that does what it claims: three slots (`extraction`, `reasoning`, `grounding`), two privacy modes (`maximum`, `balanced`), keyword-only retrieval using the `porter unicode61` tokenizer, and `ollama/granite4:3b` as the default model for all three slots — with the checker pointed at its own `reasoning` slot. Dead retrieval modes, dead config keys, and an orphan test fixture are removed, and the documentation that describes the old surface is corrected.

**Why this priority**: This is the bulk of the change and the reason the work exists. It removes user-visible falsehoods (a default reader that times out, modes that do nothing distinct, search paths that cannot run) and is independently testable through the CLI, the configuration loader, and the retrieval tests.

**Independent Test**: Load the shipped configuration and assert three slots, two selectable tiers, `granite4:3b` defaults, and a `porter unicode61` index; run `openreview --help` and a slot smoke test; run the retrieval test suite and the config/tier tests.

**Acceptance Scenarios**:

1. **Given** a fresh install, **When** the slot set is inspected, **Then** it is exactly `extraction`, `reasoning`, `grounding`.
2. **Given** a configuration file that still sets `privacy.tier: performance`, **When** any command loads the configuration, **Then** it does not error and behaves exactly as `balanced`.
3. **Given** the retrieval subsystem, **When** an index is created, **Then** the full-text table's tokenizer is `porter unicode61` and only the `sparse` (keyword) method is offered.
4. **Given** a fresh install, **When** the shipped defaults are read, **Then** all three slots default to `ollama/granite4:3b`.

---

### User Story 2 - See a contract's clause structure inside the TUI (Priority: P2)

The `graph` feature already builds a clause graph and renders an indented tree, but only from the command line; the TUI shows five numbers and nothing else. This story adds a TUI screen that builds the graph for the open document and shows its foldable clause tree, with an explicit save action that writes the same JSON the CLI writes.

**Why this priority**: It is net-new UI work with real design content, it depends on the P1 cleanup only incidentally, and it is independently demonstrable and testable. It is lower than P1 because it adds capability rather than repairing a false claim.

**Independent Test**: Open a numbered contract in the TUI, trigger the screen, and assert a foldable tree with the expected node labels renders; press save and assert the written file matches the CLI's `graph build` output; open a flat document and assert the no-hierarchy note.

**Acceptance Scenarios**:

1. **Given** a numbered contract open in the TUI, **When** the tree screen is triggered, **Then** a foldable tree renders with clause labels and annotations and no traceback.
2. **Given** the tree screen, **When** the user presses save `(S)`, **Then** `<name>.graph.json` is written and its content matches the CLI's graph JSON; **When** save is not pressed, **Then** no file is written.
3. **Given** a flat (unnumbered) document, **When** the screen is triggered, **Then** it states plainly that no clause hierarchy was detected; **Given** a parse failure, **Then** a single-line message is shown with no traceback.

---

### User Story 3 - Know whether grounding actually works (Priority: P3)

Grounding runs, but its accuracy is unknowable: strict mode removes unsupported claims before the report, so the surviving counts can never show a miss (measured 7 in, 7 out). This story builds an offline harness that generates known-good and known-bad claims from real clauses, runs a local and a cloud arm, and reports bad claims caught, good claims wrongly rejected, and latency.

**Why this priority**: It is measurement tooling rather than user-facing capability, and it is independently testable, but it depends on first repairing the claim-corruption generator so its labels are trustworthy. It is last because the product remains usable without it.

**Independent Test**: Run the required unit tests (the guard rejects a no-op corruption; the confusion-matrix arithmetic is exact including the case where the guard leaves no negatives (`N == 0`)) and run the harness against a tiny fixture set with the gateway stubbed.

**Acceptance Scenarios**:

1. **Given** the corpus is present, **When** the harness runs, **Then** it writes a JSON receipt under `docs/benchmarks/results/`; the markdown report is assembled by hand from the receipts and states the sample size, the model IDs, and the corpus/guard caveats.
2. **Given** a generated negative claim, **When** the guard runs, **Then** it asserts the claim differs from the original and is genuinely unsupported, and records how many negatives it dropped.
3. **Given** a grounding arm that rejects every claim, **When** it is scored, **Then** it catches every negative (`bad_caught == N`) but also rejects every positive (`false_reject_rate == 1.0`), so it cannot look good; **Given** the guard drains the negative arm (`N == 0`), **Then** `bad_caught == 0` and `caught_rate is None`, never `1.0`.

---

### Edge Cases

- **Corpus absent**: `data/legalbenchrag` is gitignored, so the grounding harness (and the CUAD retrieval re-measurement) must skip cleanly and leave CI green.
- **Old index in place**: an index built with the previous tokenizer cannot answer correctly after the change; the product documents that indexes must be re-created, and adds no detection or migration code.
- **Old `performance` config**: the configuration loader validates the tier against a schema before the tier parser runs, so the backwards-compatibility path must be exercised at load time, not only at parse time — an old value must not raise.
- **TUI retrieve screen**: existing documentation says the TUI retrieve screen already pins `method="sparse"` and never renders `method`; the change is a no-op there if verified, in which case no TUI edit is made.
- **`--cluster-clauses`**: it loads a local legal model through the model library directly, never through the gateway, so it is unaffected by the slot removal.
- **Graph flat output**: a flat graph scores a perfect health number by documented design; the new screen must present flatness as information, not as a failure.
- **Orphan fixture**: the labelled grounding fixture has verifiably zero consumers; deletion is safe and is preferred over repair (repair would be a separate annotation task).
- **Spec tooling**: the spec-kit commands cannot resolve a feature (no feature manifest) and target a superseded harness; the artifacts are hand-written.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (Decision 2): The system MUST create its retrieval full-text index with the `porter unicode61` tokenizer.
- **FR-002** (Decisions 2, 13): The system MUST require existing retrieval indexes to be re-created (with `openreview ingest`) and MUST NOT add index-detection or schema-migration code.
- **FR-003** (Decision 13): The system MUST support keyword (`sparse`) retrieval only; the `dense` and `hybrid` methods MUST be removed.
- **FR-004** (Decision 13): The system MUST remove the `--method` option from `ingest` and `retrieve` and the method text those commands print.
- **FR-005** (Decision 13): The system MUST remove the embedding store — the `chunk_embeddings` table, the `embedding_model` and `embedding_dim` columns, the embedding-insert path, and the embedding step in ingestion.
- **FR-006** (Decisions 13, 9): The system MUST remove the `retrieval.default_method` and `retrieval.embedding_dimension` configuration keys.
- **FR-007** (Decision 8): The system MUST expose exactly three model slots: `extraction`, `reasoning`, `grounding`.
- **FR-008** (Decisions 8, 3, 5): The system MUST remove the `embedding`, `reranking`, and `graph` slots from the slot set (`src/openreview_cli/slots.py`), the setup wizard (`src/openreview_cli/gateway/wizard.py`), the TUI settings (`SLOT_ORDER` in `src/openreview_cli/tui/tabs/settings.py:24`, rendered as the "Model Slots" list), the provider registry (`src/openreview_cli/gateway/models.json` slot tokens and provider capability flags, plus the hard-coded discovered-Ollama slots in `src/openreview_cli/gateway/registry.py:159`), the shipped configuration defaults, the CI slot loop, the measurement scripts, and the documentation.
- **FR-009** (Decisions 3, 7): The system MUST remove the `reranking` slot and MUST NOT introduce a local reranker.
- **FR-010** (Decision 9): The system MUST expose exactly two privacy modes, `maximum` and `balanced`; `performance` MUST be removed as a selectable mode.
- **FR-011** (Decision 9, W1): The system MUST keep accepting an existing `privacy.tier: performance` setting and MUST treat it as `balanced`, without raising a configuration-validation error.
- **FR-012** (Decision 12): The system MUST ship `ollama/granite4:3b` as the default model for the `extraction`, `reasoning`, and `grounding` slots.
- **FR-013** (Decisions 4, 10): The system MUST resolve the checker (QA) model from the `reasoning` slot, not from the reader's `extraction` slot.
- **FR-014** (Decisions 4, 10): The `reasoning` slot MUST have a product caller (the checker), so it is no longer a dead slot.
- **FR-015** (Decision 11c): The system MUST include a unit test proving that the parent-linking step links parents for a numbered contract and thereby yields clause-graph hierarchy edges.
- **FR-016** (Decision 11d): The system MUST provide a TUI screen that builds and displays a contract's clause-graph tree.
- **FR-017** (Decision 11d): The tree screen MUST label nodes from the same annotation source the CLI tree renderer uses; if the screen ends up formatting its own labels, the shared helper MUST be dropped rather than duplicated.
- **FR-018** (Decision 11d): The tree screen MUST build the graph in-process on a worker thread, MUST write no file unless the user presses save `(S)`, MUST state plainly when a flat document yields no hierarchy, and MUST show a single-line message with no traceback on parse failure.
- **FR-019** (W7b): The system MUST delete the orphan fixture `tests/fixtures/grounding/seeded_claims.json`.
- **FR-020** (Decision 1, W12): The grounding harness MUST generate each known-bad claim so that it is genuinely unsupported and textually different from the cited clause.
- **FR-021** (W12): The grounding harness MUST guard every generated negative (assert it differs from the original and is unsupported) and MUST record how many negatives the guard dropped.
- **FR-022** (W12): The grounding harness MUST exclude the classification corruption and MUST reclassify the citation-invalidity corruption as a citation-validity case, so neither is scored as a grounding negative.
- **FR-023** (Decision 14): The system MUST provide a grounding-accuracy harness that builds known-good and known-bad claims from real clauses in the local CUAD corpus and runs both a local arm and a cloud arm.
- **FR-024** (Decision 14): The harness MUST report bad claims caught, good claims wrongly rejected, and per-call latency, and MUST NOT use the structural metrics function as an accuracy signal.
- **FR-025** (Decision 14, W7a, R6): The harness MUST target clauses under `data/legalbenchrag/corpus/cuad/` and MUST skip cleanly (leaving CI green) when that corpus is absent.
- **FR-026** (Decision 6): After the changes land, the measurements MUST be re-run: the CI slot matrix, the CUAD retrieval measurement, and the grounding harness.
- **FR-027** (W11): The system MUST regenerate `docs/cli-tui-parity-matrix.md` from live source after the changes and MUST NOT treat its `CERTAIN` rows as proof of TUI coverage.
- **FR-028** (R8): The system MUST leave the existing production behaviour of the structural grounding-metrics function unchanged.
- **FR-029** (Constitution, Dependency Minimalism): The system MUST add no new runtime dependency.
- **FR-030** (Decision 11a): The system MUST leave the `graph` command-line feature (`build`, `view`, `metrics`, `diff`, `health`) working as before.

### Key Entities *(include if feature involves data)*

This feature deletes stored data structures rather than adding models, so the entities below are described as concepts, with no new persistent model.

- **Slot**: a named AI capability role. Now three (`extraction` reader, `reasoning` checker, `grounding` fact-checker); previously six.
- **Privacy tier**: a named privacy posture. Now two (`maximum`, `balanced`); the retired `performance` value is accepted on input and normalized to `balanced`.
- **Retrieval method**: how a search query is answered. Now one (`sparse`/BM25 over a full-text index); `dense` and `hybrid` are removed, and the removed embedding table and columns disappear with them.
- **Clause graph**: per-contract nodes (clauses/sections) and edges (parent/child, cross-reference, definition-reference), built by rule, rendered as an indented tree.
- **Grounding claim**: a claim assessed against a cited clause; now generated as known-good (verbatim supported sentence) or known-bad (cross-clause or fabricated) with a guard.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (FR-007, FR-008): A slot-constant check returns exactly `{"extraction", "reasoning", "grounding"}`.
- **SC-002** (FR-012): The shipped defaults for all three slots are `ollama/granite4:3b`, asserted by a unit test.
- **SC-003** (FR-010, FR-011): A configuration that sets `privacy.tier: performance` loads without error and yields `balanced`'s tier rules; `maximum` and `balanced` configurations are unaffected.
- **SC-004** (FR-001, FR-003, FR-004): A freshly created index's full-text table reports the `porter unicode61` tokenizer, and neither `openreview ingest --help` nor `openreview retrieve --help` lists `--method`.
- **SC-005** (FR-008): After the change, a repo-wide search for the removed slot/flag/tier terms returns only intentional historical references, each confirmed deliberate by a reviewer.
- **SC-006** (FR-007): `uv run openreview --help` loads and `uv run openreview gateway test extraction` succeeds against the three-slot set.
- **SC-007** (FR-015): A direct parent-linking unit test exists and fails if parent linking is removed.
- **SC-008** (FR-016, FR-017, FR-018): The TUI tree screen renders the expected labels and folds; save writes a file whose content matches the CLI's graph JSON; a flat document shows the no-hierarchy note; a parse failure shows one line; no file exists unless save was pressed.
- **SC-009** (FR-020, FR-021, FR-022): The guard rejects a no-op corruption; the confusion-matrix arithmetic is exact on a hand-built matrix — when the guard leaves zero negatives (`N == 0`), `bad_caught == 0` and `caught_rate is None` (never `1.0`); when the discriminator rejects every claim, `bad_caught == N` and `false_reject_rate == 1.0`.
- **SC-010** (FR-023, FR-024, FR-025): The harness runs end-to-end on a tiny fixture set with the gateway stubbed, and on the full corpus emits a JSON receipt under `docs/benchmarks/results/`; the markdown report is assembled by hand from the receipts and states the sample size, the model IDs, and the corpus/guard caveats.
- **SC-011** (FR-026, FR-027): After Phase 4, the CI slot matrix has run on three slots, the CUAD retrieval measurement has been re-run, and `docs/cli-tui-parity-matrix.md` is regenerated and committed.
- **SC-012** (Constitution, Dev Workflow): `uv run pre-commit run --all-files` is green; `uv run pytest -m "fast or slow" -q` passes; `uv run pytest -m memory -q` passes when run solo.
- **SC-013** (FR-005, FR-006, FR-010): A repo-wide search finds no live reference to the removed embedding columns, the `--method` flag, or the `performance` tier outside the intentional compatibility path.

## Assumptions

- **No existing users**: there is no deployed install, so re-creating retrieval indexes is acceptable and no migration code is written.
- **Branch/worktree**: work happens in the `feat/035-post-measurement-cleanup` worktree, based on the measurement branch; the main line is never touched during branch work.
- **Corpus is local but untracked**: the CUAD corpus is present for local runs and absent in CI; the harness must therefore degrade to a clean skip.
- **Cloud key availability**: the grounding harness's cloud arm needs a provider key; if it is unavailable, that arm is skipped and the report says so.
- **Reader sample size**: the reader accuracy comparison used five documents, so the difference between the top local models may be noise; the failure of the previously shipped default is unambiguous.
- **No new dependency**: the `porter unicode61` tokenizer ships inside the installed SQLite, the tree widget ships inside the pinned UI library, and the harness reuses existing modules.
- **Design-doc drift**: the graph sub-plan (written alongside this spec) may drift if the cleanup changes the TUI retrieval screen; it is re-checked at the start of the graph phase.
- **Hand-written artifacts**: the spec tooling cannot resolve a feature (no feature manifest) and targets a superseded harness, so `spec.md`, `plan.md`, `research.md`, and `tasks.md` are written by hand and a reviewer may miss the tooling output that would normally accompany them.
- **Scope boundary**: replacing or tuning the reranker, a reader-vs-checker model-size comparison, a human-labelled grounding corpus, retrieval schema versioning/migration, and any new dependency are all explicitly out of scope.
