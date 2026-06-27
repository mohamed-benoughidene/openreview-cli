# ReviewWizard Contract

**Phase 1 output** | **Date**: 2026-06-27

## Python Interface

```python
class ReviewWizard:
    """Interactive wizard for the `openreview review` command.

    Guides the user through mode/jurisdiction/format selection,
    runs a pre-flight gateway check, and returns a ReviewConfiguration.
    """

    def __init__(
        self,
        file_path: str,
        non_interactive: bool = False,
        mode: str | None = None,
        jurisdiction: str | None = None,
        output_format: str | None = None,
        clauses: list[str] | None = None,
    ) -> None:
        ...

    def run(self) -> ReviewConfiguration:
        """Execute the wizard flow.

        Returns a ReviewConfiguration bundle to the caller.
        The caller (app.py) decides what to do with it — the wizard
        does not call parse or gateway engines.
        """
        ...
```

## CLI Contract

```bash
# Interactive mode
openreview review <file>

# Non-interactive mode (all flags required)
openreview review <file> --non-interactive --mode full --jurisdiction us-de --output json

# Non-interactive with clause-by-clause (comma-separated clause IDs)
openreview review <file> --non-interactive --mode clause-by-clause --jurisdiction us-de --output json --clauses 1,5,12

# Partial non-interactive (missing flags → error)
openreview review <file> --non-interactive --mode full
# → Error: --jurisdiction and --output are required in non-interactive mode
```

### Flags

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--non-interactive` | bool | no | Skip wizard, use CLI flags only |
| `--mode` | "full" \| "clause-by-clause" \| "risk-scan" | non-interactive: yes | Review mode |
| `--jurisdiction` | str | non-interactive + full/clause-by-clause: yes | Jurisdiction code |
| `--output` | "json" \| "text" \| "html" | non-interactive + full/clause-by-clause: yes | Output format |

> **Naming convention**: CLI flags use short names (`--output`). The `ReviewConfiguration` field is `output_format` (Python convention). This is intentional — CLI flags are typed by users, model fields follow Python naming.
| `--clauses` | list[str] | no | Clause IDs, comma-separated (non-interactive + clause-by-clause). `None` = all clauses; non-empty list = specific IDs; empty list `[]` = error |

## Return Type

```python
@dataclass
class ReviewConfiguration:
    file_path: str
    mode: ReviewMode                      # ReviewMode.FULL | ReviewMode.CLAUSE_BY_CLAUSE | ReviewMode.RISK_SCAN (see data-model.md)
    jurisdiction: str | None              # None when mode == ReviewMode.RISK_SCAN
    output_format: OutputFormat | None    # None when mode == ReviewMode.RISK_SCAN (see data-model.md)
    clauses: list[str] | None             # None = all clauses; populated only for CLAUSE_BY_CLAUSE
```

## Errors

| Condition | Error |
|-----------|-------|
| File does not exist | Print error and exit 1 |
| Unsupported file type | Print error and exit 1 |
| Missing required flags in non-interactive mode | Print error and exit 1 |
| Gateway not reachable (pre-flight) | Warn + offer gateway setup; if declined, continue with defaults |
| `--clauses` is empty list `[]` in non-interactive + clause-by-clause mode | Print error and exit 1: "Error: --clauses requires at least one clause ID" |

## Back Navigation

The review wizard uses a **"← Back" choice** in `questionary.select()` prompts. Rules:

| Prompt | Has "← Back"? | Behavior |
|--------|--------------|----------|
| Mode selection | No | Entry point — Ctrl+C to exit |
| Jurisdiction selection | Yes | Returns to mode selection |
| Output format selection | Yes | Returns to jurisdiction selection |
| Clause multi-select | Yes | Returns to output format selection |
| Summary confirmation | Yes | Returns to mode selection (restart flow) |
