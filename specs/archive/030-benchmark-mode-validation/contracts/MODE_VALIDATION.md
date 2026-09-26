# Interface Contract: `--modes` Validation (FR-1, FR-2)

**Spec ref**: spec 030 FR-1, FR-2
**Source file**: `src/openreview_cli/benchmark/cli.py`
**Validation pattern**: Mirrors existing dataset validation at `cli.py:154-160`

## Interface

```python
VALID_MODES: frozenset[str] = frozenset({...17 modes...})

def _validate_modes(mode_list: list[str]) -> None:
    """Validate mode list against VALID_MODES. Raises typer.Exit on first
    unknown mode with exit code 78 and error message to stderr."""
```

## Behaviour

| Input | Result |
|-------|--------|
| `--modes=precheck` | Pass |
| `--modes=precheck,hirecheck,dealcheck` | Pass |
| `--modes=precheck,invalidmode` | Exit 78, stderr: `Error: Unknown mode 'invalidmode'. Valid: assetcheck, buycheck, ...` |
| `--modes=` (empty) | Pass (no modes to run) |
| `--all` | Resolves to all 17 modes, always passes |
| `--modes=PRECHECK` (wrong case) | Exit 78 (case-sensitive match) |

## Error Format

```python
for m in mode_list:
    if m not in VALID_MODES:
        typer.echo(
            f"Error: Unknown mode '{m}'. Valid: {', '.join(sorted(VALID_MODES))}",
            err=True,
        )
        raise typer.Exit(code=78)
```

## Location

Inserted after format validation (line 147) and before dataset resolution (line 149)
in `benchmark_run()`.
