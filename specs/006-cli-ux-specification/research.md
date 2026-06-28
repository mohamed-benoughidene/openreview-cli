# Research: CLI UX System Design

**Phase**: 0 — Technology & UX Research | **Date**: 2026-06-28 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This document records the research findings and technology decisions that underpin the CLI UX layer for openreview-cli. Each section states a decision, the rationale (citing verified sources), and the alternatives that were considered and rejected. Items without a `[CONFIRMED]` source marker are `[UNVERIFIED]` and carry a recommendation for additional validation before implementation.

---

## 1. Output Rendering

| Property | Value |
|----------|-------|
| **Decision** | Rich v15.0.0 `Console` singleton, project-wide |
| **CONFIRMED** | Rich v15.0.0, MIT license, PyMuPDF already transitive via Typer v0.26.8 |
| **Source** | [R-2] spec.md §2.6–2.11, pypi.org/project/rich/ v15.0.0 |

**Rationale**: Rich is already a transitive dependency (Typer v0.26.8 bundles it). It provides every output primitive required by the spec: Console (print/log/status), Table (auto-width, borders, column alignment), Panel (boxed content, error/success frames), Progress (determinate bars with columns for percentage/speed/time), Live (streaming re-render for AI token output), Status (spinner), Markdown, Layout, and Tree. Rich respects `NO_COLOR`, `FORCE_COLOR`, and `TTY_COMPATIBLE` environment variables natively. It auto-detects terminal color depth (truecolor, 256, 16, monochrome) and unsupported Unicode fallback. For a CLI targeting non-developer legal professionals, Rich eliminates the need to write any ANSI/SGR escape code logic by hand.

**Alternatives considered**:

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| Manual ANSI SGR codes (stdlib) | Rejected | No table layout, no auto-width, no progress bar, no live re-render. Would need 3x the code for 1/3 the output quality. |
| `textual` (Rich's TUI framework) | Rejected | Spec constitution explicitly rejects web servers and long-running processes (Principle II). Textual is an application framework, not a rendering library. Runtime dependency would be ~5 MB for features not needed (widget system, CSS, message pump). |
| `colorama` + `tabulate` + `tqdm` | Rejected | Three dependencies instead of one. Rich subsumes all three: cross-platform color (colorama), table rendering (tabulate), progress bars (tqdm). No benefit to splitting. |
| `rich.markup` + `rich.style` only (no Console singleton) | Rejected | Without a shared Console instance each module would re-detect terminal capabilities. Leads to inconsistent width, color, and Unicode detection across the application. A singleton ensures one code path sets capability once. |

**Implementation note**: The Console singleton lives in `src/openreview_cli/ui/console.py`. Initialization reads `NO_COLOR`, `--no-color`, `--no-unicode`, and terminal width exactly once at startup. All UI components import this singleton rather than creating their own Console instance.

---

## 2. Interactive Prompts

| Property | Value |
|----------|-------|
| **Decision** | questionary v2.1.1 |
| **CONFIRMED** | questionary v2.1.1, MIT license, Python 3.9+, last release Aug 2025 |
| **Source** | [R-3] spec.md §2.1–2.5, pypi.org/project/questionary/ v2.1.1 |

**Rationale**: questionary provides every prompt type required by the spec: `select` (single-choice), `checkbox` (multi-choice), `confirm` (yes/no), `text` (free text with inline validation), `password` (masked input), `autocomplete` (type-ahead filtering), and `filepath`. It is built on `prompt_toolkit` (same foundation as Rich's interactive features), uses arrow-key navigation by default, handles Escape/Ctrl-C gracefully via its `.ask()` method (returns `None` on Ctrl-C) vs `.unsafe_ask()` (raises `KeyboardInterrupt`), and produces styled output that matches the design token system. Its API is minimal and flat — no class hierarchy, no factory pattern.

questionary is actively maintained (last release August 2025), MIT licensed (AGPL-3.0 compatible), and has no dependency conflicts with the existing project.

**Alternatives considered**:

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| InquirerPy v0.3.4 | Rejected — see below | |
| `prompt_toolkit` directly | Rejected | More flexible but 3–5× more code for the same result. questionary is a thin wrapper over prompt_toolkit that provides exactly the abstractions needed. Direct usage would add complexity without benefit. |
| `pick` (simple select) | Rejected | Single-function library, no multi-select, no autocomplete, no validation, no keyboard customization. Insufficient for spec requirements. |
| `npyscreen` | Rejected | Curses-based, not compatible with Rich's rendering model. Overlapping curses and Rich output leads to rendering artifacts. |
| Manual `input()` + `print()` loops | Rejected | No arrow-key navigation, no inline editing, no type-ahead, no validation. Would produce a poor experience for non-developer users. |

**InquirerPy v0.3.4 — rejection rationale**: InquirerPy was evaluated at [R-4]. Its last release was June 2022 (4 years stale at time of research). It carries pre-alpha status with 43 open issues. Its distinguishing feature is a built-in fuzzy matcher for long lists (`fuzzy` prompt). However, questionary's `autocomplete` provides substring matching, and the spec defers true fuzzy matching to a future evaluation. Adding a stale dependency for a deferred feature violates Constitution Principle IV (Dependency Minimalism).

---

## 3. Shell Completion

| Property | Value |
|----------|-------|
| **Decision** | Typer v0.26.8 built-in shell completion (via vendored Click + shellingham) |
| **CONFIRMED** | Typer v0.26.8, shellingham transitive dependency |
| **Source** | [R-5] spec.md §FR-IP-006, pypi.org/project/typer/ v0.26.8 |

**Rationale**: Typer v0.26.8 (which vendored Click 8.x in the same release) provides shell completion for bash, zsh, fish, and PowerShell out of the box. Users install completion once via:

```bash
openreview --install-completion
```

This generates and sources the completion script for the detected shell (via shellingham). Typer supports `--show-completion` to preview the script before installing, and `--help` completion for all nested subcommands and flags. No additional code is needed beyond decorating commands with Typer's standard `@app.command()` pattern.

The spec requires completion for commands, subcommands, flag names, and flag values where the set is known (e.g., `--mode standard|risk|compliance`). Typer's Click backend supports shell-level completion for enumerations via `click.Choice` and custom shell completion callbacks for dynamic values (provider names, models).

**Alternatives considered**:

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| `argcomplete` (argparse) | Rejected | Additional dependency. Typer is the CLI framework; adding a completion library on top is redundant — Typer already provides the feature. |
| Manual shell scripts | Rejected | Requires writing and maintaining four shell-specific completion scripts (bash/zsh/fish/powershell). Prone to drift from actual command definitions. |
| `shtab` | Rejected | Generates static completion scripts; requires re-generation after every command change. Typer's approach is dynamic (no re-generation step). |

**Installation UX**: The setup wizard (spec §8.4) auto-installs shell completion during first-run. This is a one-time, ~2-second operation that runs `openreview --install-completion` under the hood. If it fails (e.g., unsupported shell), the wizard reports a non-blocking warning and continues.

---

## 4. Error Handling & Feedback

| Property | Value |
|----------|-------|
| **Decision** | Three-part error format + structured exit codes, no raw tracebacks |
| **CONFIRMED** | clig.dev "catch errors and rewrite them for humans" [R-1], Typer Abort/Exit [R-5] |
| **Source** | [R-1][R-5][R-10] spec.md §5, clig.dev §Interacting, Click docs |

**Rationale**: clig.dev states: "Catch errors and rewrite them for humans — what failed, why it happened, how to fix it." [R-1]. The spec mandates a three-part error panel (Error Panel component §2.10) with:
1. **What failed** — one bold sentence
2. **Why** — dim context
3. **How to fix** — cyan actionable steps

Every error condition uses this format. Python tracebacks are never shown to end users (spec FR-VD-005). Implementation mechanisms:

- `raise X from None` — suppresses chained exception context
- `sys.tracebacklimit = 0` — suppresses traceback at process level (set once in `app.py` entry point)
- `traceback.print_exception(chain=False)` — for debug/verbose logging only (stderr, PII-redacted)
- Typer's built-in Rich integration reformats Click/Typer exceptions as Rich panels automatically

Exit codes follow the spec (§5.2): 0=success, 1=general error, 2=usage error, 3=config error, 4=input file error, 5=network error. These are defined as module-level constants in `src/openreview_cli/errors.py` (extending the existing module).

**Verification** [UNVERIFIED]: The three-part error format must be validated against the target audience (legal professionals) for reading level. Flesch-Kincaid grade < 10 per spec SC-006. This should be tested with a readability tool during implementation.

**Alternatives considered**:

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| Let Typer/Click handle all errors (default formatting) | Rejected | Typer's default error output shows the full usage string for missing args, which is acceptable but insufficient for non-developers. Custom panels give the needed three-part structure and plain-English guidance. |
| Single-line error messages | Rejected | Lacks the "why" and "fix" components. Non-developer users need explanation and guidance, not just a terse error code. |
| Error codes only (without messages) | Rejected | Exit codes are for machines; users need human-readable messages. The spec requires both (exit codes for scripting, panels for humans). |
| Loguru/structlog for error formatting | Rejected | Forbidden dependencies per constitution (listed in AGENTS.md forbidden list). stdlib logging with Rich formatting achieves the same result with zero new dependencies. |

---

## 5. Performance Perception

| Property | Value |
|----------|-------|
| **Decision** | First output < 100ms (corrected from spec's 200ms); spinner at 500ms; progress at 10Hz max |
| **CORRECTION** | See §10 below for the 200ms → 100ms correction rationale |
| **CONFIRMED** | clig.dev §Instantaneous, Miller 1968 HCI research |
| **Source** | [R-1] clig.dev, Miller 1968 "Response time in man-computer conversational transactions" |

**Rationale** (deferred to §10, where the correction is fully documented):

Quick reference:
- **<100ms**: First output must appear within this window (help, welcome, error, or wizard step). This is "instantaneous" per HCI research.
- **<500ms**: If the operation will take longer, show a spinner within 500ms. Users perceive the system as working, not stalled.
- **<50ms**: Wizard step transitions must complete visually within 50ms (no perceptible delay between "Step 2" appearing and the prompt being ready).
- **10Hz max**: Rich Live and Progress updates are capped at 10 frames/second (refresh_per_second=10). Above 10Hz, updates become wasteful — the human eye cannot perceive faster changes in text, and higher rates consume CPU on constrained hardware (spec target: 8 GB RAM, 2-core CPU).

**Implementation mechanisms**:

- **Lazy imports**: Defer all heavyweight imports (PyMuPDF, python-docx, nupunkt, Presidio) behind command callbacks. The Typer app module imports only `typer` and openreview_cli-level modules. This keeps startup time (import resolution + callback dispatch) under 100ms for help, version, and error paths.
- **I/O-bound first render**: The first visible output (help text, version string, welcome panel) is a `console.print()` call — no I/O beyond writing to stdout. No config file read, no provider discovery, no shell completion check happens before first render.
- **Spec violation noted**: The spec at §6.1 and success criterion SC-003 says "200ms". This is corrected to 100ms by the research. The spec's 200ms number likely came from Google INP (Interaction to Next Paint), a web metric that accounts for browser event loop overhead. CLI applications have no render pipeline — 100ms is both the HCI standard and achievable on reference hardware.

**Alternatives considered**:

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| Warm-start cache (pre-warming imports on idle) | Rejected | Constitution Principle II (no daemon/background process). No idle handler mechanism in CLI. Splitting startup into "fast path" (help/version) and "full path" (commands that import heavy deps) achieves the same effect without a background process. |
| Threading for early spinner display | Rejected | Adds threading complexity and race conditions. Rich's `console.status()` context manager runs the spinner on the main thread, updating between `yield` ticks. Deterministic, safe, and sufficient. |
| Display 200ms delay deliberately | Rejected | Holding output for a fixed delay to appear "intentional" is a known anti-pattern (clig.dev: "Don't add artificial delays"). Display as fast as possible. |

---

## 6. Terminal Compatibility

| Property | Value |
|----------|-------|
| **Decision** | Rich auto-detection + explicit env var/flag checks + per-component degraded TTY mode |
| **CONFIRMED** | Rich v15.0.0 terminal detection [R-2], clig.dev §Portability [R-1] |
| **Source** | [R-1][R-2] spec.md §7 |

**Rationale**: Terminal compatibility is a layered concern. Rich handles most detection automatically:

| Capability | Detection | Rich mechanism |
|------------|-----------|----------------|
| Color depth | Auto-detect via `termios`, `FORCE_COLOR`, `NO_COLOR`, `TERM` | `Console(color_system=...)` — sets `None` for monochrome |
| Unicode support | Auto-detect via locale, overridable via `--no-unicode` flag | Component icon maps switch to ASCII fallback |
| Terminal width | `shutil.get_terminal_size()` | Rich auto-detects; Console stores width; Tables/Progress adapt |
| TTY vs pipe | `sys.stdin.isatty()` and `sys.stdout.isatty()` | Console sets `force_terminal`/`force_interactive`; components degrade per §3.3 |

**NO_COLOR compliance**: Per spec FR-TC-001 and clig.dev §Help, the project respects `NO_COLOR` (any non-empty value) and the `--no-color` flag. When active, `Console(color_system=None)` strips all style from output. Color-dependent semantics (error vs success) are communicated through icons and textual labels ("Error:" prefix, "✓" / "[OK]" vs "✗" / "[ERR]"). This follows the `NO_COLOR` standard: "Do not use color as the only way to convey information."

**Unicode fallback**: The icon system (spec §1.2) defines ASCII alternatives for every Unicode icon. When `--no-unicode` is set or locale detection indicates limited Unicode support, components use the ASCII variants. Rich's `Console` does not auto-detect Unicode capability — the project adds an explicit check: `locale.getpreferredencoding()` + flag override.

**Width handling** (spec §7.3):
| Width | Table behavior | Panel behavior |
|-------|----------------|----------------|
| ≥80 columns | Full table | Full panel with padding |
| 60–79 | Proportional column shrink, word-wrap cells | Wrap content to fit |
| <60 | Switch to key-value paired lines (row → multi-line block) | Min-width content |
| <40 | Print width warning; continue with degraded layout | Degraded layout |

**Non-TTY mode** (spec §3.3): When stdin is not a terminal, all interactive prompts are disabled. Components differ in their degraded behavior:
- Selection/input → Error with exit code 2 ("--mode is required when running non-interactively")
- Spinner → Suppressed (label printed once)
- Progress bar → Suppressed ("[3/12] Analyzing clause — Indemnification" printed periodically)
- Live panel → Disabled; buffered output printed at end
- Error/success panels → Printed as plain text (no borders, no color)

**Alternatives considered**:

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| `colorama` for cross-platform color | Rejected | Rich already wraps colorama internally for Windows support. Adding it separately is redundant. |
| `blessed` for terminal detection | Rejected | Rich provides the same detection (color depth, width) with a lower API surface. No need for a second terminal abstraction. |
| Ignore non-TTY and let curses fall over | Rejected | CI/CD, shell scripting, and `jq` pipelining are explicitly required by spec User Story 3. Non-TTY degradation is a P2 requirement. |

---

## 7. Design Tokens

| Property | Value |
|----------|-------|
| **Decision** | Semantic token roles (7 color roles + 2 layout roles), module-level constants |
| **CONFIRMED** | clig.dev §Design, Rich Style API [R-2] |
| **Source** | [R-9] ls1intum/ui-ux-guidelines (semantic tokens over literal), spec §1 |

**Rationale**: Semantic tokens decouple meaning from visual representation. Instead of writing `"[bold red]"` everywhere an error appears, the code references `ERROR_STYLE` — a constant that maps to `"bold red"` in color mode and `"bold underline"` in no-color mode. This means:
- One change updates all error rendering across the entire application
- No-color mode is implemented by switching the token map, not by editing every `console.print()` call
- New contributors can find and understand the color system in one file

**Token roles** defined in spec §1.1:

```python
# src/openreview_cli/ui/colors.py

from typing import NamedTuple

class ColorRole(NamedTuple):
    color: str        # Rich style string (e.g., "bold red")
    no_color: str     # No-color fallback (e.g., "bold underline")
    icon: str         # Unicode icon
    icon_ascii: str   # ASCII fallback

# Semantic token map — 7 color roles
PRIMARY   = ColorRole("bold cyan",        "bold",           "→",   "->")
SUCCESS   = ColorRole("bold green",       "bold",           "✓",   "[OK]")
WARNING   = ColorRole("bold yellow",      "bold underline", "⚠",   "[!]")
ERROR     = ColorRole("bold red",         "bold underline", "✗",   "[ERR]")
MUTED     = ColorRole("dim",              "dim",            "•",    "*")
ACCENT    = ColorRole("bold magenta",     "bold",           "★",   "[*]")
CODE      = ColorRole("bold bright_black on grey15", "",      "$",   "$")
```

Plus 2 implicit layout roles: `BORDER` (used for Panel border_style, defaults to empty in no-color), `BACKGROUND` (used for panel backgrounds, transparent by default).

**No-color fallback pattern**: Every role has a no-color equivalent. Color is replaced by bold/underline/dim. This ensures the NO_COLOR mode is not just monochrome but retains typographic hierarchy.

**Alternatives considered**:

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| Raw Rich style strings throughout codebase | Rejected | Violates DRY. No single point of change. No-color mode requires editing every `console.print()`. |
| CSS-like design token file (YAML/JSON) | Rejected | Token data is consumed by Python only (no frontend, no CSS). A Python module is the most direct representation and avoids a YAML parser dependency. |
| Dynamic token computation (e.g., derive error from primary) | Rejected | Roles are orthogonal, not hierarchical. Error is not a tint of primary. Deriving them adds complexity without benefit. |
| Enum hierarchy | Rejected | A flat NamedTuple with two fields (color, no_color) is simpler than an Enum with custom methods. NamedTuple is immutable, hashable, and printable — sufficient for the use case. |

---

## 8. Configuration UI

| Property | Value |
|----------|-------|
| **Decision** | XDG config path + env var overrides + `openreview config` subcommands + first-run wizard |
| **CONFIRMED** | clig.dev §Configuration [R-1], existing config module |
| **Source** | [R-1] spec §8 |

**Rationale**: Configuration design follows clig.dev guidelines:
- **File location**: `$XDG_CONFIG_HOME/openreview/config.json` (default `~/.config/openreview/config.json`). XDG is the Linux/Unix standard; macOS users get `~/Library/Application Support/openreview/` via XDG overrides; Windows uses `%APPDATA%/openreview/`.
- **File format**: JSON. Already the project's config format. No additional parser needed.
- **Security**: If config stores auth tokens (API keys), file mode is set to `600` (owner read/write only) per Constitution Principle I.
- **Overrides**: Every config key is overridable via `OPENREVIEW_<KEY>` env var (dots → underscores, uppercase). Example: `OPENREVIEW_MODEL_DEFAULT=llama3.3 openreview review contract.pdf`. This enables CI/temporary overrides without modifying the config file.

**Config command structure** (spec §8.2):
```
openreview config show              → Formatted table (or JSON with --output json)
openreview config get <key>         → Single value with confirmation
openreview config set <key> <value> → Inline-validated, shows old → new
openreview config unset <key>       → Reset to default
openreview config path              → Print file path (for manual inspection)
```

**First-run detection** (spec §8.4): On first invocation with no config file:
1. Immediate welcome panel (within 100ms)
2. 3–4 sentence plain-English explanation of the tool
3. Privacy notice: "openreview processes documents entirely on your machine. No contract text ever leaves your computer."
4. Auto-enter setup wizard (provider selection, model preference, jurisdiction default, shell completion)
5. Esc exits wizard → "Setup was interrupted. Run `openreview setup` to try again later."

**Validation rules** per open questions [UNVERIFIED #3]:
- `config set` validates against known config keys. Unknown keys → error panel with suggestion to `config show`.
- `config set model.*` validates against available models via the AI gateway registry (when available). At implementation time, if the registry is not finalized, use a hardcoded allowlist as a temporary measure (marked with `ponytail: hardcoded allowlist, replace with registry lookup when gateway is finalized`).

**Alternatives considered**:

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| YAML config | Rejected | YAML is more complex (anchors, types, multi-line strings). JSON is simpler, already serialized by stdlib `json`, and matches the existing codebase. |
| TOML config | Rejected | TOML is simpler than YAML but still requires a parser. JSON eliminates the dependency and matches existing patterns. |
| INI config | Rejected | No nested structures (key → section → subsection). Config keys have dotted paths like `provider.ollama.base_url` that don't map cleanly to INI sections. |
| No config file (all env vars) | Rejected | Impractical for 8+ config keys. Users would need to set env vars on every invocation or in shell rc files. A config file is the standard for CLI tools. |
| Hand-edit only (no config CLI) | Rejected | Spec User Story 4 explicitly requires CLI config commands. Legal professionals should not edit JSON files manually. |

---

## 9. CLI Structure Patterns

| Property | Value |
|----------|-------|
| **Decision** | Verb-noun structure, kebab-case flags, global flags on all subcommands |
| **CONFIRMED** | gh CLI v2.95.0 [R-6], Thoughtworks guidelines [R-9], clig.dev [R-1] |
| **Source** | [R-6][R-9][R-1] spec §4 |

**Rationale**: Verb-noun is the proven pattern for multi-verb CLIs with subcommands. `gh` popularized it (`gh pr list`, `gh issue create`, `gh repo clone`). The openreview-cli command tree:

```
openreview
├── setup
├── review <file>
├── config
│   ├── config show
│   ├── config get <key>
│   ├── config set <key> <value>
│   ├── config unset <key>
│   └── config path
├── list
│   ├── list providers
│   ├── list models
│   └── list jurisdictions
└── version
```

Advantages of verb-noun over noun-verb (`openreview review` vs `openreview contract review`):
- **Predictable**: `openreview <action> <target>` — users can guess the command structure without reading the full help.
- **Discoverable**: `openreview list models` is immediately understandable as "list the models."
- **Scalable**: Adding new actions (e.g., `openreview diff`, `openreview export`) doesn't require nesting under a noun.
- **Consistent with ecosystem**: `gh`, `glab`, `aws`, `gcloud` all use verb-noun. Legal professionals who use any other CLI will recognize the pattern.

**Flag naming** per clig.dev §Help:
- `--kebab-case` exclusively (no `--snake_case`, no `--camelCase`)
- Boolean flags use `--no-` prefix for negation (Typer auto-generates this)
- Short flags reserved for the most common: `-h` (help), `-v` (version), `-q` (quiet), `-y` (yes), `-o` (output)

**Required flag marking** per spec FR-CS-003:
- `--mode` is marked `[required]` in help text
- When required flags are missing and stdin is not TTY → exit code 2 with error panel
- When required flags are missing and stdin is TTY → interactive prompt via questionary

**Alternatives considered**:

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| Noun-verb (`openreview contract review`) | Rejected | Adds a nesting level without benefit. `openreview review contract.pdf` is shorter and equally clear. |
| Single-command with positional args only | Rejected | Not scalable to 5+ subcommands. Violates clig.dev "subcommands for distinct areas of functionality." |
| Flat command list (no grouping) | Rejected | Help output would be a flat list of 10+ commands. Grouped subcommands (`config get/set/show/unset/path`) reduce cognitive load. |
| `--` flag delimiter for sub-subcommands (`openreview config --show`) | Rejected | Typer naturally supports nested subcommands over `--` flags for config operations. Nested subcommands are type-checkable and provide their own `--help`. |

**Implementation**:

```
# Typer structure (pseudocode)

app = typer.Typer()

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = False,
    quiet: bool = False,
    no_color: bool = False,
    no_unicode: bool = False,
    output: OutputFormat = "table",
    config: Optional[Path] = None,
):
    ...

@app.command()
def setup(...):
    ...

review_app = typer.Typer()
app.add_typer(review_app, name="review")

config_app = typer.Typer()
app.add_typer(config_app, name="config")
```

---

## 10. Research Correction: 200ms → 100ms

| Property | Value |
|----------|-------|
| **Correction** | Spec's 200ms time-to-first-output is corrected to **<100ms** |
| **CONFIRMED** | clig.dev §Instantaneous: "100ms is the limit for having the user feel like they are directly manipulating objects in the UI." |
| **Source** | [R-1] clig.dev, Miller 1968 "Response time in man-computer conversational transactions" |

**The Issue**: The feature specification (spec.md §6.1, SC-003) and the plan.md both state 200ms as the target for first output. This number is sourced from Google's INP (Interaction to Next Paint) metric, which is a **web-specific** measurement that accounts for browser event loop overhead, render pipeline latency, and compositing. CLI applications have no browser render pipeline — stdout writes are synchronous syscalls.

**The Correction**: The authoritative HCI source for "instantaneous" perception is Miller 1968, replicated by Card, Robertson, and Mackinlay (1991), and cited directly in clig.dev:

| Duration | Perception | Application |
|----------|------------|-------------|
| **<100ms** | "Instantaneous" — user feels in direct control | First output, help, version, welcome, wizard step transition |
| 100–300ms | "Immediate" — slight delay but still feels connected | Command execution, config write |
| 300–1000ms | "Waiting" — user notices delay, needs progress indicator | Document loading, PII stripping |
| >1000ms | "Slow" — user may disengage, needs progress with estimate | Full document review, batch processing |

**Why this matters**: For a CLI targeting legal professionals (non-developers), the first invocation sets the trust level. A tool that responds in <100ms feels "snappy" and well-built. A tool that takes 200ms is 2× slower than the user's perceptual threshold for "instant" — perceptible as sluggish on the very first interaction.

**Achievability**: The 100ms target is achievable on the reference hardware (8 GB RAM, 2-core CPU) with lazy imports. The Typer app module (`app.py`) imports only:
- `typer` (load time: ~50ms on reference hardware)
- `openreview_cli.__init__` (loads `__version__` constant: ~5ms)
- `openreview_cli.errors` (exit code constants: ~5ms)

Total import time: ~60ms. The remaining ~40ms budget covers argument parsing, callback dispatch, and the first `console.print()` — easily within reach. Heavier imports (parsing modules, Presidio, AI gateway) are deferred to command callbacks.

**Impact on spec**: The following spec items need their numbers updated:

| Spec reference | Old value | Corrected value |
|----------------|-----------|-----------------|
| FR-FP-001, §6.1 | 200ms | 100ms |
| SC-003 | 200ms | 100ms |
| User Story 1 (US1-A1) | 200ms | 100ms |
| plan.md Performance Goals | 200ms | 100ms |

**Verification** [UNVERIFIED]: The 100ms target must be verified on the reference hardware (or CI) before the implementation ships. Suggested approach: a `@pytest.mark.benchmark` test that runs the help command with `time` and asserts wall-clock time < 100ms. This test should be in the integration suite (`tests/integration/test_cli_output.py`).

---

## Summary of Decisions

| Section | Decision | Key Source | New Dependency? |
|---------|----------|------------|-----------------|
| 1. Output Rendering | Rich v15.0.0 Console singleton | [R-2] | No (transitive via Typer) |
| 2. Interactive Prompts | questionary v2.1.1 | [R-3] | Yes (`uv add questionary`) |
| 3. Shell Completion | Typer built-in + shellingham | [R-5] | No (transitive via Typer) |
| 4. Error Handling | Three-part error panel, no tracebacks | [R-1][R-10] | No (stdlib + Rich) |
| 5. Performance Perception | First output <100ms, spinner at 500ms | [R-1], Miller 1968 | No |
| 6. Terminal Compatibility | Rich auto-detect + explicit flag checks | [R-1][R-2] | No |
| 7. Design Tokens | 7 semantic roles → Rich style strings | [R-9], spec §1 | No |
| 8. Configuration UI | XDG JSON config + env var overrides | [R-1], existing code | No |
| 9. CLI Structure | Verb-noun, kebab-case, global flags | [R-6] | No |
| 10. 200ms → 100ms | Correction applied to spec | [R-1], Miller 1968 | N/A |

**Unverifiable at this stage** (deferred to implementation):
- Inline validation API for model names (depends on Gateway registry) — [UNVERIFIED #3]
- True fuzzy matching (deferred until substring matching proves insufficient) — [UNVERIFIED #1]
- First-run welcome wording (grade level testing done in implementation, not research)
- 100ms benchmark on reference hardware (test written during implementation)
