# Research: CLI Wizard UX Redesign

**Phase 0 output** | **Date**: 2026-06-27

## Dependency Verification

| Item | Source | Version | Date | Status |
|------|--------|---------|------|--------|
| questionary | https://pypi.org/pypi/questionary/json | 2.1.1 | 2025-08-28 | CONFIRMED |
| prompt_toolkit | https://pypi.org/pypi/prompt-toolkit/ | 3.0.52 | 2025-08-27 | CONFIRMED |
| rich | https://pypi.org/pypi/rich/json | 15.0.0 | matches pyproject.toml | CONFIRMED |

### questionary v2.1.1

**License**: MIT
**Runtime dep**: `prompt_toolkit>=2.0,<4.0` (BSD-3)
**Python**: >=3.9

**Core API surface**:
- `questionary.select(message, choices)` — arrow-key single-choice, returns value or None on Ctrl+C
- `questionary.checkbox(message, choices)` — Space-to-toggle, Enter-to-confirm, returns `List[str]`
- `questionary.autocomplete(message, choices)` — case-insensitive substring filter as user types
- `questionary.password(message)` — masked text input
- `questionary.text(message, validate=...)` — free-text with inline validation
- `questionary.confirm(message, default=True)` — y/n prompt
- `questionary.form(**kwargs).ask()` — sequential prompts, returns dict
- `questionary.prompt(questions)` — dict-based prompts with `when` condition support

**Ctrl+C handling**: `.ask()` returns `None` (safe). `.unsafe_ask()` raises `KeyboardInterrupt`.

**SSH/PTY**: prompt_toolkit handles this natively — "No assumptions about I/O; every app should also run in a telnet/ssh server."

**Breaking changes in last 12 months**: None. Both questionary 2.x and prompt_toolkit 3.x are stable.

### Existing codebase patterns

**Rich Table usage** (used in SetupWizard.show_summary()):
```python
table = Table()
table.add_column("Slot", style="cyan")
table.add_column("Assigned Model", style="green")
for slot in self.steps:
    model = self.slots_config[slot].get("primary", "unconfigured")
    table.add_row(slot, model)
self.console.print(table)
```

**Current wizard pain points** (SetupWizard in `gateway/wizard.py`):
- Uses `rich.prompt.Prompt.ask(choices=[...])` — forces typed input
- 5-slot loop: provider → model → API key → grouping → save
- "back" navigation via string matching on `Prompt.ask()` return value
- No summary-before-save step
- No inline validation feedback
- No non-interactive terminal guard

## Technology Decision: questionary over alternatives

| Candidate | Why rejected |
|-----------|-------------|
| **questionary** ✅ | prompt_toolkit-based, select/checkbox/autocomplete, SSH/PTY, Ctrl+C safe, MIT, maintained (2025) |
| inquirer | Last release 2015, dead project |
| PyInquirer | Last release 2020, stale fork |
| Click prompts | No arrow-key nav, no checkbox, no autocomplete |
| raw prompt_toolkit | More code needed; questionary is the idiomatic wrapper |
| Textual | Full TUI framework — out of spec scope |

## Design Decision: Separate ReviewWizard class

SetupWizard saves to config files and returns None. ReviewWizard returns a ReviewConfiguration bundle. Different contracts → different classes. Both share questionary via a common helper in `cli/utils.py`.

## Design Decision: Rich Table for summary (confirm existing pattern)

Gateway setup already uses `Rich.Table` with `Slot | Assigned Model`. Review wizard summary follows same pattern with `Setting | Value` columns. No new dependency needed.

## Architecture notes

- `SetupWizard.__init__` currently takes no arguments; `run()` returns `None`. Public interface stays unchanged.
- `ReviewWizard.__init__(file_path, **options)`; `run()` returns `ReviewConfiguration`.
- questionary owns the terminal during prompts (prompt_toolkit Application). Rich Console output is safe before/after prompts, not during.
- Existing `atomic_write` pattern in `config/utils.py` preserved for auth.json writes.
- Existing `--non-interactive` flag pattern in `app.py:gateway_setup` reused for review command.
