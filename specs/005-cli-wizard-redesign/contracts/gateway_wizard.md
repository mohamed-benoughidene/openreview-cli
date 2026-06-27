# SetupWizard Contract (Refactored)

**Phase 1 output** | **Date**: 2026-06-27

## Python Interface (Unchanged)

```python
class SetupWizard:
    """Interactive wizard for `openreview gateway setup`.

    Guides the user through 5 slot configurations (reasoning, extraction,
    embedding, reranking, graph), saves config.yml + auth.json, and
    displays a summary table.

    Public interface unchanged after refactor. Internal prompts
    migrated from rich.prompt.Prompt.ask() to questionary.
    """

    def __init__(self) -> None:
        ...

    def run(self) -> None:
        """Execute the wizard flow.

        Saves config.yml and auth.json on successful confirmation.
        Returns None.
        """
        ...
```

## CLI Contract

```bash
# Interactive mode (refactored — arrow keys)
openreview gateway setup

# Non-interactive mode
openreview gateway setup --non-interactive \
  --reasoning ollama/qwen3:8b \
  --extraction ollama/qwen3:8b \
  --embedding ollama/nomic-embed \
  --reranking ollama/rerank \
  --graph ollama/qwen3:8b
```

### Flags (unchanged)

| Flag | Type | Description |
|------|------|-------------|
| `--non-interactive` | bool | Skip wizard, use flags only |
| `--reasoning` | str | Model for reasoning slot |
| `--extraction` | str | Model for extraction slot |
| `--embedding` | str | Model for embedding slot |
| `--reranking` | str | Model for reranking slot |
| `--graph` | str | Model for graph slot |

## Behavior Changes

| Before | After |
|--------|-------|
| `Prompt.ask()` for provider/model selection | `questionary.select()` — arrow-key navigation |
| No fuzzy filtering for model selection | `questionary.autocomplete()` for Ollama model list |
| No multi-select for grouping | `questionary.confirm()` — "Apply to extraction and graph too?" |
| No summary-before-save | Rich Table shown; user must confirm "Save?" before write |
| No validation feedback inline | `questionary.text(validate=...)` — inline red error |
| No non-interactive terminal guard | Detect piped stdin / `TERM=dumb` → fallback to flag mode |
| "back"/"cancel" via string matching on Prompt.ask() | questionary handles Ctrl+C (returns None); "← Back" as last choice in select prompts (provider, model, grouping) |

## Back Navigation

The refactored wizard uses a **"← Back" choice** in `questionary.select()` prompts instead of text-based "back" entry. Rules:

| Prompt | Has "← Back"? | Behavior |
|--------|--------------|----------|
| Provider selection | Yes (when step_idx > 0) | Decrements step_idx; clears skipped_slots if returning to step 0 |
| Model selection | Yes | Returns to provider selection for current slot |
| API key entry | No | questionary.password() — use Ctrl+C to exit instead |
| Grouping confirm | Yes | Returns to model selection for current slot |

## Return Value

```python
# Unchanged — saves to files, returns None
SetupWizard.run() -> None
```

## Files Written

- `config.yml` (YAML, gateway.models.* slots plus metadata)
- `auth.json` (JSON, API keys, chmod 600) — via `atomic_write()`
