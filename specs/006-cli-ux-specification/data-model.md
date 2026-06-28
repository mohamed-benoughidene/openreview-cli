# Data Model: CLI UX System Design

## Entities

### DesignTokens

Semantic design system for visual output: color palette, iconography, spacing, and typography rules. All tokens have no-color and no-Unicode fallbacks.

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `color_roles` | `dict[str, str]` | Semantic role → Rich style string. Roles: `primary` → `bold cyan`, `success` → `bold green`, `warning` → `bold yellow`, `error` → `bold red`, `muted` → `dim`, `accent` → `bold magenta`, `code` → `bold bright_black on grey15` | FR-VD-001, [R-2], [R-9] |
| `no_color_fallbacks` | `dict[str, str]` | Role → fallback style when `NO_COLOR` or `--no-color` active. `primary` → `bold`, `success` → `bold`, `warning` → `bold underline`, `error` → `bold underline`, `muted` → `dim`, `accent` → `bold`, `code` → `""` (plain) | FR-VD-001, FR-TC-001, [R-1] |
| `icon_map` | `dict[str, str]` | State → Unicode character. States: `success` → `✓`, `error` → `✗`, `warning` → `⚠`, `info` → `ℹ`, `pending` → `○`, `running` → `◷`, `step_marker` → `→`, `file_path` → `📄`, `lock` → `🔒` | FR-VD-004, [R-1], [R-9] |
| `ascii_icon_map` | `dict[str, str]` | State → ASCII fallback. `success` → `[OK]`, `error` → `[ERR]`, `warning` → `[!]`, `info` → `[i]`, `pending` → `[ ]`, `running` → `[...]`, `step_marker` → `->`, `file_path` → `[file]`, `lock` → `[**]` | FR-VD-004, FR-TC-002, [R-1] |
| `spacing` | `dict[str, int]` | Context → blank lines. Keys: `between_paragraphs` (1), `between_sections` (2), `after_panel` (1), `before_table` (1), `step_transition_top` (1), `step_transition_bottom` (1) | FR-VD-003, [R-1], [R-9] |
| `panel_padding` | `tuple[int, int]` | Rich Panel padding: `(1, 2)` — 1 row top/bottom, 2 columns left/right | FR-VD-003, [R-2] |
| `typography` | `dict[str, list[str]]` | Style → list of contexts where applied. `bold`: headings, key findings, command names, action prompts, current selection. `dim`: secondary info, hints, timestamps, footer, role descriptions. `italic`: sparingly, in-sentence emphasis only. `never_style`: raw file paths, contract excerpts, config values that are paths | FR-VD-002, [R-1], [R-9] |
| `width_thresholds` | `dict[str, int]` | Named thresholds for terminal-width adaptation. `compact` (80): step indicator uses `[2/4]` format. `narrow` (60): tables become key-value pairs. `minimal` (40): warning shown below this | FR-TC-003, [R-2] |
| `min_supported_width` | `int` | Minimum supported terminal width in columns: `60` | FR-TC-003, [R-2] |

---

### WizardState

State machine for the multi-step review wizard. Tracks position, accumulated input, and navigation history.

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `current_step` | `int` | Current step index (0=Entry, 1=ModeSelection, 2=Configuration, 3=Confirm, 4=Processing, 5=Results) | FR-FP-002, [R-1] |
| `total_steps` | `int` | Total steps in wizard (review wizard: 4) | FR-FP-002 |
| `mode` | `str \| None` | Selected review mode: `standard`, `risk`, or `compliance` | FR-IP-001 |
| `selected_clauses` | `list[str] \| None` | Clause types selected for analysis | FR-IP-002 |
| `selected_jurisdiction` | `str \| None` | Governing law jurisdiction | FR-IP-002 |
| `config_values` | `dict[str, Any]` | Accumulated configuration values from all steps | — |
| `validation_errors` | `dict[str, str] \| None` | Per-field validation failures: field name → error message | — |
| `allow_back` | `bool` | Whether back navigation (Esc) is allowed at current step | FR-IP-004 |
| `last_transition` | `str` | Last transition type: `next`, `back`, `cancel`, `none` | FR-IP-005 |

**Valid step configurations** (from §3.1 step table):

| `current_step` | Name | `allow_back` | Esc behavior |
|---|---|---|---|
| 1 | ModeSelection | `False` | "Setup cancelled." → exit 0 |
| 2 | Configuration | `True` | Go back to step 1 |
| 3 | Confirm | `True` | Go back to step 2 |
| 4 | Processing | `False` | "Review cancelled. Partial results not saved." → exit 1 |
| 5 | Results | `False` (terminal) | N/A (end of flow) |

---

### OutputFormat

Controls the rendering mode of `SGRenderer` for structured data output.

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `value` | `str` | Format identifier. One of: `table`, `json`, `plain` | FR-OF-001, FR-OF-002 |
| `is_default` | `bool` | `True` when `value == "table"` (the default). Used for conditional rendering decisions | FR-OF-001 |
| `is_machine_readable` | `bool` | `True` when `value == "json"`. When true, all human messaging goes to stderr; only structured JSON goes to stdout | FR-OF-002, SC-005 |

**Format behaviors** (from §4.4):

| `value` | stdout | stderr | ANSI color | Borders | Best for |
|---|---|---|---|---|---|
| `table` | Rich-formatted table | Logs, errors | Yes | Yes | Interactive terminal |
| `json` | Raw JSON | Logs, errors | No (plain text to stdout) | No | Scripting, `jq` pipelines |
| `plain` | Fixed-width columns, no borders | Logs, errors | No | No | grep/awk, log files |

---

### FeedbackPayload

Structured representation of every user-facing message: errors, warnings, and success confirmations. Guarantees the three-part format required by FR-FB-001.

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `what_happened` | `str` | Brief one-sentence description. Displayed bold in Rich output | FR-FB-001, [R-1], [R-10] |
| `why` | `str` | Context explaining why the event occurred. Displayed dim/muted | FR-FB-001, [R-1], [R-10] |
| `what_to_do` | `str` | Actionable suggestion for resolution. Displayed cyan | FR-FB-001, [R-1], [R-10] |
| `exit_code` | `int` | Exit code: 0=Success, 1=General error, 2=Usage error, 3=Config error, 4=Input file error, 5=Network error | FR-FB-002, [R-1], [R-10] |
| `severity` | `str` | One of: `success`, `warning`, `error`. Controls color (green/yellow/red), border style, and halting behavior | FR-FB-003, FR-FB-004, SC-004 |
| `panel_title` | `str \| None` | Optional Rich Panel title. Defaults derived from severity: `"[bold red]✗ Error[/bold red]"`, `"[bold yellow]⚠ Warning[/bold yellow]"`, `"[bold green]✓ Success[/bold green]"` | FR-FB-001, [R-2] |

**Severity rules** (from §5.4):

| `severity` | Color | Border | Halting? | Exit code | When |
|---|---|---|---|---|---|
| `error` | Red | Red border, `bold` | Yes | 1-5 | Operation cannot proceed |
| `warning` | Yellow | Yellow border, `bold` | No | 0 | Operation can continue safely |
| `success` | Green | Green border, `bold` | No | 0 | Operation completed successfully |

---

### TerminalCapabilities

Detected terminal properties that govern color, animation, and interaction behavior. Read once at startup; overridable by flags.

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `width` | `int` | Terminal width in columns from `shutil.get_terminal_size().columns`. Rich auto-detects; override via `Console(width=...)` | FR-TC-003, [R-2] |
| `is_tty_stdin` | `bool` | `True` when `sys.stdin.isatty()` returns `True`. Controls whether interactive prompts are shown | FR-TC-004, SC-005, [R-1] |
| `is_tty_stdout` | `bool` | `True` when `sys.stdout.isatty()` returns `True`. Controls spinner/progress suppression | FR-TC-004, SC-005 |
| `supports_color` | `bool` | Rich auto-detection, overridden to `False` when `NO_COLOR` env var set or `--no-color` flag passed | FR-TC-001, SC-007, [R-1] |
| `supports_unicode` | `bool` | `False` when `--no-unicode` flag passed or locale indicates lack of Unicode support. Controls icon selection in `DesignTokens.icon_map` vs `ascii_icon_map` | FR-TC-002, [R-1] |
| `detected_shell` | `str \| None` | Shell name detected by shellingham (e.g., `bash`, `zsh`, `fish`). Used for shell completion installation guide | FR-IP-006, [R-5] |

**Degradation matrix** (from §3.3):

| Feature | TTY=true (default) | TTY=false (pipe/CI) | `--no-color` | `--no-unicode` |
|---|---|---|---|---|
| Selection menu | questionary interactive prompt | Error: `--mode is required` → exit 2 | Plain text | N/A |
| Spinner | Rich animated spinner | Suppressed, prints label once | Monochrome spinner | N/A |
| Progress bar | Rich animated bar | Prints `[# / total] description` periodically | Monochrome | N/A |
| Error panel | Red border, Rich panel | Plain text, no borders | Plain text, `Error:` prefix | ASCII fallback icons |
| Tables | Styled Rich Table | Fixed-width plain columns | No color in cells | ASCII borders |

---

### ConfigPath

File-system location and access pattern for all configuration files. Governed by XDG Base Directory spec and overridable via environment variables and flags.

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `config_dir` | `str` | `$XDG_CONFIG_HOME/openreview/` or `~/.config/openreview/` fallback | FR-CF-001, [R-1] |
| `config_file` | `str` | `{config_dir}/config.json` | FR-CF-001 |
| `auth_file` | `str` | `{config_dir}/auth.json` | FR-CF-001, Constitution Principle I |
| `file_mode` | `int` | Unix permission mode for auth file: `0o600` (owner read/write only) | FR-CF-001, Constitution Principle I |
| `env_prefix` | `str` | Environment variable prefix for overrides: `"OPENREVIEW_"`. Dots in config keys replaced with underscores, uppercased | FR-CF-003, [R-1] |
| `exists` | `bool` | `True` when `config_file` exists on disk. Used for first-run detection | FR-CF-004, §8.4 |
| `first_run` | `bool` | `True` when `exists` is `False`. Triggers welcome panel + auto-setup wizard | §8.4, [R-1] |

**Config keys** (existing from Foundation Phase 1, extended by FR-CF-002):

| Key | Type | Default | Env var |
|---|---|---|---|
| `model.default` | `str` | `"llama3.2"` | `OPENREVIEW_MODEL_DEFAULT` |
| `model.standard` | `str` | `"llama3.2"` | `OPENREVIEW_MODEL_STANDARD` |
| `model.embedding` | `str` | `"nomic-embed-text"` | `OPENREVIEW_MODEL_EMBEDDING` |
| `model.reranking` | `str` | `""` | `OPENREVIEW_MODEL_RERANKING` |
| `provider.default` | `str` | `"ollama"` | `OPENREVIEW_PROVIDER_DEFAULT` |
| `provider.<name>.base_url` | `str` | `"http://localhost:11434/v1"` | `OPENREVIEW_PROVIDER_<NAME>_BASE_URL` |
| `pii.threshold` | `float` | `0.3` (range 0.0–1.0) | `OPENREVIEW_PII_THRESHOLD` |
| `privacy_tier` | `str` | `"maximum"` | `OPENREVIEW_PRIVACY_TIER` |

---

## Relationships

```
TerminalCapabilities ──────controls──────▶ DesignTokens
       │                                         │
       │ detects TTY, color, unicode, width      │ provides styles, icons, spacing
       ▼                                         ▼
ConfigPath ───reads──▶ WizardState ◀──renders── OutputFormat
       │                      │                       │
       │ provides config       │ tracks step, mode,   │ controls output
       │ values, first_run     │ validation_errors    │ serializer
       ▼                      ▼                       ▼
FeedbackPayload ◀─────── SGRenderer ───────────▶ stdout/stderr
       ▲                        ▲
       │                        │
       └─── formatted by ───────┘
       (3-part panels, exit codes)
```

**Entity interaction summary**:

1. **WizardState** is the runtime authority for wizard progress. It reads initial values from **ConfigPath** (existing config, first_run flag) and uses **DesignTokens** to render step indicators.
2. **OutputFormat** is passed to every rendering call, switching between `table`/`json`/`plain` output serializers.
3. **FeedbackPayload** is the single structure for all error/warning/success output. It carries the exit code that `app.py` passes to `sys.exit()`.
4. **TerminalCapabilities** is initialized once at startup, consulted by **DesignTokens** (color/unicode/width selection) and by **WizardState** (TTY detection for prompt degradation).
5. **ConfigPath** is the immutable filesystem model — it does not hold runtime config values, only paths and existence flags. Runtime values are loaded into the config loader and overlaid with env var overrides (FR-CF-003).

---

## Validation Rules

### DesignTokens

| # | Rule | Condition | Consequence | Source |
|---|------|-----------|-------------|--------|
| 1 | Every role in `color_roles` must have a corresponding entry in `no_color_fallbacks` | `NO_COLOR` env or `--no-color` flag active | Output must degrade gracefully; no color-only semantics lost | FR-TC-001, SC-007 |
| 2 | Every state in `icon_map` must have a corresponding entry in `ascii_icon_map` | `--no-unicode` flag or locale indicates no Unicode support | All icons replaced with ASCII equivalents | FR-VD-004, FR-TC-002 |
| 3 | Spacing values must be non-negative integers | Render phase | Output blocks are separated correctly | FR-VD-003 |
| 4 | `min_supported_width` must be ≥ 40 | Terminal narrower than 60 columns | Graceful degradation: key-value pairs > 60, warning below 40 | FR-TC-003 |
| 5 | `code` role must provide high-contrast on common terminal backgrounds | Render phase | Legibility on both light and dark themes | FR-VD-001, [R-9] |
| 6 | No-color fallbacks must not depend on color (only bold/underline/dim) | `NO_COLOR` active | Users with monochrome terminals can still perceive hierarchy | SC-007, [R-1] |

### WizardState

| # | Rule | Condition | Consequence | Source |
|---|------|-----------|-------------|--------|
| 1 | `current_step` must be in `[0, total_steps]` | Every transition | Invalid state raises assertion; prevents out-of-bounds navigation | FR-FP-002 |
| 2 | Back navigation is forbidden on steps where `allow_back` is `False` | User presses Esc | Step 1: exit wizard. Step 4: "Review cancelled" message | FR-IP-004, FR-IP-005 |
| 3 | Ctrl-C at any step must print a clean message and exit with code 1 | Signal received | No traceback, no partial state corruption | FR-IP-005, SC-004, FR-PP-004 |
| 4 | Step indicator must show "Step N of M: Title" at start of steps 1–4 | Step transition | Correct numbering, visual separator before step | FR-FP-002, FR-FP-006 |
| 5 | Step indicator must be removed during Results | Flow reaches Results | No redundant step display on final output | §3.1 |
| 6 | `mode` must be one of `standard`, `risk`, `compliance` when set | Before transition to Confirm | Validation failure returns user to ModeSelection with error | FR-IP-001 |

### OutputFormat

| # | Rule | Condition | Consequence | Source |
|---|------|-----------|-------------|--------|
| 1 | `value` must be one of: `table`, `json`, `plain` | Every output render | Invalid format rejected with usage error → exit 2 | FR-OF-001, FR-OF-002 |
| 2 | Default output format is `table` | No `--output` flag provided | Interactive users get styled tables by default | FR-OF-001 |
| 3 | JSON output must go to stdout; all human messaging to stderr | `value == "json"` | Pipelines can extract structured data without parsing log noise | FR-OF-002, SC-005 |
| 4 | File paths must be distinct from plain text (bold/cyan) | Path appears in output | Visual distinction prevents path-value confusion | FR-OF-003 |
| 5 | Timestamps must be human-readable (e.g., "Jun 28, 2026 14:30") | Timestamp displayed | No epoch seconds | FR-OF-004 |

### FeedbackPayload

| # | Rule | Condition | Consequence | Source |
|---|------|-----------|-------------|--------|
| 1 | All three parts (`what_happened`, `why`, `what_to_do`) must be non-empty | Every error/warning/success | Silent failures are prohibited; guarantee of actionable feedback | FR-FB-001, FR-FB-003, SC-004 |
| 2 | `exit_code` must be in `{0, 1, 2, 3, 4, 5}` | Every exit path | Invalid exit codes replaced with 1 (general error) | FR-FB-002, [R-10] |
| 3 | `severity == "error"` must halt execution (exit code ≥ 1) | Error created | Errors are blocking; no silent continuation past error | FR-FB-004 |
| 4 | `severity == "warning"` must not halt (exit code 0) | Warning created | Warnings allow continued operation | FR-FB-004 |
| 5 | `severity == "success"` must always produce output | Operation completes | Success is never silent | FR-FB-003, SC-004 |
| 6 | Color must not be the only indicator of severity | `NO_COLOR` or `--no-color` active | "Error:" label precedes message text; `severity` field used for plain text renderers | SC-004, SC-007 |
| 7 | Flesch-Kincaid grade level < 10 for all user-facing text | Every message rendered | Legal professionals can understand without domain-specific jargon | SC-006 |

### TerminalCapabilities

| # | Rule | Condition | Consequence | Source |
|---|------|-----------|-------------|--------|
| 1 | `width` must be detected at startup; minimum supported is 60 columns | Console initialized | Below 60: graceful degradation. Below 40: warning printed | FR-TC-003, [R-2] |
| 2 | All interactive prompts suppressed when `is_tty_stdin` is `False` | Command run with piped stdin | Missing required inputs produce error → exit 2, not hang | FR-TC-004, SC-005 |
| 3 | `supports_color` is `False` when `NO_COLOR` env var is non-empty | Env var detected | Rich `Console(color_system=None)`; DesignTokens uses `no_color_fallbacks` | FR-TC-001, SC-007 |
| 4 | `supports_unicode` is `False` when `--no-unicode` flag is passed | Flag detected | DesignTokens uses `ascii_icon_map`; table borders use ASCII | FR-TC-002 |
| 5 | `is_tty_stdout` `False` suppresses spinner animation and progress bar animation | Output piped to file | Spinner prints label once; progress prints periodic `[#/total]` text | SC-005, §3.3 |

### ConfigPath

| # | Rule | Condition | Consequence | Source |
|---|------|-----------|-------------|--------|
| 1 | `config_file` path must resolve to `$XDG_CONFIG_HOME/openreview/config.json` or `~/.config/openreview/config.json` fallback | Any command invocation | Consistent config location across systems | FR-CF-001 |
| 2 | `auth_file` must be created with mode `0o600` when first written | Config write with auth keys | Owner-only read prevents credential leakage | FR-CF-001, Constitution Principle I |
| 3 | Config validation runs at startup; invalid config → exit code 3 | Corrupted or malformed JSON | User directed to `openreview setup` to repair | FR-CF-004, SC-004 |
| 4 | Unknown config keys in file produce a warning but tool continues | Parsed config has unrecognized key | Unknown keys are preserved on write (no silent deletion) | §8.2, [R-1] |
| 5 | Every config key must be overridable via `OPENREVIEW_<KEY>` env var | Env var present | Env var value takes precedence over config file value | FR-CF-003 |
| 6 | Unknown keys in `config set` command are rejected with error panel | `config set <key>` with unrecognized key | Error shows `openreview config show` for valid keys | FR-CF-002 |

---

## State Transitions

### WizardState Machine

The wizard follows a linear forward flow with optional backward navigation. Based on spec §3.1.

```
                          ┌──────────────────────────────────────────────────────────────┐
                          │                                                              │
                          ▼                                                              │
    ┌──────────┐    ┌──────────────┐    ┌───────────────┐    ┌─────────┐    ┌────────────┐    ┌─────────┐
    │   Entry   │───▶│ ModeSelection │───▶│ Configuration │───▶│ Confirm │───▶│ Processing │───▶│ Results │
    │  (step 0) │    │   (step 1/4)  │    │   (step 2/4)  │    │(step 3/4)│    │ (step 4/4) │    │ (done)  │
    └──────────┘    └──────────────┘    └───────────────┘    └─────────┘    └────────────┘    └─────────┘
         │                 │                    │                  │               │
         │                 │  ◄──── Esc ────┐   │                 │               │
         │                 │  ◄──[step 2]───┘   │                 │               │
         │                 │                    │  ◄── Esc ────┐  │               │
         │                 │                    │  ◄[step 3]───┘  │               │
         │                 │                    │                 │               │
         │                 │  Esc ────────────▶ │                 │               │
         │                 │  [step 1: "Setup   │                 │               │
         │                 │   cancelled."]     │                 │               │
         │                 │  exit 0            │                 │               │
         │                 │                    │                 │               │
         │ Ctrl-C ─────────┼────────────────────┼─────────────────┼───────────────┤               │
         │ [any step]      │                    │                 │               │               │
         │  exit 1,        │                    │                 │             Processing:        │
         │  clean message  │                    │                 │             "Review cancelled.  │
         │                 │                    │                 │             Partial results     │
         │                 │                    │                 │             not saved." exit 1  │
         └─────────────────┴────────────────────┴─────────────────┴───────────────┘               │
                                                                                                  │
                                                                                                  │
    Legend:                                                                                       │
      ───▶  Forward  (Enter — confirm current selection)                                         │
      ◄───  Backward (Esc — go back one step where allowed)                                      │
      ───┼── Cancel   (Ctrl-C — exit from any step)                                              │
      ────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Transition guard summary**:

| From | Action | Guard | Next state | Exit code | Message |
|------|--------|-------|------------|-----------|---------|
| Entry | Auto | Always | ModeSelection | — | Welcome or first-run panel |
| ModeSelection | Enter | Selection valid | Configuration | — | — |
| ModeSelection | Esc | Always | (exit) | 0 | "Setup cancelled." |
| Configuration | Enter | All validations pass | Confirm | — | — |
| Configuration | Esc | `allow_back` is `True` | ModeSelection | — | — |
| Confirm | Enter | Confirmation accepted | Processing | — | — |
| Confirm | Esc | `allow_back` is `True` | Configuration | — | — |
| Processing | Complete | All clauses processed | Results | 0 | Success summary |
| Processing | Ctrl-C | Always | (exit) | 1 | "Review cancelled. Partial results not saved." |
| Any step | Ctrl-C | Always | (exit) | 1 | "Cancelled." |

**Results state**: Terminal (end of flow). No further transitions. Success output displayed. Step indicator removed (§3.1). User can exit or invoke another command.
