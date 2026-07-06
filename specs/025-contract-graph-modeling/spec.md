# Contract Graph Modeling — Heuristic Structural Metrics and Health Score

**Feature ID**: 025-contract-graph-modeling
**Status**: Draft Specification
**Created**: 2026-07-06

## Overview

Parsed contracts contain clauses with cross-references ("as defined in Section 3.2"), nested definitions ("'Confidential Information' means..."), and hierarchical structure (Articles → Sections → Subsections). Currently, the parsing engine extracts clause boundaries and text but loses these structural relationships.

This spec builds a lightweight **directed graph** from parsed contract clauses using only regex/rule-based methods — no ML, no GRPO training, no GPU. From the graph, it computes heuristic structural metrics (density, max depth, orphan ratio, broken cross-reference count, definition coverage) and emits a single **0-100 contract health score** that quantifies structural quality.

**Key constraints**: Python 3.12, uv-only deps, local CLI, memory <100 MB peak, no forbidden dependencies (no langchain, no spaCy-for-PII, no sentence-transformers, no FAISS), TDD required.

---

## User Scenarios and Testing

### Scenario 1: User generates a graph from parsed clauses (Priority: P1)

A user has parsed a contract using `openreview parse` and wants to see a structural graph of its clauses — which sections reference which, where definitions live, how deep the nesting goes.

```
openreview graph build my_contract.json
# → Output: my_contract.graph.json (default)

openreview graph build my_contract.json --output graph.json
```

The system reads the parsed clauses, builds a directed graph where each clause is a node, and edges represent:
- **Parent-child**: nesting hierarchy (Article → Section → Subsection)
- **Cross-reference**: Section 3.2 references "Attachments" in Section 7.1
- **Definition-reference**: "Confidential Information" defined in Section 1.2, referenced in Section 4.3

**Why this priority**: The graph is the foundation for all metric computation and health scoring. Without it, there are no metrics.

**Acceptance Scenarios**:

1. **Given** a parsed contract with 10 clauses across 2 articles, **When** `graph build` runs, **Then** output JSON contains 10 nodes with parent-child edges for nesting hierarchy.
2. **Given** a parsed contract where Section 3.2 contains "as set forth in Section 7.1", **When** `graph build` runs, **Then** the output contains a directed cross-reference edge from 3.2 → 7.1.
3. **Given** a parsed contract where Section 1.2 defines "Confidential Information" and Section 4.3 uses that term, **When** `graph build` runs, **Then** the output contains a definition-reference edge from 4.3 → 1.2.
4. **Given** a parsed contract with no cross-references, **When** `graph build` runs, **Then** the output contains only parent-child edges (no cross-ref or def-ref edges).
5. **Given** an empty or single-clause contract, **When** `graph build` runs, **Then** the output is a single-node graph.
6. **Given** a non-existent input file, **When** `graph build` runs, **Then** the CLI exits with a clear file-not-found error.

**Independent Test**: Parse a synthetic contract into known clause structure with known cross-references, build the graph, and verify node/edge counts match expected structure.

---

### Scenario 2: User computes heuristic metrics on the graph (Priority: P1)

A user has built a graph and wants numerical structural quality indicators to assess how well-organized the contract is.

```
openreview graph metrics my_graph.json
```

The system computes the following heuristic metrics from the graph:

| Metric | Definition |
|--------|------------|
| **Density** | Ratio of actual edges to possible edges in the directed graph (0-1). Higher = more interconnected. |
| **Max depth** | Longest path from root to leaf in the nesting hierarchy. Deep nesting may indicate complexity. |
| **Orphan ratio** | Fraction of nodes with no incoming `parent_child` edge and at least one outgoing `parent_child` edge. Standalone nodes (no incoming, no outgoing `parent_child` edges) are excluded. |
| **Broken cross-reference count** | Number of cross-reference edges where the target clause ID does not exist in the graph. |
| **Definition coverage** | Ratio of referenced terms that have a corresponding definition node. 1.0 = every referenced term is defined somewhere. |

**Why this priority**: Metrics are the primary user-facing output. Without them, the graph is an intermediate artifact with no actionable insight.

**Acceptance Scenarios**:

1. **Given** a well-structured contract with 10 clauses in a single hierarchy and complete cross-references, **When** metrics run, **Then** density ~0.1 (sparse), max depth = 3, orphan ratio = 0, broken refs = 0, definition coverage = 1.0.
2. **Given** a contract with 2 orphan clauses (no parent path to root), **When** metrics run, **Then** orphan ratio = 2/total_nodes.
3. **Given** a contract where Section 5.2 references "Section 9.9" but only 9 sections exist, **When** metrics run, **Then** broken cross-reference count >= 1.
4. **Given** a contract where 3 terms are referenced but only 2 are defined, **When** metrics run, **Then** definition coverage = 0.67.
5. **Given** a single-node graph, **When** metrics run, **Then** density = 0, max depth = 1, orphan ratio = 0, broken refs = 0, definition coverage = 1.0 (trivially).
6. **Given** a non-existent graph file, **When** metrics run, **Then** CLI exits with a clear error.

**Independent Test**: Build a known synthetic graph structure, run metrics, and verify each metric against the hand-calculated expected value.

---

### Scenario 3: User gets a single contract health score (Priority: P2)

A user wants a single 0-100 score summarising structural quality — no need to interpret five separate metrics.

```
openreview graph health my_graph.json
```

The system combines the five metrics into a single health score using a weighted formula:

```
health = w1 * (1 - density_if_high) + w2 * (1 - normalized_depth) + w3 * (1 - orphan_ratio) + w4 * (1 - broken_ref_ratio) + w5 * definition_coverage
```

Where:
- Components are normalised to [0,1] with higher = better
- Default weights: w1=0.15 (density), w2=0.20 (depth), w3=0.20 (orphans), w4=0.25 (broken refs — highest penalty), w5=0.20 (definition coverage)
- A contract with no broken refs, no orphans, moderate depth, good definition coverage, and moderate density scores ~80-100
- A contract with many broken refs and orphans scores <50

**Why this priority**: The health score is the executive summary. It compiles five metrics into one decision-ready number.

**Acceptance Scenarios**:

1. **Given** a perfect contract (no orphans, no broken refs, all terms defined, moderate depth), **When** health runs, **Then** score >= 80.
2. **Given** a contract with 5 broken refs, 3 orphans, and definition coverage of 0.5, **When** health runs, **Then** score <= 50.
3. **Given** the same metrics but custom weights (e.g., broken-ref weight = 0.5), **When** health runs with `--weights 0.1 0.1 0.1 0.5 0.2`, **Then** score differs from default-weighted score.
4. **Given** a single-node graph (trivially perfect), **When** health runs, **Then** score = 100.
5. **Given** weights that do not sum to 1.0, **When** health runs, **Then** the system normalises them internally with a warning on stderr.

**Independent Test**: Compute metrics on a synthetic graph, then manually apply the formula with known weights and verify the health score matches.

---

### Scenario 4: User visualises graph as ASCII or text output (Priority: P3)

A user wants a quick structural overview without loading a graph into a third-party tool.

```
openreview graph view my_graph.json
```

The system prints a simple text-based tree of the clause hierarchy, annotating each node with:
- Its section number
- Number of outgoing cross-references
- Whether it references definitions
- Whether it is orphaned (highlighted)

**Why this priority**: A text view is the lowest-friction way to inspect structure. It adds no dependencies (no DOT/Graphviz required) and works in the terminal.

**Acceptance Scenarios**:

1. **Given** a graph with 5 clauses in a hierarchy, **When** view runs, **Then** output shows an indented tree with section numbers.
2. **Given** a graph with orphan clauses, **When** view runs, **Then** orphan clauses are marked with `[ORPHAN]`.
3. **Given** a graph with cross-references on certain nodes, **When** view runs, **Then** those nodes show `[3 refs out]`.
4. **Given** a single-node graph, **When** view runs, **Then** output shows the single node.

**Independent Test**: Build a known graph, run view, and verify indentation and annotations match.

---

## Functional Requirements

### R1: Graph Building (from parsed clauses)

The system must build a directed graph from a parsed contract's clause list.

**Node identity**:
- `GraphNode.id = Clause.id` (the existing synthetic clause ID from parsing, e.g., `"clause-5"`). This guarantees uniqueness and traceability to the source `Clause` object.
- `GraphNode.label = section number extracted from clause title/text` (e.g., `"Section 3.2"`, `"Article 1"`). Used for display and cross-reference lookup.

**Cross-reference resolution**: The cross-reference detector builds a temporary `label → Clause.id` index from all nodes' labels, then resolves text references like `"Section 3.2"` to the corresponding node ID via that index.

**Edges** are derived from:

- **Hierarchy edges**: parent → child based on nesting level (Article → Section → Subsection), derived from `Clause.parent_id` which is populated by `clause_detector.build_hierarchy()`.
- **Cross-reference edges**: source clause → target clause. Detected via regex patterns: `"Section\s+(\d+\.?\d*)"`, `"as (?:described|set forth|provided)\s+in\s+(?:Section\s+)?(\d+\.?\d*)"`, `"pursuant\s+to\s+(?:Section\s+)?(\d+\.?\d*)"`.
- **Definition-reference edges**: source clause → definition clause. Detected via term extraction: identify defined terms (quoted or capitalised phrases followed by "means" / "refers to" / "shall mean") and track which clauses reference them.

The graph model must expose node and edge lists for serialisation (JSON) and in-memory traversal.

**Acceptance criteria**:
- Input: parsed clause list (JSON, matching `Clause` model from `src/openreview_cli/parsing/models.py`).
- Output: JSON with `nodes` (list of node objects) and `edges` (list of edge objects with type: parent-child / cross-ref / def-ref).
- All regex patterns are configurable (extensible list of patterns, not hardcoded).
- No external graph library used — graph is a simple adjacency list built with stdlib `dict` and `list`.

### R2: Heuristic Metric Computation

Given a built graph (or the ability to build one on the fly), the system must compute:

| Metric | Computation |
|--------|-------------|
| **Density** | `edges_count / (nodes_count * (nodes_count - 1))` for directed graph. If nodes <= 1, density = 0. |
| **Max depth** | Longest path from any root node (no parent) to any leaf node, traversing only parent-child edges. DFS from roots. |
| **Orphan ratio** | `orphan_count / nodes_count`. Orphan = node with no incoming `parent_child` edge and at least one outgoing `parent_child` edge. |
| **Broken cross-ref count** | Count of cross-ref edges where target node ID not in node set. |
| **Definition coverage** | `defined_terms_referenced / total_terms_referenced`. A term is "referenced" if it appears in any clause text (outside its definition). A term is "defined" if a definition clause exists for it. Coverage is computed from detected `def_ref` edges only — undetected definitions or references are not counted. This is a documented limitation of the heuristic detection approach. |

**Acceptance criteria**:
- All metrics are computed without ML, heuristics only.
- Metrics exposed as a JSON-serialisable dict.
- Edge cases (empty graph, single node, no edges) produce defined, non-NaN values.
- Computation time < 1 second for a graph with 500 nodes on target hardware (8 GB RAM, 2-core CPU).

### R3: Health Score

The system must compute a single 0-100 score by combining the five metrics.

**Constants**:
- `MAX_EXPECTED_DEPTH = 10` — upper bound for depth normalisation
- `MAX_EXPECTED_BROKEN_REFS = 10` — upper bound for broken-ref normalisation

**Formula**:
```
normalized_depth = min(max_depth / MAX_EXPECTED_DEPTH, 1.0)
density_penalty = density  # higher density = worse (over-connected)
orphan_penalty = orphan_ratio
broken_ref_ratio = min(broken_ref_count / MAX_EXPECTED_BROKEN_REFS, 1.0)

raw = w1 * (1 - density_penalty) + w2 * (1 - normalized_depth) + w3 * (1 - orphan_penalty) + w4 * (1 - broken_ref_ratio) + w5 * definition_coverage
health_score = round(raw * 100)
```

Default weights: `[0.15, 0.20, 0.20, 0.25, 0.20]`.

**Acceptance criteria**:
- Score is integer 0-100.
- Weights can be overridden via CLI or Python API.
- Weights are normalised to sum to 1.0 with a warning if they do not.
- Score of 100 = no orphans, no broken refs, all terms defined, minimal depth, minimal density.
- Score of 0 = maximal orphans, all refs broken, no definitions, maximal depth, maximal density (pathological).

### R4: Graph View (Text Tree)

The system must render the graph hierarchy as an indented text tree in the terminal.

**Acceptance criteria**:
- ASCII indentation (2 spaces per level).
- Root nodes printed first, children indented under parent.
- Cross-reference and definition-usage counts annotated per node.
- Orphan nodes marked with `[ORPHAN]`.
- Output is plain text, no ANSI escape codes unless `--color` flag is passed.
- No external dependencies (no `graphviz`, no `rich` tree — use stdlib string formatting).

### R5: CLI Integration

All graph operations exposed as subcommands of `openreview graph`:

```
openreview graph build <parsed.json> [-o graph.json]
openreview graph metrics <graph.json>
openreview graph health <graph.json> [--weights w1 w2 w3 w4 w5]
openreview graph view <graph.json> [--color]
```

**`--output` / `-o` behaviour**: Optional. Default is `{input_stem}.graph.json` (same directory as input).

**Acceptance criteria**:
- Subcommand group `graph` exists under `openreview` Typer app.
- Each subcommand has `--help` output.
- Input paths accept absolute and relative paths.
- Errors use the project's existing error handling patterns (`errors.py`).
- Exit codes follow project conventions (0 = success, 1 = user error, 2 = system error).

---

## Success Criteria

1. Graph building correctly extracts hierarchy, cross-reference, and definition edges from parsed clauses with >=90% precision on synthetic test contracts.
2. All five heuristic metrics produce correct values on known graph structures (validated against hand-calculated expected values).
3. Health score formula correctly combines metrics and produces consistent 0-100 range.
4. Text tree view renders correctly for any valid graph (including edge cases: single node, flat, deep, orphaned).
5. All graph commands run under 100 MB peak memory on a 500-node contract.
6. All new commands have consistent error handling matching project patterns.
7. TDD is followed: test files exist and fail before implementation code is written.
8. Full pre-commit suite passes with no regressions (`ruff check`, `ruff format --check`, `mypy --strict`, `pytest tests/unit/`).
9. No new dependencies added beyond what is already in `pyproject.toml`.
10. Peak memory < 100 MB for all graph operations (measured via `memory_tracker` fixture).

---

## Key Entities

| Entity | Description |
|--------|-------------|
| **ContractGraph** | Directed graph of clauses. Holds node list, edge list (typed: parent-child, cross-ref, def-ref). Serialisable to/from JSON. |
| **GraphNode** | A single clause node with ID (section number), label, full clause text, level, and metadata (source_page, title, paragraph_count). |
| **GraphEdge** | A directed edge with source ID, target ID, and type (parent-child, cross-ref, def-ref). |
| **GraphMetrics** | A dataclass holding the five computed metrics: density, max_depth, orphan_ratio, broken_ref_count, definition_coverage. |
| **HealthScore** | A single integer 0-100 with associated weight configuration. |
| **CrossReferenceDetector** | Regex-based detector that scans clause text for cross-reference patterns. Extensible with user-provided patterns. |
| **DefinitionDetector** | Regex-based detector that finds defined terms (quoted/capitalised + "means"/"shall mean") and maps them to their defining clause. |
| **ClauseHierarchyBuilder** | Derives parent-child relationships from `Clause.parent_id`. |

---

## Assumptions

1. Input parsed clauses follow the `Clause` model from `src/openreview_cli/parsing/models.py` — specifically, each clause has a `parent_id` field (hierarchy link) and `text` field.
2. Cross-references in legal English follow predictable patterns ("Section X.Y", "as defined in Section X.Y", "pursuant to Section X.Y"). Non-English contracts are out of scope for v1.
3. Defined terms are consistently formatted: quoted terms (`"Confidential Information"`) or capitalised phrases followed by "means" / "shall mean" / "refers to".
4. The graph is small enough (<5000 nodes, <20000 edges) to fit in memory without streaming.
5. No external graph database or specialised graph library is needed — stdlib data structures suffice.
6. The existing `parsing` module produces valid clause lists. Graph building is a downstream consumer, not a parser.
7. TDD: tests are written before implementation code.

---

## Dependencies

1. **Spec 002 (document-parsing)** — provides the `Clause` model and parsed clause data structure consumed by graph builder.
2. **stdlib only for graph operations** — `collections`, `json`, `re`, `dataclasses`. No external graph library.
3. **Typer** — already present, used for `openreview graph` CLI group.
4. **Pydantic** — already present, may be used for `GraphMetrics` / `HealthScore` data models if desired.

### Explicitly excluded
- NetworkX or any external graph library
- Graphviz / DOT rendering
- ML-based cross-reference detection (spaCy, transformers)
- GRPO training, GPU
- Web server or API endpoint
- Real-time or streaming graph processing
- Visual graph rendering (SVG, PNG)
- Persistence beyond JSON files (no SQLite schema changes)

---

## Scope Boundaries

### In scope
- `src/openreview_cli/graph/` package with `__init__.py`, `models.py`, `builder.py`, `detectors.py`, `metrics.py`, `health.py`, `view.py`
- `openreview graph build`, `metrics`, `health`, `view` CLI subcommands
- Regex-based cross-reference and definition detection
- Heuristic-only metric computation (no ML)
- 0-100 health score with configurable weights
- ASCII text tree view
- JSON serialisation of graph and metrics
- Unit tests (`tests/unit/test_graph_*.py`)
- Integration test (`tests/integration/test_graph_command.py`)
- Memory profiling via existing `memory_tracker` fixture

### Explicitly excluded
- ML-based cross-reference detection (deferred to future spec)
- GRPO training pipeline
- GPU support
- Visual graph rendering (DOT, SVG, PNG)
- Interactive graph exploration
- Real-time graph building during parse streaming
- Persistent graph storage in SQLite (JSON files only)
- Multi-contract graph comparison
- Graph diff between contract versions
- Contract clause similarity / clustering
- Any new dependencies beyond stdlib + existing project deps
