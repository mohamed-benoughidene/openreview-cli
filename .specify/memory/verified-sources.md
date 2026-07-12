# Verified Sources: Feature 032-tui-spec

**Generated**: 2026-07-12
**Method**: context7 docs + PyPI version checks

---

ITEM: textual
SOURCE: https://textual.textualize.io + PyPI
VERSION: 8.2.8 (current stable, confirmed 2026-07-12)
KEY FACTS:
- `app.run_test()` returns async context manager yielding `Pilot` for headless testing
- `Button.Pressed` event with `event.button.id` for handling button clicks
- `set_interval(interval, callback, *, name=None, repeat=0, pause=False)` on message pump
- `action_show_tab(tab: str)` pattern — set `TabbedContent.active` attribute
- `Input(password=True)` masks typed characters (built-in reactive attribute)
STATUS: CONFIRMED

---

ITEM: textual — TabbedContent / TabPane
SOURCE: https://textual.textualize.io/widgets/tabbed_content
VERSION: 8.2.8
KEY FACTS:
- `TabbedContent` with `TabPane("Label", id="id")` children
- `initial="tab_id"` sets default active tab
- Programmatic switch: `self.query_one(TabbedContent).active = "tab_id"`
- Nested TabbedContent supported
STATUS: CONFIRMED

---

ITEM: textual — DirectoryTree
SOURCE: https://textual.textualize.io/widgets/directory_tree
VERSION: 8.2.8
KEY FACTS:
- Subclass `DirectoryTree` and override `filter_paths(paths)` to hide files
- No built-in `show_hidden` attribute — filter via `filter_paths` method
- Spec's Ctrl-H toggle requires reactive state + `filter_paths` override
STATUS: CONFIRMED (pattern exists; no direct `show_hidden` attribute — needs custom implementation)

---

ITEM: textual — Collapsible
SOURCE: https://textual.textualize.io/widgets/collapsible
VERSION: 8.2.8
KEY FACTS:
- `Collapsible` widget with `collapsed` (bool) and `title` (str) reactive attributes
- `Toggled` event with `.collapsible` reference
- Used for collapsing/expanding content sections
STATUS: CONFIRMED

---

ITEM: textual — notify()
SOURCE: https://textual.textualize.io/api/app
VERSION: 8.2.8
KEY FACTS:
- `notify(message, *, title="", severity="information", timeout=None, markup=True)`
- Severity levels: `information`, `warning`, `error`
- Thread-safe, shows Toast notification
- Supports Rich console markup when `markup=True`
STATUS: CONFIRMED

---

ITEM: textual — action_quit_or_warn
SOURCE: context7 / Textual source
VERSION: 8.2.8
KEY FACTS:
- NOT a standard Textual built-in action
- Must be implemented as custom `action_quit_or_warn()` method on the App subclass
- Pattern: confirm quit if dirty state, else call `self.exit()`
STATUS: UNVERIFIED (custom action, not a framework primitive — needs implementation)

---

ITEM: pytest-asyncio
SOURCE: https://pytest-asyncio.readthedocs.io/en/stable + PyPI
VERSION: 1.4.0 (current stable)
KEY FACTS:
- `asyncio_mode = "auto"` in `[tool.pytest.ini_options]` auto-marks all async test functions
- Auto mode recommended for asyncio-only projects
- `strict` mode (default) requires explicit `@pytest.mark.asyncio` decorator
- Compatible with pytest 8.x and Python 3.12
STATUS: CONFIRMED

---

ITEM: pydantic
SOURCE: https://docs.pydantic.dev + PyPI
VERSION: 2.13.4 (current stable)
KEY FACTS:
- No built-in `from_config` classmethod — pattern built via `@model_validator(mode='before')` or `model_validate()`
- `ConfigDict(from_attributes=True)` for ORM/object validation
- `@classmethod` validators receive raw dict in `mode='before'`
- `model_validate(data)` creates instance from dict
STATUS: CONFIRMED (no direct `from_config`; pattern is standard Pydantic v2 practice)

---

ITEM: rich
SOURCE: https://rich.readthedocs.io + PyPI
VERSION: 15.0.0 (current stable), installed: 13.7.1
KEY FACTS:
- Rich is Textual's rendering backend — same author (Textualize)
- Rich 13.x installed in workspace; 15.0.0 available on PyPI
- No breaking changes for Textual 8.2.8 between 13.x and 15.x
- Textual pins its own Rich version requirement
STATUS: CONFIRMED

---

ITEM: typer
SOURCE: https://typer.tiangolo.com + PyPI
VERSION: 0.26.8 (current stable)
KEY FACTS:
- Existing dependency, no version pinned in plan
- Compatible with Python 3.12
- Used for CLI subcommands (unchanged by TUI feature)
STATUS: CONFIRMED

---

ITEM: questionary
SOURCE: https://github.com/tmbo/questionary + PyPI
VERSION: 2.1.1 (current stable)
KEY FACTS:
- Existing dependency, retained for non-TUI subcommands
- Uses prompt_toolkit under the hood
- TUI replaces questionary's interactive prompts within the TUI session
STATUS: CONFIRMED

---

ITEM: asyncio_mode=auto configuration
SOURCE: https://pytest-asyncio.readthedocs.io/en/stable/concepts.html
VERSION: N/A (config pattern)
KEY FACTS:
- Set in `pyproject.toml` under `[tool.pytest.ini_options]`
- `asyncio_mode = "auto"` — no per-test `@pytest.mark.asyncio` needed
- Default is `strict` if not specified
- Existing project uses this pattern (per plan.md)
STATUS: CONFIRMED

---

## Summary Counts

| Metric | Count |
|--------|-------|
| **TOTAL ITEMS** | 12 |
| **CONFIRMED** | 11 |
| **UNVERIFIED** | 1 |
| **FETCH FAILED** | 0 |

## Version Drift Notes

| Dep | Plan/Spec says | PyPI current | Drift? |
|-----|---------------|-------------|--------|
| textual | >=8.2.8 | 8.2.8 | None |
| pydantic | (no version in plan) | 2.13.4 | N/A |
| rich | (existing, no version pinned) | 15.0.0 (installed 13.7.1) | Minor — Textual handles its own Rich pin |
| typer | (existing, no version pinned) | 0.26.8 | N/A |
| questionary | (existing, no version pinned) | 2.1.1 | N/A |
| pytest-asyncio | (no version in plan) | 1.4.0 | N/A |

**No version drift concerns.** All claimed versions match current stable releases.
