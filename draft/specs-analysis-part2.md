# Spec Analysis — Part 2 (S-4 through S-6)

Generated 2026-06-28. Extracted from spec directory files in `/specs/004-ai-gateway/`, `/specs/005-cli-wizard-redesign/`, `/specs/006-cli-ux-specification/`.

═══════════════════════════════════════════
SPEC S-4: 004-ai-gateway
───────────────────────────────────────────

FEATURE / DOMAIN
An AI Gateway model routing layer connecting the openreview review engine to AI
providers (cloud and local), with 5 task-specific slots, fallback chains, cost
tracking, interactive setup, and BYOK key management.
___

DEFINED CAPABILITIES
CAP1: Route requests through 5 task-specific slots (reasoning, extraction,
      embedding, reranking, graph) via a single `route_request()` function.
CAP2: Support 8+ providers: OpenAI, Anthropic, Google, Ollama, OpenRouter,
      Cohere, HuggingFace, and Custom (OpenAI-compatible endpoint).
CAP3: Chat completion routing (reasoning, extraction, graph slots).
CAP4: Embedding routing (embedding slot).
CAP5: Reranking routing (reranking slot).
CAP6: Interactive first-time setup wizard (SetupWizard class) walking through
      all 5 slots with provider selection, model selection, API key entry,
      and summary-before-save.
CAP7: Non-interactive setup via command-line flags (--<slot> <provider/model>).
CAP8: Automatic fallback and retry on provider failure (exponential backoff,
      configurable retry count, fallback model per slot, on-failure modes:
      error/skip/warn).
CAP9: Cost tracking per API call (token counts input/output, estimated cost
      USD) aggregated by review session (UUID auto-generated per invocation).
CAP10: Cost limit enforcement (per-review and daily ceilings, pre-call check).
CAP11: CLI management subcommands: status, providers, models, set, test,
       refresh, costs, install-models.
CAP12: YAML configuration import (5-slot-keyed format, all errors reported at
      once, env-var-based API key references only, no inline keys).
CAP13: API key storage in dedicated auth.json with chmod 600, overridable by
      environment variables.
CAP14: Atomic config file writes (temp file → fsync → rename).
CAP15: Local model discovery via Ollama API (`GET /api/tags`).
CAP16: Model registry cache with remote refresh, built-in minimal fallback.
CAP17: Three-tier logging (console INFO, debug file, no body logs unless
      --debug-unsafe).
CAP18: API key redaction in all log output and CLI display.
CAP19: Gateway routing overhead benchmark <50ms per request.
CAP20: Network isolation test (respx mock, all calls to user-configured
      providers only).
CAP21: Slot parameter injection (temperature, max_tokens, dimensions from
      slot config).
CAP22: Response metadata including which model served and whether fallback
      was used.
CAP23: Slots skippable during setup (unconfigured slots raise clear errors
      on use).
CAP24: Provider grouping offer during wizard ("Apply this provider to
      extraction and graph too?").
CAP25: API key validation during setup via `GET /v1/models` or 1-token
      fallback.
CAP26: YAML import validation before write (report-all-errors-at-once).
CAP27: Overwrite confirmation prompt for YAML import.
CAP28: Route-through-flag and env-var API key resolution.
CAP29: Ollama empty-state handling (not running, no models, timeout).
CAP30: Wizard progress indicator ("Step X of 5"), back navigation,
      cancel-with-save.
CAP31: Built-in default config (all slots default to Ollama models).
___

TECH DECISIONS
TD1: LiteLLM as provider abstraction layer for chat completion, embedding,
     and reranking.
TD2: Pydantic v2 for configuration validation (BaseSettings, YamlConfig-
     SettingsSource).
TD3: questionary v2.1.1 for interactive wizard prompts.
TD4: Rich for CLI tables, progress, spinner, summary UI.
TD5: SQLite for cost records and session state (existing storage/ module).
TD6: YAML for config file (~/.config/openreview/config.yml).
TD7: JSON for auth file (~/.config/openreview/auth.json, chmod 600).
TD8: JSON for model registry cache (~/.cache/openreview/model_registry.json).
TD9: Dataclass models for runtime types (SlotConfig, ModelParams, etc.) with
     @dataclass(slots=True).
TD10: Pydantic models for config validation only.
TD11: Atomic file writes (temp → fsync → rename).
TD12: Lazy imports for heavy dependencies (litellm, rich).
TD13: Exceptions use GatewayError dataclass (exit_code, slot, message, action).
TD14: Typer for CLI framework, Typer sub-apps for gateway command group.
TD15: httpx for HTTP requests (Ollama discovery, API key validation).
TD16: Provider model format: `provider/model-id` (e.g. openai/gpt-4o).
TD17: Env var overrides for API keys (OPENAI_API_KEY, etc.) take precedence
     over auth file.
TD18: Config env var overrides use OPENREVIEW_GATEWAY__ prefix (double
     underscore for nesting).
TD19: Reserved exit codes: 0=success, 1=general, 5=config, 6=cost limit,
     7=gateway.
TD20: Wide- (≥80) and narrow- (<80) column terminal adaptation for Rich
     tables.
TD21: Five-slot-keyed YAML import schema with separate api_key_env block.
TD22: Model registry entries include slot_compatibility, context_window,
     ram_required_mb, pricing info.
___

IMPLEMENTATION STATUS
All tasks (T001–T069) marked [X] completed in tasks.md. Phases:
Phase 1 (Setup), Phase 2 (Foundational), Phase 3 (US1 Routing), Phase 4
(US2 Setup Wizard), Phase 5 (US3 Fallback), Phase 6 (US4 Cost Tracking),
Phase 7 (US5 CLI Management), Phase 8 (US6 YAML Import), Phase 9 (Polish)
— all marked complete.

CAP1: BUILT
CAP2: BUILT
CAP3: BUILT
CAP4: BUILT
CAP5: BUILT
CAP6: BUILT
CAP7: BUILT
CAP8: BUILT
CAP9: BUILT
CAP10: BUILT
CAP11: BUILT
CAP12: BUILT
CAP13: BUILT
CAP14: BUILT
CAP15: BUILT
CAP16: BUILT
CAP17: BUILT
CAP18: BUILT
CAP19: BUILT
CAP20: BUILT
CAP21: BUILT
CAP22: BUILT
CAP23: BUILT
CAP24: BUILT
CAP25: BUILT
CAP26: BUILT
CAP27: BUILT
CAP28: BUILT
CAP29: BUILT
CAP30: BUILT
CAP31: BUILT
___

INTERFACES / CONTRACTS
I1: `route_request(slot, messages, input_text, query, documents, session_id,
    **kwargs) -> GatewayResponse` — core routing function.
I2: `SetupWizard.__init__() -> None`, `SetupWizard.run() -> None` — setup
    wizard class.
I3: CLI: `openreview gateway setup [--<slot> <p/m>] [--no-interactive]`
I4: CLI: `openreview gateway status`
I5: CLI: `openreview gateway providers`
I6: CLI: `openreview gateway models <provider>`
I7: CLI: `openreview gateway set <slot> <provider/model> [--fallback]
    [--temperature] [--max-tokens] [--dimensions]`
I8: CLI: `openreview gateway test <slot>`
I9: CLI: `openreview gateway refresh`
I10: CLI: `openreview gateway costs [--session] [--days] [--clear] [--json]`
I11: CLI: `openreview gateway import <file> [--force] [--dry-run]`
I12: CLI: `openreview gateway install-models <model>...`
I13: `GatewayResponse` dataclass — content, input_tokens, output_tokens,
     cost_usd, model, provider, slot, fallback_used, latency_ms, raw_response.
I14: `RerankResult` dataclass — index, score, document.
I15: `GatewayError` exception — exit_code, slot, message, action.
I16: `GatewayEngine` class — internal engine with `route_request()`.
I17: `CostStore` class — SQLite CRUD for cost records and sessions.
I18: `ModelRegistry` class — cache management, remote fetch, built-in
     fallback.
I19: `ImportValidator` class — YAML import parsing, validation, env var
     resolution.
I20: Auth file format: `{"openai": "...", "anthropic": "..."}`
I21: Config file YAML schema: `gateway.models.<slot>.primary/.fallback/.params`
     plus `gateway.fallback`, `gateway.cost_limits`, `gateway.registry`,
     `gateway.logging`.
I22: Import file YAML schema: five top-level slot keys (reasoning, extraction,
     embedding, reranking, graph) + optional `api_key_env` block.
___

DEPENDENCIES
DEP1: LiteLLM (provider abstraction) — new dependency.
DEP2: Pydantic v2 + pydantic-settings (config validation) — already
     permitted in constitution.
DEP3: httpx (HTTP client) — already in deps.
DEP4: Rich (CLI UI) — already in deps.
DEP5: Typer (CLI framework) — already in deps.
DEP6: PyYAML (YAML loading) — already in deps.
DEP7: SQLite (cost/session storage) — stdlib, existing storage/ module.
DEP8: S-2 (Document Parsing) — PII stripping runs before gateway, but
     gateway does not depend on parsing directly.
DEP9: config/loader.py extensions (Pydantic models for gateway section).
DEP10: config/auth.py extensions (get_api_key() function).
DEP11: Ollama (local model server) — external dependency, user-managed.
___

GAPS / TODOS
G1: Spec defers response caching, multi-user API key management, and
    automatic model selection based on contract complexity — explicitly
    out of scope.
G2: Cost estimates based on provider-published pricing tables; actual costs
    may vary.
G3: Provider API version compatibility managed by LiteLLM — the gateway
    delegates this.
G4: Spec notes 3 deferred tasks (T033, T034, T035) blocked by downstream
    infrastructure that does not exist yet (review command, config change
    detection).
G5: The cloud model registry URL in defaults is placeholder
    (`https://example.com/models.json`).
════════════════════════════════════════════

═══════════════════════════════════════════
SPEC S-5: 005-cli-wizard-redesign
───────────────────────────────────────────

FEATURE / DOMAIN
Redesign CLI wizard UX by replacing `rich.prompt.Prompt.ask()` with
`questionary` interactive prompts (arrow-key navigation, checkbox, autocomplete)
across the gateway setup wizard and a new review wizard.
___

DEFINED CAPABILITIES
CAP1: Arrow-key navigable single-select prompts (questionary.select) for all
      wizard choices.
CAP2: Multi-select with space-to-toggle and Enter-to-confirm for selecting
      multiple items (e.g., clauses).
CAP3: Free-text prompt with inline fuzzy filtering (questionary.autocomplete)
      for long lists (e.g., model selection, jurisdiction).
CAP4: Inline input validation feedback on the same prompt screen (red error
      text beneath input).
CAP5: Summary-before-save Rich Table confirmation in gateway setup wizard.
CAP6: Non-interactive terminal detection (piped stdin, `TERM=dumb`,
      `sys.stdin.isatty()`) with graceful fallback to flag-based mode.
CAP7: Ctrl+C graceful exit at any wizard step (questionary returns None,
      clean "Cancelled by user." message).
CAP8: "Back" navigation via a "← Back" choice in select prompts.
CAP9: Pre-flight gateway readiness check for review wizard (≥1 chat model +
      ≥1 embedding configured).
CAP10: New `ReviewWizard` class (separate from `SetupWizard`) that returns a
       `ReviewConfiguration` bundle.
CAP11: New `openreview review <file>` Typer command with 3-step wizard flow
       (mode → jurisdiction/output → confirm) plus clause multi-select for
       clause-by-clause mode.
CAP12: Conditional step branching in review wizard (risk-scan mode skips
       jurisdiction/output/clauses prompts).
CAP13: Instruction hints on all wizard prompts (FR-08).
CAP14: File integrity validation before review wizard starts (readable
       PDF/DOCX).
CAP15: Prompt helper wrappers in `cli/utils.py` (shared between both wizards):
       _select, _checkbox, _autocomplete, _confirm, _text, _password.
CAP16: Review wizard non-interactive mode with --non-interactive, --mode,
       --jurisdiction, --output, --clauses flags.
CAP17: Gateway setup wizard refactored to use questionary internally while
       preserving public API unchanged.
CAP18: API key entry via questionary.password() with inline validation.
___

TECH DECISIONS
TD1: questionary v2.1.1 as the interactive prompt library (arrow-key select,
     checkbox, autocomplete, confirm, text, password).
TD2: Rich for summary tables and styled output (already in deps).
TD3: Typer for CLI framework (already in deps).
TD4: prompt_toolkit (transitive via questionary, BSD-3) for SSH/PTY support.
TD5: Separate `ReviewWizard` and `SetupWizard` classes (different contracts).
TD6: ReviewWizard returns `ReviewConfiguration` dataclass to caller; does not
     call parse or gateway engines.
TD7: Shared prompt helper functions in `cli/utils.py` with consistent styling.
TD8: questionary defaults for styling (ansidark theme, ◉/○ markers, default
     instruction hints).
TD9: Back navigation via "← Back" choice in select prompts (not text-based
     matching).
TD10: Terminal compatibility targets: ANSI-capable terminals; `TERM=dumb`
      falls back to typed choices with monochrome.
TD11: questionary's built-in Ctrl+C handling (`.ask()` returns None safely).
TD12: Jurisdiction codes as a fixed module-level constant list (12 codes for
      MVP).
___

IMPLEMENTATION STATUS
All tasks (T001–T032) marked [X] completed in tasks.md. Phases 1–7 all
complete.

CAP1: BUILT
CAP2: BUILT
CAP3: BUILT
CAP4: BUILT
CAP5: BUILT
CAP6: BUILT
CAP7: BUILT
CAP8: BUILT
CAP9: BUILT
CAP10: BUILT
CAP11: BUILT
CAP12: BUILT
CAP13: BUILT
CAP14: BUILT
CAP15: BUILT
CAP16: BUILT
CAP17: BUILT
CAP18: BUILT
___

INTERFACES / CONTRACTS
I1: `SetupWizard.__init__() -> None`, `SetupWizard.run() -> None` — public
    API unchanged from S-4.
I2: `ReviewWizard.__init__(file_path, non_interactive=False, mode=None,
    jurisdiction=None, output_format=None, clauses=None)`.
I3: `ReviewWizard.run() -> ReviewConfiguration`.
I4: `ReviewConfiguration` dataclass — file_path, mode (ReviewMode enum),
    jurisdiction (str|None), output_format (OutputFormat|None),
    clauses (list[str]|None).
I5: CLI: `openreview review <file> [--non-interactive] [--mode <mode>]
    [--jurisdiction <code>] [--output <format>] [--clauses <ids>]`
I6: CLI: `openreview gateway setup [--non-interactive] [--<slot> <p/m>]...`
    (unchanged from S-4).
I7: `_select()`, `_checkbox()`, `_autocomplete()`, `_confirm()`, `_text()`,
    `_password()` wrappers in `src/openreview_cli/cli/utils.py`.
I8: `_is_interactive()` terminal detection function in `cli/utils.py`.
I9: `ReviewMode` enum: FULL, CLAUSE_BY_CLAUSE, RISK_SCAN.
I10: `OutputFormat` enum: JSON, TEXT, HTML.
I11: Jurisdiction constant list (12 codes: us-de, us-ca, us-ny, us-tx,
     us-il, uk, eu-gdpr, eu-de, eu-fr, ca, au, sg).
___

DEPENDENCIES
DEP1: questionary v2.1.1 — new runtime dependency.
DEP2: Rich (summary tables) — already in deps.
DEP3: Typer (CLI) — already in deps.
DEP4: prompt_toolkit (transitive via questionary) — new transitive dep.
DEP5: S-4 (AI Gateway) — review wizard depends on gateway configuration for
     pre-flight readiness check.
DEP6: Config module (src/openreview_cli/config/) — for reading existing
     gateway config.
DEP7: File system — local PDF/DOCX file for review command.
___

GAPS / TODOS
G1: S-5 spec explicitly says the review engine (Phase 5+) is out of scope —
     the wizard produces a config dict and hands it off.
G2: Persistent wizard state across sessions is out of scope.
G3: Custom keybinding configuration by users is out of scope.
G4: Internationalization / localization is out of scope.
G5: Full TUI application (no Textual app class as main shell) is out of scope.
G6: The spec notes its interaction patterns are superseded by S-6 (006-cli-ux-
     specification) which covers the same domain but with broader UX scope.
G7: Pre-flight check is basic (file validation only); encrypted/damaged file
     detection is marked as partial in T031.
G8: Fuzzy filtering uses questionary.autocomplete (substring match), not true
     fuzzy (typo-tolerant) matching.
════════════════════════════════════════════

═══════════════════════════════════════════
SPEC S-6: 006-cli-ux-specification
───────────────────────────────────────────

FEATURE / DOMAIN
Comprehensive CLI UX layer for openreview-cli: semantic design tokens, a Rich/
questionary component library (11 interactive components), multi-step wizard
state machine, verb-noun command structure, structured error/warning/success
feedback, terminal compatibility detection, and configuration UX.
___

DEFINED CAPABILITIES
CAP1: Semantic color palette (7 roles: primary, success, warning, error,
      muted, accent, code) with NO_COLOR fallbacks and Rich style strings.
CAP2: Icon system with Unicode default and ASCII fallback mapping for all
      9 states (success, error, warning, info, pending, running, step_marker,
      file_path, lock).
CAP3: Spacing rules (1 blank line between paragraphs, 2 between sections,
      etc.).
CAP4: Typography rules (bold for headings, dim for secondary, italic
      sparingly, no underline for non-links).
CAP5: 11 UI components: Selection Menu, Multi-select, Fuzzy Search Select,
      Confirmation Dialog, Text Input with Validation, Spinner, Progress Bar,
      Live Panel, Result Table, Error Panel, Step Indicator.
CAP6: SGRenderer singleton wrapping Rich Console (NO_COLOR, --no-color,
      --no-unicode, terminal width, TTY detection).
CAP7: Three-part error format panel (what failed / why / how to fix) with
      red border, formatting error_panel(), warning_panel(), info_panel(),
      success_panel().
CAP8: Structured exit code map (0=success, 1=general, 2=usage, 3=config,
      4=input file, 5=network, 6=AI error, 7=interrupted, 8=unknown).
CAP9: Wizard state machine (Entry → ModeSelection → Configuration → Confirm
      → Processing → Results) with forward/back/cancel transitions.
CAP10: Keyboard shortcut map (↑↓ Enter Space Esc Ctrl-C / Tab Shift+Tab
       Home/End).
CAP11: Non-interactive mode (all prompts disabled when !isatty, exit code 2
       for missing required flags).
CAP12: --yes flag auto-confirms all prompts with safe defaults.
CAP13: --output flag (table/json/plain) — JSON to stdout, messaging to stderr.
CAP14: Verb-noun command structure (openreview setup, review, config, list,
       version) with --kebab-case flags.
CAP15: Global flags on all subcommands: --verbose, --quiet, --no-color,
       --no-unicode, --no-spinner, --output, --config.
CAP16: First-run detection (no config file) with welcome panel + privacy
       notice + auto-enter setup wizard.
CAP17: Config subcommands (show, get, set, unset, path) with inline
       validation and error panels.
CAP18: Config env var overrides (OPENREVIEW_<KEY>) that override
       config.json values.
CAP19: Config validation on startup (corrupted JSON = exit code 3, unknown
       keys = warning panel, continue).
CAP20: Terminal width adaptation (≥80 full table, 60–79 proportional shrink,
       <60 key-value pairs, <40 warning).
CAP21: Non-TTY component degradation matrix (spinner → label once, progress
       bar → periodic [N/total] text, error panel → plain text, etc.).
CAP22: Streaming AI output via Rich Live panel for token-by-token display.
CAP23: Spinner at 500ms threshold for indeterminate operations.
CAP24: Progress bar for determinate operations with clause-by-clause labeling.
CAP25: Cancel during processing: "Review cancelled. Partial results not saved."
       exit code 7.
CAP26: Background task labeling in plain English ("Analyzing clause 3 of 12
       — Indemnification...").
CAP27: Tab completion via Typer built-in (bash/zsh/fish/powershell).
CAP28: Typo suggestion for commands ("Unknown command 'reviw'. Did you mean
       'review'?").
CAP29: Shell completion auto-install during setup wizard.
CAP30: --quiet flag suppresses all non-error output (spinner remains visible).
CAP31: --no-spinner flag disables all animated output.
CAP32: --verbose flag with PII-redacted detail.
CAP33: Flesch-Kincaid grade level < 10 for all user-facing text.
CAP34: First-render latency <100ms (corrected from spec's 200ms).
___

TECH DECISIONS
TD1: Rich v15.0.0 for all output rendering (Console singleton, Table, Panel,
     Progress, Live, Status, Markdown).
TD2: questionary v2.1.1 for all interactive prompts (select, checkbox,
     confirm, text, password, autocomplete).
TD3: Typer v0.26.8 for CLI framework, command structure, help, exit codes,
     shell completion (vendored Click 8.x).
TD4: shellingham for shell detection during completion install (already
     transitive via Typer).
TD5: SGRenderer singleton wrapping Rich Console in src/openreview_cli/ui/.
TD6: Semantic ColorRole NamedTuple (color, no_color, icon, icon_ascii).
TD7: Design tokens as module-level Python constants in colors.py.
TD8: UI components isolated in src/openreview_cli/ui/components/ sub-package.
TD9: Wizard state machine in src/openreview_cli/ui/components/wizard.py.
TD10: Config file at $XDG_CONFIG_HOME/openreview/config.json (JSON format).
TD11: Auth file at same dir, chmod 600.
TD12: Env var prefix OPENREVIEW_ for config overrides (dots → underscores).
TD13: First-run detection by checking config file existence.
TD14: 3-part error panel format with error_panel() raising SystemExit.
TD15: SGTable wrapping Rich Table with output_format (table/json/plain).
TD16: Non-TTY detection via sys.stdin.isatty() and sys.stdout.isatty().
TD17: Icon maps in console.py: ICONS dict (Unicode), ICONS_ASCII dict,
      get_icon() function.
TD18: Keyboard shortcuts as module-level frozendict in key_bindings.py.
TD19: difflib.get_close_matches() for fuzzy search on lists >8 items.
TD20: Progress update rate capped at 10Hz max.
TD21: Lazy imports for heavy modules behind command callbacks.
TD22: Max clause label length = 60 characters.
TD23: JSON output structure: {"status": "...", "document": {...}, "findings":
      [...], "summary": {...}}.
___

IMPLEMENTATION STATUS
All tasks (T001–T087) marked [X] completed. 8 phases + 1 convergence phase.
Phase 1 Setup, Phase 2 Foundational (33 tasks across 15 components), Phase 3
US1 First-Run, Phase 4 US2 Interactive Review, Phase 5 US3 CI/Automation,
Phase 6 US4 Configuration Management, Phase 7 US5 Help Discoverability,
Phase 8 Polish & Hardening, Phase 9 Convergence (12 gap-closure tasks).

CAP1: BUILT
CAP2: BUILT
CAP3: BUILT
CAP4: BUILT
CAP5: BUILT
CAP6: BUILT
CAP7: BUILT
CAP8: BUILT
CAP9: BUILT
CAP10: BUILT
CAP11: BUILT
CAP12: BUILT
CAP13: BUILT
CAP14: BUILT
CAP15: BUILT
CAP16: BUILT
CAP17: BUILT
CAP18: BUILT
CAP19: BUILT
CAP20: BUILT
CAP21: BUILT
CAP22: BUILT
CAP23: BUILT
CAP24: BUILT
CAP25: BUILT
CAP26: BUILT
CAP27: BUILT
CAP28: BUILT
CAP29: BUILT
CAP30: BUILT
CAP31: BUILT
CAP32: BUILT
CAP33: BUILT
CAP34: BUILT
___

INTERFACES / CONTRACTS
I1: Root: `openreview [--verbose] [--quiet] [--no-color] [--no-unicode]
    [--no-spinner] [--output <fmt>] [--config <path>] [--help] [--version]`
I2: `openreview setup [--no-interactive]`
I3: `openreview review <file> [--mode <mode>] [--output <fmt>]
    [--clauses <list>] [--jurisdiction <code>] [--yes] [--no-pii]`
I4: `openreview config show [--output <fmt>]`
I5: `openreview config get <key>`
I6: `openreview config set <key> <value>`
I7: `openreview config unset <key>`
I8: `openreview config path`
I9: `openreview list providers [--output <fmt>]`
I10: `openreview list models [--output <fmt>]`
I11: `openreview list jurisdictions [--output <fmt>]`
I12: `openreview models list [--output <fmt>]`
I13: `openreview models pull <name>`
I14: `openreview models info <name>`
I15: Exit code constants: SUCCESS=0, GENERAL_ERROR=1, USAGE_ERROR=2,
     CONFIG_ERROR=3, INPUT_ERROR=4, NETWORK_ERROR=5, AI_ERROR=6,
     INTERRUPTED=7, UNKNOWN=8.
I16: SGRenderer class (console.py) — singleton, properties: console,
     is_interactive, supports_unicode, supports_color, get_icon().
I17: WizardState data model (current_step, total_steps, mode, clauses,
     jurisdiction, config_values, validation_errors, allow_back,
     last_transition).
I18: WizardStep protocol: render(), validate(), resolve_next().
I19: 4 panel functions: info_panel(), warning_panel(), error_panel(),
     success_panel().
I20: SGTable class: constructor(title, columns, rows, output_format) →
     render().
I21: Spinner class (context manager): label, spinner type, non-TTY fallback.
I22: Progress class (context manager): total, description, advance(n),
     update(desc), cancel().
I23: Prompt wrappers: select(), checkbox(), fuzzy_select(), confirm(),
     text(), password().
I24: Key bindings constants: KEY_BINDINGS frozendict mapping key →
     (action, description, component).
I25: StatusLine class (context manager): update(message), 60-char truncation.
I26: 3 header functions: separator(), breadcrumb(), step_indicator().
I27: render_markdown(text) → Rich Text (line-by-line parser, no AST).
I28: Validation functions: validate_path(), validate_config_key(),
     validate_range(), validate_not_empty(), validate_enum().
I29: Feedback functions: format_error(what, why, fix, exit_code),
     format_success(message, detail).
I30: DesignToken data model: color_roles, no_color_fallbacks, icon_map,
     ascii_icon_map, spacing, panel_padding, typography, width_thresholds,
     min_supported_width.
I31: ConfigPath data model: config_dir, config_file, auth_file, file_mode,
     env_prefix, exists, first_run.
I32: TerminalCapabilities data model: width, is_tty_stdin, is_tty_stdout,
     supports_color, supports_unicode, detected_shell.
I33: FeedbackPayload data model: what_happened, why, what_to_do, exit_code,
     severity, panel_title.
I34: OutputFormat type: table/json/plain with is_default and
     is_machine_readable booleans.
___

DEPENDENCIES
DEP1: Rich v15.0.0 (already transitive via Typer).
DEP2: questionary v2.1.1 (new dependency).
DEP3: Typer v0.26.8 (already installed).
DEP4: shellingham (already transitive via Typer).
DEP5: Existing config module (src/openreview_cli/config/) for loading/saving
      JSON config.
DEP6: Existing errors.py (extended with exit codes 0–5, 6–8).
DEP7: Existing cli/utils.py (refactored to delegate to ui/components/prompt.py).
DEP8: S-5 (CLI Wizard Redesign) — S-6 supersedes interaction patterns but
      preserves S-5's command structure and configuration logic.
DEP9: S-4 (AI Gateway) — review wizard depends on gateway configuration.
DEP10: S-2/document parsing — review processing uses parsed clauses.
DEP11: textstat (dev dependency only) — for Flesch-Kincaid readability
       validation.
___

GAPS / TODOS
G1: Spec explicitly supersedes S-5's interaction patterns but preserves its
    command structure and config logic.
G2: Section 4 UNVERIFIED items: InquirerPy fuzzy matching (deferred),
    opencode selection menu visual appearance (not replicated), config set
    model validation API (depends on gateway registry), man-page generation
    (deferred).
G3: Spec notes "Web docs and man pages" are deferred open questions.
G4: Full TUI application (Textual) explicitly out of scope.
G5: Internationalization / localization out of scope.
G6: Convergence tasks T076–T087 show gaps closed during implementation:
    some were marked "partial" or "missing" before convergence (global flags,
    setup summary, --no-pii, autocomplete, icon meanings, config set old/new
    value display, --no-spinner, help examples placement, error help suffix,
    zero-clause warning, --mode [required] marking, first-run cancel message).
G7: The spec's original 200ms first-output target was corrected to 100ms
    based on research (clig.dev/Miller 1968).
G8: Spec supersedes existing exit code scheme (5=config, 6=cost, 7=gateway,
    9=PII) with new scheme (0–8 codes).
G9: Config file format changes from YAML (S-4) to JSON (S-6) — this is a
    format divergence between specs.
════════════════════════════════════════════
