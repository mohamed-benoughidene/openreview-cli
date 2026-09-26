# Contract Graph Modeling — Data Model

**Spec**: `specs/025-contract-graph-modeling/spec.md`
**Created**: 2026-07-06

---

## 1. Core Entities

### 1.1 GraphNode

A single clause in the contract graph.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Clause identifier (e.g., `"clause-1"`, `"clause-5"` — synthetic ID from parsing). Unique within graph. |
| `label` | `str` | Human-readable section number (e.g., `"Section 3.2"`, `"Article 1"`). |
| `text` | `str` | Full clause text. Included for context; not used in metric computation. |
| `level` | `int` | Nesting depth from parsing (0 = root level article, 1 = section, 2 = subsection). |
| `metadata` | `dict[str, Any]` | Extensible metadata: `source_page`, `title`, `paragraph_count`, etc. Preserved from `Clause` model. |

**Constraints**:
- `id` must be non-empty and unique within the graph
- `level >= 0`

### 1.2 EdgeType

Enumeration of directed edge types:

| Value | Meaning | Example |
|-------|---------|---------|
| `parent_child` | Hierarchical nesting: parent clause contains child clause | Article 1 → Section 1.1 |
| `cross_ref` | A clause references another by section number | Section 3.2 → Section 7.1 ("as set forth in Section 7.1") |
| `def_ref` | A clause uses a term defined elsewhere | Section 4.3 → Section 1.2 (uses "Confidential Information" defined in 1.2) |

### 1.3 GraphEdge

A directed edge between two nodes.

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | `str` | ID of the source node (referencing clause) |
| `target_id` | `str` | ID of the target node (referenced clause) |
| `edge_type` | `EdgeType` | Type of relationship |
| `metadata` | `dict[str, Any]` | Extensible: `pattern_matched` (which regex pattern found this ref), `term` (for def-ref edges, the defined term name) |

**Constraints**:
- `source_id` and `target_id` must reference existing node IDs
- `edge_type` must be a valid `EdgeType` value
- Self-referencing edges (source_id == target_id) are excluded

### 1.4 ContractGraph

The top-level graph container.

| Field | Type | Description |
|-------|------|-------------|
| `nodes` | `dict[str, GraphNode]` | Nodes keyed by ID. Dict provides O(1) lookup. |
| `edges` | `list[GraphEdge]` | All edges in insertion order. |
| `metadata` | `dict[str, Any]` | Graph-level metadata: `source_path`, `clause_count`, `built_at`, `graph_version` (`"1.0"`). |

**Derived properties** (computed on access, not stored):

| Property | Type | Computation |
|----------|------|-------------|
| `adjacency` | `dict[str, list[GraphEdge]]` | Adjacency list: source_id → outgoing edges. Built by scanning `edges`. |
| `inbound` | `dict[str, list[GraphEdge]]` | Reverse adjacency: target_id → incoming edges. Built by scanning `edges`. |
| `roots` | `list[str]` | Node IDs with no incoming `parent_child` edges. |
| `orphan_ids` | `list[str]` | Node IDs with no incoming `parent_child` edge and at least one outgoing `parent_child` edge. |
| `node_count` | `int` | `len(nodes)` |
| `edge_count` | `int` | `len(edges)` |

---

## 2. JSON Serialisation Format

### 2.1 Serialised Graph

```json
{
  "metadata": {
    "source_path": "/path/to/contract.pdf",
    "clause_count": 12,
    "built_at": "2026-07-06T12:00:00Z",
    "graph_version": "1.0"
  },
  "nodes": [
    {
      "id": "clause-1",
      "label": "Section 1",
      "text": "Definitions. For purposes of this Agreement...",
      "level": 0,
      "metadata": {}
    },
    {
      "id": "clause-2",
      "label": "Section 1.1",
      "text": "\"Confidential Information\" means...",
      "level": 1,
      "metadata": {}
    }
  ],
  "edges": [
    {
      "source_id": "clause-1",
      "target_id": "clause-2",
      "edge_type": "parent_child",
      "metadata": {}
    },
    {
      "source_id": "clause-4",
      "target_id": "clause-7",
      "edge_type": "cross_ref",
      "metadata": {
        "pattern_matched": "Section\\s+(\\d+\\.?\\d*)"
      }
    },
    {
      "source_id": "clause-5",
      "target_id": "clause-2",
      "edge_type": "def_ref",
      "metadata": {
        "term": "Confidential Information"
      }
    }
  ]
}
```

### 2.2 Methods

- `ContractGraph.to_json() -> str` — serialise to formatted JSON
- `ContractGraph.from_json(data: str | dict) -> ContractGraph` — deserialise from JSON string or parsed dict
- `ContractGraph.to_file(path: str | Path) -> None` — serialise to JSON file
- `ContractGraph.from_file(path: str | Path) -> ContractGraph` — load from JSON file

---

## 3. Metrics

### 3.1 GraphMetrics

```python
@dataclass
class GraphMetrics:
    density: float              # 0.0 to 1.0
    max_depth: int              # >= 1
    orphan_ratio: float         # 0.0 to 1.0
    broken_ref_count: int       # >= 0
    definition_coverage: float  # 0.0 to 1.0
```

### 3.2 Metric Algorithms

**Density**:
```
if node_count <= 1:
    density = 0.0
else:
    max_possible = node_count * (node_count - 1)
    density = edge_count / max_possible
```

Rationale: Directed graph density. A well-structured contract has low density (~0.1 or less for 10 clauses). High density indicates over-connectedness (every clause referencing every other).

**Max Depth**:
```
# Traverse only parent_child edges
roots = nodes with no incoming parent_child edges
max_depth = 0
for each root:
    depth = dfs(root, follow=parent_child)
    max_depth = max(max_depth, depth)
```

Rationale: Deep nesting indicates complexity. A typical contract has depth 2-4. Depth >6 may indicate poor organisation.

**Orphan Ratio**:
```
orphan_count = 0
for each node:
    has_parent = node has incoming parent_child edge
    has_children = node has outgoing parent_child edges
    if not has_parent and has_children:
        orphan_count += 1  # has children but no parent = orphaned subtree
    # Nodes with no parent AND no children are standalone (not orphaned)
    # Standalone clauses are introductory text, signatures, etc.
orphan_ratio = orphan_count / node_count
```

Rationale: Orphaned clauses are structural defects. A node with no incoming `parent_child` edge but with outgoing `parent_child` edges is disconnected from the hierarchy. Standalone nodes (no incoming and no outgoing `parent_child` edges) are intentional (boilerplate, preamble).

**Broken Cross-Reference Count**:
```
broken_count = 0
for each edge where edge_type == cross_ref:
    if edge.target_id not in nodes:
        broken_count += 1
```

Rationale: A cross-reference to a non-existent section is a clear drafting error. Each broken ref reduces document quality.

**Definition Coverage**:
```
# From def_ref edges
referenced_terms = set of unique terms from all def_ref edges
defined_terms = set of terms defined in definition clauses
if len(referenced_terms) == 0:
    definition_coverage = 1.0  # trivially perfect
else:
    definition_coverage = len(defined_terms & referenced_terms) / len(referenced_terms)
```

Rationale: A term referenced but never defined is a drafting gap. Coverage <1.0 means some terms are used before definition.

---

## 4. Health Score

### 4.1 HealthScore

```python
@dataclass
class HealthScore:
    score: int          # 0-100
    weights: list[float]  # The weights used (after normalisation)
```

### 4.2 Constants and Formula

```
MAX_EXPECTED_DEPTH = 10       # Upper bound for depth normalisation
MAX_EXPECTED_BROKEN_REFS = 10 # Upper bound for broken-ref normalisation

Components (all normalised to [0, 1], higher = better):
  c1 = 1.0 - density                         # Low density is good
  c2 = 1.0 - min(max_depth / MAX_EXPECTED_DEPTH, 1.0) # Shallow depth is good (max 10 is worst)
  c3 = 1.0 - orphan_ratio                    # No orphans is good
  c4 = 1.0 - min(broken_ref_count / MAX_EXPECTED_BROKEN_REFS, 1.0) # No broken refs is good
  c5 = definition_coverage                   # Higher coverage is good

Default weights: [0.15, 0.20, 0.20, 0.25, 0.20]
Sum must = 1.0 (auto-normalised with warning if not)

raw = w1*c1 + w2*c2 + w3*c3 + w4*c4 + w5*c5
health_score = round(clamp(raw * 100, 0, 100))
```

### 4.3 Weight Rationale

| Component | Weight | Rationale |
|-----------|--------|-----------|
| Density (c1) | 0.15 | Least impactful — moderate density is fine; only extreme over-connectedness matters |
| Max Depth (c2) | 0.20 | Moderate impact — deep nesting hurts readability |
| Orphans (c3) | 0.20 | Moderate impact — disconnected subtrees are structural defects |
| Broken Refs (c4) | 0.25 | **Highest impact** — a cross-reference to a non-existent section is a clear drafting error |
| Definition Coverage (c5) | 0.20 | Moderate impact — undefined terms create ambiguity |

### 4.4 Edge Cases

| Graph State | Expected Score | Reasoning |
|-------------|---------------|-----------|
| Single node, no edges | 100 | Trivially perfect |
| Flat (all roots, no hierarchy), no refs | ~92 | Low density (0), min depth (1), no orphans (0), no broken refs (0), trivially perfect coverage (1.0) |
| All refs broken, all nodes orphaned | 0 | Pathological worst case |
| Normal contract, moderate refs | 70-90 | Expected range for well-drafted contracts |
| Normal contract, several broken refs | 40-60 | Detection threshold for quality issues |

---

## 5. Inheritance from Parsing Models

The graph builder consumes `Clause` objects from the parsing module:

```
Clause.id                       →  GraphNode.id        (synthetic clause ID, e.g., "clause-5")
Clause title/text (extracted    →  GraphNode.label     (section number, e.g., "Section 3.2")
  numbering regex)
Clause.text                     →  GraphNode.text
Clause.level                    →  GraphNode.level
Clause.parent_id                →  Used by builder to build parent_child edges (not stored in graph node)
```

**Cross-reference resolution**: The `CrossReferenceDetector` builds a temporary `label → Clause.id` index from all `GraphNode.label` values. When regex patterns match `"Section 3.2"` in clause text, the label is looked up in the index to resolve the target `GraphNode.id`.

The `ContractGraph` is a **downstream consumer** of `Clause` — it does not modify or depend on the parsing module beyond the `Clause` dataclass interface.

### 5.1 Section Number Extraction

Section numbers are extracted from clause content using the existing `_NUMBERING_PATTERNS` and `detect_numbering_pattern()` from `src/openreview_cli/parsing/clause_detector.py`:

| Priority | Pattern | Example | Level |
|----------|---------|---------|-------|
| 1 | `ARTICLE/Article/SECTION/Section + Roman/Number` | `Article 1`, `Section 2` | 0 |
| 2 | `Clause/clause + digit` | `Clause 5` | 0 |
| 3 | Digit-dotted: `\d+\.(?:\d+\.)*` | `3.2`, `3.2.1` | 1 |
| 4 | `Section + digit.digit` | `Section 3.2` | 1 |
| 5 | Parenthesised letter: `\([a-z]\)` | `(a)`, `(b)` | 2 |
| 6 | Parenthesised digit: `\(\d+\)` | `(1)`, `(2)` | 2 |
| 7 | Parenthesised Roman: `\([ivxlcdm]+\)` | `(i)`, `(ii)` | 2 |

**Extraction algorithm**:

1. **label** is extracted from `Clause.title` first (the extracted heading text). If `Clause.title` is empty or contains no numbering pattern, fall back to the first line of `Clause.text`.
2. The first matching pattern in the table above determines the **section label** string (e.g., `"Section 3.2"`).
3. `GraphNode.label` stores the full matched label. If no pattern matches, label falls back to `"Clause {id}"`.
4. `GraphNode.level` is derived from the matched pattern's level column, not from `Clause.level`. This ensures consistent level semantics independent of parsing quirks.
