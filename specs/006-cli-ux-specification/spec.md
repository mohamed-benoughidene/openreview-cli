# Feature Specification: CLI UX System Design

**Feature Branch**: `006-cli-ux-specification`

**Created**: 2026-06-28

**Status**: Draft

**Input**: UX specification for openreview-cli — design tokens, component library, interaction patterns, command structure, feedback design, performance perception, terminal compatibility, and configuration UX. Grounded in 10 fetched research sources.

## User Scenarios & Testing

### User Story 1 — First-time Legal Professional Runs openreview (Priority: P1)

A lawyer installs openreview-cli on their laptop and runs `openreview` for the first time. They have no config file, no prior knowledge of the tool, and are not a developer. The tool must present a guided, friendly onboarding experience that explains what it does and helps them set up in under 2 minutes.

**Why this priority**: First-run experience determines whether users trust the tool and continue using it. Legal professionals will abandon tools that look like "developer software." This is the gatekeeper for all other features.

**Independent Test**: Can be tested by a fresh install with no config file — verify the first-run flow completes without errors, exposes no raw stack traces, and produces a usable config.

**Acceptance Scenarios**:

1. **Given** the tool is installed with no config file, **When** the user runs `openreview`, **Then** a welcome message appears within 100ms explaining what openreview does in plain language, and offers to run the setup wizard or show help.
2. **Given** the first-run wizard starts, **When** the user presses Esc or Ctrl-C, **Then** the tool exits gracefully with a message like "Setup was interrupted. Run `openreview setup` to try again."
3. **Given** the user completes setup, **When** the wizard finishes, **Then** they see a success summary: config file location, configured AI provider, shell completion status, and a suggested next command with example.

---

### User Story 2 — Legal Professional Reviews a Contract Interactively (Priority: P1)

A lawyer has a 50-page PDF contract. They run the interactive review wizard, selecting a review mode, confirming options, and watching the analysis progress clause-by-clause with streaming output. They see results formatted clearly and can understand risk findings without technical jargon.

**Why this priority**: This is the core product workflow. Without usable review UX, the tool has no value.

**Independent Test**: Run a review of a test PDF through the wizard, verify each step displays properly, progress indicators appear, results are formatted as tables with clear risk ratings.

**Acceptance Scenarios**:

1. **Given** the user runs `openreview review contract.pdf`, **When** the wizard starts, **Then** they see "Step 1 of 4: Review Mode" with arrow-key-selectable options.
2. **Given** the user is at the confirmation step, **When** they press Enter to confirm, **Then** processing begins with a spinner labeled "Analyzing clause 1 of 47 — Definitions..."
3. **Given** processing is underway, **When** the user presses Ctrl-C, **Then** the tool prints "Review cancelled. Partial results were not saved." and exits with code 1.
4. **Given** processing completes, **When** results are shown, **Then** findings appear in a table with Risk Level, Clause, and Recommendation columns, and a summary panel at the bottom.

---

### User Story 3 — Legal Professional Uses Non-Interactive Mode (Priority: P2)

A legal ops professional wants to batch-process contracts in a shell script. They run `openreview review contract.pdf --mode standard --output json --yes` and get JSON output without any interactive prompts.

**Why this priority**: Automation use cases are critical for power users but secondary to the interactive experience that serves the primary user base.

**Independent Test**: Run the command in a `| jq` pipeline, verify no prompts appear, output is valid JSON, and exit code reflects success/failure.

**Acceptance Scenarios**:

1. **Given** the user runs with `--yes` flag, **When** all required inputs are provided, **Then** no interactive prompts appear and processing proceeds.
2. **Given** a required input is missing and stdin is not a TTY, **When** the user runs a command, **Then** the tool exits with code 2 and prints "Error: --mode is required when running non-interactively. See `openreview review --help`."
3. **Given** `--output json` is passed, **When** the review completes, **Then** results are printed as valid JSON to stdout and all messaging goes to stderr.

---

### User Story 4 — Legal Professional Configures Tool Settings (Priority: P2)

A lawyer needs to change their AI provider, add a jurisdiction profile, or update their config. They use `openreview config` commands rather than manually editing JSON files, and get inline validation of their inputs.

**Why this priority**: Configuration is fundamental to using the tool correctly. Legal professionals should never need to edit JSON by hand.

**Acceptance Scenarios**:

1. **Given** the user runs `openreview config set model standard llama3.2`, **When** the value is valid, **Then** a success message confirms the change with old and new values shown.
2. **Given** the user runs `openreview config set model standard invalid-model`, **When** the value is invalid, **Then** an error panel shows "Model 'invalid-model' is not recognized. Run `openreview config list-models` to see available models."
3. **Given** the config file is corrupted, **When** the user runs any command, **Then** a warning appears on startup: "Config file at ~/.config/openreview/config.json is invalid. Run `openreview setup` to fix it." The tool exits with code 3.

---

### User Story 5 — Legal Professional Seeks Help (Priority: P3)

A lawyer forgets the exact command or flag. They run `--help`, see examples, and get useful suggestions when they make a typo.

**Why this priority**: Help discoverability reduces support burden and user frustration.

**Acceptance Scenarios**:

1. **Given** the user runs `openreview --help`, **When** help displays, **Then** examples appear before the full flag listing, in plain English with real-looking contract scenarios.
2. **Given** the user types `openreview reviw contract.pdf`, **When** the command is misspelled, **Then** the tool prints "Unknown command 'reviw'. Did you mean 'review'?" and exits with code 2.
3. **Given** the user runs `openreview review --help`, **When** help for the review subcommand shows, **Then** required flags are clearly marked and flagged with a `[required]` label, not buried in a dense list.

---

### Edge Cases

- What happens when the terminal is narrower than 60 columns? Tables collapse to key-value pairs; panels truncate gracefully with width awareness [R-2][R-1].
- What happens when stdin is not a TTY (e.g., piped input)? All interactive prompts are disabled; commands that require missing input exit with error code 2 and a message [R-1].
- What happens when NO_COLOR is set? All output becomes monochrome; icons use ASCII fallbacks; spinners and progress bars still work but without color [R-1][R-2].
- What happens when the user's terminal doesn't support Unicode? All icons fall back to ASCII equivalents; table borders use ASCII characters [R-1][R-2].
- What happens when the config file contains an unknown key? A warning prints on startup but the tool continues; unknown keys are preserved on write [R-1].
- What happens when a 50-page contract has no detectable clauses? A warning panel displays "No standard clauses detected. The document may be a scanned image, unreadable PDF, or non-standard format."

## Requirements

### Fetch Log (R-1 to R-10)

**[R-1]** URL: https://clig.dev — Status: OK
- Human-first design: design for humans first, machines second
- Output to stdout, messaging/logging/errors to stderr
- Errors: catch and rewrite for humans ("what failed, why, how to fix")
- --json flag for structured output, --plain for grep-friendly tabular text
- NO_COLOR and TTY detection for disabling color/animations
- Confirm before destructive actions, --no-input flag to skip all prompts
- Help: examples before flag listing, suggest corrections for typos (e.g., "Did you mean...?")
- Use pager (less -FIRX) for long output
- Subcommand consistency: same flag names for same things across subcommands
- Robustness: handle unexpected input gracefully, idempotent where possible

**[R-2]** URL: https://pypi.org/project/rich/ v15.0.0 (Apr 12, 2026) — Status: OK
- Console: print(), log(), status() for spinner animation
- Table: column configuration, alignment, border styles, auto-width to terminal
- Progress: track() wrapper, Progress with columns (percentage, speed, time remaining)
- Panel: boxed content with border styles
- Layout: split terminal into regions
- Live: context manager for streaming/re-rendering output (token streaming)
- Markdown, Syntax highlighting, Tree, Columns
- Emoji support via :name: syntax

**[R-3]** URL: https://pypi.org/project/questionary/ v2.1.1 (Aug 28, 2025) — Status: OK
- Prompt types: text, password, file path, confirmation, select, rawselect, checkbox, autocomplete
- Built on prompt_toolkit for keyboard navigation
- Simple API: questionary.select(message, choices).ask()
- MVP status: well-maintained, MIT licensed, Python 3.9+

**[R-4]** URL: https://pypi.org/project/InquirerPy/ v0.3.4 (Jun 27, 2022) — Status: OK
- Key differentiator: fuzzy search prompt (fuzzy matching on long lists)
- VI/Emacs keybinding customization
- Based on prompt_toolkit like questionary
- **Note**: Last updated June 2022 (4 years old), Pre-alpha status. Use for fuzzy search reference pattern only; questionary is the preferred implementation library due to maintenance status.

**[R-5]** URL: https://pypi.org/project/typer/ v0.26.8 (Jun 26, 2026) — Status: OK
- Rich integration built-in for error formatting (Panels)
- Vendored Click since 0.26.0 — unified codebase
- Auto-completion for bash/zsh/fish/powershell via shellingham
- TYPER_USE_RICH env var to disable Rich globally
- Callback patterns for validation, context injection

**[R-6]** URL: https://github.com/cli/cli v2.95.0 — Status: OK
- Verb-noun command structure: `gh issue create`, `gh pr review`
- Interactive prompts with defaults, `?` for confirmation
- Structured output with tables (issue lists, PR status)
- GitHub CLI uses Go, but UX patterns transfer:
  - Grouped commands in help (start work, manage, review)
  - `--json` flag for scripting
  - Color semantics: green=open, red=closed, purple=merged

**[R-7]** URL: https://opencode.ai/docs/keybinds — Status: OK
- Arrow key navigation for file/agent selection
- Slash `/` for command palette
- Escape for session interrupt
- Keyboard shortcuts: n=new, s=status, c=compact, l=list sessions
- Enter to confirm, Esc to cancel pattern

**[R-8]** URL: https://github.com/charmbracelet/gum — Status: OK
- gum confirm: Yes/No dialog with styled borders, exits 0/1
- gum choose: arrow key selection, --limit for multi-select, --no-limit
- gum filter: fuzzy matching, tab/ctrl+space to select, enter to confirm
- gum spin: spinner with types (line, dot, minidot, pulse, globe, etc.), auto-stops after command
- gum style: colored/styled text with padding, borders, foreground/background
- **Key pattern**: composed tools, not a monolithic framework

**[R-9]** URL: web_search "CLI UX design professional terminal 2024 2025 best practices" — Status: OK
- **ls1intum/ui-ux-guidelines**: semantic color tokens (text.error over red-500), never hardcode values
- **Evil Martians**: green + checkmark for success, clear spinners/progress after completion, clean log output
- **Amanda Pinsker (GitHub CLI)**: space, bold, color, icons create hierarchy; design for CLI same as any visual design
- **Thoughtworks**: noun-verb command structure, prompt but never mandate, tables for data structure, error with code+title+description+resolution+URL

**[R-10]** URL: web_search "Python CLI error message design UX 2024" — Status: OK
- **clig.dev**: catch errors, rewrite for humans, 3-part structure (what/why/fix), most important at end
- **bettercli.org**: exit 0=success, non-zero=failure; binary 0/1 simplest when unsure
- **Click docs**: exit 0 for --help, exit 2 for input error (incorrect usage), exit 1 for abort
- **Thoughtworks**: error code + title + description + resolution steps

### Functional Requirements

#### Visual Design

- **FR-VD-001**: System MUST define and use a semantic color palette (primary, success, warning, error, muted, accent) mapped to Rich style strings per the Design Tokens section below. [R-9][R-2]
- **FR-VD-002**: System MUST use bold for emphasis (headings, key findings, action prompts), dim/muted for secondary information, and italic sparingly for notes. [R-1][R-9]
- **FR-VD-003**: System MUST provide vertical spacing between output blocks: 1 blank line between paragraphs, 2 blank lines between major sections, panel borders around error/success summaries. [R-9]
- **FR-VD-004**: System MUST use a consistent icon set with both Unicode and ASCII fallbacks. Unicode is default; ASCII used when `NO_COLOR` env var is set, `FORCE_COLOR=0`, `sys.platform == "win32"`, or `--no-unicode` flag is passed. Fallback mapping:

| Meaning   | Unicode (default) | ASCII fallback |
|-----------|-------------------|----------------|
| Success   | ✓ (U+2713)        | [OK]           |
| Error     | ✗ (U+2717)        | [FAIL]         |
| Warning   | ⚠ (U+26A0)        | [WARN]         |
| Arrow     | ▶ (U+25B6)        | >              |
| Bullet    | ● (U+25CF)        | *              |
| Separator | ━ (U+2501)        | -              |

[R-1][R-2]
- **FR-VD-005**: System MUST never expose raw Python tracebacks to users. Errors are caught and reformatted using the Error Panel component. [R-1][R-5]
- **FR-VD-006**: System MUST support information hierarchy: key findings and actions are visually prominent; secondary details are muted; warnings and errors use distinct colors. [R-9]

#### Interaction Patterns

- **FR-IP-001**: System MUST provide arrow-key navigable selection menus for single-select, multi-select (space to toggle), and nested menus. [R-3][R-7]
- **FR-IP-002**: System MUST provide fuzzy search on lists longer than 8 items (jurisdictions, clause types, output formats) using Python stdlib `difflib.get_close_matches(query, choices, n=5, cutoff=0.4)` mapped to questionary's `autocomplete` parameter. Fallback to exact substring match if no difflib match within cutoff. [R-4][R-8]
- **FR-IP-003**: System MUST show inline confirmation dialogs with the safe default clearly indicated (Yes/No, with No pre-selected for destructive actions). [R-1][R-8]
- **FR-IP-004**: System MUST support back-navigation in multi-step wizards (Esc or Backspace goes back one step where allowed). [R-7]
- **FR-IP-005**: System MUST handle Escape and Ctrl-C gracefully at every interactive prompt with clean "Cancelled by user." message, no stack traces. Does NOT apply during active processing — see FR-PP-004. [R-1][R-7]
- **FR-IP-006**: System MUST provide Tab completion for commands, subcommands, and flag names via shell completion installation (Typer built-in). [R-5]

#### Flow & Pacing

- **FR-FP-002**: System MUST show a step indicator in multi-step flows: "Step 2 of 4: Configuration" with correct numbering. [R-1]
- **FR-FP-003**: System MUST display an animated spinner during any operation taking longer than 500ms, with a descriptive label that updates during work. [R-2][R-8]
- **FR-FP-004**: System MUST use a determinate progress bar for operations with a known total (clause-by-clause review). [R-2]
- **FR-FP-005**: System MUST display partial LLM analysis results as they become available via token-by-token streaming from the AI Gateway (`src/openreview_cli/gateway/`). Applies to review result display (US2 Scenario 4), NOT to document parsing which is clause-by-clause batch processing. [R-2]
- **FR-FP-006**: System MUST clearly separate transitions between wizard steps with a visual divider or panel, not a continuous wall of text. [R-9]

#### Feedback System

- **FR-FB-001**: System MUST use a three-part error format: what failed (brief), why it happened (context), how to fix it (actionable suggestion). Displayed in a red-bordered panel. [R-1][R-10]
- **FR-FB-002**: System MUST use distinct exit codes: 0=success, 1=general error, 2=usage error (wrong flags/args), 3=config error, 4=input file error. [R-1][R-10]
- **FR-FB-003**: System MUST show success state clearly after each operation: a green checkmark with a one-line summary. Never silent on success. [R-1][R-9]
- **FR-FB-004**: System MUST distinguish warnings from errors visually (yellow vs red) and behaviorally (warnings don't halt; errors do). [R-1]
- **FR-FB-005**: System MUST support `--verbose` flag that adds detail (processing steps, config values used, timing) to stderr. All verbose output MUST be PII-redacted per constitution Principle I. [R-1]
- **FR-FB-006**: System MUST support `--quiet` flag suppressing all non-essential output (warnings, status chatter, success messages). Spinner and progress bar REMAIN visible — they are status indicators, not output. Combine `--quiet --no-spinner` (FR-TC-004a) to suppress all UI elements and produce exit-code-only results for CI/piped environments. [R-1]

#### Output Formatting

- **FR-OF-001**: System MUST display structured data (clause lists, risk findings, model lists) as Rich Tables, never as raw JSON or Python repr. [R-2]
- **FR-OF-002**: System MUST support `--output json` for machine-readable output to stdout, with all human messaging on stderr. [R-1][R-6]
- **FR-OF-003**: System MUST highlight file paths distinctly from plain text (e.g., bold or cyan). [R-1]
- **FR-OF-004**: System MUST display timestamps in human-readable format (e.g., "Jun 28, 2026 14:30"), not epoch seconds. [R-1]

#### Command Structure

- **FR-CS-001**: System MUST use verb-noun convention: `openreview review`, `openreview config`, `openreview setup`, not mixed styles. [R-6][R-9]
- **FR-CS-002**: System MUST use `--kebab-case` for all multi-word flags consistently. [R-1]
- **FR-CS-003**: System MUST mark required flags with `[required]` in help text and show an error when they are missing. [R-1]
- **FR-CS-004**: System MUST provide sensible defaults for all optional flags, documented in help text. [R-1]
- **FR-CS-005**: System MUST group subcommands in help output with descriptive headers (e.g., "Review Commands", "Configuration Commands"). [R-6]

#### Help System

- **FR-HS-001**: System MUST provide `--help` at every level: tool, subcommand, and flag group. [R-1]
- **FR-HS-002**: Help text MUST lead with real examples, not just usage strings. [R-1]
- **FR-HS-003**: Error messages MUST end with "Run `openreview <command> --help` for usage." when input is incorrect. [R-1][R-10]
- **FR-HS-004**: System MUST provide `--version` returning the semantic version from `src/openreview_cli/__init__.py`. [R-1]
- **FR-HS-005**: System MUST suggest corrections for typos: "Unknown command 'reviw'. Did you mean 'review'?" [R-1]

#### Configuration

- **FR-CF-001**: Config file MUST be stored at `$XDG_CONFIG_HOME/openreview/config.json` (default `~/.config/openreview/config.json`). [R-1]
- **FR-CF-002**: Users MUST be able to view and set config via `openreview config get <key>` and `openreview config set <key> <value>`. Unknown keys MUST be rejected with an error panel suggesting `openreview config show` to list valid keys. [R-1]
- **FR-CF-003**: Every config key MUST be overridable via `OPENREVIEW_<KEY>` environment variable. [R-1]
- **FR-CF-004**: Config MUST be validated on startup; corrupted or invalid config prints a warning and the tool exits with code 3. [R-1]

#### Terminal Compatibility

- **FR-TC-001**: System MUST respect the `NO_COLOR` environment variable and `--no-color` flag, disabling all ANSI color codes. [R-1]
- **FR-TC-002**: System MUST fall back to ASCII characters when Unicode is unavailable (detected via locale or `--no-unicode` flag). [R-1]
- **FR-TC-003**: System MUST detect terminal width and adapt rendering. Width ≥80: full Rich Table with borders. Width 60–79: Rich Table with `safe_box=False` (no borders), columns auto-minimized. Width <60: collapse to key-value pair list (Rich Panel with nested Text elements), one item per line, as specified in Edge Case #1. Never overflow or truncate mid-word. [R-2]
- **FR-TC-004**: System MUST detect when stdin is not a TTY and disable all interactive prompts, emitting clear errors for missing required inputs. [R-1]
- **FR-TC-004a**: System MUST support `--no-spinner` flag disabling all animated output (spinner, progress bar animation). Progress status is still available as static text updates. Useful for CI/pipe output. [R-1]
- **FR-TC-005**: System MUST provide a `--yes` flag that auto-confirms all prompts at their safe defaults, enabling non-interactive automation. [R-1]

#### Performance Perception

- **FR-PP-001**: System MUST display something within 100ms on every invocation (logo, welcome, error, or help). [R-1]
- **FR-PP-002**: System MUST never leave the terminal silent for more than 500ms during any operation without a spinner or status message. [R-1][R-8]
- **FR-PP-003**: System MUST label background work: "Analyzing clause 3 of 12 — Indemnification..." format. [R-2]
- **FR-PP-004**: System MUST handle Ctrl-C during active processing (document analysis, LLM calls) with clean message: "Review cancelled. Partial results were not saved." Exit code 1. Covers the gap between interactive prompts where FR-IP-005 does not apply. [R-1]

### Key Entities

- **Design Token**: A semantic color/style definition mapping a role (primary, success, error) to a Rich style string, with a no-color fallback.
- **Component**: A reusable UI element (spinner, table, panel, progress bar) with a defined API, keyboard handling, and TTY-degraded fallback.
- **Wizard Step**: A state in the multi-step review flow with a defined entry/exit condition, allowed navigation paths, and escape behavior.
- **UX Profile**: A named output configuration (interactive, quiet, json, plain) that controls color, symbols, spinners, and output format.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A first-time user with no prior openreview knowledge can complete setup and run their first review in under 5 minutes.
- **SC-002**: Every interactive prompt can be bypassed by a corresponding `--flag`, enabling full non-interactive/CI usage.
- **SC-003**: The tool renders its first output within 100ms on the reference hardware (8 GB RAM, 2-core CPU, no GPU).
- **SC-004**: Zero raw Python tracebacks are ever displayed to users; all errors use the three-part error panel format.
- **SC-005**: The tool functions correctly in a non-TTY environment (pipe/CI) with all prompts disabled and required inputs demanded as flags.
- **SC-006**: All user-facing text is understandable by a non-developer legal professional (Flesch-Kincaid grade level < 10).
- **SC-007**: The tool respects NO_COLOR and produces fully functional monochrome output without color-dependent semantics.

## Assumptions

- The existing Typer app structure (`src/openreview_cli/app.py`) remains the entry point and will be extended, not replaced.
- Rich v15.0.0 is already a transitive dependency (via Typer) and can be used directly.
- questionary v2.1.1 is the preferred interactive prompt library, mirroring the opencode selection pattern.
- The project's existing codebase conventions (constitution, privacy-first, local-only) remain binding.
- Legal professional users: all visible text must avoid developer jargon, raw file paths, and stack traces.
- The first product mode to ship will use this UX design; remaining modes follow the same patterns.
- Terminal width detection and Unicode fallback are standard Rich features and need only configuration, not custom logic.
- This spec covers the UX layer (design tokens, components, patterns, command structure). Implementation details for individual product mode logic (review, precheck, dealcheck, etc.) are out of scope.
- The existing 005-cli-wizard-redesign spec is a predecessor; this spec supersedes its interaction patterns but preserves its command structure and configuration logic.

---

# openreview-cli UX Specification

## 1. Design Tokens

### 1.1 Color Palette

Semantic colors mapped to Rich style strings [R-2][R-9]. Every role has a no-color fallback using bold/underline only.

| Role    | Rich Style                         | When to use                                                              |
|---------|------------------------------------|--------------------------------------------------------------------------|
| primary | `bold cyan`                        | Headings, key prompts, command names in help, file paths                  |
| success | `bold green`                       | ✓ checkmarks, completion summaries, "Review complete"                     |
| warning | `bold yellow`                      | ⚠ warnings, deprecation notices, non-blocking issues                     |
| error   | `bold red`                         | ✗ errors, fatal issues, validation failures                               |
| muted   | `dim`                              | Secondary info, hints, timestamps, "Press Enter to continue"              |
| accent  | `bold magenta`                     | Highlights, step indicators, mode names, special callouts                 |
| code    | `bold bright_black on grey15`      | Config keys, flag names, inline code references                           |

**No-color fallbacks**:
- `primary` → `bold`
- `success` → `bold`
- `warning` → `bold underline`
- `error` → `bold underline`
- `muted` → `dim`
- `accent` → `bold`
- `code` → `` (no style, plain text)

Color detection: Rich auto-detects terminal capability. Additionally, disable all color when `NO_COLOR` is set or `--no-color` is passed. [R-1][R-2]

### 1.2 Icon System

Two versions for every state: Unicode (default) and ASCII (fallback when `--no-unicode` or terminal lacks Unicode support). [R-1][R-9]

| State       | Unicode | ASCII   | When to use                                          |
|-------------|---------|---------|------------------------------------------------------|
| success     | ✓       | [OK]    | After completed operations, config saves              |
| error       | ✗       | [ERR]   | Errors, failures, validation rejections               |
| warning     | ⚠       | [!]     | Warnings, non-blocking issues, deprecation notices    |
| info        | ℹ       | [i]     | Informational notes, hints                            |
| pending     | ○       | [ ]     | Items not yet processed in a list, inactive steps     |
| running     | ◷       | [...]   | In-progress operations (paired with spinner)          |
| step marker | →       | ->      | Current step indicator, "next action" pointers        |
| file path   | 📄      | [file]  | File path prefix                                      |
| lock/secure | 🔒      | [**]    | Privacy/security indicator (all processing local)     |

**Ponytail note**: `running` uses the Rich spinner character (auto-animated); the static Unicode character `◷` is only for documentation/tables. Rich handles spinner animation internally — use `rich.console.Console.status()` [R-2] or the Spinner component.

### 1.3 Spacing Rules

[Based on clig.dev readability guidelines [R-1] and Git CLI patterns [R-6]]

- **Between paragraphs/items**: 1 blank line
- **Between major sections**: 2 blank lines
- **After a panel (error/success)**: 1 blank line before next content
- **Before a table**: 1 blank line above and below
- **Step transitions**: A thin horizontal rule (`─` x terminal width) with 1 blank line on each side
- **Panel borders**: Rich Panel with `padding=(1, 2)` — 1 row top/bottom, 2 columns left/right [R-2]
- **Do not** add blank lines between every log line — group related output together [R-1]

### 1.4 Typography Rules

[Based on clig.dev [R-1] and GitHub CLI design patterns [R-9]]

- **Bold**: headings, key findings, command names, action prompts, current selection in lists
- **Dim**: secondary info, hints, timestamps, "Press Enter to continue", footer text, role descriptions
- **Italic**: sparingly — only for emphasis within a sentence, never for UI elements
- **Never style**: raw file paths in user data output, contract text excerpts (preserve exact formatting), config values that are file paths
- **No underline** for non-link text (reserve for hyperlinks or no-color fallback)

## 2. Component Library

Each component is a self-contained Python unit reusing Rich v15.0.0 [R-2] and questionary v2.1.1 [R-3].

### 2.1 Selection Menu (single-select) [R-3][R-7]

Arrow-key navigation. Enter to confirm, Esc to cancel.

```python
import questionary

choice = questionary.select(
    message="Select review mode:",
    choices=[
        questionary.Choice(title="Standard Review — Clause-by-clause analysis", value="standard"),
        questionary.Choice(title="Risk-Focused — Identify high-risk clauses only", value="risk"),
        questionary.Choice(title="Compliance Check — Check against policy playbook", value="compliance"),
    ],
    qmark="→",       # step marker [R-1]
    pointer="▶",     # selection indicator
    use_shortcuts=True,
    use_arrow_keys=True,
    use_jk_keys=False,  # vi keys disabled; our users aren't devs
).ask()
```

**When to use**: Any prompt with 2-15 discrete options.
**When NOT to use**: Lists longer than 15 items (use fuzzy search, §2.3). Binary yes/no (use confirmation §2.4).

### 2.2 Multi-select [R-3][R-8]

Space to toggle, Enter to confirm. Selected items prefixed with `✓`.

```python
result = questionary.checkbox(
    message="Select clause types to analyze:",
    choices=[
        questionary.Choice(title="Indemnification"),       # value defaults to title
        questionary.Choice(title="Limitation of Liability"),
        questionary.Choice(title="Termination"),
        questionary.Choice(title="Confidentiality"),
        questionary.Choice(title="Payment Terms", checked=True),
    ],
    validate=lambda answer: len(answer) > 0 or "Select at least one clause type.",
).ask()
```

**When to use**: Selecting multiple items from a list (clause types, jurisdictions, output sections).

### 2.3 Fuzzy Search Select [R-4][R-8]

For long lists (>8 items): jurisdictions, clause types, output formats. Type to filter, arrow keys to navigate, Enter to select.

```python
# questionary's autocomplete provides type-ahead filtering,
# not true fuzzy matching. For fuzzy, use custom completion:
import questionary

def fuzzy_completer(text, choices):
    """Return choices containing `text` anywhere (case-insensitive)."""
    lower = text.lower()
    return [c for c in choices if lower in c.lower()]

jurisdiction = questionary.autocomplete(
    message="Select jurisdiction:",
    choices=[
        "United States — Federal",
        "United States — California",
        "United States — Delaware",
        "United States — New York",
        # ... 50+ entries
    ],
    validate=lambda text: text in choices or "Select a jurisdiction from the list.",
).ask()
```

**When to use**: Any list with more than 8 items where filtering by typing is faster than arrow-key scrolling.
**When NOT to use**: Lists with <8 items (use selection menu §2.1). Binary or <4 options (use confirmation or select).

**Ponytail note**: questionary's `autocomplete` handles substring matching out of the box. If true fuzzy matching (typo-tolerant) is needed, InquirerPy v0.3.4 offers `fuzzy` [R-4] but requires adding a new dependency last updated in 2022. Add only when substring matching proves insufficient.

### 2.4 Confirmation Dialog [R-3][R-8]

Yes/No with safe default clearly visible. Keyboard shortcut shown.

```python
confirmed = questionary.confirm(
    message="Start review with these settings?",
    default=False,  # safe default: don't proceed without explicit yes
    auto_enter=False,  # require explicit input
).ask()
# Displays: "Start review with these settings? (y/N)"
```

**Default rules** [R-1]:
- **Non-destructive** (start review, save config): default=`True` → `(Y/n)`
- **Destructive/mutating** (delete, overwrite, proceed with paid API): default=`False` → `(y/N)`
- `--yes` flag auto-answers with the safe default

### 2.5 Text Input with Validation [R-3]

Inline validation feedback, not post-submit.

```python
def validate_provider(value: str) -> str | bool:
    if not value.strip():
        return "Provider name cannot be empty."
    from src.openreview_cli.gateway.engine import resolve_provider
    if not resolve_provider(value):
        return f"Provider '{value}' not found. Run 'openreview list-providers' for options."
    return True

provider = questionary.text(
    message="AI provider name:",
    validate=validate_provider,
    qmark="→",
).ask()
```

**When to use**: Any free-text input that needs validation (provider names, file paths, API keys).
**When NOT to use**: Input from a fixed list (use selection). Binary choice (use confirmation).

### 2.6 Spinner [R-2]

Animated spinner with updatable label for indeterminate-duration operations.

```python
from rich.console import Console
from rich.status import Status

console = Console()
with console.status("[bold]Loading configuration...", spinner="dots") as status:
    # long operation
    result = expensive_call()
    status.update("[bold]Almost done...")

console.print("[bold green]✓[/bold green] Configuration loaded.")
```

**Available spinners** (from Rich): `dots`, `dots2`, `dots3`, `dots4`, `dots5`, `dots6`, `dots7`, `dots8`, `dots9`, `dots10`, `dots11`, `dots12`, `dots8Bit`, `dots9Bit`, `dots10Bit`, `dots11Bit`, `dots12Bit`, `sand`, `material`, `weather`, `line`, `line2`, `pipe`, `simpleDots`, `simpleDotsScrolling`, `star`, `star2`, `flip`, `hamburger`, `growVertical`, `growHorizontal`, `balloon`, `balloon2`, `noise`, `bounce`, `boxBounce`, `boxBounce2`, `triangle`, `arc`, `circle`, `squareCorners`, `circleQuarters`, `circleHalves`, `squish`, `toggle`, `toggle2`, `toggle3`, `toggle4`, `toggle5`, `toggle6`, `toggle7`, `toggle8`, `toggle9`, `toggle10`, `toggle11`, `toggle12`, `toggle13`, `arrow`, `arrow2`, `arrow3`, `bouncingBar`, `bouncingBall`, `smiley`, `monkey`, `hearts`, `clock`, `earth`, `material`, `moon`, `runner`, `pong`, `shark`, `dqpb`, `weather`, `christmas`, `grenade`, `point`, `layer`, `betaWave` [R-2]

**Recommended default**: `dots` (unobtrusive, familiar).

### 2.7 Progress Bar (Determinate) [R-2]

For clause-by-clause review with known total.

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    TimeRemainingColumn(),
    console=console,
) as progress:
    task = progress.add_task("[bold]Analyzing clauses...", total=len(clauses))
    for clause in clauses:
        analyze(clause)
        progress.update(task, advance=1, description=f"[bold]Clause {clause.number} — {clause.title}...")
```

**When to use**: Any operation with a known, countable total (clauses, documents, questions).
**When NOT to use**: Unknown-duration operations (use spinner §2.6). Operations < 500ms (no indicator needed).

### 2.8 Live Panel [R-2]

Streaming AI output — show tokens as they arrive.

```python
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown

buffer = []
with Live(Panel("", title="AI Analysis"), refresh_per_second=10, console=console) as live:
    for token in stream_ai_response():
        buffer.append(token)
        live.update(Panel(Markdown("".join(buffer)), title="AI Analysis"))
```

**When to use**: Any streaming AI response where showing partial output improves perceived performance.
**When NOT to use**: Batch results that arrive all at once (use table §2.9). Non-AI operations.

### 2.9 Result Table [R-2]

Contract clause findings with risk ratings.

```python
from rich.table import Table

table = Table(title="Review Results — MSA Contract", header_style="bold cyan")
table.add_column("Risk", style="bold", width=8)
table.add_column("Clause", style="dim", width=18)
table.add_column("Finding", width=50)
table.add_column("Recommendation", style="green", width=50)

table.add_row("[bold red]HIGH[/bold red]", "Indemnification 4.2",
              "Unlimited indemnity obligation with no liability cap",
              "Negotiate a liability cap; standard is 12 months' fees")
table.add_row("[bold yellow]MEDIUM[/bold yellow]", "Termination 8.1",
              "Termination for convenience with 15-day notice",
              "Request 30-day notice period minimum")
table.add_row("[bold green]LOW[/bold green]", "Governing Law 12.0",
              "Standard choice of law — Delaware",
              "No action needed")

console.print(table)
```

**When to use**: Any tabular output: clause findings, model lists, config values, provider lists.

### 2.10 Error Panel [R-1][R-5][R-10]

Three-part structure: what failed / why / how to fix. Boxed, red border.

```python
from rich.panel import Panel

def show_error(what: str, why: str, fix: str, exit_code: int = 1) -> None:
    panel = Panel.fit(
        f"[bold]What failed:[/bold] {what}\n\n"
        f"[dim]Why:[/dim] {why}\n\n"
        f"[bold cyan]How to fix:[/bold cyan] {fix}",
        title="[bold red]✗ Error[/bold red]",
        border_style="red",
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()

# Usage:
show_error(
    what="Cannot open file 'contract.pdf'.",
    why="The file was not found at /home/user/contracts/contract.pdf.",
    fix="Check the file path and try again:\n  openreview review /home/user/contracts/contract.pdf\n"
        "Run `openreview review --help` for usage.",
    exit_code=4,
)
```

**When to use**: Every error condition, replacing all raw exceptions/tracebacks.

### 2.11 Step Indicator [R-1][R-7]

Shown at the top of each wizard step.

```python
def show_step(current: int, total: int, title: str) -> None:
    """Display step indicator before each wizard step."""
    steps = []
    for i in range(1, total + 1):
        if i < current:
            steps.append("[bold green]✓[/bold green]")
        elif i == current:
            steps.append(f"[bold cyan]▶[/bold cyan]")
        else:
            steps.append("[dim]○[/dim]")
    progress = " ".join(steps)
    console.print(f"\n{progress}  [bold]Step {current} of {total}:[/bold] [cyan]{title}[/cyan]\n")

# Usage: show_step(2, 4, "Configuration")
# Output: ✓ ▶ ○ ○  Step 2 of 4: Configuration
```

## 3. Interaction Patterns

### 3.1 Multi-step Wizard Flow

State machine for the review wizard [R-1][R-7]:

```
Entry → Mode Selection → Configuration → Confirm → Processing → Results
```

**Navigation rules**:
- **Forward**: Enter (confirm current selection and advance)
- **Backward**: Esc (go back one step; disabled on Step 1 and during Processing)
- **Cancel**: Ctrl-C (exit immediately from any step with clean message)
- **Skip back**: Esc on Step 1 exits the wizard entirely

**Step details**:

| Step | Name          | Component Used      | Allow Back? | Esc Behavior                           |
|------|---------------|---------------------|-------------|----------------------------------------|
| 1/4  | Mode Selection| Selection Menu (§2.1)| No          | "Setup cancelled." → exit code 0       |
| 2/4  | Configuration | Multi-select (§2.2) + Text Input (§2.5) | Yes | Go back to Step 1                  |
| 3/4  | Confirm       | Confirmation (§2.4) | Yes         | Go back to Step 2                      |
| 4/4  | Processing    | Progress Bar (§2.7) + Live Panel (§2.8) | No | "Review cancelled. Partial results not saved." → exit 1 |
| —    | Results       | Result Table (§2.9) | No (end)    | N/A (end of flow)                      |

**Progress indicator**: Step indicator (§2.11) displayed at the top of Steps 1–4. Removed during Results.

### 3.2 Keyboard Shortcut Map

[R-3][R-7][R-8]

| Key       | Action                          | Component                        |
|-----------|---------------------------------|----------------------------------|
| ↑ / ↓     | Move selection up/down           | Selection Menu (§2.1), Multi-select (§2.2) |
| → / ←     | Navigate between option groups   | Confirmation (§2.4)              |
| Enter     | Confirm current selection        | All interactive components       |
| Space     | Toggle item in multi-select      | Multi-select (§2.2)              |
| Esc       | Go back / cancel current step    | All interactive components       |
| Ctrl-C    | Exit immediately (any step)      | Global                           |
| /         | Jump to filter/search input      | Fuzzy Search (§2.3)              |
| Tab       | Cycle forward, auto-complete     | Autocomplete (§2.3), shell completion (§FR-IP-006) |
| Shift+Tab | Cycle backward                   | Fuzzy Search (§2.3)              |
| Home/End  | Jump to first/last option        | Selection Menu (§2.1), Multi-select (§2.2) |

### 3.3 CI / Non-interactive Mode

[Based on clig.dev interactivity section [R-1]]

**Detection**: `sys.stdin.isatty()` returns `False` when piped or run in CI. [R-1]

**Behavior per component when non-TTY**:

| Component            | Non-TTY Behavior                                                |
|----------------------|-----------------------------------------------------------------|
| Selection Menu       | Error: "--mode is required. See --help." → exit 2              |
| Multi-select         | Error: "--clauses is required. See --help." → exit 2           |
| Fuzzy Search         | Error: "--jurisdiction is required. See --help." → exit 2      |
| Confirmation         | Accepts --yes flag; without it, error: "--yes is required for non-interactive use." → exit 2 |
| Text Input           | Error: "--provider is required. See --help." → exit 2         |
| Spinner              | Suppressed (no TTY animation). Prints label once.              |
| Progress Bar         | Suppressed. Prints "[# / total] description" periodically.     |
| Live Panel           | Disabled. Prints full output at end.                           |
| Error Panel          | Printed without Rich borders (plain text format).              |
| Step Indicator       | Printed as plain text: "[1/4] Mode Selection"                  |

**Safe defaults**: When `--yes` is passed, all confirmations auto-accept with their safe defaults (`False` for destructive, `True` otherwise). [R-1]

## 4. Command Structure

### 4.1 Command Hierarchy

Verb-noun convention matching GitHub CLI (`gh`) patterns [R-6] and Thoughtworks guidelines [R-9].

```
openreview
├── setup                              Run first-time setup wizard
│   --no-interactive                   Skip all prompts (use config from flags)
│
├── review <file>                      Review a contract (interactive wizard)
│   --mode <standard|risk|compliance>  Review mode [required in non-TTY]
│   --output <json|table|plain>        Output format (default: table)
│   --clauses <list>                   Clause types to analyze (default: all)
│   --jurisdiction <name>              Governing law jurisdiction
│   --yes                              Auto-confirm all prompts with safe defaults
│   --no-pii                           Skip PII stripping (debug only)
│
├── config                             Manage configuration
│   ├── config show                    Display current configuration
│   │   --output <json|table>           Format (default: table)
│   ├── config get <key>               Get a specific config value
│   ├── config set <key> <value>       Set a config value
│   ├── config unset <key>             Reset a config value to default
│   └── config path                    Print config file path
│
├── list                               List available resources
│   ├── list providers                 Show configured AI providers
│   ├── list models                    Show available models per provider
│   └── list jurisdictions             Show known jurisdictions
│
└── version                            Print version and exit
```

**Global flags** (available on every subcommand):
| Flag            | Type    | Default  | Description                                      |
|-----------------|---------|----------|--------------------------------------------------|
| `--verbose`     | flag    | false    | Show detailed processing steps to stderr          |
| `--quiet`       | flag    | false    | Suppress all non-error output                     |
| `--no-color`    | flag    | false    | Disable all ANSI color codes                      |
| `--no-unicode`  | flag    | false    | Use ASCII fallback icons                          |
| `--output`      | choice  | table    | Output format: json, table, plain                 |
| `--config`      | path    | XDG path | Path to config file                               |

### 4.2 Flag Naming Convention [R-1]

- **Format**: `--kebab-case` for all multi-word flags. No `--snake_case`, no `--camelCase`.
- **Correct**: `--no-color`, `--output-format`, `--clause-types`
- **Incorrect**: `--no_color`, `--outputFormat`, `--clause_types`
- **Boolean flags**: Negated with `--no-` prefix (Typer auto-generates). E.g., `--pii` / `--no-pii`.
- **Short flags**: Reserved for the most common flags only [R-1]: `-h` / `--help`, `-v` / `--version`, `-q` / `--quiet`, `-y` / `--yes`, `-o` / `--output`.

### 4.3 Global Flags

All subcommands accept `--verbose`, `--quiet`, `--no-color`, `--no-unicode`, `--output`, `--config`. These are defined at the root Typer app. [R-5]

### 4.4 --output Flag [R-1][R-6]

| Value   | Produces                                        | When to use                                  |
|---------|-------------------------------------------------|----------------------------------------------|
| `table` | Rich-formatted table with borders and styling    | Default — interactive terminal use            |
| `json`  | Valid JSON to stdout, all messaging to stderr    | Scripting, piping to `jq`, CI pipelines       |
| `plain` | Fixed-width columns, no borders, no color — aligned text for grep/awk filtering | `grep`/`awk` filtering, log files             |

## 5. Feedback Design

### 5.1 Error Message Format [R-1][R-10]

Three-part structure. Every error message uses this format, including validation failures, missing files, config errors, and API errors.

**Format**:
1. **What failed** — one sentence, bold
2. **Why** — brief context, dim/muted
3. **How to fix** — actionable steps, cyan

See Error Panel component (§2.10) for the implementation.

```python
# Text fallback (non-TTY, --plain, --no-color):
def show_error_text(what: str, why: str, fix: str) -> None:
    import sys
    print(f"\nError: {what}", file=sys.stderr)
    print(f"  {why}", file=sys.stderr)
    print(f"  {fix}", file=sys.stderr)
    print(file=sys.stderr)
```

### 5.2 Exit Code Map [R-1][R-10]

| Code | Meaning          | When                                               |
|------|------------------|----------------------------------------------------|
| 0    | Success          | Operation completed successfully                    |
| 1    | General error    | Unhandled error, Ctrl-C cancellation, API failure  |
| 2    | Usage error      | Wrong flags, missing required args, unknown command |
| 3    | Config error     | Invalid/missing config, corrupted config file      |
| 4    | Input file error | File not found, unreadable, wrong format, encrypted without password |
| 5    | Network error    | API unreachable, timeout (only for PII-stripped external calls) |

### 5.3 Success Message Format [R-1][R-9]

After every successful operation, display a concise, positive message. Never leave success silent.

```
✓ Review complete. 12 clauses analyzed, 3 findings. [2m 34s]

  View the full report:
    openreview review contract.pdf

```

**What NOT to show**: raw JSON dumps, Python repr, debug logs, raw file paths without context, technical identifiers.

### 5.4 Warning vs Error [R-1]

**Decision rule**:

| Condition                           | Action                                     |
|--------------------------------------|---------------------------------------------|
| Operation can continue safely         | **Warning** — yellow, non-blocking           |
| Operation cannot proceed              | **Error** — red, halt with exit code         |
| User input is recoverable             | **Warning** — suggest correction, re-prompt  |
| User input is structurally invalid    | **Error** — explain, link to help            |
| Config key is unknown                 | **Warning** — print, continue (preserve key) |
| Config file is corrupted              | **Error** — exit code 3                      |
| Optional feature fails (e.g., model registry refresh) | **Warning** — degraded but functional |
| Required feature fails (e.g., PII engine) | **Error** — exit code 1                 |

## 6. Performance Perception

### 6.1 Time-to-First-Output Target [R-1]

Within 100ms of invocation, one of these must appear:
- The help text (`--help`)
- The version string (`--version`)
- The welcome/setup message (first run)
- An error message (invalid command, missing args)
- The first wizard step (review command with TTY)

**Implementation**: Defer all heavy imports (parsers, Presidio, Ollama clients) behind the Typer command callback. The app module should import only `typer` and `openreview_cli`-level imports. Lazy imports for document parsing and AI gateway modules.

### 6.2 Streaming Strategy [R-2]

Use `rich.live.Live` to stream AI analysis output:

1. Display a `Live` panel with "Generating analysis..." spinner
2. As tokens arrive from the AI provider, append to buffer and re-render
3. On completion, replace spinner with `✓` and final formatted output
4. If token rate drops below 1 token/2s, update spinner label to "Waiting for response..."

### 6.3 Background Task Labeling [R-2][R-1]

Spinner and progress labels use plain English with specific progress:

```
"Loading document..."
"Stripping personal information..."
"Analyzing clause 3 of 12 — Indemnification (Section 4.2)"
"Generating compliance recommendations..."
```

Maximum label length: 60 characters (fits in 80-char terminal with spinner and progress).

### 6.4 Cancellation [R-1][R-7]

**Ctrl-C during any step**:
1. KeyboardInterrupt caught at the app root
2. Print: `\n✗ Cancelled.` (or `\nCancelled.` in no-unicode mode)
3. Cleanup: close any open file handles, remove temp files
4. Exit code 1
5. NEVER print a traceback for Ctrl-C

**Ctrl-C during Processing specifically**:
1. Additional context: no partial results are saved
2. Print: `✗ Review cancelled. Partial results were not saved.`

## 7. Terminal Compatibility

### 7.1 Capability Detection [R-2][R-1]

Rich handles most detection internally. Explicit checks needed:

| Capability       | Detection Method                           | Rich Setting                         |
|------------------|--------------------------------------------|--------------------------------------|
| Color support    | `NO_COLOR` env, `--no-color` flag, Rich auto-detect | `Console(color_system=...)`        |
| Unicode support  | `--no-unicode` flag, locale check           | Icon fallback map in config          |
| Terminal width   | `shutil.get_terminal_size().columns`        | Rich auto-detects; override via `Console(width=...)` |
| TTY vs pipe      | `sys.stdin.isatty()`, `sys.stdout.isatty()` | Component degradation (see §3.3)     |

### 7.2 NO_COLOR Compliance [R-1]

When `NO_COLOR` env var is set (non-empty) or `--no-color` is passed:

- All Rich `style` strings are stripped (Rich auto-handles via `Console(color_system=None)`)
- Unicode icons remain unless `--no-unicode` is also set
- Spinners still animate (monochrome)
- Error/success panels use ASCII borders only (no red/green)
- All color-dependent semantics are communicated through text: "Error:" prefix instead of red color

```python
import os
if os.environ.get("NO_COLOR", "") or no_color_flag:
    console = Console(color_system=None)
```

### 7.3 Width Handling [R-2]

Rich Tables auto-adjust column widths to fit terminal. Minimum supported width: 60 columns.

**Below 80 columns**:
- Tables reduce column widths proportionally, wrapping text within cells
- Panel content wraps to fit
- Step indicator uses compact format: `[2/4]` instead of `Step 2 of 4`

**Below 60 columns**:
- Tabular output switches to key-value paired lines (each row becomes a multi-line block)
- Result table → each finding is a separate panel with inline risk label

**Below 40 columns**: Warn "Terminal too narrow for optimal display. Increase width for best experience." but continue.

## 8. Configuration UX

### 8.1 Config File Location [R-1]

Primary: `$XDG_CONFIG_HOME/openreview/config.json` (typically `~/.config/openreview/config.json`)

Fallback (XDG not set): `~/.config/openreview/config.json`

Security: Created with mode `600` (owner read/write only) if `auth.json` keys are embedded. [Constitution Principle I]

### 8.2 Config Command

```
openreview config get <key>         # Display a config value
openreview config set <key> <value> # Set a config value
openreview config unset <key>       # Reset to default
openreview config show              # Display all config (table or json)
openreview config path              # Print config file path
```

**Config keys** (existing from Foundation Phase 1):

| Key                              | Description                           | Default                    |
|----------------------------------|---------------------------------------|----------------------------|
| `model.default`                  | Default chat model                    | `"llama3.2"`               |
| `model.standard`                 | Standard review model                 | `"llama3.2"`               |
| `model.embedding`                | Embedding model                       | `"nomic-embed-text"`       |
| `model.reranking`                | Reranking model                       | `""`                        |
| `provider.default`               | Default provider                      | `"ollama"`                  |
| `provider.<name>.base_url`       | Provider base URL                     | `"http://localhost:11434/v1"`|
| `pii.threshold`                  | PII confidence threshold (0.0–1.0)   | `0.3`                       |
| `privacy_tier`                   | maximum / balanced / performance      | `"maximum"`                 |

### 8.3 Env Var Overrides [R-1]

Every config key is overridable via environment variable:

```
OPENREVIEW_MODEL_DEFAULT=llama3.3 openreview review contract.pdf
```

Format: `OPENREVIEW_<SECTION>_<KEY>` (uppercase, dots replaced with underscores).

**Full mapping**:
| Config key                  | Env var                                |
|-----------------------------|----------------------------------------|
| `model.default`             | `OPENREVIEW_MODEL_DEFAULT`             |
| `model.standard`            | `OPENREVIEW_MODEL_STANDARD`            |
| `model.embedding`           | `OPENREVIEW_MODEL_EMBEDDING`           |
| `model.reranking`           | `OPENREVIEW_MODEL_RERANKING`           |
| `provider.default`          | `OPENREVIEW_PROVIDER_DEFAULT`          |
| `provider.ollama.base_url`  | `OPENREVIEW_PROVIDER_OLLAMA_BASE_URL`  |
| `pii.threshold`             | `OPENREVIEW_PII_THRESHOLD`             |
| `privacy_tier`              | `OPENREVIEW_PRIVACY_TIER`              |

### 8.4 First-run Detection [R-1]

**On first invocation** (no config file found):

1. Immediate output (within 100ms): a welcome panel
2. The panel explains what openreview does in 3-4 plain-English sentences
3. A privacy notice: "openreview processes documents entirely on your machine. No contract text ever leaves your computer."
4. Auto-enter the setup wizard immediately after the welcome message. The wizard guides through: provider selection, model preference, jurisdiction default, and shell completion installation.
5. Esc exits the wizard at any step. Print: "Setup was interrupted. Run `openreview setup` to try again later."

If the user declines setup (Esc):
- Print: "You can set up later with `openreview setup`. For now, use `openreview --help` to explore available commands."
- Config file is NOT created (incomplete setup).

## 9. Implementation Order

Ranked by impact/effort. Each tier can ship independently.

### Tier 1 — Foundation (largest impact, enables all other tiers)

1. **Rich Console singleton**: Initialize a project-wide `Console` that respects NO_COLOR, width detection, Unicode detection. Wire into `app.py`. [R-2]
2. **Error Panel component**: Replace all `raise`/`sys.exit` calls with the three-part error panel. Wire into Typer's error callback. [R-5] [§2.10]
3. **Exit code constants**: Define module-level constants. Wire new exit codes into all error paths. [§5.2]
4. **Design token constants**: Define Python constants for all styles, icons, symbol maps. [§1]

### Tier 2 — Core Interaction (what users feel)

5. **Step Indicator component**: Wire into the review wizard. [§2.11]
6. **Spinner + Progress Bar**: Replace all bare `sleep`/wait paths with Rich status/progress. [§2.6][§2.7]
7. **Result Table**: Replace raw text output with Rich Tables for all list displays. [§2.9]
8. **Success/warning message format**: Standardize all completion messages. [§5.3][§5.4]

### Tier 3 — Interactive Prompts

9. **Selection Menu**: Replace existing text prompts with questionary select. [§2.1]
10. **Confirmation Dialog**: Wire into all destructive/mutating actions. [§2.4]
11. **Fuzzy Search**: Wire for jurisdiction and model selection. [§2.3]
12. **Multi-select**: Wire for clause type selection. [§2.2]

### Tier 4 — Polish

13. **Live panel streaming**: Wire for AI analysis output. [§2.8]
14. **NO_COLOR + TTY degradation**: Complete fallback coverage for all components. [§7]
15. **First-run experience**: Welcome panel + guided setup. [§8.4]
16. **Config command UX**: Formatted output for `config show/get/set`. [§8.2]
17. **Help text redesign**: Examples-first, plain English, grouped commands. [FR-HS]

## 10. Open Questions

1. **UNVERIFIED**: InquirerPy v0.3.4 fuzzy search — last updated June 2022 (marked Pre-Alpha). The questionary autocomplete provides substring matching but not true fuzzy (typo-tolerant) matching. If typo tolerance is needed, evaluate InquirerPy's maintenance status at implementation time or implement a lightweight fuzzy matcher as a questionary completer callback. Source: [R-4].

2. **UNVERIFIED**: The exact appearance of `opencode`'s selection menu (arrow key animation, highlight color, scroll behavior) — documented keybindings confirmed [R-7], but the visual rendering style was not fully replicated. Recommendation: use questionary defaults mirroring the proven prompt_toolkit look, which closely matches opencode's selection UX.

3. **UNVERIFIED**: `openreview config set` inline validation for model names — the exact validation API (checking against provider registry vs embedded list) depends on how the AI gateway registry is structured. Design the validation callback interface as a protocol so it can be swapped when the registry is finalized. Source: this is a project-internal dependency, not an external library.

4. **UNVERIFIED**: Man-page generation tool recommended by clig.dev (ronn) — not evaluated because this project's constitution (Principle IV) restricts adding runtime deps. Man pages are a nice-to-have per clig.dev; hold until user demand validates the need. Without man pages, `openreview help` and web docs cover the discoverability gap.

## Assumptions Addendum

- The existing codebase already has an `errors.py` module with exit code constants. This spec extends that module rather than replacing it.
- questionary v2.1.1 is not currently in `pyproject.toml`. It must be added (`uv add questionary`) when the interactive prompt components are implemented.
- The Rich dependency is already satisfied transitively via Typer v0.26.8.
- The project's constitution constraints (no new deps without feature need, <100 MB memory budget, privacy-first) remain binding and are not violated by this UX layer.
- All UI text shown to users must be reviewed for Flesch-Kincaid grade level < 10 (legal professionals are the audience, not developers).

## Clarifications

### Session 2026-06-28

- Q: What does `--verbose` output, and where does it go? → A: Verbose output goes to stderr with PII redaction applied. Constitution Principle I requires redaction in all logs. Stderr keeps stdout clean for `--output json` piping.
- Q: What happens when `config set` encounters an unknown key? → A: Reject unknown keys with an error panel suggesting `config show`. Prevents silent misconfiguration.
- Q: First-run: auto-enter wizard or manual `openreview setup`? → A: Auto-enter the setup wizard after the welcome message, with Esc to exit. Reduces friction for non-developer users.
- Q: Should the setup wizard install shell completion? → A: Yes, auto-install during setup. One-time operation, zero user effort, ~2 seconds.
- Q: What does `--output plain` format look like? → A: Fixed-width columns, no borders, no color. Predictable alignment for grep/awk usage.
