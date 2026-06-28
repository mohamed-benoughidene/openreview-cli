# CLI UX Contract: openreview-cli

**Source**: Specification at `specs/006-cli-ux-specification/spec.md`
**Status**: Phase 1 output — binding interface contract
**Last updated**: 2026-06-28
**Applies to**: All commands, subcommands, and interactive flows in `openreview-cli`

---

## 1. Command Signatures

### 1.1 Global Flags

All subcommands accept these global flags, defined at the root Typer app level per [FR-CS-002]. Every multi-word flag uses `--kebab-case`. Short flags are reserved for the most common flags only [R-1].

| Flag | Type | Default | Description | Ref |
|------|------|---------|-------------|-----|
| `--verbose` | flag | `false` | Show detailed processing steps to stderr. All verbose output MUST be PII-redacted per constitution Principle I. | [FR-FB-005] |
| `--quiet` | flag | `false` | Suppress all non-error output and spinners. Errors still print. | [FR-FB-006] |
| `--no-color` | flag | `false` | Disable all ANSI color codes. Respects `NO_COLOR` env var. | [FR-TC-001] |
| `--no-unicode` | flag | `false` | Use ASCII fallback icons instead of Unicode. Auto-detected from locale when flag absent. | [FR-TC-002] |
| `--output` | choice | `table` | Output format. Valid: `table`, `json`, `plain`. | [FR-OF-002] |
| `--config` | path | `$XDG_CONFIG_HOME/openreview/config.json` | Path to config file. Overrides default XDG location. | [FR-CF-001] |
| `--help` | flag | — | Show help at any level (tool, subcommand, flag group). | [FR-HS-001] |
| `--version` | flag | — | Print semantic version from `src/openreview_cli/__init__.py` and exit. | [FR-HS-004] |

**Short flags** (limited to the most common) [R-1]:

| Short | Long | Scope |
|-------|------|-------|
| `-h` | `--help` | All levels |
| `-v` | `--version` | Root only |
| `-q` | `--quiet` | All subcommands |
| `-y` | `--yes` | `review` subcommand |
| `-o` | `--output` | All subcommands with output |

**Non-interactive mode** [FR-TC-004]: When `sys.stdin.isatty()` is `False`, all interactive prompts are disabled. Commands that require missing input exit with code 2 and a message explaining the required flag.

---

### 1.2 `openreview` — Root Command

```
openreview [global-flags]
openreview [global-flags] <command> [command-args] [command-flags]
openreview [global-flags] --help
openreview [global-flags] --version
```

**First-run behavior** [FR-CF-001, §8.4]:
- When no config file exists at `$XDG_CONFIG_HOME/openreview/config.json`, display a welcome panel within 200ms explaining the tool in 3–4 plain-English sentences, plus a privacy notice.
- Auto-enter the setup wizard immediately after the welcome message.
- Esc at any wizard step prints: "Setup was interrupted. Run `openreview setup` to try again later." Config file is NOT created.
- Esc on the welcome screen (before entering wizard) prints: "You can set up later with `openreview setup`. For now, use `openreview --help` to explore available commands."

**Error on unknown command** [FR-HS-005]: Prints "Unknown command '<typed>'. Did you mean '<suggestion>'?" and exits with code 2.

**Expected stdout**:
- `--version`: version string only
- `--help`: formatted help with examples-first, plain English, grouped subcommands
- No args (no config): welcome panel

**Expected stderr**: Nothing unless `--verbose` is set (PII-redacted startup info).

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Help, version, or valid command dispatched |
| 2 | Unknown command, missing required arg |
| 3 | Config file corrupted or invalid [FR-CF-004] |

---

### 1.3 `openreview setup` — Setup Wizard

```
openreview [global-flags] setup [--no-interactive]
```

**Purpose**: Run the first-time setup wizard: provider selection, model preference, jurisdiction default, and shell completion installation [§8.4].

**Flags**:

| Flag | Type | Default | Description | Ref |
|------|------|---------|-------------|-----|
| `--no-interactive` | flag | `false` | Skip all prompts; apply defaults or exit with code 2 if required flags are missing in non-TTY mode. | [FR-TC-004] |

**Wizard steps** (see §5 Wizard State Machine for full contract):

| Step | Name | Component | Allow Back? | Esc Behavior |
|------|------|-----------|-------------|--------------|
| 1/4 | Welcome & Privacy Notice | Panel (§2.10) | No | "Setup cancelled." → exit 0 |
| 2/4 | Provider Configuration | Selection Menu + Text Input | Yes | Return to Step 1 |
| 3/4 | Model Preference | Fuzzy Search Select | Yes | Return to Step 2 |
| 4/4 | Shell Completion Install | Confirmation Dialog | No (once started) | Cancel install, continue |

**Config keys created** [§8.2]:

| Key | Source |
|-----|--------|
| `provider.default` | Step 2 — provider selection |
| `provider.<name>.base_url` | Step 2 — base URL input |
| `model.default` | Step 3 — default model |
| `model.standard` | Step 3 — review model |

**Expected stdout**:
- `table` (default): step indicator, component prompts, success summary at end
- `json`: `{"status": "complete", "config_path": "...", "provider": "...", "model": "..."}`

**Expected stderr**: Processing details with `--verbose`; error panels on failure.

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Setup completed successfully |
| 1 | Interrupted by Ctrl-C during processing [FR-PP-004] |
| 2 | Missing required input in non-interactive mode |
| 3 | Config write failure |
| 4 | Shell completion install script not found |

---

### 1.4 `openreview review <file>` — Document Review

```
openreview [global-flags] review <file> [--mode <mode>] [--output <format>]
    [--clauses <list>] [--jurisdiction <name>] [--yes] [--no-pii]
```

**Purpose**: Review a contract document interactively or in batch mode. <file> is a path to a PDF or DOCX.

**Arguments**:

| Arg | Required | Description |
|-----|----------|-------------|
| `file` | Yes | Path to contract document (PDF or DOCX). Error if missing, unreadable, or wrong format [FR-CS-003]. |

**Flags**:

| Flag | Type | Default | Description | Ref |
|------|------|---------|-------------|-----|
| `--mode` | choice | prompted | Review mode: `standard`, `risk`, `compliance`. Required in non-TTY mode. | [§4.1] |
| `--output` | choice | `table` | Output format: `json`, `table`, `plain`. See §3 Output Format Contract. | [FR-OF-002] |
| `--clauses` | list | all | Clause types to analyze (comma-separated). Non-TTY: error if missing. | [§4.1] |
| `--jurisdiction` | string | config default | Governing law jurisdiction. Fuzzy-search prompt when TTY. | [§2.3] |
| `--yes` | flag | `false` | Auto-confirm all prompts with safe defaults. Required for non-interactive use. | [FR-TC-005] |
| `--no-pii` | flag | `false` | Skip PII stripping (debug only). | [§4.1] |

**Non-interactive contract** [FR-TC-004]:
- When not a TTY, `--mode`, `--clauses` (if not "all"), and `--yes` must be provided.
- Missing required flag → exit code 2 with message: "`--mode` is required when running non-interactively. See `openreview review --help`."

**Wizard steps** (see §5 Wizard State Machine):

| Step | Name | Component | Allow Back? | Esc Behavior |
|------|------|-----------|-------------|--------------|
| 1/4 | Mode Selection | Selection Menu | No | "Review cancelled." → exit 1 |
| 2/4 | Clause & Jurisdiction Config | Multi-select + Fuzzy Search | Yes | Return to Step 1 |
| 3/4 | Confirmation | Confirmation Dialog | Yes | Return to Step 2 |
| 4/4 | Processing | Progress Bar + Live Panel | No | "Review cancelled. Partial results not saved." → exit 1 |
| — | Results | Result Table | End | N/A |

**Expected stdout**:
- `table` (default): Rich Table with Risk Level, Clause, Finding, Recommendation columns; summary panel at bottom
- `json`: Array of finding objects to stdout; all human messaging to stderr
- `plain`: Fixed-width columns, no borders, no color

**Expected stderr**: Progress labels, spinner updates, error panels. With `--verbose`: PII-redacted processing steps.

**Exit codes**:
| Code | Condition |
|------|-----------|
| 0 | Review completed successfully |
| 1 | Cancelled by Ctrl-C (partial results discarded) [FR-PP-004] |
| 2 | Missing required flag in non-interactive mode |
| 3 | Config error (e.g., model not configured) |
| 4 | Input file not found, unreadable, encrypted, wrong format |
| 5 | Network error contacting AI provider |
| 6 | AI provider returned error (model unreachable, rate limited) |
| 7 | Interrupted by user during processing |

**JSON output structure** (`--output json`):

```json
{
  "status": "success",
  "document": {
    "path": "contract.pdf",
    "pages": 50,
    "clauses_detected": 47,
    "clauses_analyzed": 12
  },
  "findings": [
    {
      "risk": "high",
      "clause": "Indemnification 4.2",
      "finding": "Unlimited indemnity obligation with no liability cap",
      "recommendation": "Negotiate a liability cap; standard is 12 months' fees"
    }
  ],
  "summary": {
    "total_findings": 3,
    "high": 1,
    "medium": 1,
    "low": 1,
    "duration_seconds": 154.0
  }
}
```

---

### 1.5 `openreview config` — Configuration Management

```
openreview [global-flags] config show [--output <format>]
openreview [global-flags] config get <key>
openreview [global-flags] config set <key> <value>
openreview [global-flags] config unset <key>
openreview [global-flags] config path
```

**Purpose**: View and modify configuration values. Users should never need to edit JSON by hand [User Story 4].

**Subcommand details**:

#### `config show`

Display all configuration values.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output` | choice | `table` | Format: `json`, `table`, `plain`. |

**Expected stdout**:
- `table`: Rich Table with Key, Value, Default columns [FR-OF-001]
- `json`: JSON object with all config keys
- `plain`: Fixed-width columns, no borders

**Exit codes**: 0 success, 3 config read error.

#### `config get <key>`

Display a single config value [FR-CF-002].

**Expected stdout**: The value alone (no additional formatting). For `--output json`: `{"key": "model.default", "value": "llama3.2"}`.

**Expected stderr**: Error panel if key is unknown, with suggestion: "Unknown config key 'foo'. Run `openreview config show` to list valid keys." [FR-CF-002].

**Exit codes**: 0 success, 2 unknown key, 3 config read error.

#### `config set <key> <value>`

Set a config value [FR-CF-002].

**Validation**: Reject unknown keys with error panel suggesting `config show`. Inline validation for model names (checks against provider registry when available) [§10 UNVERIFIED #3].

**Expected stdout**: Success message with old and new values:
```
✓ Config updated: model.default changed from "llama3.1" to "llama3.2"
```

**Exit codes**: 0 success, 2 unknown key, 2 invalid value, 3 config write error.

#### `config unset <key>`

Reset a config value to its default [§8.2].

**Expected stdout**: Success message:
```
✓ Config reset: model.default restored to "llama3.2" (default)
```

**Exit codes**: 0 success, 2 unknown key, 3 config write error.

#### `config path`

Print the config file path [§8.2].

**Expected stdout**: Absolute path to config file, one line.

**Exit codes**: 0 always (path is always resolvable).

---

### 1.6 `openreview models` — Model Management

```
openreview [global-flags] models list [--output <format>]
openreview [global-flags] models pull <name>
openreview [global-flags] models info <name>
```

**Purpose**: List, pull (download), and inspect AI models managed by the tool.

#### `models list`

List available models per provider.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output` | choice | `table` | Format: `json`, `table`, `plain`. |

**Expected stdout**:
- `table`: Rich Table with Provider, Model, Status, Size columns
- `json`: Array of model objects
- `plain`: Fixed-width columns

**Exit codes**: 0 success, 5 network error (registry unreachable), 1 general error.

#### `models pull <name>`

Download/pull a model [§4.1].

**Expected stdout** (TTY): Progress bar during download, success message on completion:
```
✓ Model "llama3.2" pulled successfully (3.2 GB)
```

**Expected stderr**: Progress updates.

**Exit codes**: 0 success, 1 cancelled (Ctrl-C), 5 network error, 6 provider error.

#### `models info <name>`

Display model details.

**Expected stdout**:
- `table`/`plain`: Name, Provider, Parameters, Quantization, Description in a formatted panel or table
- `json`: Full model metadata object

**Exit codes**: 0 success, 2 unknown model, 5 network error.

---

### 1.7 `openreview list` — Resource Listing

```
openreview [global-flags] list providers [--output <format>]
openreview [global-flags] list models [--output <format>]
openreview [global-flags] list jurisdictions [--output <format>]
```

**Purpose**: List available resources (providers, models, jurisdictions).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output` | choice | `table` | Format: `json`, `table`, `plain`. |

**Expected stdout**: Tabular listing per resource type.

**Exit codes**: 0 success.

---

## 2. Output Format Contract

### 2.1 `table` (default) [FR-OF-001]

**Guarantees**:
- Rich-formatted Table with visible borders (unicode box-drawing or ASCII, depending on Unicode support)
- Column headers styled in `bold cyan` (or `bold` when no-color)
- Color-coded risk levels: `HIGH` = `bold red`, `MEDIUM` = `bold yellow`, `LOW` = `bold green`
- Auto-width to terminal (minimum supported: 60 columns) [FR-TC-003]
- Below 80 columns: proportional reduction, text wrapping within cells
- Below 60 columns: fall back to key-value paired lines (each row → multi-line block)
- Below 40 columns: warn "Terminal too narrow for optimal display." and continue
- All Rich styling: borders, color, bold/dim/italic per design tokens [FR-VD-001]

**When to use**: Default — interactive terminal use.

### 2.2 `json` [FR-OF-002]

**Guarantees**:
- Valid JSON printed to stdout only
- All human messaging, progress, spinner output, and error panels go to stderr
- JSON is parseable by `jq` and any JSON library
- Top-level structure is always an object with `"status"` field: `"success"`, `"error"`, or `"cancelled"`
- On error: `{"status": "error", "code": <int>, "message": "..."}`
- No trailing whitespace or non-JSON content on stdout

**When to use**: Scripting, piping to `jq`, CI pipelines.

### 2.3 `plain` [§4.4 clarification]

**Guarantees**:
- Fixed-width columns, no borders, no color
- Predictable alignment for `grep`/`awk` processing
- No ANSI escape codes under any circumstance (even without `--no-color`)
- Same column ordering as `table` format
- No Rich styling, no panels, no step indicators (use compact `[N/M]` prefix)
- Spinner/progress: suppressed; prints `[# / total] description` periodically
- Error messages: plain text without Rich borders (same 3-part content)

**When to use**: `grep`/`awk` filtering, log files, terminals that degrade gracefully.

---

## 3. Exit Code Contract

Replaces the existing exit codes in `src/openreview_cli/errors.py` [FR-FB-002]. All error paths must use these codes. The old scheme (5=config, 6=cost, 7=gateway, 9=PII) is superseded.

| Code | Name | When | Ref |
|------|------|------|-----|
| 0 | Success | Operation completed successfully | [FR-FB-002] |
| 1 | General error | Unhandled error, Ctrl-C cancellation (outside processing), API failure, fallback case | [FR-FB-002] |
| 2 | Usage error | Wrong flags, missing required args, unknown command, invalid flag values | [FR-FB-002] |
| 3 | Config error | Invalid/missing config file, corrupted config, config write failure | [FR-CF-004] |
| 4 | Input file error | File not found, unreadable, encrypted without password, wrong format | [FR-FB-002] |
| 5 | Network error | API unreachable, timeout, DNS failure (PII-stripped external calls only) | [§5.2] |
| 6 | AI error | AI provider returned error, model unreachable, rate limited, invalid response | [§5.2] |
| 7 | Interrupted | User interrupted during processing (Ctrl-C in processing step), with partial-results-not-saved message | [FR-PP-004] |
| 8 | Unknown | Catch-all for unexpected internal errors that don't fit other categories | [§5.2] |

**Rules**:
- `--help` and `--version` always exit with code 0, even if config is broken.
- Config corruption on startup exits with code 3 before dispatching any subcommand.
- Ctrl-C at interactive prompts (not yet in processing) exits with code 1, not 7.
- Ctrl-C during processing (step 4/4 of review wizard) exits with code 7.
- Missing required input in non-TTY mode exits with code 2.

---

## 4. Interactive Prompt Contract

### 4.1 Function Signatures

Wraps questionary v2.1.1 [R-3] in a project-level adapter. Each function:

1. Returns `None` when cancelled by user (Esc or Ctrl-C).
2. Can raise `KeyboardInterrupt` if the caller has registered a handler (configurable via "safe mode" vs "unsafe mode").
3. Is skippable when `sys.stdin.isatty()` is `False` — the caller must check TTY status and provide fallback.

```python
from typing import Any


def select(
    prompt: str,
    choices: list[Choice],
    default: str | None = None,
    qmark: str = "→",
    pointer: str = "▶",
) -> str | None:
    """Arrow-key navigable single-select menu.

    For lists longer than 15 items, use fuzzy_select() instead.
    Returns the selected value string, or None if cancelled (Esc/Ctrl-C).
    """
    ...


def checkbox(
    prompt: str,
    choices: list[Choice],
    defaults: list[str] | None = None,
    validate: bool = True,
) -> list[str] | None:
    """Multi-select with space to toggle, Enter to confirm.

    Selected items show ✓ prefix.
    Returns list of selected values, or None if cancelled.
    """
    ...


def fuzzy_select(
    prompt: str,
    choices: list[str],
    placeholder: str = "Type to filter...",
) -> str | None:
    """Type-ahead filter selection for lists longer than 8 items.

    Uses questionary.autocomplete with substring matching.
    Returns the selected value string, or None if cancelled.
    """
    ...


def confirm(
    prompt: str,
    default: bool = False,
    auto_yes: bool = False,
) -> bool | None:
    """Yes/No confirmation dialog.

    default=False for destructive/mutating actions (y/N).
    default=True for non-destructive actions (Y/n).
    Returns bool for confirmed choice, or None if cancelled.
    When auto_yes=True (from --yes flag), returns default immediately
    without prompting.
    """
    ...


def text(
    prompt: str,
    default: str | None = None,
    validate: Callable[[str], str | bool] | None = None,
    placeholder: str = "",
) -> str | None:
    """Free-text input with optional inline validation.

    validate function returns True for valid, str for error message.
    Returns the input string, or None if cancelled.
    """
    ...


def password(
    prompt: str,
    validate: Callable[[str], str | bool] | None = None,
) -> str | None:
    """Password/secret input (masked characters).

    Returns the input string, or None if cancelled.
    """
    ...
```

### 4.2 Return Type Contract

| User Action | Return Value |
|-------------|--------------|
| Enter to confirm | `str` (select, fuzzy_select, text, password) / `list[str]` (checkbox) / `bool` (confirm) |
| Esc (cancel step) | `None` |
| Ctrl-C in safe mode | `None` |
| Ctrl-C in unsafe mode | Raises `KeyboardInterrupt` |

### 4.3 Non-TTY Behavior [§3.3]

| Function | Non-TTY Behavior |
|----------|------------------|
| `select()` | Prints error to stderr: "`--<flag>` is required. See `--help`." Returns `None`. |
| `checkbox()` | Same pattern. |
| `fuzzy_select()` | Same pattern. |
| `confirm()` | If `auto_yes=True`, returns `default`. Otherwise prints error and returns `None`. |
| `text()` | Same pattern. |
| `password()` | Error: "Password cannot be entered non-interactively. Use `--<flag>` or env var." |

**Caller responsibility**: When a prompt function returns `None` and TTY is false, the caller must exit with code 2 and a clear error message.

### 4.4 Default Rules for Confirmation [FR-IP-003]

| Action Type | Default | Example | `--yes` behavior |
|-------------|---------|---------|------------------|
| Non-destructive | `True` (Y/n) | "Start review?" | Yes, proceed |
| Destructive/mutating | `False` (y/N) | "Overwrite existing report?" | No, safe |
| Paid operation | `False` (y/N) | "Proceed with API call ($0.02)?" | No, safe |

---

## 5. Wizard State Machine Contract

### 5.1 States

The wizard is a deterministic state machine. States are defined in `src/openreview_cli/ui/components/wizard.py` per the plan.

```
                    ┌──────────────────────────────────────────────┐
                    │                                              │
                    v                                              │
Entry ──► ModeSelection ──► Configuration ──► Confirm ──► Processing ──► Results
   │           │                │                │
   └──exit 0───┘                │                │
                    ◄───────────┘                │
                    ◄────────────────────────────┘
```

**State diagram**:

```
State Entry:
  on_enter → render welcome, detect first-run
  transitions: next → ModeSelection (Enter)
               cancel → exit 0 (Esc/Ctrl-C)

State ModeSelection:
  on_enter → render step indicator (1/N), show mode selection menu
  render   → questionary.select with mode choices
  validate → selected mode is one of: standard, risk, compliance
  transitions: next → Configuration (Enter after selection)
               back → Entry (Esc, only if first-run wizard)
               cancel → exit 1 (Ctrl-C)

State Configuration:
  on_enter → render step indicator (2/N), show clause + jurisdiction prompts
  render   → questionary.checkbox for clauses
           → questionary.autocomplete for jurisdiction
  validate → clauses list non-empty; jurisdiction recognized
  transitions: next → Confirm (Enter)
               back → ModeSelection (Esc)
               cancel → exit 1 (Ctrl-C)

State Confirm:
  on_enter → render step indicator (3/N), show summary of selections
  render   → questionary.confirm (safe default: True for non-destructive)
  validate → response is True
  transitions: next → Processing (Enter on Yes)
               back → Configuration (Esc)
               cancel → exit 1 (Ctrl-C)
               no   → back to Configuration

State Processing:
  on_enter → render step indicator (4/N), start progress bar + live panel
  render   → rich.progress.Progress + rich.live.Live
  validate → N/A (continuous)
  transitions: complete → Results (automatic when processing finishes)
               cancel → exit 7 (Ctrl-C, "Review cancelled. Partial results not saved.")
               back → disallowed

State Results:
  on_enter → render result table, summary panel, next-steps hint
  render   → rich.table.Table + rich.panel.Panel
  transitions: exit → exit 0 (Enter or auto)
               cancel → exit 0 (Ctrl-C — results already complete)
```

### 5.2 Transition Table

| From | Event | To | Side Effects |
|------|-------|----|--------------|
| Entry | `next` (Enter) | ModeSelection | Render welcome (first-run only) |
| Entry | `cancel` (Esc, Ctrl-C) | — | Exit code 0, print cancel message |
| ModeSelection | `next` (Enter) | Configuration | Store selected mode |
| ModeSelection | `back` (Esc) | Entry | If first-run: exit 0. If from `setup`: exit 0. |
| ModeSelection | `cancel` (Ctrl-C) | — | Exit code 1, "Review cancelled." |
| Configuration | `next` (Enter) | Confirm | Store clauses, jurisdiction |
| Configuration | `back` (Esc) | ModeSelection | Preserve previous selections |
| Configuration | `cancel` (Ctrl-C) | — | Exit code 1 |
| Confirm | `next` (Yes) | Processing | Begin document processing |
| Confirm | `no` | Configuration | Return to adjust settings |
| Confirm | `back` (Esc) | Configuration | Preserve previous selections |
| Confirm | `cancel` (Ctrl-C) | — | Exit code 1 |
| Processing | `complete` | Results | Store final results |
| Processing | `cancel` (Ctrl-C) | — | Exit code 7, partial results not saved |
| Processing | `back` (Esc) | — | Disallowed (no-op) |
| Results | `exit` (Enter, auto) | — | Exit code 0 |

### 5.3 Validation Hooks

Each step MUST define these hooks. The state machine calls them in order:

```
class WizardStep(Protocol):
    def render(self) -> None:
        """Display the step UI to the user.
        Must complete within 50ms visual render time.
        """

    def validate(self) -> str | None:
        """Validate current state. Return None if valid,
        or an error message string if invalid.
        Called before allowing 'next' transition.
        """

    def resolve_next(self) -> str:
        """Return the name of the next state.
        Default implementation returns the next state in the
        linear sequence; override for conditional branching.
        """
```

**Hook contract**:

| Step | `render()` output | `validate()` rules | `resolve_next()` |
|------|-------------------|--------------------|------------------|
| Entry | Welcome panel (first-run) or skip | Config detection | Always → `"ModeSelection"` |
| ModeSelection | Step indicator + selection menu | Selected mode is one of `standard`, `risk`, `compliance` | → `"Configuration"` |
| Configuration | Step indicator + clause checkbox + jurisdiction fuzzy search | At least 1 clause selected; jurisdiction valid if provided | → `"Confirm"` |
| Confirm | Step indicator + selection summary + confirmation dialog | Response is `True` | `True` → `"Processing"` / `False` → `"Configuration"` |
| Processing | Step indicator + progress bar + live panel | N/A (continuous streaming) | On completion → `"Results"` |
| Results | Result table + summary panel + next-steps | N/A | `"__exit__"` |

### 5.4 Step Indicator Contract [§2.11]

Displayed at the top of Steps 1–4. Removed during Results.

**Format** (TTY, Unicode):
```
✓ ▶ ○ ○  Step 2 of 4: Configuration
```

**Legend**:
- `✓` (green bold) = completed step
- `▶` (cyan bold) = current step
- `○` (dim) = upcoming step

**Compact format** (below 80 columns):
```
[2/4] Configuration
```

**Non-TTY format**:
```
[2/4] Configuration
```

### 5.5 Processing Step Contract

**For determinate operations** (clause-by-clause analysis) [FR-FP-004]:
```python
progress_bar = Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    TimeRemainingColumn(),
)
task = progress_bar.add_task("Analyzing clauses...", total=n_clauses)
```

**For indeterminate operations** (model pull, config save) [FR-FP-003]:
```python
with console.status("[bold]Loading configuration...", spinner="dots"):
    ...
```

**Label format**: "Analyzing clause {N} of {total} — {Title}" [FR-FP-003]
**Maximum label length**: 60 characters. Truncate titles beyond this.

**Update frequency**: 10 Hz maximum (Rich default). Progress bar advances on each clause completion.

---

## 6. Error and Feedback Contract

### 6.1 Error Format (Three-Part Panel) [FR-FB-001]

Every user-facing error uses exactly three sections:

```
┌── ✗ Error ──────────────────────────────────────┐
│                                                   │
│   What failed: Cannot open file 'contract.pdf'.   │
│                                                   │
│   Why: The file was not found at                   │
│   /home/user/contracts/contract.pdf.               │
│                                                   │
│   How to fix: Check the file path and try again:  │
│     openreview review /path/to/contract.pdf        │
│   Run `openreview review --help` for usage.       │
│                                                   │
└───────────────────────────────────────────────────┘
```

**Non-TTY / plain text fallback** [§5.1]:
```
Error: Cannot open file 'contract.pdf'.
  Why: The file was not found at /home/user/contracts/contract.pdf.
  How to fix: Check the file path and try again.
    openreview review /path/to/contract.pdf
  Run `openreview review --help` for usage.
```

### 6.2 Success Format [FR-FB-003]

```
✓ Review complete. 12 clauses analyzed, 3 findings. [2m 34s]

  View the full report:
    openreview review contract.pdf
```

### 6.3 Warning vs Error Decision Rules [§5.4]

| Condition | Action |
|-----------|--------|
| Operation can continue safely | Warning — yellow, non-blocking |
| Operation cannot proceed | Error — red, halt with exit code |
| User input is recoverable | Warning — suggest correction, re-prompt |
| User input is structurally invalid | Error — explain, link to help |
| Config key is unknown | Warning — print, continue (preserve key on write) |
| Config file is corrupted | Error — exit code 3 |
| Optional feature fails (e.g., model registry refresh) | Warning — degraded but functional |
| Required feature fails (e.g., PII engine) | Error — exit code 1 |

### 6.4 Verbose Output Contract [FR-FB-005]

When `--verbose` is set:
- Processing steps printed to stderr with timestamps
- Config values used, model selected, parsing durations
- ALL output MUST be PII-redacted: no file contents, no contract excerpts, no API keys
- Use `[dim]` style for verbose lines to visually distinguish from primary output

---

## 7. Terminal Compatibility Contract

### 7.1 Capability Detection

| Capability | Detection Method | Behavior |
|------------|-----------------|----------|
| Color support | `NO_COLOR` env, `--no-color` flag, Rich auto-detect | `Console(color_system=None)` disables all color [FR-TC-001] |
| Unicode support | `--no-unicode` flag, locale detection | Icon fallback map: ✓ → [OK], ✗ → [ERR], etc. [FR-TC-002] |
| Terminal width | `shutil.get_terminal_size().columns` | Rich auto-adjusts; <60 col → key-value pairs; <40 col → warning [FR-TC-003] |
| TTY vs pipe | `sys.stdin.isatty()` | Disable all interactive prompts; require flags for required inputs [FR-TC-004] |

### 7.2 Icon Fallback Map

| State | Unicode (default) | ASCII fallback |
|-------|-------------------|----------------|
| success | ✓ | `[OK]` |
| error | ✗ | `[ERR]` |
| warning | ⚠ | `[!]` |
| info | ℹ | `[i]` |
| pending | ○ | `[ ]` |
| running | ◷ | `[...]` |
| step marker | → | `->` |
| file path | 📄 | `[file]` |
| lock/secure | 🔒 | `[**]` |

---

## 8. Design Token Contract

### 8.1 Color Palette

Semantic roles mapped to Rich style strings [FR-VD-001]. Every role has a no-color fallback.

| Role | Rich Style | No-Color Fallback | When to Use |
|------|-----------|-------------------|-------------|
| `primary` | `bold cyan` | `bold` | Headings, key prompts, command names in help, file paths |
| `success` | `bold green` | `bold` | Checkmarks, completion summaries, "Review complete" |
| `warning` | `bold yellow` | `bold underline` | Warnings, deprecation notices, non-blocking issues |
| `error` | `bold red` | `bold underline` | Errors, fatal issues, validation failures |
| `muted` | `dim` | `dim` | Secondary info, hints, timestamps, footer text |
| `accent` | `bold magenta` | `bold` | Highlights, step indicators, mode names, special callouts |
| `code` | `bold bright_black on grey15` | (none) | Config keys, flag names, inline code references |

### 8.2 Spacing Rules

| Context | Spacing |
|---------|---------|
| Between paragraphs/items | 1 blank line |
| Between major sections | 2 blank lines |
| After a panel (error/success) | 1 blank line before next content |
| Before a table | 1 blank line above and below |
| Step transitions | Thin horizontal rule (`─` × terminal width) + 1 blank line each side |
| Panel borders | Rich Panel with `padding=(1, 2)` |

### 8.3 Typography Rules [FR-VD-002]

| Style | When to Use |
|-------|-------------|
| **Bold** | Headings, key findings, command names, action prompts, current selection in lists |
| **Dim** | Secondary info, hints, timestamps, "Press Enter to continue", footer text |
| *Italic* | Sparingly — emphasis within a sentence, never for UI elements |
| No underline | Reserved for hyperlinks or no-color fallback only |

---

## 9. Keyboard Shortcut Map (Interactive Mode)

[Based on R-3, R-7, R-8]

| Key | Action | Component |
|-----|--------|-----------|
| ↑ / ↓ | Move selection up/down | Selection Menu, Multi-select, Fuzzy Search |
| → / ← | Navigate between option groups | Confirmation Dialog |
| Enter | Confirm current selection | All interactive components |
| Space | Toggle item in multi-select | Multi-select |
| Esc | Go back / cancel current step | All interactive components |
| Ctrl-C | Exit immediately (any step) | Global |
| / | Jump to filter/search input | Fuzzy Search |
| Tab | Cycle forward, auto-complete | Fuzzy Search, shell completion |
| Shift+Tab | Cycle backward | Fuzzy Search |
| Home / End | Jump to first/last option | Selection Menu, Multi-select |

---

## 10. Performance Perception Contract

| Requirement | Target | Ref |
|-------------|--------|-----|
| First output render | Within 200ms of invocation | [FR-PP-001] |
| Terminal silence max | 500ms without spinner/status | [FR-PP-002] |
| Background task labels | "Analyzing clause N of M — Title..." | [FR-PP-003] |
| Spinner update rate | 10 Hz maximum | [R-2] |
| Progress bar update | On each clause completion | [FR-FP-004] |
| Step transition render | Within 50ms | [§9 plan] |
| Ctrl-C response | Clean message, no traceback, within 100ms | [FR-PP-004] |

**Implementation**: Defer all heavy imports (parsers, Presidio, Ollama clients) behind the Typer command callback. The app module must import only `typer` and shallow `openreview_cli`-level imports [§6.1].

---

## 11. Non-Interactive Contract (CI / Pipe Mode)

When `sys.stdin.isatty()` is `False` OR `--no-interactive`/`--yes` is passed:

1. All interactive prompts (`select`, `checkbox`, `fuzzy_select`, `confirm`, `text`, `password`) are skipped.
2. For each skipped prompt, the corresponding `--flag` value is used.
3. If a required `--flag` is missing, exit with code 2 and a message: "`--<flag>` is required when running non-interactively. See `openreview <command> --help`."
4. `--yes` auto-answers all confirmations with their safe default.
5. Spinners are suppressed (label printed once). Progress bars print `[N / total] description` periodically.
6. Live panels are disabled; full output printed at end.
7. Error panels print without Rich borders (plain text 3-part format).
8. Step indicator prints as `[1/4] Mode Selection` (no Unicode, no color).

---

## 12. References

| Ref | Source |
|-----|--------|
| [R-1] | clig.dev — CLI design guidelines |
| [R-2] | Rich v15.0.0 — terminal formatting library |
| [R-3] | questionary v2.1.1 — interactive prompts |
| [R-4] | InquirerPy v0.3.4 — fuzzy search reference (not used directly) |
| [R-5] | Typer v0.26.8 — CLI framework |
| [R-6] | GitHub CLI v2.95.0 — verb-noun command pattern |
| [R-7] | opencode.ai/docs/keybinds — keyboard interaction patterns |
| [R-8] | charmbracelet/gum — component composition patterns |
| [R-9] | Web research — CLI UX design best practices (ls1intum, Evil Martians, Amanda Pinsker, Thoughtworks) |
| [R-10] | Web research — Python CLI error message design |
| [FR-*] | Functional Requirements from spec.md |

This contract is binding for all implementation tiers. Any deviation requires spec amendment.
