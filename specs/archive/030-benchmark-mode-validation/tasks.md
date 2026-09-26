# Tasks: Benchmark Mode Validation — Mode Whitelist, Accuracy Baseline, Orphan E2E Tests

**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Research**: [research.md](./research.md)
**Data Model**: [data-model.md](./data-model.md)
**Contracts**: [contracts/](./contracts/)
**Constitution**: [.specify/memory/constitution.md](../../.specify/memory/constitution.md)

**Branch**: `feat/030-benchmark-mode-validation`
**Package**: `openreview_cli`
**CLI command**: `openreview`

## Parallel Group Structure

**IMPLEMENTATION RUNS IN 3 PARALLEL GROUPS (A, B, C)** with NO file overlap:

| Group | Spec Ref | Files | Scope |
|-------|----------|-------|-------|
| **A (D-75)** | FR-1, FR-2, FR-3 | `benchmark/cli.py`, `benchmark/runner.py`, `tests/integration/test_benchmark_modes.py` | VALID_MODES, parse-time validation, dead param removal |
| **B (D-76)** | FR-4, FR-5 | `benchmark/baseline.py` (new), `tests/integration/test_benchmark_baseline.py` (new), `docs/benchmarks/.gitkeep` (new) | Mock + real accuracy baseline, baseline subcommand wiring into `cli.py` |
| **C (D-77)** | FR-6 | `tests/integration/test_orphan_modes_e2e.py` (new), fixture verification | Orphan mode E2E tests (9 modes parametrized) |

**Phases 1, 2, 6, 7** are shared (Setup, Foundational, Integration, Polish) — run BEFORE groups or AFTER all groups complete.

## Format

`- [ ] TXXX [P?] [Story?] Description with file path`

- `[P]` = Can run in parallel with other `[P]` tasks (different files, no dependencies)
- `[Story]` = Maps to user story: `[US1]` = mode validation, `[US2]` = CI baseline, `[US3]` = real baseline, `[US4]` = orphan E2E
- TDD enforced: test tasks BEFORE implementation tasks in every story
- All checklist items use `[ ]` — updated to `[X]` on completion

---

## Phase 1: Setup (T001)

**Purpose**: Verify working tree, branch, deps. No parallel groups can start until this passes.

- [ ] T001 Verify working tree clean (`git status --short`), branch is `feat/030-benchmark-mode-validation`, deps installed (`uv sync`), pre-commit hooks available (`uvx pre-commit run --all-files`)

---

## Phase 2: Foundational (T002–T004)

**Purpose**: Shared context and fixtures that BOTH groups need before parallel split.

- [ ] T002 Read existing benchmark test pattern at `tests/integration/test_benchmark_cuad.py` — confirm `BenchmarkRunner` + `_mock_pipeline` usage pattern, `monkeypatch` mocking style, `fixtures_dir` convention. Document findings in a comment block if needed.
- [ ] T003 [P] Confirm all 9 orphan mode fixture directories exist with PDFs: `tests/fixtures/benchmark/{licensecheck,leasecheck,privacycheck,indemnitycheck,consultcheck,workcheck,loicheck,subcheck,settlementcheck}/`. If any missing, flag as BLOCKER.
- [ ] T004 [P] Confirm `AssessmentColor` enum exists at `review/colors.py` with values `green`, `amber`, `red`. Confirm `ClauseAssessment.color` field type is `AssessmentColor | None`. Confirm `ReviewReport.assessments` is the correct access path (not `report.clauses`).

**Checkpoint**: Foundation ready. Groups A, B, C can proceed in parallel.

---

## Phase 3: Group A — D-75 (Mode Whitelist + Dead Param) [US1]

**Goal**: `VALID_MODES` frozenset with parse-time validation rejects unknown modes with exit 78. Dead `mode` param removed from `run_dataset()`.

**Files owned**: `src/openreview_cli/benchmark/cli.py`, `src/openreview_cli/benchmark/runner.py`, `tests/integration/test_benchmark_modes.py`

**Independent test**: `uv run openreview benchmark run --modes=invalidmode` → exit 78, error on stderr.

### Tests (Group A — write first, TDD)

- [ ] T-A-01 [P] [US1] Write test: `test_modes_validation_rejects_unknown` in `tests/integration/test_benchmark_modes.py` — invoke `benchmark run --modes=invalidmode`, assert exit code 78, assert error message contains "Unknown mode 'invalidmode'" on stderr. Run test, expect FAIL (no VALID_MODES yet).
- [ ] T-A-02 [P] [US1] Write test: `test_modes_validation_accepts_all_17` in `tests/integration/test_benchmark_modes.py` — invoke `benchmark run --modes=<all 17 comma-separated>`, assert exit 0. Run test, expect FAIL.
- [ ] T-A-03 [P] [US1] Write test: `test_valid_modes_contains_17_entries` in `tests/integration/test_benchmark_modes.py` — import `VALID_MODES` from `openreview_cli.benchmark.cli`, assert `len(VALID_MODES) == 17`, assert each known mode is present. Run test, expect FAIL (module not imported yet).
- [ ] T-A-04 [P] [US1] Write test: `test_run_dataset_no_mode_param` in `tests/integration/test_benchmark_modes.py` — run `git grep "def run_dataset" src/openreview_cli/benchmark/runner.py` and assert signature does NOT contain `mode:`. Or write a unit test that calls `runner.run_dataset("cuad", _mock_pipeline)` (without `mode=`) and assert it returns `DatasetResult`. Run test, expect FAIL (param still present).
- [ ] T-A-05 [P] [US1] Write test: `test_dataset_name_convention` in `tests/integration/test_benchmark_modes.py` — after multi-mode iteration, assert `dataset_name` contains `::` mode separator. Run test, expect FAIL (no multi-mode iteration yet).

### Implementation (Group A)

- [ ] T-A-06 [US1] Add `VALID_MODES: frozenset[str]` constant in `src/openreview_cli/benchmark/cli.py` after `VALID_DATASETS` (line ~33) with all 17 modes from spec FR-1. Add `# ponytail: hard-coded mode list — source of truth for benchmark mode validation.` comment. Verify: `grep '# ponytail: hard-coded mode list' src/openreview_cli/benchmark/cli.py` — confirm non-empty. Run T-A-03 test, expect PASS.
- [ ] T-A-07 [US1] Add mode validation loop in `benchmark_run()` in `cli.py` — after dataset validation (line ~160) and before dataset resolution, parse `modes` string into list, validate each mode against `VALID_MODES`. Unknown mode → `typer.echo(err=True)` + `raise typer.Exit(code=78)`. Follow exact pattern of dataset validation at lines 154-160. Run T-A-01, T-A-02 tests, expect PASS.
- [ ] T-A-08 [US1] Remove `mode: str = "precheck"` parameter from `BenchmarkRunner.run_dataset()` signature in `src/openreview_cli/benchmark/runner.py` (line ~71). Do NOT change the function body. Verify no caller passes `mode=` keyword (already confirmed in research.md). Run T-A-04 test, expect PASS.
- [ ] T-A-09 [US1] Add multi-mode iteration in `benchmark_run()` in `cli.py` — for each dataset, iterate over each mode in `mode_list`. Tag result with `dataset_name = f"{dataset}::{mode}"`. Run `--all` produces 51 DatasetResult entries (17 modes × 3 datasets). Run T-A-05 test, expect PASS.
- [ ] T-A-10 [US1] Run Group A tests with coverage: `uv run pytest tests/integration/test_benchmark_modes.py -v`. All 5 tests PASS.
- [ ] T-A-11 [US1] Run lint and type on Group A files: `uv run ruff check src/openreview_cli/benchmark/cli.py src/openreview_cli/benchmark/runner.py tests/integration/test_benchmark_modes.py && uv run mypy src/openreview_cli/benchmark/cli.py src/openreview_cli/benchmark/runner.py tests/integration/test_benchmark_modes.py`. All clean.

**Checkpoint**: Group A complete — mode validation, dead param, multi-mode iteration all working.

---

## Phase 4: Group B — D-76 (Mock + Real Accuracy Baselines) [US2] [US3]

**Goal**: Mock baseline runs all 17 modes × 3 datasets (51 results) in CI. Real baseline produces `docs/benchmarks/baseline-{date}.json` with per-mode × per-dataset metrics.

**Files owned**: `src/openreview_cli/benchmark/baseline.py` (new), `tests/integration/test_benchmark_baseline.py` (new), `docs/benchmarks/.gitkeep` (new), `src/openreview_cli/benchmark/cli.py` (baseline subcommand wiring)

**Dependency on Group A**: Group B edits `cli.py` (T-B-10) which overlaps with Group A edits. **Run Group B sequentially AFTER Group A's cli.py changes (T-A-06, T-A-07) are complete.** See T-B-10 `[BLOCKS: T-A-07]` annotation.

**Independent test**: `uv run pytest tests/integration/test_benchmark_baseline.py -v` → 7+ tests pass.

### Tests (Group B — write first, TDD)

- [ ] T-B-01 [P] [US2] Write test: `test_baseline_command_exists` in `tests/integration/test_benchmark_baseline.py` — invoke `openreview benchmark baseline --help`, assert exit 0 and output contains "Run accuracy baseline". Run test, expect FAIL (no command yet).
- [ ] T-B-02 [P] [US2] Write test: `test_mock_baseline_produces_51_results` in `tests/integration/test_benchmark_baseline.py` — call `run_mock_baseline()` from `baseline.py` with all 17 modes, assert returned list has 51 entries (17 × 3 datasets). Check each entry has `dataset_name` with `::` separator. Run test, expect FAIL (module doesn't exist yet).
- [ ] T-B-03 [P] [US3] Write test: `test_mock_baseline_result_schema` in `tests/integration/test_benchmark_baseline.py` — assert each entry is `BaselineResult` dataclass with expected fields (`mode`, `dataset`, `extraction_f1`, etc.). Run test, expect FAIL (dataclass doesn't exist yet).
- [ ] T-B-04 [P] [US3] Write test: `test_real_baseline_command_save_flag` in `tests/integration/test_benchmark_baseline.py` — invoke `openreview benchmark baseline --save-baseline --format json --output /tmp/test-baseline.json`, assert file created with valid JSON. Run test, expect FAIL (no baseline command yet).
- [ ] T-B-05 [P] [US3] Write test: `test_baseline_json_schema` in `tests/integration/test_benchmark_baseline.py` — parse `test-baseline.json`, validate against `BaselineReport` schema (git_commit, provider, model, timestamp, mode_results array). Run test, expect FAIL (no output yet).
- [ ] T-B-06 [P] [US3] Write test: `test_baseline_cli_flag_conflict` in `tests/integration/test_benchmark_baseline.py` — assert `--save-baseline` without `--format json` errors. Run test, expect FAIL (no flag yet).
- [ ] T-B-07 [P] [US3] Write test: `test_report_per_mode_grouping` in `tests/integration/test_benchmark_baseline.py` — after mock baseline run, validate that `BaselineReport.mode_results` contains entries grouped by mode with per-mode metrics. Assert that each mode section has non-null metrics. For terminal output, assert that the formatted report contains mode-name headings (e.g., `precheck`, `hirecheck`). Run test, expect FAIL (FR-7 not implemented yet).

### Implementation (Group B)

- [ ] T-B-08 [US2] Create `src/openreview_cli/benchmark/baseline.py` — new module. Define `BaselineResult` and `BaselineReport` dataclasses matching data-model.md entities:
  ```python
  @dataclass
  class BaselineResult:
      mode: str
      dataset: str
      extraction_f1: float | None = None
      comparison_f1: float | None = None
      classification_f1: float | None = None
      hallucination_rate: float | None = None
      pii_recall: float | None = None
      latency_ms: float | None = None
      peak_memory_mb: float | None = None

  @dataclass
  class BaselineReport:
      mode_results: list[BaselineResult]
      git_commit: str
      git_branch: str | None
      provider: str
      model: str
      timestamp: str
      metadata: dict[str, Any] = field(default_factory=dict)
  ```
- [ ] T-B-09 [US2] Implement `run_mock_baseline(modes: list[str]) -> list[BaselineResult]` in `baseline.py` — loop over 17 modes × 3 datasets (CUAD, MAUD, ContractNLI), call `runner.run_dataset(dataset, _mock_pipeline)` from existing harness, wrap result in `BaselineResult`. Run T-B-02, T-B-03 tests, expect PASS.
- [ ] T-B-10 [US2] [BLOCKS: T-A-07] Wire `benchmark baseline` subcommand in `src/openreview_cli/benchmark/cli.py` — add `baseline` Typer subcommand/app. Add `--all` (default), `--modes`, `--format` (json only), `--output` (file path), `--save-baseline` flag. Default behavior runs mock baseline. Run T-B-01 test, expect PASS.
- [ ] T-B-11 [US3] Implement `build_gateway_pipeline(mode: str) -> PipelineFn` in `baseline.py` — wraps `Gateway.chat()` call for real baseline runs. Implement `run_real_baseline(modes: list[str]) -> BaselineReport` — calls `build_gateway_pipeline` for each mode and dataset, compiles `BaselineReport` with git metadata. Run T-B-04 test, expect PASS.
- [ ] T-B-12 [US3] Wire `--save-baseline` + `--output` in `cli.py` — on completion, serialize `BaselineReport` to JSON and write to output path. Add validation: `--save-baseline` requires `--format json` and `--output`. Run T-B-04, T-B-05, T-B-06 tests, expect PASS.
- [ ] T-B-13 [US2] Create `docs/benchmarks/` directory with `.gitkeep`. Add brief README.md explaining baseline files are committed reference accuracy snapshots.
- [ ] T-B-14 [US3] Run Group B tests: `uv run pytest tests/integration/test_benchmark_baseline.py -v`. All 7+ tests PASS.
- [ ] T-B-15 [US3] Run lint and type on Group B files: `uv run ruff check src/openreview_cli/benchmark/baseline.py tests/integration/test_benchmark_baseline.py && uv run mypy src/openreview_cli/benchmark/baseline.py tests/integration/test_benchmark_baseline.py`. All clean.

**Checkpoint**: Group B complete — mock baseline runs in CI, real baseline produces JSON snapshot.

---

## Phase 5: Group C — D-77 (Orphan E2E Tests) [US4]

**Goal**: 9 orphan modes have end-to-end pipeline tests: parse fixture → strip PII → run review (mock gateway) → assert 3-color output.

**Files owned**: `tests/integration/test_orphan_modes_e2e.py` (new), fixture verification for 9 modes.

**Independent test**: `uv run pytest tests/integration/test_orphan_modes_e2e.py -v` → 9 passed.

### Fixture Verification (Group C)

- [ ] T-C-F01 [P] [US4] Verify fixture directory for `licensecheck` exists at `tests/fixtures/benchmark/licensecheck/` with at least 1 parseable PDF (`doc_1.pdf` or similar). If not, create minimal fixture.
- [ ] T-C-F02 [P] [US4] Verify fixture directory for `leasecheck` exists at `tests/fixtures/benchmark/leasecheck/` with at least 1 parseable PDF. If not, create minimal fixture.
- [ ] T-C-F03 [P] [US4] Verify fixture directory for `privacycheck` exists at `tests/fixtures/benchmark/privacycheck/` with at least 1 parseable PDF. If not, create minimal fixture.
- [ ] T-C-F04 [P] [US4] Verify fixture directory for `indemnitycheck` exists at `tests/fixtures/benchmark/indemnitycheck/` with at least 1 parseable PDF. If not, create minimal fixture.
- [ ] T-C-F05 [P] [US4] Verify fixture directory for `consultcheck` exists at `tests/fixtures/benchmark/consultcheck/` with at least 1 parseable PDF. If not, create minimal fixture.
- [ ] T-C-F06 [P] [US4] Verify fixture directory for `workcheck` exists at `tests/fixtures/benchmark/workcheck/` with at least 1 parseable PDF. If not, create minimal fixture.
- [ ] T-C-F07 [P] [US4] Verify fixture directory for `loicheck` exists at `tests/fixtures/benchmark/loicheck/` with at least 1 parseable PDF. If not, create minimal fixture.
- [ ] T-C-F08 [P] [US4] Verify fixture directory for `subcheck` exists at `tests/fixtures/benchmark/subcheck/` with at least 1 parseable PDF. If not, create minimal fixture.
- [ ] T-C-F09 [P] [US4] Verify fixture directory for `settlementcheck` exists at `tests/fixtures/benchmark/settlementcheck/` with at least 1 parseable PDF. If not, create minimal fixture.

### Tests (Group C — TDD)

- [ ] T-C-10 [US4] Write parametrized test file `tests/integration/test_orphan_modes_e2e.py` with:
  ```python
  @pytest.mark.parametrize("mode", [
      "licensecheck", "leasecheck", "privacycheck", "indemnitycheck",
      "consultcheck", "workcheck", "loicheck", "subcheck", "settlementcheck",
  ])
  def test_orphan_mode_e2e(mode, monkeypatch, fixtures_dir):
  ```
  - Locate fixture: `fixtures_dir / "benchmark" / mode / "doc_1.pdf"` — `pytest.skip()` if absent
  - Mock AI gateway using `monkeypatch.setattr("openreview_cli.gateway.router.Gateway.chat", mock_gateway_chat)`
  - Run pipeline: parse document via `stream_clauses()`, strip PII via `PiiEngine.strip_clauses()`, call `run_review(document_path=..., mode=mode)`
  - Assert `isinstance(report, ReviewReport)` and `len(report.assessments) > 0`
  - Assert each `assessment.color is not None` and `assessment.color in (AssessmentColor.green, AssessmentColor.amber, AssessmentColor.red)`

  Run test file, expect all 9 tests to FAIL (no mock gateway setup yet).

- [ ] T-C-11 [US4] Create mock gateway response function in same test file (or `conftest.py` if reusable):
  ```python
  def mock_gateway_chat(self, messages, model_slot="default", **kwargs):
      """Return a mock assessment response with green/amber/red color."""
      return {
          "choices": [{
              "message": {
                  "content": json.dumps({
                      "clause_id": "mock-001",
                      "clause_text": "Mock clause for testing",
                      "color": random.choice(["green", "amber", "red"]),
                      "rationale": "Mock rationale for pipeline test",
                  })
              }
          }]
      }
  ```
  Note: Shape must match what `run_review()` expects from `Gateway.chat()`.

- [ ] T-C-12 [US4] Run tests: `uv run pytest tests/integration/test_orphan_modes_e2e.py -v`. All 9 tests PASS.
- [ ] T-C-13 [US4] Run lint and type on Group C files: `uv run pytest tests/integration/test_orphan_modes_e2e.py -v --tb=short`. All PASS.

**Checkpoint**: Group C complete — all 9 orphan modes have passing E2E tests.

---

## Phase 6: Integration (T-INT)

**Purpose**: After all 3 parallel groups complete, resolve cross-group conflicts and run full suite.

- [ ] T-INT-01 Run full non-memory test suite: `uv run pytest tests/unit/ tests/integration/ -k 'not memory' -q`. All tests PASS.
- [ ] T-INT-02 Run memory tests solo: `uv run pytest -m memory -q --timeout=300`. All PASS.
- [ ] T-INT-03 Run lint: `uv run ruff check . --quiet`. No errors.
- [ ] T-INT-04 Run type check: `uv run mypy src/ tests/ --strict --quiet`. No errors.
- [ ] T-INT-05 Fix any cross-group conflicts (import collisions, shared fixture changes, type mismatches across group boundaries). Re-run T-INT-01 through T-INT-04.
- [ ] T-INT-06 Run quickstart validation scenarios 1–6 from `quickstart.md`:
  - `uv run openreview benchmark run --modes=invalidmode` → exit 78
  - `uv run openreview benchmark run --modes=precheck,hirecheck,dealcheck` → exit 0
  - `git grep "def run_dataset" src/openreview_cli/benchmark/runner.py` → no `mode` param
  - `uv run openreview benchmark run --all --ci` → exit 0
  - `uv run openreview benchmark run --datasets=cuad --modes=precheck,hirecheck,dealcheck --verbose` → exit 0
  - `uv run pytest tests/integration/test_orphan_modes_e2e.py -v` → 9 passed
- [ ] T-INT-07 Verify `VALID_MODES` contains all 17 modes by running a quick shell test: for each mode, `uv run openreview benchmark run --modes=<mode>` → exit 0.

---

## Phase 7: Polish (T-POL)

**Purpose**: Final cleanup, documentation, and verification.

- [ ] T-POL-01 Run pre-commit suite: `uvx pre-commit run --all-files`. All hooks pass.
- [ ] T-POL-02 Final test suite: `uv run pytest tests/unit/ tests/integration/ -k 'not memory' -q`. All PASS.
- [ ] T-POL-03 Final lint + type: `uv run ruff check . --quiet && uv run mypy src/ tests/ --strict --quiet`. All clean.
- [ ] T-POL-04 Update all `[ ]` markers to `[X]` in this file for completed tasks.
- [ ] T-POL-05 Verify no blueprint codes leaked: `grep -E '\bC-[0-9]|\bNX-[0-9]|\bTRL[ ]?[0-9]|\b§[0-9]|\bR-[0-9]|\bQ-[0-9]' specs/030-benchmark-mode-validation/tasks.md` — confirm zero matches.

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Blocks |
|-------|-----------|--------|
| Phase 1 (Setup) | — | Everything |
| Phase 2 (Foundational) | Phase 1 | Groups A, B, C |
| Phase 3 (Group A) | Phase 2 | — (parallel with B, C) |
| Phase 4 (Group B) | Phase 2, Group A (T-A-06/T-A-07) for `cli.py` edits | — (parallel with C post-Group-A) |
| Phase 5 (Group C) | Phase 2 | — (parallel with A, B) |
| Phase 6 (Integration) | Phases 3, 4, 5 | Phase 7 |
| Phase 7 (Polish) | Phase 6 | — |

### Parallel Execution Strategy

```bash
# After Phase 2:
# Sub-agent 1: Group A (Phase 3) — D-75 files only
# Sub-agent 2: Group B (Phase 4) — D-76 files only
# Sub-agent 3: Group C (Phase 5) — D-77 files only

# After all 3 complete:
# Phase 6 (Integration) — merge branches / resolve conflicts / run full suite
# Phase 7 (Polish) — final checks
```

### Within-Group Parallel Opportunities

| Group | [P] Count | What runs in parallel |
|-------|----------|----------------------|
| A | 5 | All 5 test tasks (T-A-01 through T-A-05) can write in parallel (same file append OK via parametrize). T-A-06 through T-A-11 sequential. |
| B | 5 | All 7 test tasks (T-B-01 through T-B-07) can write in parallel. T-B-08 through T-B-15 mostly sequential (dataclass first, then function, then CLI wiring). |
| C | 9 | All 9 fixture verifications (T-C-F01 through T-C-F09) fully parallel — different directories. T-C-10 through T-C-13 sequential (one test file). |

### TDD Enforcement

**Every user story follows**: Write test (expect FAIL) → implement (expect PASS) → refactor.

- [US1] T-A-01 through T-A-05 (tests FAIL) → T-A-06 through T-A-09 (impl PASS)
- [US2] T-B-01 through T-B-03 (tests FAIL) → T-B-08, T-B-09 (impl PASS)
- [US3] T-B-04 through T-B-07 (tests FAIL) → T-B-10 through T-B-12 (impl PASS)
- [US4] T-C-10 (test FAIL) → T-C-11 (mock impl) → T-C-12 (test PASS)

---

## Success Criteria Verification Map

| SC | Description | Task Verifying |
|----|-------------|---------------|
| SC-1 | Mode validation rejects unknown → exit 78 | T-A-01 |
| SC-2 | All 17 modes accepted → exit 0 | T-A-02 |
| SC-3 | Dead `mode` param removed from `run_dataset()` | T-A-04 |
| SC-4 | Mock baseline produces 51 DatasetResult entries | T-B-02 |
| SC-5 | Baseline JSON validates against BaselineReport schema | T-B-05 |
| SC-6 | All 9 orphan mode E2E tests pass | T-C-12 |
| SC-7 | Each orphan test asserts three-color verdict | T-C-10 (assertion in test) |
| SC-8 | Mode coverage visible in report | T-A-05, T-INT-07 |
| SC-9 | CI regression detection works with mock baseline | T-INT-01 (full suite pass) |

---

## Notes

- **No new runtime dependencies** — this spec adds zero dependencies beyond what `pyproject.toml` already declares.
- **No new database tables** — baseline JSON files are file-based snapshots in `docs/benchmarks/`.
- **Field reconciliation**: Test code MUST use actual model fields (`report.assessments`, `assessment.color`, `AssessmentColor.green/.amber/.red` — lowercase enum), NOT spec pseudocode (`report.clauses`, `color_verdict`, capitalized strings).
- **Mock gateway**: `monkeypatch.setattr("openreview_cli.gateway.router.Gateway.chat", ...)` — pattern from `test_benchmark_cuad.py`.
- **D-72 remains deferred**: `scripts/benchmarks/` directory skeleton not part of this spec.
- **PII dataset** (4th dataset) is skipped in multi-mode iteration per plan.md: `if dataset == "pii": continue`.
- **ASSERT all type errors are fixed** — no `# type: ignore`, no `Any` where concrete types exist, no `cast()` to suppress correct type checking.
