# Tasks: CLI UX System Design

**Input**: Design documents from `/specs/006-cli-ux-specification/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-ux-contract.md

**Tests**: REQUIRED — TDD workflow mandated by AGENTS.md and constitution Principle V.
Tests are written FIRST and must FAIL before implementation begins.

---

## Phase 1: Setup (Shared Infrastructure)

*No story label. Pre-requisite for all other phases. Install deps, create package skeletons, define shared types.*

- [X] T001 [P] Install questionary v2.1.1 with `uv add questionary` and `uv lock`
- [X] T002 [P] Create ui/ package directory structure: `src/openreview_cli/ui/__init__.py`, `src/openreview_cli/ui/components/__init__.py`
- [X] T003 [P] Create `src/openreview_cli/types.py` — define `OutputFormat` (table, json, plain), `WizardStep` (Literal for step names), `ColorRole` NamedTuple. Move `OutputFormat` from `src/openreview_cli/cli/review.py` into types.py and update all imports.
- [X] T003a [P] Migrate `OutputFormat` enum from `src/openreview_cli/cli/review.py` to `src/openreview_cli/types.py`. Update all imports in `cli/review.py`, `cli/utils.py`, and any other consumer to import from `openreview_cli.types`. Run `uv run mypy src/ tests/` to verify no broken imports.
- [X] T004 [P] Run `uv run mypy src/ tests/` and `uv run pytest -q` to confirm migration is clean — no import errors, all existing tests pass.

---

## Phase 2: Foundational (Blocking Prerequisites)

*No story label. Core component library, design tokens, error infrastructure, and console layer. Every component has a TDD pair: test first, then implementation.*

### Design Tokens & Console

- [X] T005 [P] Write unit test `tests/unit/test_ui_colors.py` — verify each `ColorRole` (PRIMARY, SUCCESS, WARNING, ERROR, MUTED, ACCENT, CODE) has `.color`, `.no_color`, `.icon`, `.icon_ascii` fields. Verify no-color fallback strings contain no color references (no "red", "green", "yellow", "cyan", "magenta", "bright_black").
- [X] T006 [P] Implement `src/openreview_cli/ui/colors.py` — 7 semantic `ColorRole` tuples per spec §1.1, NO_COLOR fallback strings per spec §1.1 table.
- [X] T007 [P] Write unit test `tests/unit/test_ui_console.py` — verify `SGRenderer` singleton: `NO_COLOR` env var disables color, `--no-color` flag disables color, TTY detection via `force_terminal`/`force_interactive`, console width accessible, reuses same instance across imports, raises no error when both `NO_COLOR` and `FORCE_COLOR` are set (Rich precedence rules).
- [X] T008 [P] Implement `src/openreview_cli/ui/console.py` — `SGRenderer` class wrapping `rich.console.Console`. Singleton pattern. Capability detection: reads `NO_COLOR`, `--no-color`, `--no-unicode`, terminal width. Exposes `console: Console`, `is_interactive: bool`, `supports_unicode: bool`, `supports_color: bool` as properties.
- [X] T008a [P] Write unit test `tests/unit/test_ui_console.py` — verify icon mapping: `ICONS["check"] == "✓"`, `ICONS_ASCII["check"] == "[OK]"`, `get_icon("check", ascii_fallback=True) == "[OK]"` when `NO_COLOR` or `sys.platform == "win32"`. Verify icon dict is immutable (frozen or tuple-backed). Verify all 6 icon meanings have both Unicode and ASCII entries.
- [X] T008b [P] Implement icon mapping in `src/openreview_cli/ui/console.py`: `ICONS` dict (Unicode), `ICONS_ASCII` dict (ASCII fallback), `get_icon(name, ascii_fallback=False) -> str` function. Fallback triggered by: `NO_COLOR=1`, `FORCE_COLOR=0`, `sys.platform == "win32"`, or `UnicodeEncodeError` on render.

### Errors (Extend)

- [X] T009 [P] Write unit test `tests/unit/test_errors.py` (extend existing) — verify exit code constants: `SUCCESS=0`, `GENERAL_ERROR=1`, `USAGE_ERROR=2`, `CONFIG_ERROR=3`, `INPUT_ERROR=4`, `NETWORK_ERROR=5`. Verify `ERROR_MESSAGES` dict maps each code to a short descriptive string. Verify `ExitCode` enum (or IntEnum) supports `0 <= code <= 5`.
- [X] T010 [P] Extend `src/openreview_cli/errors.py` — add exit codes 0–5 (existing: 0, 1; extend to 2/3/4/5). Add `ERROR_MESSAGES` mapping. Add `ExitCode` IntEnum (optional — if existing pattern uses module constants, stay consistent). Add `sys.tracebacklimit = 0` at module level.

### Panel Component

- [X] T011 [P] Write unit test `tests/unit/test_ui_panel.py` — verify `info_panel`, `warning_panel`, `error_panel`, `success_panel` each render correct Rich Panel with correct border_style, title prefix (ℹ/⚠/✗/✓ or ASCII fallback), and three-part error panel format (What failed / Why / How to fix). Verify no-color mode strips border color but keeps title and content. Verify ASCII fallback icons in no-unicode mode.
- [X] T012 [P] Implement `src/openreview_cli/ui/components/panel.py` — 4 public functions: `info_panel(message, title)`, `warning_panel(message, title)`, `error_panel(what, why, fix, exit_code)`, `success_panel(message, title)`. All use `SGRenderer.console` for output. `error_panel` raises `SystemExit(exit_code)` after printing.

### Table Component

- [X] T013 [P] Write unit test `tests/unit/test_ui_table.py` — verify `SGTable` renders as Rich Table by default, as JSON (`--output json` → `json.dumps` to stdout), as plain fixed-width columns (`--output plain` — no borders, no color). Verify auto-width adapts to console width. Verify column headers use header_style. Verify empty table renders "No data" message.
- [X] T014 [P] Implement `src/openreview_cli/ui/components/table.py` — `SGTable` class wrapping Rich `Table`. Constructor takes `title`, `columns` (list of `(name, style, width)` tuples), `rows` (list of tuples), `output_format` (OutputFormat enum). Method: `render()` → prints to console (Rich table, JSON stdout, or plain text).

### Spinner Component

- [X] T015 [P] Write unit test `tests/unit/test_ui_spinner.py` — verify spinner creates `rich.status.Status` in TTY mode, prints label once in non-TTY mode, updates label text during operation, clears on exit. Verify it does not create visible artifacts when `--quiet` is set. Verify Ctrl-C during spinner exits cleanly.
- [X] T016 [P] Implement `src/openreview_cli/ui/components/spinner.py` — `Spinner` class wrapping Rich `Status`. Context manager. Parameter: `label` (str), `spinner` (str, default "dots"). Non-TTY fallback: prints `label...` once on enter, does nothing else. Exits cleanly on KeyboardInterrupt.

### Progress Component

- [X] T017 [P] Write unit test `tests/unit/test_ui_progress.py` — verify progress bar shows determinate progress with description updates. Verify non-TTY fallback prints `[current/total] description` periodically (simulate by advancing and checking output). Verify `--quiet` suppresses output. Verify `cancel()` method prints "Cancelled" and stops. Verify completion auto-cleans the bar.
- [X] T018 [P] Implement `src/openreview_cli/ui/components/progress.py` — `Progress` class wrapping Rich `Progress`. Context manager. Parameters: `total`, `description`, `console`. Methods: `advance(n=1)`, `update(description)`, `cancel()`. Non-TTY: prints one-line updates at 10Hz max (throttled).

### Prompt Component (questionary wrapper)

- [X] T019 [P] Write unit test `tests/unit/test_ui_prompt.py` — verify all prompt functions delegate to questionary: `select()`, `checkbox()`, `confirm()`, `text()`, `password()`. Verify `--yes` flag auto-answers confirm with safe default. Verify non-TTY raises error (exit code 2) for missing required input. Verify Escape returns `None`, Ctrl-C raises `SystemExit(1)`. Verify validate callback works on `text()`.
- [X] T020 [P] Implement `src/openreview_cli/ui/components/prompt.py` — wrapper functions around questionary. Each function: `select(message, choices, ...) → str | None`, `checkbox(message, choices, ...) → list[str] | None`, `confirm(message, default, ...) → bool`, `text(message, validate, ...) → str | None`, `password(message, ...) → str | None`. Non-TTY detection: if `not SGRenderer.is_interactive`, raise usage error. `--yes` flag: auto-return default for confirm, error for others. Use `unsafe_ask()` (raises on Ctrl-C) for all except where custom handling is needed. Refactor existing `_select`, `_checkbox`, `_autocomplete` helpers in `src/openreview_cli/cli/utils.py` to delegate here.

### Wizard Component

- [X] T021 [P] Write unit test `tests/unit/test_ui_wizard.py` — verify wizard state machine transitions: Entry→Mode→Config→Confirm→Processing→Results. Verify back-navigation (Esc returns to previous step). Verify Ctrl-C exits with code 1 and message "Setup was interrupted." Verify step indicator (2.11) renders correct ✓/▶/○ progression. Verify non-TTY bypasses all interactive steps.
- [X] T022 [P] Implement `src/openreview_cli/ui/components/wizard.py` — `Wizard` class with state machine. Steps: `Entry`, `ModeSelection`, `Configuration`, `Confirm`, `Processing`, `Results`. Each step is a method that returns next step name or `None` (exit). Navigation: Enter→advance, Esc→back, Ctrl-C→exit. Step indicator rendered via header component. Uses `SGRenderer.is_interactive` for TTY detection.

### Key Bindings Component

- [X] T023 [P] Write unit test `tests/unit/test_ui_key_bindings.py` — verify key binding constants are correct: UP/DOWN arrows, Enter, Space, Esc, Ctrl-C, Tab, Shift+Tab, Home/End. Verify conflict detection (no two actions use same key). Verify `KEY_BINDINGS` dict is immutable.
- [X] T024 [P] Implement `src/openreview_cli/ui/components/key_bindings.py` — module-level constants for all key bindings per spec §3.2. `KEY_BINDINGS` frozendict mapping key → (action, description, component). `Action` Literal type: "move_up", "move_down", "confirm", "cancel", "exit", "toggle", "filter", "complete", "cycle_forward", "cycle_backward", "jump_start", "jump_end".

### Status Line Component

- [X] T025 [P] Write unit test `tests/unit/test_ui_status_line.py` — verify status line shows LLM streaming status, mode context. Verify it updates in place (no newline). Verify non-TTY prints final status only. Verify `--quiet` suppresses. Verify label truncation at 60 characters.
- [X] T026 [P] Implement `src/openreview_cli/ui/components/status_line.py` — `StatusLine` class. Context manager. Shows: `[mode] [spinner] message`. Updates via `update(message)`. Truncates to 60 chars. Non-TTY: writes to stderr once on exit. Uses Rich `Console.status()` if spinner desired, or a simple `sys.stdout.write('\r...')` for plain updates.

### Header Component

- [X] T027 [P] Write unit test `tests/unit/test_ui_header.py` — verify `separator()` prints horizontal rule of correct width. Verify `breadcrumb()` prints breadcrumb trail (e.g., `setup > provider`). Verify step indicator (spec 2.11) renders ✓/▶/○ dots with labels. Verify all functions respect NO_COLOR.
- [X] T028 [P] Implement `src/openreview_cli/ui/components/header.py` — 3 functions: `separator(char='─')` — fills terminal width, `breadcrumb(steps: list[str], current: int)` — interactive/active/dim breadcrumbs, `step_indicator(current, total, title)` — spec §2.11 format.

### Markdown Component

- [X] T029 [P] Write unit test `tests/unit/test_ui_markdown.py` — verify minimal markdown renderer supports `# h1`, `## h2`, `### h3`, `- bullet`, `**bold**`, inline `` `code` ``. Verify unknown syntax is passed through as plain text. Verify no external markdown parser is used (stdlib only + Rich). Verify output uses Rich Text/Style, not raw strings.
- [X] T030 [P] Implement `src/openreview_cli/ui/components/markdown.py` — `render_markdown(text: str) → Rich.Text` function. Line-by-line parser handling h1-h3 (`# ` prefix), bullet lists (`- `), bold (`**...**`), code (`` `...` ``). Renders via Rich `Text` with appropriate `Style`. Uses `SGRenderer` styles. **ponytail: line-by-line parser, no AST. Add full parser if markdown rendering becomes a performance bottleneck or if nesting requirements grow.**

### Validation Component

- [X] T031 [P] Write unit test `tests/unit/test_ui_validation.py` — verify `validate_path(path)` returns `(bool, error_msg)`. Verify `validate_config_key(key)` rejects unknown keys. Verify `validate_range(value, min, max)` bounds checks. Verify `validate_not_empty(value)` rejects whitespace-only. Verify `validate_enum(value, allowed)` case-insensitive matching.
- [X] T032 [P] Implement `src/openreview_cli/ui/components/validation.py` — validation functions returning `(is_valid: bool, error: str | None)`. Functions: `validate_path(path_str)`, `validate_config_key(key, known_keys)`, `validate_range(value, min, max)`, `validate_not_empty(value)`, `validate_enum(value, allowed)`.

### Feedback Component

- [X] T033 [P] Write unit test `tests/unit/test_ui_feedback.py` — verify 3-part error format produces correct Rich panel. Verify exit code mapping shows correct code per error type. Verify `format_error(what, why, fix, exit_code)` returns structured dict. Verify `--verbose` adds detail to stderr. Verify PII redaction (FR-FB-005) on verbose output — no raw file paths in error messages.
- [X] T034 [P] Implement `src/openreview_cli/ui/feedback.py` — `format_error(what, why, fix, exit_code)` → calls `error_panel` from panel.py. `format_success(message, detail)` → calls `success_panel`. `EXIT_CODE_MAP` dict: error type → exit code. Verbose logging: uses stdlib `logging.Logger`, PII-redacted (replace file paths with `[path]`, API keys with `[key]`).

### Refactor cli/utils.py

- [X] T035 [P] Refactor `src/openreview_cli/cli/utils.py` — replace direct questionary imports with imports from `src/openreview_cli/ui/components/prompt.py`. Remove any duplicate `_select`, `_checkbox`, `_autocomplete` helpers. Verify no import cycles introduced. Run `uv run mypy src/ tests/` after refactor.

---

## Phase 3: User Story 1 — First-Run Experience (P1) 🎯 MVP

**Goal**: A lawyer installs openreview-cli and runs `openreview` for the first time. The tool detects no config, displays a welcome message within 100ms, offers to run setup wizard, and completes setup without errors or tracebacks.

**Independent Test**: Fresh install with no config file — verify first-run flow completes without errors, exposes no raw stack traces, and produces a usable config at `~/.config/openreview/config.json`.

- [X] T036 [P] [US1] Write unit test `tests/unit/test_first_run.py` — verify `is_first_run()` returns `True` when config file does not exist, `False` when config exists. Verify `mark_first_run_done()` creates sentinel or config. Verify auto-wizard trigger calls wizard on first run, skips on subsequent runs. Verify parallel safety (two processes racing first-run detection).
- [X] T037 [P] [US1] Implement `src/openreview_cli/config/first_run.py` — `is_first_run(config_path) → bool` checks config file existence. `mark_first_run_done(config_path)` creates minimal config. First-run trigger in `app.py`: on callback, if no config and no `--version`/`--help`, auto-launch wizard.
- [X] T038 [P] [US1] Write integration test `tests/integration/test_cli_wizard.py` — test first-run wizard end-to-end: simulate `openreview` with no config → welcome panel appears → wizard steps complete → config file written. Verify each wizard step renders correct UI. Verify Esc exits with message "Setup was interrupted." Verify Ctrl-C exits cleanly.
- [X] T039 [P] [US1] Implement first-run wizard flow in `src/openreview_cli/app.py` — at `app.callback()` level, detect first run, render welcome panel (within 100ms), offer setup wizard entry. Wire `setup` command that re-enters wizard. Add `--no-interactive` flag to `setup` command.
- [X] T040 [P] [US1] Write integration test `tests/integration/test_cli_config.py` — verify first-run wizard produces valid config at XDG path. Verify config has required keys (provider, model, jurisdiction). Verify `openreview setup --no-interactive --provider ollama` works without prompts.
- [X] T041 [P] [US1] Wire `setup` subcommand in `app.py` — `setup` command with optional `--no-interactive` flag. Delegates to `Wizard` state machine with `Entry` step set to setup-specific flow (mode selection skipped — setup has its own steps: provider, jurisdiction, completion install).

---

## Phase 4: User Story 2 — Interactive Legal Review (P1) 🎯 MVP

**Goal**: A lawyer runs `openreview review contract.pdf`. The wizard guides them through mode selection → configuration → confirm → processing → results. Progress indicators update clause-by-clause. Results display in a table with risk ratings.

**Independent Test**: Run a review of a test PDF through the wizard, verify each step displays properly, progress indicators appear, results formatted as tables with clear risk ratings.

- [X] T042 [P] [US2] Write unit test for review wizard steps — verify wizard entry point starts at Mode Selection (not setup). Verify step order: Mode → Config → Confirm → Processing → Results. Verify Esc back-navigation works on Config/Confirm steps but not on Processing.
- [X] T043 [P] [US2] Implement review wizard flow in `src/openreview_cli/app.py` — `review` command with Typer subcommand group. Accepts positional `file` argument, optional `--mode`, `--clauses`, `--jurisdiction`, `--yes`. Interactive path: launches wizard. Non-interactive: uses flag values, errors if missing required.
- [X] T044 [P] [US2] Write integration test `tests/integration/test_cli_wizard.py` (extend) — simulate `openreview review test.pdf` with TTY. Mock questionary to return specific values at each step. Verify step indicator renders correctly. Verify confirmation step shows selected options. Verify progress bar updates per clause. Verify results table has Risk/Clause/Finding/Recommendation columns.
- [X] T045 [P] [US2] Write integration test for streaming output — mock a 3-clause document. Verify `Progress` component updates for each clause. Verify live display shows partial results as they arrive (if AI gateway mock provides tokens). Verify spinner displays during non-clause processing (loading, PII stripping).
- [X] T046 [P] [US2] Implement processing display in review wizard — `Processing` step uses `Progress` (clause count known) and `Spinner` (PII stripping, AI generation). On completion, transition to `Results` step. Results step renders `SGTable` with findings.
- [X] T046a [P] [US2] Write unit test `tests/unit/test_ui_status_line.py` — verify `format_clause_label(3, 12, "Indemnification")` returns `"Analyzing clause 3 of 12 — Indemnification..."` and `format_clause_label(12, 12, "Indemnification", done=True)` returns `"Analyzed clause 12 of 12 — Indemnification"`. Verify label truncation at 60 characters. Verify empty clause title produces `"Analyzing clause 3 of 12..."` without trailing dash.
- [X] T047 [P] [US2] Write integration test for cancellation — verify Ctrl-C during Processing prints "Review cancelled. Partial results were not saved." and exits with code 1. Verify no partial config or temp files remain.
- [X] T048 [P] [US2] Implement cancellation handler in review wizard — catch `KeyboardInterrupt` in progress/spinner context managers. Clean message per spec FR-PP-004. Re-raise `SystemExit(1)`.

---

## Phase 5: User Story 3 — CI/Automation Mode (P2)

**Goal**: A legal ops professional batch-processes contracts with `openreview review contract.pdf --mode standard --output json --yes` — no interactive prompts, valid JSON to stdout, all messaging to stderr.

**Independent Test**: Run the command in a `| jq` pipeline, verify no prompts appear, output is valid JSON, exit code reflects success/failure.

- [X] T049 [P] [US3] Write unit test for `--non-interactive` detection — verify `sys.stdin.isatty()` mock returns `False` triggers non-TTY mode. Verify `--yes` auto-confirms all prompts. Verify missing required flag exits with code 2 and clear error message.
- [X] T050 [P] [US3] Implement non-interactive detection in `SGRenderer` — extend `is_interactive` property to check `sys.stdin.isatty()` AND `sys.stdout.isatty()` AND absence of `--non-interactive` / `--yes` override flags. All prompt functions check this before calling questionary.
- [X] T051 [P] [US3] Write integration test `tests/integration/test_cli_output.py` — verify `openreview review test.pdf --mode standard --output json --yes` produces valid JSON on stdout. Verify no questionary prompts appear (mock stdin as non-TTY). Verify errors go to stderr only.
- [X] T052 [P] [US3] Write integration test for piped output detection — verify `| jq` pipeline works: `openreview review test.pdf --mode standard --output json --yes` piped to `python -c "import sys,json; json.load(sys.stdin)"`. Verify exit code 0.
- [X] T053 [P] [US3] Implement output routing — `--output json` writes structured JSON to stdout, all human messages (errors, warnings, progress) to stderr. `--output plain` writes grep-friendly text to stdout. `--output table` (default) writes Rich table to stdout.

---

## Phase 6: User Story 4 — Configuration Management (P2)

**Goal**: A lawyer changes AI provider via `openreview config set model standard llama3.2` with inline validation. Unknown keys rejected with error panel.

**Independent Test**: Run `openreview config set model standard invalid-model`, verify error panel with suggestion to run `config list-models`.

- [X] T054 [P] [US4] Write unit test for config subcommands — verify `config show` displays all keys in table. Verify `config get <key>` returns single value. Verify `config set <key> <value>` validates key existence and writes. Verify `config unset <key>` resets to default. Verify `config path` returns XDG path string.
- [X] T055 [P] [US4] Write unit test for unknown key rejection — verify `config set unknown-key value` prints error panel with "Unknown config key" and suggests `config show`. Verify error uses exit code 2.
- [X] T056 [P] [US4] Write unit test for corrupted config — verify loading corrupted JSON exits with code 3 and shows error panel pointing to `openreview setup`.
- [X] T057 [P] [US4] Implement config subcommands in `src/openreview_cli/app.py` — `config_app` Typer sub-group with `show`, `get`, `set`, `unset`, `path` commands. Each validates input and uses `feedback.py` for output formatting.
- [X] T058 [P] [US4] Write integration test `tests/integration/test_cli_config.py` (extend) — verify `openreview config set provider ollama` writes to config file. Verify `openreview config get provider` reads back value. Verify `openreview config show --output json` outputs valid JSON. Verify `openreview config set unknown.key value` exits with code 2.
- [X] T058a [P] [US4] Implement env var overlay in `src/openreview_cli/config/loader.py`: read every `OPENREVIEW_<KEY>` variable (e.g. `OPENREVIEW_PROVIDER=ollama`), map to config key by lowercasing and replacing underscores with dots (`OPENREVIEW_LOG_LEVEL` → `log.level`), overlay on top of `config.json` values. Unknown `OPENREVIEW_BOGUS` vars are ignored (warned at debug level).
- [X] T058b [P] [US4] Write unit test `tests/unit/test_config_loader.py` — verify `OPENREVIEW_PROVIDER=ollama` overrides `config.json` provider key. Verify unknown `OPENREVIEW_BOGUS` is ignored (warned at debug level). Verify env var takes precedence over config file value.
- [X] T059 [P] [US4] Implement config validation on startup — in `app.callback()`, load config. If JSON is corrupt, print error panel, exit code 3. If unknown keys present, print warning panel (non-blocking, continue).

---

## Phase 7: User Story 5 — Help Discoverability (P3)

**Goal**: A lawyer runs `openreview --help`, sees examples before flags, and gets "Did you mean 'review'?" on typos.

**Independent Test**: Run `openreview --help`, verify examples appear before flag listing at the top level and for each subcommand.

- [X] T060 [P] [US5] Write integration test for `--help` output — verify `openreview --help` contains usage line, example section (before flags), grouped subcommands, `--version` flag. Verify `openreview review --help` shows `[required]` markers on `--mode`. Verify `openreview config --help` shows nested subcommand groups.
- [X] T061 [P] [US5] Wire `--help` formatting in `app.py` — use Typer's built-in Rich help (already enabled). Add custom help text groups with `rich_help_panel="Review Commands"`, `"Configuration Commands"` per spec FR-CS-005. Add examples section using Typer's `epilog` or custom callback.
- [X] T062 [P] [US5] Write integration test for typo suggestion — verify `openreview reviw` prints "Unknown command 'reviw'. Did you mean 'review'?" and exits code 2. Typer v0.26.8 has built-in typo correction via `difflib.get_close_matches()` (enabled by default via `suggest_commands=True`). Confirm no custom code needed.
- [X] T063 [P] [US5] Verify Typer `suggest_commands` is enabled (default). Typer v0.26.8 difflib.get_close_matches() handles typo suggestions out of the box. No implementation task — just confirm in T062 test.
- [X] T064 [P] [US5] Write integration test for `--version` — verify `openreview --version` prints the version string from `src/openreview_cli/__init__.py` and exits code 0. Verify no other output.
- [X] T065 [P] [US5] Implement `--version` flag referencing `src/openreview_cli/__init__.py` `__version__` in `src/openreview_cli/app.py`.
- [X] T066 [P] [US5] Write test for shell completion auto-install in setup wizard — verify wizard offers to install shell completion, runs `openreview --install-completion` on confirmation, and reports success/failure as non-blocking warning.
- [X] T067 [P] [US5] Implement completion install in setup wizard — after provider/jurisdiction steps, prompt "Install shell completion? (recommended)" with confirm default=True. On confirm, run `click.Context(parent).invoke(install_completion)` or shell out to `openreview --install-completion`. On failure, print warning panel (non-blocking, continue).

---

## Phase 8: Polish & Hardening

*No story label. Edge cases, benchmarks, memory tests, final pre-commit verification.*

- [X] T068 [P] Write unit test for narrow terminal (<60 cols) — verify tables collapse to key-value pairs, panels truncate gracefully. Mock `shutil.get_terminal_size()` to return width=50.
- [X] T069 [P] Write unit test for NO_COLOR + no-unicode combined — verify panels print with ASCII borders (no color), icons use ASCII fallbacks (`[OK]`, `[ERR]`, `[!]`, `[i]`), bold/underline retained for hierarchy.
- [X] T070 [P] Write unit test for empty document edge case — verify "No standard clauses detected" warning panel displays when document has zero clauses.
- [X] T071 [P] Write unit test for `--quiet` mode — verify suppress flag suppresses all non-error output (no spinner, no progress, no success message). Verify errors still display.
- [X] T072 [P] Write unit test for `--verbose` mode — verify additional detail printed to stderr (processing steps, config values used). Verify PII redaction active: file paths replaced with `[path]`, API keys with `[key]`.
- [X] T073 [P] Memory budget test — verify `--help` peak memory < 5 MB (tracemalloc, not RSS). Verify wizard import peak memory < 10 MB. Extend `tests/integration/test_memory.py` if it exists; otherwise add test to `tests/unit/test_ui_console.py`.
- [X] T072a [P] Write integration test `tests/integration/test_cli_output.py` — measure first-render latency: invoke `openreview --help` via subprocess, capture timing from `Popen` to first stdout byte with `time.perf_counter()`, assert elapsed < 0.150 (150ms — 50ms headroom for CI variance).
- [X] T074 [P] Add `textstat` as dev dependency: `uv add --dev textstat`. Write unit test `tests/unit/test_readability.py` that iterates all user-facing strings (panel titles, error messages, wizard prompts, help text), calls `textstat.flesch_kincaid_grade()`, asserts grade < 10. Export strings to a registry module OR scan with grep/regex for "user-facing" marker comments.
- [X] T075 [P] Final pre-commit sweep — run `uvx pre-commit run --all-files`. Fix any ruff, mypy, or pytest failures. Verify `uv run pytest tests/unit/ -q` passes for all UI tests.

---

## Dependencies & Execution Order

```
Phase 1 ─────────────────────────────────────────────────────────────────────┐
  T001 (questionary install) — no deps                                       │
  T002 (package dirs) — no deps                                              │
  T003 (types.py) — T002                                                     │
  T003a (migrate OutputFormat) — T003                                        │
  T004 (verify migration) — T003a                                            │
                                                                             │
Phase 2 ─────────────────────────────────────────────────────────────────────┤
  ┌─ Colors (T005,T006) — T001                                              │
  ├─ Console (T007,T008,T008a,T008b) — T006                                 │
  ├─ Errors (T009,T010) — no deps                                           │
  ├─ Panel (T011,T012) — T008, T006, T010                                   │
  ├─ Table (T013,T014) — T008, T003 (OutputFormat)                          │
  ├─ Spinner (T015,T016) — T008                                             │
  ├─ Progress (T017,T018) — T008                                            │
  ├─ Prompt (T019,T020) — T008, T001 (questionary)                          │
  ├─ Wizard (T021,T022) — T020, T028 (header), T012 (panel)                 │
  ├─ KeyBindings (T023,T024) — no deps                                      │
  ├─ StatusLine (T025,T026) — T008                                          │
  ├─ Header (T027,T028) — T008, T006                                        │
  ├─ Markdown (T029,T030) — T008, T006                                      │
  ├─ Validation (T031,T032) — no deps                                       │
  ├─ Feedback (T033,T034) — T012, T010                                      │
  └─ Refactor utils (T035) — T020                                           │
                                                                             │
Phase 3 (US1) ──────────────────────────────────────────────────────────────┤
  First-run (T036,T037) — T003, config module                               │
  Wizard integration (T038,T039) — T022 (Wizard), T037 (first_run)          │
  Config verification (T040,T041) — T037, T039                              │
                                                                             │
Phase 4 (US2) ──────────────────────────────────────────────────────────────┤
  Review wizard steps (T042,T043) — T022 (Wizard), T037 (first_run)         │
  Wizard integration tests (T044,T045) — T043                               │
  Processing display (T046,T046a) — T018 (Progress), T016 (Spinner), T014 (Table) │
  Cancellation (T047,T048) — T046, programming                              │
                                                                             │
Phase 5 (US3) ──────────────────────────────────────────────────────────────┤
  Non-interactive detection (T049,T050) — T008 (SGRenderer), T020 (Prompt)  │
  Output routing (T051,T052,T053) — T014 (Table), T053                      │
                                                                             │
Phase 6 (US4) ──────────────────────────────────────────────────────────────┤
  Config subcommand tests (T054,T055,T056) — T003 (types), config module    │
  Config subcommand impl (T057) — T010 (errors), T012 (panel)              │
  Config integration (T058,T058a,T058b,T059) — T057                         │
                                                                             │
Phase 7 (US5) ──────────────────────────────────────────────────────────────┤
  Help formatting (T060,T061) — app.py                                      │
  Typo suggestion (T062,T063) — T061                                        │
  Version flag (T064,T065) — app.py                                         │
  Completion install (T066,T067) — T041 (setup command)                     │
                                                                             │
Phase 8 ─────────────────────────────────────────────────────────────────────┘
  T068–T075 — all preceding phases must pass                                │
```

### Critical Path to MVP
```
T001 → T002 → T003 → T005/T006 → T007/T008 → T011/T012 → T019/T020
→ T021/T022 → T027/T028 → T036/T037 → T038/T039 → T040/T041

MVP = Phase 3 (US1) done. Core components (console, colors, panel, prompt,
wizard, header, first_run) wire up the first-run experience.
```

---

## Parallel Example

Four independent workstreams that can proceed in parallel after Phase 1 is complete:

| Workstream | Tasks | Dependencies | Can Merge When |
|------------|-------|-------------|----------------|
| **A: Core Components** | T005–T008b (colors, console, icons), T011–T018 (panel, table, spinner, progress) | T001–T003 | All A tasks pass unit tests |
| **B: Interactive Components** | T019–T030 (prompt, wizard, key_bindings, status_line, header, markdown, validation) | T001–T003, T008 | All B tasks pass unit tests |
| **C: Errors & Feedback** | T009–T010 (errors), T033–T034 (feedback) | T001–T003 | All C tasks pass unit tests |
| **D: Validation & Config** | T031–T032 (validation), T035 (refactor) | T001–T003, T020 | D passes unit tests, utils refactor merges |

Workstreams A–D can schedule independently. Merge order does not matter as long as each workstream's tests pass. Phase 3 (US1) aggregates at T036 after A/B/C/D all merge.

---

## Implementation Strategy

1. **MVP = User Story 1 (Phase 3)** — First-run experience. Delivers value: a new user can install and complete setup. Everything before it (Phase 1 + Phase 2) is scaffolding that enables this.
2. **Phase 4 (US2)** ships next — the core product workflow. Interactive review wizard builds directly on the wizard component and prompt/panel/table from Phase 2.
3. **Phase 5 + 6** (US3 + US4) ship together — non-interactive mode and config commands. These overlap: config validation is needed for both. Both are P2.
4. **Phase 7 (US5)** ships last — help polish. P3, no critical path dependencies. Can be deferred or cut without affecting any other story.
5. **Phase 8** — hardening across all phases. Runs last but individual tests (T068–T072) can be written alongside their related components.

---

## Summary

| Category | Count |
|----------|-------|
| Phase 1 — Setup | 5 tasks (1 test + 3 impl + 1 migration) |
| Phase 2 — Foundational | 33 tasks (17 test + 15 impl + 1 refactor) |
| Phase 3 — US1 (First-Run) | 6 tasks |
| Phase 4 — US2 (Interactive Review) | 8 tasks |
| Phase 5 — US3 (CI/Automation) | 5 tasks |
| Phase 6 — US4 (Configuration) | 8 tasks |
| Phase 7 — US5 (Help) | 8 tasks |
| Phase 8 — Polish & Hardening | 9 tasks |
| **Total** | **82 tasks** |
| Of which are test-first tasks | **~43 (~52%)** |
| Of which are implementation | **~39 (~48%)** |

---

## Phase 9: Convergence

*Gap-closure tasks identified by `/speckit.converge`. See convergence findings for traceability.*

- [X] T076 [HIGH] Wire 7 global CLI flags at root Typer level — `--verbose`, `--quiet`, `--no-color`, `--no-unicode`, `--no-spinner`, `--output`, `--config` per spec §4.3 and FR-FB-005, FR-FB-006, FR-TC-001, FR-TC-002, FR-TC-004a, FR-OF-002 (`missing`)
- [X] T077 [HIGH] Show config file location, configured AI provider, shell completion status, and a suggested next command in the setup wizard success summary per US1/AC3 and spec §8.4 (`partial`)
- [X] T078 [HIGH] Add `--no-pii` CLI flag to the `review` command per spec §4.1 command tree — unblocked now that the review command exists (`missing`)
- [X] T079 [MEDIUM] Implement `autocomplete()` function in `src/openreview_cli/ui/components/prompt.py` using `difflib.get_close_matches()` for fuzzy search on lists >8 items per FR-IP-002 (`missing`)
- [X] T080 [MEDIUM] Add missing icon meanings to `ICONS`/`ICONS_ASCII` dicts in `console.py`: Arrow (▶/>), Bullet (●/*), Separator (━/-), step marker (→/->), file path (📄/[file]), lock (🔒/[**]) per FR-VD-004 and spec §1.2 (`partial`)
- [X] T081 [MEDIUM] Read and display the old config value alongside the new value in `config set` success message per US4/AC1 (`partial`)
- [X] T082 [MEDIUM] Add `--no-spinner` global flag that disables animated spinner/progress and falls back to static text updates per FR-TC-004a; wire into Spinner and Progress components (`missing`)
- [X] T083 [LOW] Move help examples before the option/command listing in Typer help output per US5/AC1 and FR-HS-002 (`partial`)
- [X] T084 [LOW] Append "Run `openreview <command> --help` for usage." to error messages in `error_panel()` and `format_error()` per FR-HS-003 (`missing`)
- [X] T085 [LOW] Show "No standard clauses detected" warning panel in review flow when document has zero detectable clauses per spec Edge Cases #6 (`missing`)
- [X] T086 [LOW] Mark `--mode` as `[required]` in the review command's help text per US5/AC3 and FR-CS-003 (`partial`)
- [X] T087 [LOW] Add trailing instruction "Run `openreview setup` to try again later." to first-run wizard Esc/cancel message per US1/AC2 and spec §8.4 (`partial`)
