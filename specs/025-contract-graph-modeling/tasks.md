---
description: "Feature implementation tasks for Contract Graph Modeling (025)"

---

# Tasks: Contract Graph Modeling — Heuristic Structural Metrics and Health Score

**Input**: Design documents from `specs/025-contract-graph-modeling/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), data-model.md, contracts/cli-contract.md

**Tests**: Test tasks included per spec requirement — spec.md explicitly mandates TDD (tests before implementation).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format

- `[P]` = parallelizable (different files, no dependencies)
- `[Story]` = user story label (US1–US4)
- Exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Understand existing graph API patterns, verify env, load contracts.

- [x] T001 Read `src/openreview_cli/parsing/models.py` — examine `Clause` dataclass fields (id, title, text, level, parent_id) consumed by graph builder
- [x] T002 Read `src/openreview_cli/app.py` existing command groups (parse, review, gateway) to understand Typer group registration pattern
- [x] T003 Read `specs/025-contract-graph-modeling/contracts/cli-contract.md` and `data-model.md` for interface contracts
- [x] T004 Read `specs/025-contract-graph-modeling/research.md` for key design decisions
- [x] T005 Verify runtime env: `python3 --version`, `uv run pytest tests/unit/ -q` — confirm green on existing tests

---

## Phase 2: Foundational — Graph Data Models (P1, blocking)

**Purpose**: Define `GraphNode`, `GraphEdge`, `EdgeType`, `ContractGraph` dataclasses. Adjacency-list representation. JSON serialisation round-trip.

**Dependencies**: Phase 1 complete. BLOCKS all user stories.

### Tests (TDD: write first, ensure failure, then implement)

- [x] T006 [US1] Write unit tests in `tests/unit/test_graph_models.py`:
  - GraphNode creation with valid/invalid fields
  - EdgeType enum values (parent_child, cross_ref, def_ref)
  - GraphEdge creation with source/target/type
  - ContractGraph adjacency property (derived from edges)
  - ContractGraph inbound property
  - ContractGraph roots property
  - ContractGraph orphan_ids property
  - JSON round-trip: `to_json()` → `from_json()` yields equal graph
  - Edge cases: empty graph, single node, max edges
  - Self-referencing edge exclusion
  - `to_file()` / `from_file()` convenience methods

### Implementation

- [x] T007 [P] [US1] Create `src/openreview_cli/graph/__init__.py` — public exports: `GraphNode`, `GraphEdge`, `EdgeType`, `ContractGraph`
- [x] T008 [P] [US1] Create `src/openreview_cli/graph/models.py` with:
  - `GraphNode(id: str, label: str, text: str, level: int, metadata: dict)`
  - `EdgeType` enum: `parent_child`, `cross_ref`, `def_ref`
  - `GraphEdge(source_id: str, target_id: str, edge_type: EdgeType, metadata: dict)`
   - `ContractGraph(nodes: dict[str, GraphNode], edges: list[GraphEdge], metadata: dict[str, Any] = {})` with adjacency, inbound, roots, orphan_ids properties
   - `to_json()`, `from_json()`, `to_file()`, `from_file()` methods
- [x] T009 [P] [US1] Update `src/openreview_cli/__init__.py` — add `graph` to exports

**Checkpoint**: Foundation ready — graph models compile, serialise round-trip, pass unit tests.

---

## Phase 3: User Story 1 — Graph Build from Parsed Clauses (Priority: P1) 🎯 MVP

**Goal**: Build a directed clause graph from a parsed contract JSON file. Hierarchy edges from `Clause.parent_id`; cross-ref and def-ref edges detected via regex.

**Independent Test**: Parse a synthetic contract into known clause structure with known cross-references, build the graph, verify node/edge counts match expected structure.

**Dependencies**: Phase 2 complete (models). Also depends on `src/openreview_cli/parsing/models.py` `Clause` dataclass.

### Tests for User Story 1 (TDD: write first, ensure failure, then implement)

- [x] T010 [P] [US1] Write unit tests in `tests/unit/test_graph_builder.py`:
  - Clause hierarchy: `parent_id` mappings produce correct parent-child edges
  - Clause with null `parent_id` → root node
  - Clause with dangling `parent_id` → root node or warning
  - Edge cases: all roots (null parent_id), single clause, mixed hierarchy
  - `build_from_parsed` convenience with JSON load
- [x] T011 [P] [US1] Write unit tests in `tests/unit/test_graph_detectors.py`:
  - CrossReferenceDetector default patterns match "Section 3.2", "as set forth in Section 7.1", "pursuant to Section 5"
  - Self-reference exclusion (source matches target)
  - Extensible `patterns: list[re.Pattern]` parameter
  - DefinitionDetector matches quoted terms: `"Confidential Information" means...`, `'Term' shall mean...`, `'Widget' refers to...`
  - Capitalised term heuristic: `Confidential Information means...`
  - `extract_definitions(clauses)` returns dict[term → clause_id]
  - `count_references(text, definitions)` returns list of (term, clause_id) pairs
- [x] T012 [US1] Write integration tests in `tests/integration/test_graph_command.py` — end-to-end: parse → build → verify hierarchy + cross-ref + def-ref edges

### Implementation for User Story 1

- [x] T013 [P] [US1] Create `src/openreview_cli/graph/builder.py` with:
  - `ClauseHierarchyBuilder.build(clauses: list[Clause]) -> ContractGraph`
  - Use `Clause.parent_id` to build `parent_child` edges directly
  - For each clause, match `parent_id` to a GraphNode ID to establish parent link
  - Handle edge cases: null parent_id → root node, dangling parent_id → root or warn
  - `build_from_parsed(path: str) -> ContractGraph` convenience
- [x] T014 [P] [US1] Create `src/openreview_cli/graph/detectors.py` with:
  - `CrossReferenceDetector(patterns: list[re.Pattern] | None = None)` — default patterns: `Section\s+(\d+\.?\d*)`, `as (?:described|set forth|provided)\s+in\s+(?:Section\s+)?(\d+\.?\d*)`, `pursuant\s+to\s+(?:Section\s+)?(\d+\.?\d*)`
  - `detect(text: str) -> list[str]` returns target clause IDs, ignores self-references
  - `DefinitionDetector` — `extract_definitions(clauses: list[Clause]) -> dict[str, str]`, `count_references(text: str, definitions: dict[str, str]) -> list[tuple[str, str]]`
- [x] T015 [US1] Wire detectors into builder pipeline: after building hierarchy edges, scan all clause text for cross-refs and def-refs, add those edges to the graph
- [x] T016 [US1] Update `src/openreview_cli/graph/__init__.py` — export `ClauseHierarchyBuilder`, `build_from_parsed`, `CrossReferenceDetector`, `DefinitionDetector`

**Checkpoint**: `build_from_parsed` produces graph with hierarchy + cross-ref + def-ref edges. Unit + integration tests pass.

---

## Phase 4: User Story 2 — Heuristic Metric Computation (Priority: P1)

**Goal**: Compute five heuristic structural metrics from a built graph — density, max depth, orphan ratio, broken cross-reference count, definition coverage.

**Independent Test**: Build a known synthetic graph structure, run metrics, verify each metric against hand-calculated expected value.

**Dependencies**: Phase 3 (detectors provide def-ref edges).

### Tests for User Story 2 (TDD: write first, then implement)

- [x] T017 [P] [US2] Write unit tests in `tests/unit/test_graph_metrics.py`:
  - Density: 0 for single node, 0.5 for 2 nodes with 1 edge, 0 for 0 nodes
  - Max depth: 1 for flat, 3 for A→B→C chain, 0 for empty
  - Orphan ratio: 0 for complete hierarchy, 0.5 for 1 orphan out of 2 nodes
  - Broken cross-ref count: 0 for all valid refs, N for N missing targets
  - Definition coverage: 1.0 for all-terms-defined, 0.5 for half-defined, 1.0 for no refs (trivially)
  - Edge cases: empty graph → all zeros; single node → density=0, depth=1, orphan=0, broken=0, coverage=1.0

### Implementation for User Story 2

- [x] T018 [P] [US2] Create `src/openreview_cli/graph/metrics.py` with:
  - `GraphMetrics` dataclass: `density: float`, `max_depth: int`, `orphan_ratio: float`, `broken_ref_count: int`, `definition_coverage: float`
  - `compute_metrics(graph: ContractGraph) -> GraphMetrics` implementing algorithms from data-model.md §3.2
  - Edge case handling: empty → all zeros; single node → defined values
  - Update `src/openreview_cli/graph/__init__.py` — export `GraphMetrics`, `compute_metrics`

**Checkpoint**: `compute_metrics` produces correct values on synthetic graphs. Unit tests pass.

---

## Phase 5: User Story 3 — Health Score (Priority: P2)

**Goal**: Combine five metrics into a single 0-100 contract health score using weighted formula. Configurable weights.

**Independent Test**: Compute metrics on synthetic graph, manually apply formula with known weights, verify health score matches.

**Dependencies**: Phase 4 (metrics).

### Tests for User Story 3 (TDD: write first, then implement)

- [x] T019 [P] [US3] Write unit tests in `tests/unit/test_graph_health.py`:
  - Default weights produce expected score for known metric values
  - Perfect graph (empty/single node) → score = 100
  - Pathological graph (all broken, all orphaned) → score = 0
  - Custom weights change score
  - Weights that don't sum to 1.0 are normalised with warning on stderr (use `capsys`)
  - All-zero weights fall back to defaults
  - Wrong weight count raises error

### Implementation for User Story 3

- [x] T020 [P] [US3] Create `src/openreview_cli/graph/health.py` with:
  - `HealthScore` dataclass: `score: int`, `weights: list[float]`
  - Constants: `MAX_EXPECTED_DEPTH = 10`, `MAX_EXPECTED_BROKEN_REFS = 10`
  - `compute_health(metrics: GraphMetrics, weights: list[float] | None = None) -> HealthScore`
  - Default weights: `[0.15, 0.20, 0.20, 0.25, 0.20]`
  - Normalisation: `normalized_depth = min(max_depth / MAX_EXPECTED_DEPTH, 1.0)`, `broken_ref_ratio = min(broken_ref_count / MAX_EXPECTED_BROKEN_REFS, 1.0)`
  - Formula: `raw = sum(w * c)`, `score = round(clamp(raw * 100, 0, 100))`
  - Weight normalisation with stderr warning if sum ≠ 1.0
  - Update `src/openreview_cli/graph/__init__.py` — export `HealthScore`, `compute_health`

**Checkpoint**: Health score computed correctly. Unit tests pass.

---

## Phase 6: User Story 4 — Text Tree View (Priority: P3) [P]

**Goal**: Render clause hierarchy as ASCII indented text tree with cross-ref/def annotations. No rich.Tree, no graphviz — pure stdlib string formatting.

**Dependencies**: Phase 2 only (models). Can run in parallel with Phases 3-5.

### Tests (TDD: write first, then implement)

- [x] T021 [P] [US4] Write unit tests in `tests/unit/test_graph_view.py`:
  - Indentation: root at 0, children at +2 spaces per level
  - Root nodes printed first, children indented under parent
  - Cross-ref annotation: `[3 refs out]` for nodes with 3 outgoing cross-ref edges
  - Def-ref annotation: `[DEF-REF: 2]` for nodes using 2 defined terms; `[DEFINES: "term"]` for definition nodes
  - Orphan marking: `[ORPHAN]` for nodes with no parent and has children
  - Empty graph → empty output; single node → single line
  - `color=True` adds ANSI codes (red for orphan, yellow for high ref count)
  - `color=False` produces no ANSI codes

### Implementation

- [x] T022 [P] [US4] Create `src/openreview_cli/graph/view.py` with:
  - `render_tree(graph: ContractGraph, color: bool = False) -> str`
  - Find root nodes (no parent), DFS from each root
  - Format: `{label}  {text_snippet}  [{N refs out}] [DEF-REF: N] [ORPHAN]`
  - No ANSI codes unless `color=True`
  - Update `src/openreview_cli/graph/__init__.py` — export `render_tree`

**Checkpoint**: Text tree renders correctly for any valid graph. Unit tests pass.

---

## Phase 7: CLI Integration (Priority: P1)

**Goal**: `openreview graph` subcommand group with `build`, `metrics`, `health`, `view` subcommands.

**Dependencies**: All Phases 2-6 complete.

### Tests (TDD: write first, then implement)

- [x] T023 [P] [US1+US2+US3+US4] Write CLI integration tests in `tests/integration/test_graph_command.py`:
  - `graph build` smoke test: create temp parsed JSON → build → verify JSON output file exists with correct structure
  - `graph build` non-existent file → exit code 1
  - `graph build` malformed JSON → exit code 2
  - `graph metrics` smoke test: build graph → compute metrics → verify output contains "Density", "Max Depth", etc.
  - `graph metrics` non-existent file → exit code 1
  - `graph health` smoke test: build graph → compute health → verify "Health Score: N/100" in output
  - `graph health` with custom weights → score differs from default
  - `graph health` non-normalised weights → warning on stderr
  - `graph health` non-existent file → exit code 1
  - `graph view` smoke test: build graph → render tree → verify indented output
  - `graph view --color` → ANSI codes present
  - `graph view` non-existent file → exit code 1
  - `openreview graph --help` shows all subcommands

### Implementation

- [x] T024 [P] [CLI] Add `graph_app = typer.Typer(name="graph", help="Build and analyse contract clause graphs.")` to `src/openreview_cli/app.py`
- [x] T025 [P] [US1] Implement `graph_build` command: read parsed JSON → `build_from_parsed` → serialize to output → echo summary. Error handling: file-not-found → exit 1, bad JSON → exit 2
- [x] T026 [P] [US2] Implement `graph_metrics` command: load graph → `compute_metrics` → print formatted table. Error handling: file-not-found → exit 1, bad JSON → exit 2
- [x] T027 [P] [US3] Implement `graph_health` command: load graph → `compute_metrics` → `compute_health` → print score. Validate `--weights` has exactly 5 non-negative floats. Error handling: file-not-found → exit 1, bad JSON/bad weights → exit 2
- [x] T028 [P] [US4] Implement `graph_view` command: load graph → `render_tree` → print to stdout. Error handling: file-not-found → exit 1, bad JSON → exit 2
- [x] T029 Register `app.add_typer(graph_app)` in `src/openreview_cli/app.py` — wire all 4 subcommands

**Checkpoint**: All four `openreview graph` subcommands work end-to-end. Integration tests pass.

---

## Phase 8: Memory Profiling and Validation (Priority: P1)

**Purpose**: Verify peak memory <100 MB for graph operations using existing `memory_tracker` fixture. Run full pre-commit suite.

**Dependencies**: All phases complete.

### Tests

- [x] T030 Add memory test in `tests/integration/test_memory.py`:
  - Build 500-node synthetic graph with `ClauseHierarchyBuilder`
  - Compute `compute_metrics`, `compute_health`, `render_tree`
  - Assert peak < 100 MB using existing `memory_tracker` fixture
  - Use `@pytest.mark.memory` decorator

### Validation

- [x] T031 Run `uv run pytest tests/unit/test_graph_*.py tests/integration/test_graph_command.py -q` — verify new tests pass
- [x] T032 Run `uv run pytest -m memory` — verify peak memory under 110 MB
- [x] T033 Run `uv run ruff check src/ tests/` — no new lint issues
- [x] T034 Run `uv run ruff format --check src/ tests/` — no formatting issues
- [x] T035 Run `uv run mypy --strict src/ tests/` — no type errors

**Checkpoint**: All validation passes. Memory budget OK. Pre-commit suite green.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [x] T036 [P] Run full pre-commit suite: `uvx pre-commit run --all-files` — fix any ruff/mypy/pytest issues
- [x] T037 [P] Run full test suite: `uv run pytest tests/unit/ tests/integration/ -q` — verify no regressions in existing tests
- [x] T038 [P] Verify `openreview graph --help` shows all 4 subcommands with descriptions matching cli-contract.md
- [x] T039 [P] Verify error messages match cli-contract.md exit codes and message patterns
- [x] T040 [P] Run `uv run pytest --co -q` — confirm no test collection errors

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 2 (models) ──→ Phase 3 (builder+detectors)
      ↓                    ↓
      ├──────────→ Phase 4 (metrics) ──→ Phase 5 (health)
      │
      └──→ Phase 6 (view)

All phases ─────────────────────────────────────────────────────────→ Phase 7 (CLI)
All phases ─────────────────────────────────────────────────────────→ Phase 8 (memory)
All phases ─────────────────────────────────────────────────────────→ Phase 9 (polish)
```

### User Story Parallelism

After Phase 2 completes:
- **Phase 6 (view)**: independent — depends only on Phase 2 (models), can run alongside Phases 3-5
- **Phase 4 (metrics)**: depends on both Phase 2 (models) + Phase 3 (builder+detectors)
- **Phases 3→4→5**: sequential chain (each depends on previous)

### Within Each Phase

- Tests MUST be written and FAIL before implementation (TDD)
- Implementation tasks in dependency order
- `[P]` tasks within a phase are parallel (different files, no conflicts)

---

## Implementation Strategy

### MVP First (Phase 3 Only — US1 Graph Build)

1. Complete Phase 1: Setup (read existing patterns)
2. Complete Phase 2: Foundational (graph models + __init__)
3. Complete Phase 3: US1 — Graph Build (P1) — first shippable value
4. **STOP and VALIDATE**: `build_from_parsed` produces correct graph with hierarchy + cross-ref + def-ref edges
5. Graph build is the MVP

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 Graph Build → MVP (value: users can generate clause graphs)
3. US2 Metrics → insight (value: structural quality indicators)
4. US3 Health Score → synthesis (value: single 0-100 score)
5. US4 View → visibility (value: terminal text tree)
6. CLI Integration → all commands accessible
7. Memory + Validation → CI green
8. Polish → full suite green

---

## Task Summary

| Phase | Tasks | Dependencies |
|-------|-------|-------------|
| 1: Setup | T001–T005 | None |
| 2: Foundational (models) | T006–T009 | Phase 1 |
| 3: US1 Graph Build | T010–T016 | Phase 2 |
| 4: US2 Metrics | T017–T018 | Phase 3 |
| 5: US3 Health Score | T019–T020 | Phase 4 |
| 6: US4 View [P] | T021–T022 | Phase 2 only |
| 7: CLI Integration | T023–T029 | Phases 2-6 |
| 8: Memory & Validation | T030–T035 | All phases |
| 9: Polish | T036–T040 | All phases |
| **Total** | **40 tasks** | |

## User Story Mapping

| User Story | Tasks | Priority |
|------------|-------|----------|
| [US1] Graph Build | T006–T016 | P1 |
| [US2] Metrics | T017–T018 | P1 |
| [US3] Health Score | T019–T020 | P2 |
| [US4] View | T021–T022 | P3 |
| CLI Integration | T023–T029 | P1 |
| Memory + Validation | T030–T035 | P1 |
| Polish | T036–T040 | P2 |

## Notes

- `[P]` tasks = different files, no dependencies
- `[Story]` label maps task to specific user story
- Each user story independently completable and testable
- ALL test tasks — write test first, verify failure, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Zero new dependencies — use stdlib (json, re, pathlib, dataclasses, collections) + existing project deps (typer, pydantic)
- Memory tests use existing `memory_tracker` fixture from `tests/conftest.py`
- No as any, @ts-ignore, @ts-expect-error — Python project, no type suppression
