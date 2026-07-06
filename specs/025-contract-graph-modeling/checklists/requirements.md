# Requirements Checklist: Contract Graph Modeling

**Purpose**: Track completion of all requirements and acceptance criteria for spec 025
**Created**: 2026-07-06
**Feature**: `specs/025-contract-graph-modeling/spec.md`

---

## R1: Graph Building

- [ ] REQ-001 Input accepts parsed clause JSON matching `Clause` model from `parsing/models.py`
- [ ] REQ-002 Hierarchy edges derived from Clause.parent_id
- [ ] REQ-003 Cross-reference edges detected via regex patterns on clause text
- [ ] REQ-004 Definition-reference edges detected via term extraction (quoted/capitalised + "means")
- [ ] REQ-005 Output JSON contains `nodes` list with ID, label, text snippet per node
- [ ] REQ-006 Output JSON contains `edges` list with source, target, type per edge
- [ ] REQ-007 Edge types: `parent-child`, `cross-ref`, `def-ref`
- [ ] REQ-008 Regex patterns configurable (extensible list, not hardcoded strings)
- [ ] REQ-009 No external graph library — stdlib `dict`/`list` adjacency list
- [ ] REQ-010 Empty/single-clause contract produces single-node graph (no crash)
- [ ] REQ-011 Non-existent input file produces clear error with non-zero exit

## R2: Heuristic Metrics

- [ ] REQ-012 **Density**: computed as `edges / (nodes * (nodes-1))`, 0 for <=1 nodes
- [ ] REQ-013 **Max depth**: longest DFS path from root to leaf (parent-child edges only)
- [ ] REQ-014 **Orphan ratio**: fraction of nodes that have children but no parent in the parent_child hierarchy (standalone boilerplate excluded)
- [ ] REQ-015 **Broken cross-ref count**: count of cross-ref edges with missing target node
- [ ] REQ-016 **Definition coverage**: `defined_terms_referenced / total_terms_referenced`
- [ ] REQ-017 All metrics return defined, non-NaN values for edge cases (empty, single-node)
- [ ] REQ-018 Metrics exposed as JSON-serialisable dict
- [ ] REQ-019 Computation < 1 second for 500-node graph on target hardware
- [ ] REQ-020 No ML used — heuristic/rule-based only

## R3: Health Score

- [ ] REQ-021 Score computed as weighted combination of 5 metrics
- [ ] REQ-022 Score is integer 0-100
- [ ] REQ-023 Default weights: `[0.15, 0.20, 0.20, 0.25, 0.20]`
- [ ] REQ-024 Weights overridable via CLI `--weights` or Python API
- [ ] REQ-025 Weights normalised to sum to 1.0 with stderr warning if they do not
- [ ] REQ-026 Perfect contract (no orphans, no broken refs, full definition coverage) scores >= 80
- [ ] REQ-027 Poor contract (many broken refs, orphans, low coverage) scores <= 50
- [ ] REQ-028 Single-node graph scores 100

## R4: Graph View (Text Tree)

- [ ] REQ-029 Output is indented ASCII tree (2 spaces per level)
- [ ] REQ-030 Root nodes printed first, children indented under parent
- [ ] REQ-031 Each node shows section number and outgoing cross-ref/def-ref count
- [ ] REQ-032 Orphan nodes marked with `[ORPHAN]`
- [ ] REQ-033 Plain text output, no ANSI codes unless `--color` flag
- [ ] REQ-034 No external dependencies for rendering (stdlib only)

## R5: CLI Integration

- [ ] REQ-035 `openreview graph build <parsed.json> [-o graph.json]` subcommand (default: `{input_stem}.graph.json`)
- [ ] REQ-036 `openreview graph metrics <graph.json>` subcommand
- [ ] REQ-037 `openreview graph health <graph.json> [--weights w1 w2 w3 w4 w5]` subcommand
- [ ] REQ-038 `openreview graph view <graph.json> [--color]` subcommand
- [ ] REQ-039 All subcommands have `--help` output
- [ ] REQ-040 Input paths accept absolute and relative paths
- [ ] REQ-041 Error handling uses project patterns from `errors.py`
- [ ] REQ-042 Exit codes follow conventions (0=success, 1=user error, 2=system error)

## Cross-Cutting

- [ ] REQ-043 TDD: test files exist and fail before implementation code is written
- [ ] REQ-044 Unit tests in `tests/unit/test_graph_*.py` cover all 5 metrics
- [ ] REQ-045 Integration test in `tests/integration/test_graph_command.py` covers CLI flow
- [ ] REQ-046 Memory profiling via `memory_tracker` fixture (< 100 MB peak)
- [ ] REQ-047 `ruff check` passes with no new violations
- [ ] REQ-048 `mypy --strict` passes with no new errors
- [ ] REQ-049 No new dependencies added to `pyproject.toml`
- [ ] REQ-050 All graph commands work on target hardware (8 GB RAM, 2-core CPU)

---

## Verification Log

| Check ID | Status | Date | Notes |
|----------|--------|------|-------|
| REQ-001 | ☐ | | |
| REQ-002 | ☐ | | |
| ... | ☐ | | |
