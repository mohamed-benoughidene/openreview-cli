# Contract Graph Modeling — Plan

**Spec**: `specs/025-contract-graph-modeling/spec.md`
**Status**: Planning Complete
**Created**: 2026-07-06

---

## Constitution Gate Evaluation

| Gate | Status | Notes |
|------|--------|-------|
| **AGPL-3.0 compatibility** | PASS | All new code is original; no incompatible deps added. |
| **Python 3.12 only** | PASS | Uses stdlib + existing project deps only (typer, pydantic). |
| **uv-only package management** | PASS | No pip/poetry/pipx. `uv add` not needed — no new deps. |
| **Local CLI only** | PASS | No web server, no long-running process, no FastAPI/Flask. |
| **Privacy first** | PASS | Graph operates on parsed clauses only (no raw text persisted to logs). No PII-relevant processing. |
| **Memory <100 MB peak** | PASS | Graph operations on stdlib dicts/lists; 5000 nodes × 20000 edges ≈ 5-10 MB. Streaming not required. |
| **Forbidden deps excluded** | PASS | No langchain, llama-index, FAISS, spaCy, sentence-transformers, Click, loguru/structlog. |
| **TDD required** | PASS | All tasks below produce test files before implementation. |
| **No pre-install of speculative deps** | PASS | No new deps. Stdlib + typer + pydantic already in project. |
| **Spec not treated as final** | CONFIRMED | All design decisions documented with alternatives in research.md. |

**Gate result**: PASS — all gates clear. Proceed to implementation.

---

## Phase Breakdown

### Phase 1: Graph Data Models and Core Types (P1, ~2 sessions)

**What**: Define `GraphNode`, `GraphEdge`, `ContractGraph` dataclasses in `src/openreview_cli/graph/models.py`. Adjacency-list representation using `dict[str, list[GraphEdge]]`. JSON serialisation round-trip.

**Tasks**:
1. Create `src/openreview_cli/graph/__init__.py` (public exports)
2. Create `src/openreview_cli/graph/models.py` with:
   - `GraphNode(id: str, label: str, text: str, level: int, metadata: dict)`
   - `EdgeType` enum: `parent_child`, `cross_ref`, `def_ref`
   - `GraphEdge(source_id: str, target_id: str, edge_type: EdgeType, metadata: dict)`
   - `ContractGraph(nodes: dict[str, GraphNode], edges: list[GraphEdge], metadata: dict[str, Any] = {})` with adjacency list property
   - `to_json()` / `from_json()` / `to_file()` / `from_file()` methods for JSON serialisation
3. Write `tests/unit/test_graph_models.py` (test first, verify serialisation round-trip, edge cases: empty graph, single node)

**Dependencies**: `src/openreview_cli/parsing/models.py` (Clause model for builder input).

**Jackpot risk (T052)**: Low. New file, no cross-module conflicts. Test skeleton exists.

---

### Phase 2: Clause Hierarchy Builder (P1, ~2 sessions)

**What**: `ClauseHierarchyBuilder` in `src/openreview_cli/graph/builder.py`. Takes `list[Clause]`, uses `Clause.parent_id` to build `parent_child` edges directly.

**Tasks**:
1. Create `src/openreview_cli/graph/builder.py` with `ClauseHierarchyBuilder.build(clauses: list[Clause]) -> ContractGraph`
   - GraphNode.id = Clause.id (synthetic clause ID, not extracted numbering)
   - GraphNode.label = section number extracted from clause title/text
   - Use `Clause.parent_id` to build `parent_child` edges directly — match `parent_id` against `GraphNode.id`
   - Add `parent_child` edge
   - Handle edge cases: null parent_id (root node), dangling parent_id (parent not in clause list)
2. `build_from_parsed(path: str) -> ContractGraph` convenience that loads parsed JSON via `format_json` reverse
3. Write `tests/unit/test_graph_builder.py` (synthetic clause lists, verify parent assignments)

**Dependencies**: Phase 1 (models). `src/openreview_cli/graph/__init__.py` exports `build_from_parsed`.

---

### Phase 3: Cross-Reference and Definition Detectors (P1, ~3 sessions)

**What**: Two regex-based detectors in `src/openreview_cli/graph/detectors.py`. Configurable pattern lists. No ML.

**Tasks**:
1. Create `CrossReferenceDetector`:
   - Default regex patterns: `Section\s+(\d+\.?\d*)`, `as (?:described|set forth|provided)\s+in\s+(?:Section\s+)?(\d+\.?\d*)`, `pursuant\s+to\s+(?:Section\s+)?(\d+\.?\d*)`
   - Extensible `patterns: list[re.Pattern]` parameter
   - Builds a temporary `label → GraphNode.id` index from all node labels
   - `detect(text: str) -> list[str]` returns target clause IDs by looking up matched labels in the index
   - Heuristic: ignore self-references (source matches target)
2. Create `DefinitionDetector`:
   - Detect definition patterns: `"(?:')([^"']+)["']\s+means\b`, `"(?:')([^"']+)["']\s+shall\s+mean\b`, `"(?:')([^"']+)["']\s+refers?\s+to\b`
   - Also detect capitalised terms without quotes: `([A-Z][A-Za-z\s]+)\s+means\b` (heuristic — bound false positives)
   - `extract_definitions(clauses: list[Clause]) -> dict[str, str]` maps term → defining clause ID
   - `count_references(text: str, definitions: dict[str, str]) -> list[tuple[str, str]]` returns (term, clause_id) pairs for referenced terms
3. Wire detectors into builder: after building hierarchy edges, scan all clause text for cross-refs and def-refs, add those edges to the graph
4. Write `tests/unit/test_graph_detectors.py` (synthetic clause text, verify detected references)
5. Write `tests/integration/test_graph_command.py` (end-to-end: parse → build → verify edges)

**Dependencies**: Phase 1 (models), Phase 2 (graph building with hierarchy edges).

---

### Phase 4: Heuristic Metrics (P1, ~2 sessions)

**What**: `GraphMetrics` dataclass + computation in `src/openreview_cli/graph/metrics.py`. Five metrics, all heuristics, no ML.

**Tasks**:
1. Create `src/openreview_cli/graph/metrics.py` with `compute_metrics(graph: ContractGraph) -> GraphMetrics`:
   - **Density**: `len(edges) / (len(nodes) * (len(nodes) - 1))` if nodes > 1, else 0.0
   - **Max depth**: DFS from root nodes following only parent-child edges, track max depth
   - **Orphan ratio**: Count nodes with no incoming `parent_child` edge and at least one outgoing `parent_child` edge. Ratio = orphan_count / total_nodes
   - **Broken cross-ref count**: For each cross-ref edge, check if target_id exists in nodes. Count missing.
   - **Definition coverage**: For each def-ref edge, check if referenced term has a definition clause. Count defined/total.
2. Edge case handling: empty graph → all zeros; single node → density=0, depth=1, orphan=0, broken=0, coverage=1.0
3. Write `tests/unit/test_graph_metrics.py` (synthetic graphs with known expected values)

**Dependencies**: Phase 1 (models), Phase 3 (detectors must provide def-ref edges).

---

### Phase 5: Health Score (P2, ~1 session)

**What**: `HealthScore` computation in `src/openreview_cli/graph/health.py`. Weighted formula combining five metrics.

**Tasks**:
1. Create `src/openreview_cli/graph/health.py` with `compute_health(metrics: GraphMetrics, weights: list[float] | None = None) -> HealthScore`:
   - Default weights: `[0.15, 0.20, 0.20, 0.25, 0.20]`
   - Constants: `MAX_EXPECTED_DEPTH = 10`, `MAX_EXPECTED_BROKEN_REFS = 10`
   - Normalisation: `normalized_depth = min(max_depth / MAX_EXPECTED_DEPTH, 1.0)`, `density_penalty = density`, `orphan_penalty = orphan_ratio`, `broken_ref_ratio = min(broken_ref_count / MAX_EXPECTED_BROKEN_REFS, 1.0)`, `definition_coverage = definition_coverage`
   - Formula: `raw = sum(w * component)` then `health_score = round(raw * 100)`
   - If weights don't sum to 1.0, normalise and emit warning on stderr
   - Bounds: clamp to [0, 100]

2. Write `tests/unit/test_graph_health.py` (verify health score for known metric values; verify weight normalisation warning)

**Dependencies**: Phase 4 (metrics).

---

### Phase 6: Text Tree View (P3, ~1 session)

**What**: ASCII text tree renderer in `src/openreview_cli/graph/view.py`. No rich.Tree, no graphviz — pure stdlib string formatting.

**Tasks**:
1. Create `src/openreview_cli/graph/view.py` with `render_tree(graph: ContractGraph, color: bool = False) -> str`:
   - Find root nodes (no parent), render each root
   - DFS from root, indent 2 spaces per depth level
   - Format: `{section_number} {title} [{N refs out}] [DEF-REF: N] [ORPHAN]`
   - No ANSI codes unless `color=True` (then red for orphan, yellow for high ref count)
2. Write `tests/unit/test_graph_view.py` (verify indentation, annotations, orphan marking)

**Dependencies**: Phase 1 (models).

---

### Phase 7: CLI Integration (P1, ~1 session)

**What**: `openreview graph` subcommand group in `app.py`. Four subcommands: `build`, `metrics`, `health`, `view`.

**Tasks**:
1. Add `graph_app = typer.Typer(name="graph", ...)` to `app.py`
2. Wire commands:
   - `graph build <parsed.json> [-o graph.json]` — calls `build_from_parsed`, serialises to JSON (default: `{input_stem}.graph.json`)
   - `graph metrics <graph.json>` — loads graph, computes metrics, prints table
   - `graph health <graph.json> [--weights w1 w2 w3 w4 w5]` — loads graph, computes metrics + health
   - `graph view <graph.json> [--color]` — loads graph, renders tree
3. Error handling: file-not-found → typer.Exit(code=1), malformed JSON → typer.Exit(code=2), using `errors.py` conventions
4. `--help` output for each subcommand
5. Write `tests/integration/test_graph_command.py` (CLI smoke tests)

**Dependencies**: Phase 2-6 (all graph modules). `app.add_typer(graph_app)` must not conflict with existing groups.

---

### Phase 8: Memory Profiling and Validation (P1, ~1 session)

**Tasks**:
1. Add memory test in `tests/integration/test_memory.py` using existing `memory_tracker` fixture
   - Build a 500-node synthetic graph
   - Compute metrics, health, and view
   - Assert peak < 100 MB
2. Run full pre-commit suite: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest tests/unit/`
3. Verify no regressions in existing tests

**Dependencies**: All phases complete.

---

## Task Dependencies

```
Phase 1 (models) ──→ Phase 2 (hierarchy builder) ──→ Phase 3 (detectors)
      ↓                    ↓
      ├──────────→ Phase 4 (metrics) ──→ Phase 5 (health)
      │
      └──→ Phase 6 (view)

All phases ──────────────────────────────────────────────────────────────────────────────────→ Phase 7 (CLI)
All phases ──────────────────────────────────────────────────────────────────────────────────→ Phase 8 (validation)
```

Phases 1, 2, 3, 4, 6 can be partially parallelised after Phase 1 is complete:
- Phase 6 (view) depends only on Phase 1 (models)
- Phase 4 (metrics) depends on Phase 1 (models) + Phase 3 (detectors)
- Phase 5 (health) depends on Phase 4

---

## Files Changed

### New files
| File | Phase | Purpose |
|------|-------|---------|
| `src/openreview_cli/graph/__init__.py` | 1 | Public exports |
| `src/openreview_cli/graph/models.py` | 1 | GraphNode, GraphEdge, ContractGraph dataclasses |
| `src/openreview_cli/graph/builder.py` | 2 | ClauseHierarchyBuilder, build_from_parsed |
| `src/openreview_cli/graph/detectors.py` | 3 | CrossReferenceDetector, DefinitionDetector |
| `src/openreview_cli/graph/metrics.py` | 4 | compute_metrics, GraphMetrics |
| `src/openreview_cli/graph/health.py` | 5 | compute_health, HealthScore |
| `src/openreview_cli/graph/view.py` | 6 | render_tree |
| `tests/unit/test_graph_models.py` | 1 | Unit tests for graph models |
| `tests/unit/test_graph_builder.py` | 2 | Unit tests for clause hierarchy builder |
| `tests/unit/test_graph_detectors.py` | 3 | Unit tests for cross-ref/def detectors |
| `tests/unit/test_graph_metrics.py` | 4 | Unit tests for heuristic metrics |
| `tests/unit/test_graph_health.py` | 5 | Unit tests for health score |
| `tests/unit/test_graph_view.py` | 6 | Unit tests for text tree view |
| `tests/integration/test_graph_command.py` | 7 | Integration tests for graph CLI commands |

### Modified files
| File | Phase | Change |
|------|-------|--------|
| `src/openreview_cli/__init__.py` | 1 | Add `graph` to exports (if explicit) |
| `src/openreview_cli/app.py` | 7 | Add `graph_app` typer group with 4 subcommands |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cross-reference regex misses legal phrasing | Medium | Medium | Extensible pattern list; default patterns cover common English legal phrasing; user can add patterns |
| Definition detector false positives from capitalised terms | Medium | Low | Heuristic bound described in spec; metric documentation should note limitation |
| Orphan ratio heuristic excludes genuine orphans | Low | Medium | Filter described in spec (standalone nodes with no children not counted as orphans); configurable threshold |
| Health score weights not validated empirically | Medium | Low | No published benchmark exists (documented in research.md); default weights are reasonable heuristics; custom weights supported |
| Memory spike from large graph JSON deserialisation | Low | Low | 5000 nodes × 20000 edges ≈ 5-10 MB; well under 100 MB budget |
| Non-English contract cross-references not detected | Low | Low | Explicitly out of scope for v1; documented in assumptions |

---

## Timeline Estimate

| Phase | Sessions | Dependencies |
|-------|----------|-------------|
| 1: Models | 2 | None |
| 2: Hierarchy Builder | 2 | Phase 1 |
| 3: Detectors | 3 | Phase 1, 2 |
| 4: Metrics | 2 | Phase 1, 3 |
| 5: Health Score | 1 | Phase 4 |
| 6: View | 1 | Phase 1 |
| 7: CLI Integration | 1 | All phases |
| 8: Memory & Validation | 1 | All phases |
| **Total** | **13** | |

---

## Deferred Tasks

- Multi-contract graph comparison (excluded by spec)
- Graph diff between contract versions (excluded by spec)
- Visual graph rendering (DOT/SVG/PNG — excluded by spec)
- ML-based cross-reference detection (deferred to future spec)
- Persistent graph storage in SQLite (JSON files only per spec)
- Contract clause similarity / clustering (excluded by spec)
- Non-English contract support (out of scope for v1)
