---

description: "Dependency-ordered task list for the Citation Grounding Discriminator (N-5) feature. Implements a post-hoc LLM-based discriminator that validates assessment claims against source document clauses."

---

# Tasks: Citation Grounding Discriminator (N-5)

**Input**: Design documents from `specs/012-citation-grounding/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/grounding-cli.md

**Tests**: TDD — tests MUST be written BEFORE the implementation they cover. Each test file starts as a failing test suite.

**Organization**: Tasks are grouped by user story. Each story is independently implementable and testable. US1 and US2 are both P1 (tied per §6.3) and form the MVP; they are grouped into a single phase because the discriminator naturally implements both modes in the same class.

> **⚠ ERROR**: `.specify/memory/task-context.md` not found. Constitution §Task Grounding Rule requires this file for path validation. Run `speckit.task-grounding` before executing any task. All paths below are based on plan.md and repo inspection — verify against task-context.md when available.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new `grounding/` module and establish its public API contract. No logic — just directory structure and exports.

- [x] **T001** Create `src/openreview_cli/grounding/` package directory with empty `__init__.py`
- [x] **T002** Populate `src/openreview_cli/grounding/__init__.py` with public API exports:
  - `run_grounding()` function
  - `CGReport`, `GroundingVerdict`, `CitationProvenance`, `GroundingResult`, `CGMetrics`, `DiscriminationAuditEntry`
  - `CitationGroundingDiscriminator`, `GroundingAuditLog`
  - Wire `__all__` for explicit exports matching `review/__init__.py` pattern

**Checkpoint**: `uv run python -c "from openreview_cli.grounding import run_grounding, CGReport, GroundingVerdict, CitationProvenance, CitationGroundingDiscriminator, GroundingAuditLog"` succeeds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, audit infrastructure, prompt templates, and ClauseAssessment schema expansion. ALL user stories depend on these modules being complete.

**⚠ CRITICAL**: No user story work can begin until this phase is complete.

- [x] **T003** [P] Create `src/openreview_cli/grounding/models.py` with:
    - `GroundingVerdict(StrEnum)` — `GROUNDED`, `UNGROUNDED`, `UNCERTAIN`
  - `CitationProvenance` dataclass (`slots=True`) — `clause_id: str`, `paragraph_index: int`, `confidence: float`
  - `GroundingResult` dataclass (`slots=True`) — `claim_index: int`, `verdict: GroundingVerdict`, `provenances: list[CitationProvenance]`, `reason: str | None`
  - `CGMetrics` dataclass (`slots=True`) — `citation_precision: float`, `citation_relevance: float`, `citation_locality: float`
  - `CGReport` dataclass — `verdicts: list[GroundingResult]`, `mode: Literal["strict", "lenient"]`, `metrics: CGMetrics`, `total_claims: int`, `grounded_count: int`, `ungrounded_count: int`, `uncertain_count: int`, `merge_into(report: ReviewReport) -> ReviewReport`
  - `DiscriminationAuditEntry` dataclass — `claim_hash: str`, `verdict: GroundingVerdict`, `confidence: float`, `provenances: list[CitationProvenance]`, `reason: str | None`, `timestamp: datetime`
  - Match existing dataclass patterns from `src/openreview_cli/review/models.py` (same import style, slot usage where appropriate)

- [x] **T004** [P] Create `src/openreview_cli/grounding/audit.py` with:
  - `GroundingAuditLog` — constructor takes `output_dir: str | Path`
  - `append(entry: DiscriminationAuditEntry) -> None` — writes JSON line immediately
  - `flush() -> None` — no-op for interface completeness
  - Output file: `{output_dir}/grounding-audit.jsonl`
  - Uses `hashlib.sha256(claim_text.encode()).hexdigest()` for claim hashing (Constitution §I)

- [x] **T005** [P] Create `src/openreview_cli/grounding/prompts.py` with:
  - `GROUNDING_PROMPT_TEMPLATE` — batched grounding prompt (5-10 claims per call)
  - `build_grounding_messages(source_clauses: list[Clause], claims: list[tuple[int, str, str]]) -> list[dict[str, str]]` — builds system+user messages for gateway chat
  - `parse_grounding_response(response: str) -> list[tuple[int, GroundingVerdict, list[CitationProvenance], float]]` — parses LLM response into structured results
  - Prompt instructs LLM to respond with structured JSON per claim: `{verdict, provenances: [{clause_id, paragraph_index, confidence}], confidence, reason}`
  - Match prompt template patterns from `src/openreview_cli/review/prompts.py`

- [x] **T006** [P] Add 3 optional fields to `ClauseAssessment` in `src/openreview_cli/review/models.py`:
  - `grounding_verdict: GroundingVerdict | None = None`
  - `grounding_provenances: list[CitationProvenance] | None = None`
  - `grounding_confidence: float | None = None`
  - Import `GroundingVerdict` and `CitationProvenance` from `openreview_cli.grounding.models` (lazy import or TYPE_CHECKING guard to avoid circular deps at module level)
  - All fields default to `None` — fully backwards compatible
  - Add test verifying existing `ClauseAssessment` instances (without grounding fields) still construct and serialize correctly via `dataclasses.asdict()`

- [x] **T007** [P] Write unit tests in `tests/unit/test_grounding_models.py`:
  - `GroundingVerdict` enum has correct string values
  - `CitationProvenance` construction and slots behavior
  - `GroundingResult` accepts all verdict types
  - `CGMetrics` field ranges (0.0-1.0 validation)
  - `CGReport` field defaults and `merge_into()` signature
  - `DiscriminationAuditEntry` SHA-256 hash behavior (same claim text → same hash, different text → different hash)
  - `CGReport.merge_into()` correctly sets ClauseAssessment fields in non-strict mode
  - `CGReport.merge_into()` removes ungrounded claims in strict mode
  - Edge case: empty claims list in `CGReport`

- [x] **T008** [P] Write unit tests in `tests/unit/test_grounding_audit.py`:
  - `GroundingAuditLog` creates output directory if missing
  - `append()` writes valid JSONL line
  - `append()` is unbuffered (file flushed after each write)
  - Flush is a no-op (no error)
  - Audit file path is `{output_dir}/grounding-audit.jsonl`
  - Multiple append entries are each on their own line
  - Claim hash is 64-character hex string (SHA-256)

**Checkpoint**: Foundation ready — `uv run pytest tests/unit/test_grounding_models.py tests/unit/test_grounding_audit.py -v` all pass. User story implementation can now begin.

---

## Phase 3: US1 + US2 — Strict & Lenient Grounding (Priority: P1) 🎯 MVP

**Goal**: Deliver both strict mode (ungrounded claims excluded) and lenient mode (ungrounded claims flagged) as a combined MVP. Both are P1 per spec §6.3 — the discriminator class implements both modes via a `mode` parameter. Multi-provenance behavior is mode-dependent: strict flags uncertain, lenient assigns all matching provenances with a warning.

**Independent Test**: Feed a `ReviewReport` with 10 claims (8 grounded, 2 deliberately ungrounded). Strict mode returns 8 claims with warnings. Lenient mode returns 10 claims with 2 flagged ungrounded.

### Tests for US1 + US2 (TDD — write first, expect fail)

- [x] **T009** [P] Write discriminator unit tests in `tests/unit/test_grounding_discriminator.py`:
  - Test `CitationGroundingDiscriminator.__init__()` with default strict mode, explicit lenient mode, and custom gateway/model
  - Test `ground_claim()` — returns `(GroundingVerdict, list[CitationProvenance], confidence)` tuple structure
  - Test strict mode: ungrounded claims are excluded from output (via `ground_report()` → `CGReport.merge_into()`)
  - Test lenient mode: all claims retained, ungrounded/uncertain flagged
  - Test skip logic: claims with `citation_valid=False` are skipped (no discriminator processing)
  - Test empty claims list: returns empty `CGReport` with 0 counts, no error
  - Test multi-provenance: strict mode flags as uncertain (default ungrounded), lenient mode assigns all matching provenances with warning
  - Test edge cases: duplicate clause IDs, no clause structure in document, zero-length claims (logged warning), encoding errors (logged warning, no crash)
  - Test claim index linkage: `GroundingResult.claim_index` correctly maps back to `ClauseAssessment` position in `ReviewReport.assessments`
  - Test `merge_into()` behavior in strict mode: UNGROUNDED and UNCERTAIN claims removed from `assessments` list, warnings logged
  - Test `merge_into()` behavior in lenient mode: all claims retained, `grounding_verdict` set on each
  - Verify `reason` field populated for ungrounded/uncertain verdicts

### Implementation for US1 + US2

- [x] **T010** Implement `src/openreview_cli/grounding/discriminator.py`:
  - `CitationGroundingDiscriminator.__init__(mode="strict", gateway=None, model=None)` — stores mode, creates Gateway instance if not provided
  - `ground_claim(claim_text, cited_clause_id, clause_text) -> tuple[GroundingVerdict, list[CitationProvenance], float]` — single claim grounding via gateway call
  - `ground_report(report, document) -> CGReport` — processes all claims in a ReviewReport:
    - Reads `citation` field from each `ClauseAssessment` to determine cited clause
    - Skips claims where `qa_verdict` is `QAVerdict.disagree` or `citation_valid=False` (uses existing checks)
    - Batches claims (5-10 per gateway call) using `build_grounding_messages()` from prompts.py
    - Calls `gateway.chat("grounding", messages)` for each batch (reuses existing grounding slot)
    - Parses response via `parse_grounding_response()` from prompts.py
    - Applies mode-dependent multi-provenance rules
    - Constructs `CGReport` with per-claim verdicts and provenances
    - Records audit entries for every claim
  - Uses `GroundingAuditLog` for audit trail
  - Uses `compute_cg_metrics()` from metrics.py for CP/CR/CL computation
  - Edge case handling: empty claims → empty CGReport, duplicate IDs → flag as uncertain with logged warning, no clause structure → paragraph-only grounding with warning, zero-length claims → trivially ungrounded with logged warning

- [x] **T011** Wire grounding into the review pipeline in `src/openreview_cli/review/__init__.py`:
  - Update `run_review()` to accept optional `grounding_mode: str | None = None` parameter
  - After the QA phase (line ~125 in current code), add Phase 5: Grounding
  - Import `run_grounding` from `openreview_cli.grounding` (lazy import — only when grounding mode is set)
  - Call `grounding_result = run_grounding(report, doc, mode=grounding_mode)`
  - Call `grounding_result.merge_into(report)` to populate ClauseAssessment fields
  - In strict mode, ungrounded claims are removed from the assessments list; warnings printed to stderr
  - Guard: `if grounding_mode is not None` — `None` means skip grounding (backwards compatible)
  - Guard: `if not assessments` — skip grounding when no claims to process
  - Guard: if gateway is unavailable, log warning and continue without grounding (graceful degradation per FR-010)

- [x] **T012** Wire grounding CLI flags in `src/openreview_cli/app.py`:
  - Add `--grounding-mode` option to `precheck review` command: `Literal["strict", "lenient"]` (default `strict`)
  - Add `--no-grounding` flag to `precheck review` command (disables grounding entirely)
  - Pass `grounding_mode` parameter to `run_review()` — `None` when `--no-grounding` is set
  - Match existing flag patterns (e.g., `--no-pii` for boolean flags, `--extraction-model` for string options)
  - CLi contract per `specs/012-citation-grounding/contracts/grounding-cli.md`:
    - `openreview precheck contract.pdf --grounding-mode=strict` (default, can omit)
    - `openreview precheck contract.pdf --grounding-mode=lenient`
    - `openreview precheck contract.pdf --no-grounding`
  - Update `format_terminal()` and `format_json()` calls in the review command to include grounding data when present
  - Validate `--grounding-mode` value (error on invalid values)

- [x] **T013** Write integration test in `tests/integration/test_grounding_pipeline.py`:
  - End-to-end test: seeded `ReviewReport` → `run_grounding()` → merged `ReviewReport` with grounding fields
  - Uses mock gateway (monkeypatch `Gateway.chat()` to return canned grounding responses)
  - Verifies strict mode: 2 ungrounded claims excluded, output contains 8 of 10 claims
  - Verifies lenient mode: all 10 claims present, 2 flagged ungrounded
  - Verifies skip logic: claims with `citation_valid=False` are not sent to gateway
  - Verifies `merge_into()` produces correct `ClauseAssessment` field values
  - Verifies audit log is written when grounding runs
  - Verifies audit log is NOT written when `--no-grounding`
  - Verifies empty claims list produces empty CGReport with no error
  - Match test patterns from existing integration tests (e.g., `tests/integration/test_parse_command.py`)
  - Use `tests/fixtures/` for test data, not inline fixtures for complex data

**Checkpoint**: At this point, MVP is shippable. Both strict and lenient modes work end-to-end.

---

## Phase 4: US3 — Audit & Provenance Inspection (Priority: P2)

**Goal**: Allow compliance officers to inspect citation provenance for individual claims. The audit log records every discrimination decision. Report formatting displays grounding verdicts in terminal tables and JSON output.

**Independent Test**: Run grounding on a known report, inspect audit log file for completeness, and verify per-claim provenance fields in terminal/JSON output.

- [x] **T014** [P] Write audit integration tests in `tests/unit/test_grounding_discriminator.py`:
  - `test_audit_log_completeness`: after grounding 10 claims, audit log contains exactly 10 entries
  - `test_audit_log_content`: each entry has non-empty `claim_hash`, valid `verdict`, `confidence` in [0.0, 1.0], valid ISO-8601 `timestamp`
  - `test_audit_log_reason`: ungrounded/uncertain claims have populated `reason` field; grounded claims have `reason=None`
  - `test_audit_log_integrity`: claim hashes are deterministic (same claim text → same hash across multiple runs)
  - `test_audit_log_skip`: claims skipped due to `citation_valid=False` do NOT appear in audit log

- [x] **T015** Integrate audit log with grounding pipeline in `src/openreview_cli/grounding/discriminator.py`:
  - `CitationGroundingDiscriminator` creates a `GroundingAuditLog` instance on init
  - Every `ground_claim()` call appends a `DiscriminationAuditEntry` via `ground_report()`
  - Audit log output directory: configured via `output_dir` parameter (defaults to cwd or `--output` from CLI)
  - Audit entries include: claim hash (SHA-256), verdict, confidence, provenances, reason (if ungrounded/uncertain), timestamp
  - Claims skipped due to `citation_valid=False` do NOT generate audit entries (no redundant noise)
  - Audit log path is logged to `logger.info` on first write

- [x] **T016** Extend report formatter in `src/openreview_cli/review/report.py`:
  - **Terminal table** (`format_terminal()`):
    - Add grounding verdict column after "Status" column: `G` (grounded, green), `U` (ungrounded, red), `?` (uncertain, yellow), `—` (not processed)
    - Use Rich styling: `[green]G[/green]`, `[red]U[/red]`, `[yellow]?[/yellow]`, `[dim]—[/dim]`
    - In strict mode, print excluded claim warnings to stderr: `"⚠ Claim #3 '...' excluded: not grounded in clause 4.3"`
    - Add grounding summary line after amber count: `"Grounding: 8/10 claims grounded, 1 ungrounded, 1 uncertain (strict mode)"`
    - Column width: 6 chars for grounding verdict
    - Only display grounding column when at least one assessment has non-None `grounding_verdict`
  - **JSON output** (`format_json()` via `_report_to_dict()`):
    - `dataclasses.asdict()` already includes the new optional fields — they serialize as `null` when unset
    - No changes needed to JSON serialization logic
    - Verify that grounding fields appear in JSON output when populated

- [x] **T017** Write report formatting tests in `tests/unit/test_grounding_discriminator.py` or a new test file:
  - `test_terminal_grounding_column`: terminal output contains grounding verdict column when grounding data present
  - `test_terminal_no_grounding_column`: terminal output has no grounding column when grounding is absent
  - `test_terminal_grounding_summary`: terminal output contains grounding summary line
  - `test_json_grounding_fields`: JSON output contains `grounding_verdict`, `grounding_provenances`, `grounding_confidence` when populated
  - `test_json_grounding_null`: JSON output shows `null` for grounding fields when not processed
  - `test_terminal_excluded_claims`: strict mode shows warnings for excluded claims on stderr
  - Match existing test patterns from `tests/unit/` (check for Rich console output via string matching)

**Checkpoint**: Audit trail is inspectable and report formatting includes grounding information.

---

## Phase 5: US4 — Accuracy Validation & CG Metrics (Priority: P3)

**Goal**: Developers can validate discriminator accuracy against a seeded corpus. Structural CG metrics (CP/CR/CL) are computed deterministically. CG-DPO detector wires into the existing benchmark harness.

**Independent Test**: Run CG metrics against known inputs and verify expected values. Run discriminator against seeded corpus and verify ≥98.5% accuracy.

- [x] **T018** [P] Write CG metrics unit tests in `tests/unit/test_grounding_metrics.py`:
  - `test_cp_all_valid`: 100% CP when all cited clause_ids exist in document
  - `test_cp_some_invalid`: 50% CP when half of cited clause_ids are missing
  - `test_cp_zero_claims`: CP is 1.0 (no grounded claims = vacuously precise)
  - `test_cr_all_valid`: 100% CR when all claim texts appear in cited clauses (case-insensitive substring match)
  - `test_cr_some_invalid`: partial CR when some claims don't match clause text
  - `test_cr_zero_claims`: CR is 1.0 (vacuously relevant)
  - `test_cl_all_valid`: CL is 1.0 when all paragraph indices are within cited clause bounds
  - `test_cl_some_invalid`: CL < 1.0 when some paragraph indices exceed clause length
  - `test_cl_zero_claims`: CL is 1.0 (vacuously local)
  - `test_all_metrics_together`: compute CP=1.0, CR=0.75, CL=1.0 for a mixed corpus
  - `test_metrics_no_grounded_claims`: edge case when no claims are grounded (metrics return 0.0)
  - All metrics return floats in [0.0, 1.0]

- [x] **T019** Implement `compute_cg_metrics()` in `src/openreview_cli/grounding/metrics.py`:
  - `compute_cg_metrics(verdicts: list[GroundingResult], document: Document) -> CGMetrics`
  - **CP** (Citation Precision): `count(claims where cited clause_id in Document.clauses) / count(grounded claims)`
    - O(1) per claim via `set(clause.clause_id for clause in document.clauses)` hash lookup
    - Returns 1.0 if no grounded claims (vacuously precise per P-6 convention)
  - **CR** (Citation Relevance): `count(claims where claim_text.lower() in cited_clause_text.lower()) / count(grounded claims)`
    - Simple substring check (case-insensitive)
    - Returns 1.0 if no grounded claims
    - Ponytail: simple `in` operator — semantic relevance deferred
  - **CL** (Citation Locality): `avg(paragraph_index < len(cited_clause.paragraphs) for each grounded claim)`
    - Each claim's `paragraph_index` validated against cited clause's paragraph count
    - Returns 1.0 if no grounded claims
  - All three metrics are O(n) deterministic, no LLM calls, no imports beyond stdlib

- [x] **T019b** [P] [US4] Create `HallucinationDetector` ABC and `LexicalOverlapDetector` in `src/openreview_cli/benchmark/hallu_detect.py`:
  - Define `class HallucinationDetector(ABC):` with abstract method `detect(self, claims: list[str], sources: list[str]) -> list[bool]`
  - Refactor existing standalone `detect_lexical()` and other functions into `class LexicalOverlapDetector(HallucinationDetector):`
  - Move standalone `detect_hallucinations()` orchestration into the class if it wraps the detector
  - Wire `CGDPODetector(HallucinationDetector)` in T020 to use the same ABC
  - All existing callers of standalone functions continue to work (delegation methods kept as backward-compatible wrappers or updated to use the new classes)
  - Write tests in `tests/unit/test_grounding_discriminator.py`:
    - `test_hallucination_detector_abc`: ABC cannot be instantiated directly
    - `test_lexical_overlap_detector`: wraps existing lexical detection logic
    - `test_hallucination_detector_interface_enforcement`: non-implementing class raises TypeError

- [x] **T020** [P] Add `CGDPODetector` in `src/openreview_cli/benchmark/hallu_detect.py`:
  - New class implementing `HallucinationDetector` interface (implicit — no formal ABC, same pattern as existing `LexicalOverlapDetector`)
  - `__init__(self, mode: str = "strict", gateway=None, model=None)` — stores config, creates `CitationGroundingDiscriminator` on first use
  - `detect(self, claims: list[str], sources: list[str]) -> list[bool]`:
    - Wraps `CitationGroundingDiscriminator.ground_report()` by creating synthetic `ReviewReport` and `Document` from inputs
    - Maps verdicts: `GROUNDED → True`, `UNGROUNDED → False`, `UNCERTAIN → False` (conservative per R-9)
    - Returns `True` for grounded (no hallucination detected), `False` for ungrounded (hallucination detected)
  - Works with the existing benchmark harness CLI flag `--hallucination-method=cg-dpo` (per AGENTS.md transition plan)
  - Default stays `lexical`; `cg-dpo` is opt-in until TRL 7+

- [x] **T021** [P] Create corruption strategy generators in `tests/fixtures/grounding/`:
  - `generate_seed_corpus.py` — generates ≥1,000 seeded claims with ground truth labels
  - Four adapted corruption strategies (P-6 → contract domain):
    - `clause_swap`: Replace correct clause_id with different clause_id from same document
    - `category_swap`: Replace playbook category while keeping clause text; creates category-level mismatch
    - `hallucination`: Generate claim text with no support in any clause (pure fabrication)
    - `anachronism`: Cite non-existent clause ID (e.g., "v99.99") or version mismatch
  - Outputs `tests/fixtures/grounding/claims.json` with schema:
    ```json
    {"claim_text": "...", "cited_clause_id": "4.3", "ground_truth": true, "corruption_type": null}
    {"claim_text": "...", "cited_clause_id": "7.1", "ground_truth": false, "corruption_type": "clause_swap"}
    ```
  - Write tests in `tests/unit/test_grounding_discriminator.py`:
    - `test_accuracy_above_985`: ≥98.5% overall accuracy against the seeded corpus (requires ground_truth.json)
    - `test_accuracy_per_corruption`: No corruption type below 95% accuracy
    - Note: these tests require the seeded corpus to exist; mark with `@pytest.mark.slow` if >1s to run
    - Note: these tests require a live LLM via gateway; mark with `@pytest.mark.integration` to exclude from CI fast test suite

- [x] **T022** Write CG metrics implementation tests in `tests/unit/test_grounding_metrics.py` (continuing from T018):
  - Test `compute_cg_metrics()` integration with actual `CGReport` and `Document` objects
  - Test that `compute_cg_metrics()` is callable from `CitationGroundingDiscriminator.ground_report()`
  - Verify CP/CR/CL values in `CGReport.metrics` after a full grounding run

**Checkpoint**: Accuracy validation pipeline works. CG metrics computed. CGDPODetector available for benchmark harness.

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: Final integration, validation, and quality checks.

- [x] **T023** Create grounding test fixtures:
  - `tests/fixtures/grounding/claims.json` — seeded corpus (1,000+ claims with ground truth, T021)
  - `tests/fixtures/grounding/seed_doc.pdf` — source document for seeded corpus
  - `tests/fixtures/grounding/ground_truth.json` — expected verdicts for accuracy measurement
  - Small inline test fixtures in test files for fast unit tests (not requiring the full corpus)

- [x] **T024** Run full test suite: `uv run pytest`
  - All unit tests pass (including new grounding tests)
  - All integration tests pass (including new grounding pipeline tests)
  - Memory tests pass (`uv run pytest -m memory`)
  - Fix any regressions: existing tests must not break from ClauseAssessment field additions

- [x] **T025** Run lint: `uv run ruff check .` — zero new violations
  - Fix any new lint issues
  - Run format check: `uv run ruff format --check .` — zero formatting diffs

- [x] **T026** Run type check: `uv run mypy src/ tests/` — zero new typing errors
  - No `# type: ignore` for grounding module code
  - `Literal["strict", "lenient"]` typed correctly
  - Import guarding for `GroundingVerdict` / `CitationProvenance` in `review/models.py` using `TYPE_CHECKING`

- [x] **T027** Run pre-commit: `uv run pre-commit run --all-files` — all hooks pass
  - `ruff --fix` — no issues
  - `ruff-format` — no reformatting
  - `mypy` — clean
  - `pytest-fast` — fast tests pass
  - stdlib hygiene — no issues

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 + US2 (Phase 3)**: Depends on Foundational — BLOCKS all subsequent phases
- **US3 (Phase 4)**: Depends on Phase 3 (requires discriminator to produce audit data)
- **US4 (Phase 5)**: Depends on Phase 3 (requires discriminator for accuracy testing); independent from US3
- **Polish (Phase 6)**: Depends on all desired stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    └── Phase 2 (Foundational)
            ├── Phase 3 (US1+US2 — Strict & Lenient) ← MVP
            │       ├── Phase 4 (US3 — Audit & Provenance)
            │       └── Phase 5 (US4 — Accuracy)
            └── Phase 6 (Polish)
```

- **US1 + US2 (P1)**: Can start after Foundational (Phase 2). Core discriminator — both modes required per §6.3.
- **US3 (P2)**: Can start after US1+US2 complete. Extends discriminator with audit integration and report formatting.
- **US4 (P3)**: Can start after US1+US2 complete. Adds metrics module, CG-DPO detector, and accuracy validation.
- US3 and US4 are independent of each other and can run in parallel after Phase 3.

### Within Each Phase

- Tests (marked TDD) MUST be written and FAIL before implementation
- Data models before services
- Core implementation before integration
- Phase complete before moving to next

### Parallel Opportunities

- All Phase 1 tasks: sequential (small, one file at a time)
- All Phase 2 tasks marked [P]: run in parallel (4 independent files: models.py, audit.py, prompts.py, review/models.py, plus 2 test files)
- Phase 4 tasks T014 and T016: run in parallel (audit tests and report formatting)
- Phase 5 tasks T018/T019 (metrics) and T020/T021 (CGDPODetector + corpus): run in parallel
- Phase 6 tasks T024–T027: sequential (each depends on previous fix cycle)

### Parallel Execution Example (Phase 2)

```bash
# Launch all 6 independent Phase 2 tasks in parallel:
Task: "Create models.py"                          # T003
Task: "Create audit.py"                           # T004
Task: "Create prompts.py"                         # T005
Task: "Add fields to ClauseAssessment"            # T006
Task: "Write test_grounding_models.py"            # T007 (tests written first, expect fail)
Task: "Write test_grounding_audit.py"             # T008 (tests written first, expect fail)
```

---

## Implementation Strategy

### MVP Focus (Phase 1 → 2 → 3)

The MVP delivers US1 + US2 (both P1, per spec §6.3 requirement). This provides:
- A working LLM-based citation grounding discriminator
- Both strict mode (safe default) and lenient mode (visibility-first)
- Full integration with the existing review pipeline
- CLI flags (`--grounding-mode=strict|lenient`, `--no-grounding`)

**MVP ship**: Stop after Phase 3 (T013 complete).

### Full Delivery (MVP + Polish)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1+US2 → Ship MVP
4. Complete Phase 4: US3 → Audit & provenance
5. Complete Phase 5: US4 → Accuracy validation
6. Complete Phase 6: Polish

---

## Summary

| Item | Count |
|------|-------|
| **Total tasks** | 28 |
| Phase 1 (Setup) | 2 |
| Phase 2 (Foundational) | 6 |
| Phase 3 (US1+US2 — P1 MVP) | 5 |
| Phase 4 (US3 — P2) | 4 |
| Phase 5 (US4 — P3) | 6 |
| Phase 6 (Polish) | 5 |
| [P] parallel tasks | 8 |
| New source files | 5 (`__init__.py`, `models.py`, `discriminator.py`, `metrics.py`, `audit.py`, `prompts.py`) |
| Modified source files | 5 (`review/models.py`, `review/__init__.py`, `review/report.py`, `benchmark/hallu_detect.py`, `app.py`) |
| New test files | 5 (`test_grounding_models.py`, `test_grounding_discriminator.py`, `test_grounding_metrics.py`, `test_grounding_audit.py`, `test_grounding_pipeline.py`) |
| New fixture files | 3 (`claims.json`, `seed_doc.pdf`, `ground_truth.json`) |

### MVP scope (Phase 1-3, 13 tasks)

The MVP includes strict + lenient grounding with full pipeline integration and CLI flags. This is shippable as a standalone feature — audit inspection (US3) and accuracy validation (US4) are additive enhancements.

### File creation order

1. `src/openreview_cli/grounding/__init__.py`
2. `src/openreview_cli/grounding/models.py` + `tests/unit/test_grounding_models.py`
3. `src/openreview_cli/grounding/audit.py` + `tests/unit/test_grounding_audit.py`
4. `src/openreview_cli/grounding/prompts.py`
5. Modify `src/openreview_cli/review/models.py`
6. `src/openreview_cli/grounding/metrics.py` + `tests/unit/test_grounding_metrics.py`
7. `src/openreview_cli/grounding/discriminator.py` + `tests/unit/test_grounding_discriminator.py`
8. Modify `src/openreview_cli/review/__init__.py`
9. Modify `src/openreview_cli/review/report.py`
10. Modify `src/openreview_cli/benchmark/hallu_detect.py`
11. Modify `src/openreview_cli/app.py`
12. `tests/integration/test_grounding_pipeline.py`
13. `tests/fixtures/grounding/`
