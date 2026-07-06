# Contract Graph Modeling — Quickstart

**Spec**: `specs/025-contract-graph-modeling/spec.md`
**Created**: 2026-07-06

> **Prerequisites**: Python 3.12, `uv sync` completed, `openreview` CLI installed in venv.

---

## Build a Graph

Parse a contract and build its structural graph:

```bash
# Step 1: Parse the contract (produces clause JSON)
openreview parse my_contract.pdf --format json > parsed_contract.json

# Step 2: Build the graph from parsed clauses
openreview graph build parsed_contract.json --output contract_graph.json
```

**Output**: `contract_graph.json` — JSON with `nodes` (array of clause nodes) and `edges` (array of typed edges).

---

## Compute Metrics

Analyse the graph's structural properties:

```bash
openreview graph metrics contract_graph.json
```

**Example output**:
```
Contract Graph Metrics
──────────────────────
Density:              0.087
Max Depth:            4
Orphan Ratio:         0.000
Broken Cross-Refs:    1
Definition Coverage:  0.833

Interpretation: Well-structured contract.
1 broken cross-reference found (Section 5.2 → Section 9.9, but only 9 sections exist).
1 term used without definition.
```

---

## Get the Health Score

Compile five metrics into a single 0-100 score:

```bash
# Default weights
openreview graph health contract_graph.json
# → Health Score: 82/100 (Good)

# Custom weights (penalise broken refs more heavily)
openreview graph health contract_graph.json --weights 0.1 0.1 0.1 0.5 0.2
# → Health Score: 64/100 (Custom weights increased broken-ref penalty)
```

---

## Visualise as Text Tree

Inspect the clause hierarchy in the terminal:

```bash
# Plain text
openreview graph view contract_graph.json

# With colour highlighting (orphans in red, high-ref nodes in yellow)
openreview graph view contract_graph.json --color
```

**Example output**:
```
Article 1  Definitions                        [2 refs out]  [DEF-REF: 3]
  Section 1.1  Confidential Information       [0 refs out]  [DEFINES: "Confidential Information"]
  Section 1.2  Term                             [0 refs out]
Article 2  Term and Termination               [2 refs out]
  Section 2.1  Effective Date                   [0 refs out]
  Section 2.2  Termination                    [1 ref out]
    Section 2.2.1  Termination for Cause      [0 refs out]  [ORPHAN]
  Section 2.3  Survival                       [1 ref out]
Section 3  Miscellaneous                      [1 ref out]   [ORPHAN]
```

---

## Python API (for scripting)

All graph operations are available as Python imports:

```python
from openreview_cli.graph.models import ContractGraph, GraphNode, GraphEdge
from openreview_cli.graph.builder import build_from_parsed
from openreview_cli.graph.metrics import compute_metrics
from openreview_cli.graph.health import compute_health
from openreview_cli.graph.view import render_tree

# Build from parsed clause file
graph = build_from_parsed("parsed_contract.json")

# Or build programmatically
from openreview_cli.parsing.stream import parse_document
doc, clauses = parse_document("my_contract.pdf")
graph = build_from_parsed(clauses=clauses)

# Compute metrics
metrics = compute_metrics(graph)
print(f"Density: {metrics.density:.3f}")
print(f"Max depth: {metrics.max_depth}")
print(f"Broken refs: {metrics.broken_ref_count}")

# Compute health score
health = compute_health(metrics)
print(f"Health: {health.score}/100")

# Render text tree
print(render_tree(graph))

# Serialise/deserialise
graph_json = graph.to_json()
restored = ContractGraph.from_json(graph_json)
```

---

## Command Reference

| Command | Purpose | Priority |
|---------|---------|----------|
| `openreview graph build <parsed.json>` | Build graph from parsed clauses | P1 |
| `openreview graph metrics <graph.json>` | Compute heuristic metrics | P1 |
| `openreview graph health <graph.json>` | Compute 0-100 health score | P2 |
| `openreview graph view <graph.json>` | Render ASCII tree view | P3 |

---

## Common Workflows

### Full Pipeline (Parse → Graph → Metrics → Health)

```bash
openreview parse contract.pdf --format json > parsed.json && \
openreview graph build parsed.json --output graph.json && \
openreview graph metrics graph.json && \
openreview graph health graph.json
```

### Batch Analysis of Multiple Contracts

```bash
for pdf in contracts/*.pdf; do
  base=$(basename "$pdf" .pdf)
  openreview parse "$pdf" --format json > "build/${base}.json"
  openreview graph build "build/${base}.json" --output "build/${base}-graph.json"
  score=$(openreview graph health "build/${base}-graph.json" | grep -oP 'Health Score: \K\d+')
  echo "${base}: ${score}/100"
done
```

### Validate Before Sending to External Review

```bash
# Quick check before engaging outside counsel
openreview graph health draft_nda.pdf
# Score < 60 → send back for revision
```

---

## Understanding the Health Score

| Score Range | Meaning | Action |
|-------------|---------|--------|
| 90-100 | Excellent structure | None needed |
| 70-89 | Good structure | Minor improvements possible |
| 50-69 | Moderate issues | Review broken refs and orphans |
| 30-49 | Significant issues | Structural revision recommended |
| 0-29 | Poor structure | Major restructuring needed |

> These thresholds are heuristic defaults. Adjust based on your organisation's quality standards.
