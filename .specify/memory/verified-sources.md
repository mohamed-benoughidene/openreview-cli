## Verified Sources — CLI UX System Design (specs/006-cli-ux-specification)

Generated: 2026-06-28 | Hook: speckit.research-grounding

---

ITEM: rich
SOURCE: https://pypi.org/project/rich/ · https://rich.readthedocs.io/en/stable/introduction.html
VERSION: 15.0.0 (released Apr 12, 2026)
KEY FACTS:
- Console: Core object for styled terminal output; word-wraps to terminal width; bbcode-like markup for inline color/style
- Live/Status: console.status() shows indeterminate spinner without blocking; spinner from cli-spinners
- Table: Flexible tables with unicode box chars; auto-resizes columns; nested renderables in cells
- Progress: Multiple flicker-free progress bars via track() or Progress; configurable columns (%  speed  ETA  file size)
- NO_COLOR: Rich respects NO_COLOR env var (v14.0.0+ treats empty NO_COLOR as disabled); also respects FORCE_COLOR and TTY_COMPATIBLE for CI; Python >=3.9.0; MIT license
STATUS: CONFIRMED

---

ITEM: questionary
SOURCE: https://pypi.org/project/questionary/ · https://questionary.readthedocs.io/
VERSION: 2.1.1 (released Aug 28, 2025)
KEY FACTS:
- select()/checkbox(): Accept prompt string + choices list; .ask() returns value synchronously; select returns single, checkbox returns list
- confirm(): Yes/no boolean; .ask()/.unsafe_ask() pattern; returns True/False or None on safe KBI
- text()/password(): Free-text input; password() masks input; patch_stdout=True for thread-safe rendering
- Keyboard handling: Safe (.ask()) catches Ctrl+C, prints "Cancelled by user", returns None; unsafe (.unsafe_ask()) raises KeyboardInterrupt; kbi_msg customizable
- Non-interactive: No built-in fallback — callers must handle None return or catch KeyboardInterrupt; ask_async/unsafe_ask_async for asyncio; Python >=3.9; MIT License. Maintainer: Tom Bocklisch (tmbo)
STATUS: CONFIRMED

---

ITEM: typer
SOURCE: https://pypi.org/project/typer/ · https://typer.tiangolo.com/
VERSION: 0.26.8 (released Jun 26, 2026)
KEY FACTS:
- Command registration: app.command() decorator; multi-command apps require command name; custom names via @app.command("custom-name")
- Shell completion: Built-in for Bash, Zsh, Fish, PowerShell; auto-generates --install-completion and --show-completion flags; uses shellingham for shell detection
- Exit codes: typer.Exit(code=1) raises SystemExit with code; typer.Abort() prints "Aborted." and exits 1
- Echo/secho/style: typer.echo() prints to stdout/stderr; secho() = echo() + style() in one call; style() applies fg/bg/bold/dim/underline; Rich integration automatic
- Context object: ctx.obj for shared state; ctx.params dict; ctx.invoked_subcommand; ctx.resilient_parsing; available by declaring parameter of that type
STATUS: CONFIRMED

---

ITEM: InquirerPy
SOURCE: https://pypi.org/project/InquirerPy/ · https://github.com/kazhala/InquirerPy
VERSION: 0.3.4
KEY FACTS:
- Last PyPI release: June 27, 2022 — nearly 4 years old
- GitHub last push: August 1, 2024 — minor maintenance only; 43 open issues; 6 contributors
- Development Status: Pre-Alpha classifier despite functional stability
- vs questionary: InquirerPy's own author recommends questionary as "a fantastic fork... already a well established and stable library"; InquirerPy only needed for extra customization or fuzzy prompt
- Maintenance: Effectively dormant — no releases in 4 years; no active triage on 43 issues
STATUS: POTENTIALLY STALE — 4 years since last release; questionary is the actively maintained alternative

---

ITEM: gh
SOURCE: https://cli.github.com/ · https://github.com/cli/cli/releases
VERSION: v2.95.0 (released Jun 17, 2026)
KEY FACTS:
- Verb-noun command structure: gh pr list, gh issue create — mirrors git subcommand pattern
- Rich help output: Every subcommand has --help with flags, --json/--jq for programmatic use
- Interactive prompts: Built-in workflow mode for gh pr create with multi-step prompts (title, body, prerelease check, submit)
STATUS: CONFIRMED

---

ITEM: gum
SOURCE: https://github.com/charmbracelet/gum/releases
VERSION: v0.17.0 (released Sep 5, 2025)
KEY FACTS:
- 13 interactive components: choose, confirm, file, filter, format, input, join, pager, spin, style, table, write, log
- Styling via Lip Gloss: Every element customizable via --flags or GUM_* env variables; --cursor.foreground, --prompt.foreground, --padding
- Terminal compatibility: Auto-detects TTY vs pipe; falls back gracefully; COSIGN-signed releases; Linux/macOS/Windows/FreeBSD/OpenBSD/NetBSD
STATUS: CONFIRMED

---

ITEM: clig.dev
SOURCE: https://clig.dev/
VERSION: N/A (guidelines, not versioned)
KEY FACTS:
- Exit codes: Return zero on success, non-zero on failure; map non-zero to important failure modes
- stdout vs stderr: Primary output to stdout; log/error messages to stderr
- Verb-noun structure: "noun verb" ordering most common; e.g. docker container create
- Flag naming: Prefer flags to args; full-length versions of all flags; single-letter only for common flags; standard names: -d/--debug, -f/--force, --json, -h/--help, -n/--dry-run, -q/--quiet
- Error messages: Catch errors and rewrite for humans; most important info at end; signal-to-noise ratio crucial
- Responsiveness: "Print something to the user in <100ms" — clig.dev says 100ms, not 200ms
STATUS: CONFIRMED

---

ITEM: 200ms responsiveness threshold
SOURCE: Miller 1968 (canonical); Nielsen Alertbox; Google Core Web Vitals; U Luebeck 2017; Superhuman engineering
VERSION: N/A (research metric)
KEY FACTS:
- HCI research (Miller 1968): 100ms perceived as instantaneous; 1s = limit for continuous flow
- Modern research (U Luebeck 2017): Users perceive latencies as low as 60ms
- Web metrics (Google INP): <=200ms = "good" (web rendering, not general HCI)
- Product practice (Superhuman): Targets 50-60ms internally; promotes "100ms rule"
- CORRECTION: The 200ms figure is a web performance metric (Google INP), not the canonical HCI perception threshold. HCI literature says 100ms is "instantaneous"
STATUS: CONFIRMED (with correction: 100ms is the HCI threshold; 200ms is web-specific)

---

ITEM: Python error message design
SOURCE: https://docs.python.org/3/library/traceback.html · https://clig.dev/ · multiple implementation sources
VERSION: N/A (Python 3.12+ stdlib)
KEY FACTS:
- Traceback suppression: raise CustomError("msg") from None; sys.tracebacklimit = 0 hides lines entirely; __suppress_context__ = True
- Standard pattern: try/except -> traceback.format_exc() -> sys.stderr.write() for debug; clean user message to stdout/stderr
- clig.dev aligned: Catch errors and rewrite for humans; signal-to-noise ratio crucial; most important info at end
- Python 3.13+: Traceback output colorized by default; controllable via env vars; traceback.print_exception() supports chain=True/False
STATUS: CONFIRMED
