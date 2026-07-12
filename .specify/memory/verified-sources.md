# Verified Sources: Feature 032-tui-spec

**Generated**: 2026-07-11
**Hook**: `speckit.research-grounding`
**Feature**: Interactive TUI (Terminal User Interface)

---

## Dependency Research Results

### 1. textual (>=8.2.8) — TUI Framework

- **SOURCE**: https://pypi.org/project/textual/
- **VERSION**: 8.2.8 (current stable, matches spec requirement exactly)
- **KEY FACTS**:
  - Rapid application development framework for Python terminal UIs
  - Built on Rich (already a project dependency), uses async I/O
  - Supports `Input(password=True)` for masked fields (FR-032a)
  - `ModalScreen` class for confirmation overlays (FR-011, FR-025)
  - `DirectoryTree` widget for file picker (FR-033-035)
  - Testing via `app.run_test()` with async `Pilot` for keyboard/mouse simulation
  - CSS-based styling with `.tcss` files
  - Mouse support on by default
- **STATUS**: CONFIRMED
- **NOTE**: Plan says >=8.2.8, PyPI shows 8.2.8 is the latest release. No version drift.

---

### 2. pytest-asyncio (>=0.24.0) — Async Test Runner

- **SOURCE**: https://pypi.org/project/pytest-asyncio/
- **VERSION**: 1.4.0 (current stable)
- **KEY FACTS**:
  - Provides asyncio support for pytest
  - `asyncio_mode = "auto"` automatically applies asyncio marker to all async tests (no `@pytest.mark.asyncio` needed)
  - Recommended default mode for projects using asyncio as sole async library
  - Configuration via `tool.pytest.ini_options` in pyproject.toml
  - Compatible with pytest 9.x
- **STATUS**: CONFIRMED
- **⚠ VERSION DRIFT**: pyproject.toml pins `>=0.24.0`, current stable is **1.4.0** (major version jump). The plan references testing via `app.run_test()` with `asyncio_mode=auto` which is confirmed as a valid configuration. Recommendation: update minimum version constraint when adding dependency.

---

### 3. pydantic (>=2.13.4) — Data Validation

- **SOURCE**: https://pypi.org/project/pydantic/
- **VERSION**: 2.13.4 (current stable, exact match)
- **KEY FACTS**:
  - Data validation using Python type hints, powered by Rust core logic
  - Already in pyproject.toml as runtime dependency
  - Used in TUI domain layer for config models
  - v2 series with strict mode support
- **STATUS**: CONFIRMED
- **NOTE**: No version drift. Already in project.

---

### 4. rich (>=15.0.0) — Terminal Formatting

- **SOURCE**: https://pypi.org/project/rich/
- **VERSION**: 15.0.0 (current stable, exact match)
- **KEY FACTS**:
  - Rich text and beautiful formatting in the terminal
  - Foundation dependency of Textual (Textual is built on Rich)
  - Already in pyproject.toml as runtime dependency
  - Supports tables, progress bars, markdown, syntax highlighting
- **STATUS**: CONFIRMED
- **NOTE**: No version drift. Already in project.

---

### 5. typer (>=0.26.7) — CLI Framework

- **SOURCE**: https://pypi.org/project/typer/
- **VERSION**: 0.26.8 (current stable)
- **KEY FACTS**:
  - CLI framework built on Click
  - Already in pyproject.toml as runtime dependency
  - Used for existing CLI subcommands (TUI is additive, not a replacement)
  - `--no-tui` flag will be added to force CLI behavior
- **STATUS**: CONFIRMED
- **NOTE**: pyproject.toml pins `>=0.26.7`, current is `0.26.8`. Minor patch drift, no action needed.

---

### 6. questionary (>=2.1.1) — Interactive Prompts

- **SOURCE**: https://pypi.org/project/questionary/
- **VERSION**: 2.1.1 (current stable, exact match)
- **KEY FACTS**:
  - Interactive prompts library for Python
  - Already in pyproject.toml as runtime dependency
  - Retained for non-TUI subcommands (plan explicitly states this)
  - TUI replaces questionary for interactive flows within TUI context
- **STATUS**: CONFIRMED
- **NOTE**: No version drift. Already in project. TUI supersedes questionary for TUI-context interactions only.

---

## Summary

| # | Item | Plan Version | Verified Version | Status | Drift |
|---|------|-------------|-----------------|--------|-------|
| 1 | textual | >=8.2.8 | 8.2.8 | CONFIRMED | None |
| 2 | pytest-asyncio | >=0.24.0 | 1.4.0 | CONFIRMED | ⚠ Major (0.x → 1.x) |
| 3 | pydantic | >=2.13.4 | 2.13.4 | CONFIRMED | None |
| 4 | rich | >=15.0.0 | 15.0.0 | CONFIRMED | None |
| 5 | typer | >=0.26.7 | 0.26.8 | CONFIRMED | Minor patch |
| 6 | questionary | >=2.1.1 | 2.1.1 | CONFIRMED | None |

### Totals

- **TOTAL ITEMS**: 6
- **CONFIRMED**: 6
- **UNVERIFIED**: 0
- **FETCH FAILED**: 0

### POTENTIALLY STALE Items

None. All items are current as of 2026-07-11.

### Version Drift

1. **pytest-asyncio**: pyproject.toml pins `>=0.24.0`, PyPI current stable is **1.4.0**. This is a major version jump (0.x → 1.x). The `asyncio_mode = "auto"` feature referenced in the plan (T002a) is confirmed as available and recommended. When adding the dev dependency, the constraint should be updated to `>=1.0.0` or `>=1.4.0` to reflect the current stable.

2. **typer**: pyproject.toml pins `>=0.26.7`, PyPI current stable is `0.26.8`. Minor patch drift, no action needed — the `>=` constraint already covers it.

### Behavioral Claims Verified

- **Textual `Input(password=True)`**: Confirmed — Input widget supports password-style masking (FR-032a)
- **Textual `ModalScreen`**: Confirmed — available for confirmation overlays (FR-011, FR-025)
- **Textual `DirectoryTree`**: Confirmed — available for file picker (FR-033-035)
- **Textual `app.run_test()` async Pilot**: Confirmed — testing via async Pilot with keyboard/mouse simulation
- **pytest-asyncio `asyncio_mode = "auto"`**: Confirmed — automatically applies asyncio marker, no `@pytest.mark.asyncio` needed
- **Rich is Textual's foundation**: Confirmed — Textual is built on Rich, sharing the dependency family
- **Questionary retained for non-TUI subcommands**: Confirmed — plan explicitly retains it for existing CLI flows
