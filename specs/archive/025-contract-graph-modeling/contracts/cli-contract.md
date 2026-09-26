# Graph Commands — CLI Interface Contract

**Spec**: `specs/025-contract-graph-modeling/spec.md`
**Created**: 2026-07-06

> This contract defines the CLI surface for `openreview graph` subcommands. All new commands are added under a `graph_app = typer.Typer(name="graph")` group in `app.py`.

---

## 1. Subcommand Group: `openreview graph`

```
openreview graph [OPTIONS] COMMAND [ARGS]...
```

**Parent app**: `typer.Typer(name="graph", help="Build and analyse contract clause graphs.")`
**Registration**: `app.add_typer(graph_app)`

---

## 2. `openreview graph build`

Build a directed clause graph from a parsed contract JSON file.

### Signature

```python
@graph_app.command()
def build(
    input_path: str = typer.Argument(
        ..., help="Path to a parsed contract JSON file (output of 'openreview parse --format json')."
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Path for the output graph JSON file (default: {input_stem}.graph.json)."
    ),
) -> None
```

### Behaviour

1. Read `input_path` as JSON array of `Clause` objects (matching `parsing/models.py` `Clause` dataclass)
2. Build `ContractGraph` using `ClauseHierarchyBuilder` + `CrossReferenceDetector` + `DefinitionDetector`
   - GraphNode.id = Clause.id (synthetic clause ID from parsing, e.g., `"clause-5"`)
   - GraphNode.label = section number extracted from clause title/text (e.g., `"Section 3.2"`)
   - CrossReferenceDetector builds a temporary `label → Clause.id` index from all node labels to resolve `"Section 3.2"` references to the correct target node ID
   - Hierarchy edges come from `Clause.parent_id`, not from numbering inference
3. Serialise to `output` as JSON via `ContractGraph.to_json()`

### Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Success — graph written to `output` |
| 1 | `input_path` does not exist or is not a file |
| 2 | `input_path` is not valid JSON or does not match Clause schema |

### Examples

```bash
openreview graph build parsed_contract.json
# → Output: parsed_contract.graph.json

openreview graph build parsed_contract.json --output contract_graph.json
# → Output: contract_graph.json
```

---

## 3. `openreview graph metrics`

Compute heuristic structural metrics from a graph JSON file.

### Signature

```python
@graph_app.command()
def metrics(
    graph_path: str = typer.Argument(
        ..., help="Path to a graph JSON file (output of 'graph build')."
    ),
) -> None
```

### Behaviour

1. Load `ContractGraph` from `graph_path` via `ContractGraph.from_json()`
2. Compute `GraphMetrics` via `compute_metrics()`
3. Print metrics to stdout as a formatted table

### Output Format

```
Contract Graph Metrics
──────────────────────
Density:              0.087
Max Depth:            4
Orphan Ratio:         0.000
Broken Cross-Refs:    1
Definition Coverage:  0.833
```

### Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Success — metrics computed and displayed |
| 1 | `graph_path` does not exist |
| 2 | `graph_path` is not valid graph JSON |

### Example

```bash
openreview graph metrics contract_graph.json
```

---

## 4. `openreview graph health`

Compute a 0-100 health score from a graph JSON file.

### Signature

```python
@graph_app.command()
def health(
    graph_path: str = typer.Argument(
        ..., help="Path to a graph JSON file (output of 'graph build')."
    ),
    weights: list[float] = typer.Option(
        None, "--weights", "-w",
        help="Five custom weights: density depth orphans broken-refs coverage. "
             "Auto-normalised to sum 1.0.",
    ),
) -> None
```

### Behaviour

1. Load `ContractGraph` from `graph_path`
2. Compute `GraphMetrics` via `compute_metrics()`
3. Compute `HealthScore` via `compute_health(metrics, weights)`
4. If weights are provided and do not sum to 1.0, normalise and emit warning to stderr: `"Warning: weights normalised from {sum:.4f} to 1.0"`
5. Print health score to stdout

### Output Format

```
Health Score: 82/100
```

### Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Success — health score computed |
| 1 | `graph_path` does not exist |
| 2 | `graph_path` is not valid graph JSON; or `weights` does not contain exactly 5 values |

### Validation

- `--weights` must have exactly 5 values
- Each value must be a float >= 0.0
- If weights sum > 0 but != 1.0, normalise with warning
- If all weights are 0.0, use defaults

### Examples

```bash
# Default weights
openreview graph health contract_graph.json

# Custom weights (penalise broken refs more heavily)
openreview graph health contract_graph.json --weights 0.1 0.1 0.1 0.5 0.2

# Normalised (warning emitted)
openreview graph health contract_graph.json --weights 0.2 0.2 0.2 0.3 0.3
# → Warning: weights normalised from 1.2000 to 1.0
```

---

## 5. `openreview graph view`

Render the clause hierarchy as an indented ASCII text tree.

### Signature

```python
@graph_app.command()
def view(
    graph_path: str = typer.Argument(
        ..., help="Path to a graph JSON file (output of 'graph build')."
    ),
    color: bool = typer.Option(
        False, "--color", "-c", help="Enable ANSI colour highlighting."
    ),
) -> None
```

### Behaviour

1. Load `ContractGraph` from `graph_path`
2. Render ASCII tree via `render_tree(graph, color)`
3. Print to stdout
4. No ANSI escape codes unless `--color` is passed

### Output Format

```
Article 1  Definitions                        [2 refs out]  [DEF-REF: 3]
  Section 1.1  Confidential Information       [0 refs out]
  Section 1.2  Term                             [0 refs out]
Article 2  Term and Termination               [2 refs out]
  Section 2.1  Effective Date                   [0 refs out]
  Section 2.2  Termination                    [1 ref out]
    Section 2.2.1  Termination for Cause      [0 refs out]  [ORPHAN]
```

### Annotation Legend

| Annotation | Meaning |
|------------|---------|
| `[N refs out]` | Node has N outgoing cross-reference edges |
| `[DEF-REF: N]` | Node uses N defined terms |
| `[DEFINES: "term"]` | Node defines a term |
| `[ORPHAN]` | Node has children but no parent (disconnected subtree) |

### Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Success — tree rendered |
| 1 | `graph_path` does not exist |
| 2 | `graph_path` is not valid graph JSON |

### Example

```bash
openreview graph view contract_graph.json
openreview graph view contract_graph.json --color
```

---

## 6. Error Handling

All graph subcommands follow the project's existing error conventions in `errors.py`:

| Error | Exit Code | Message Pattern |
|-------|-----------|-----------------|
| File not found | 1 | `"Error: File not found: {path}"` |
| Invalid JSON / schema | 2 | `"Error: Invalid graph file: {details}"` |
| Argument validation | 1 | `"Error: {description of the problem}"` |

Errors are printed to stderr. All use `typer.echo(message, err=True)` and `raise typer.Exit(code=N)`.

---

## 7. Python API (internal contract)

The CLI functions delegate to the Python API. Each CLI function is a thin wrapper (parse args → call Python API → format output):

```python
# CLI function for 'graph build'
def build(input_path: str, output: str | None) -> None:
    from openreview_cli.graph.builder import build_from_parsed
    graph = build_from_parsed(input_path)
    if output is None:
        from pathlib import Path
        output = str(Path(input_path).with_suffix(".graph.json"))
    graph.to_file(output)
    typer.echo(f"Graph built: {len(graph.nodes)} nodes, {len(graph.edges)} edges → {output}")

# CLI function for 'graph metrics'
def metrics(graph_path: str) -> None:
    graph = ContractGraph.from_file(graph_path)
    m = compute_metrics(graph)
    _print_metrics_table(m)

# CLI function for 'graph health'
def health(graph_path: str, weights: list[float] | None) -> None:
    graph = ContractGraph.from_file(graph_path)
    m = compute_metrics(graph)
    h = compute_health(m, weights)
    typer.echo(f"Health Score: {h.score}/100")

# CLI function for 'graph view'
def view(graph_path: str, color: bool) -> None:
    graph = ContractGraph.from_file(graph_path)
    typer.echo(render_tree(graph, color=color))
```

---

## 8. Dependencies

- `typer` — already installed (parent app)
- `pydantic` — already installed (optional, for GraphMetrics/HealthScore validation)
- stdlib: `json`, `pathlib`, `re`, `collections`, `dataclasses`
- No new dependencies added to `pyproject.toml`
