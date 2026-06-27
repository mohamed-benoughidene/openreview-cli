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
| `--clauses` | list[str] | no | Clause IDs (non-interactive + clause-by-clause) |

## Return Type

```python
@dataclass
class ReviewConfiguration:
    file_path: str
    mode: str                          # "full" | "clause-by-clause" | "risk-scan"
    jurisdiction: str | None           # None when mode == "risk-scan"
    output_format: str | None          # None when mode == "risk-scan"
    clauses: list[str] | None           # None = all clauses; populated only for clause-by-clause
```

## Errors

| Condition | Error |
|-----------|-------|
| File does not exist | Print error and exit 1 |
| Unsupported file type | Print error and exit 1 |
| Missing required flags in non-interactive mode | Print error and exit 1 |
| Gateway not reachable (pre-flight) | Warn + offer gateway setup; if declined, continue with defaults |
