# Research Notes: TUI Implementation

**Date**: 2026-07-11
**Source**: context7 (current docs as of 2026-07-11)

## Decision: TUI framework

- **Decision**: Textual 8.2.8
- **Rationale**: Same author as Rich (already a dep). Built on Rich. Active maintenance (latest release 2026-06-30). Provides all required primitives: App, Screen, ModalScreen, TabbedContent, DataTable, OptionList, ListView, DirectoryTree, Input with `password=True`, ProgressBar, BINDINGS. Async-first (matches existing PAKTON pipeline). Pilot framework for testing.
- **Source (version)**: https://github.com/textualize/textual/blob/main/CHANGELOG.md
- **Source (screens/modals)**: https://github.com/textualize/textual/blob/main/docs/guide/screens.md
- **Alternatives considered**:
  - **prompt_toolkit** (already a transitive dep via questionary): lower-level, would require building tabbed UI from scratch. Higher dev cost.
  - **Textual** wins on built-in widgets, screen stacking, and testing framework.

## Decision: TTY detection at entry point

- **Decision**: `sys.stdin.isatty()` check in `app.py` BEFORE any Textual import. If false, print friendly message and `sys.exit(0)`.
- **Rationale**: Textual itself checks TTY but only after expensive imports. We want the cheap check first to keep the no-TUI exit fast (per FR-001a).
- **Source**: https://github.com/textualize/textual/blob/main/textual/src/textual/drivers/linux_driver.py (Textual's internal pattern uses `sys.__stdin__.isatty()`).
- **Alternatives considered**:
  - Letting Textual handle it: Textual raises an exception in headless mode, but the exception is not user-friendly and arrives after a slow import. Our check is faster and clearer.

## Decision: API key masking

- **Decision**: Use Textual's `Input` widget with `password=True`.
- **Rationale**: Built-in reactive attribute. No custom widget needed. Confirmed in current docs.
- **Source**: https://github.com/textualize/textual/blob/main/docs/widgets/input.md — `password: bool = False` — "True if the input should be masked."

## Decision: Modal vs full-screen

- **Decision**: Use Textual `ModalScreen` for confirmations and small dialogs. Use `Screen` for wizard steps and full-page forms. Match our spec's modal/full-screen split.
- **Rationale**: ModalScreen automatically blocks key bindings on the underlying screen and applies a semi-transparent background. Standard pattern in Textual.
- **Source**: https://github.com/textualize/textual/blob/main/docs/guide/screens.md.

## Decision: Testing strategy

- **Decision**: `pytest-asyncio` for TUI integration tests using `app.run_test()` returning a Pilot object. Existing CLI tests untouched.
- **Rationale**: Textual's official testing pattern. Async def tests. Pilot simulates keyboard and mouse.
- **Source**: https://github.com/textualize/textual/blob/main/docs/guide/testing.md.
- **Note**: Memory tests for the TUI must be standalone (per the project's existing test_pii_memory.py caveat in AGENTS.md).

## Decision: Dependency footprint

- **Decision**: Add `textual>=8.2.8` to `pyproject.toml` runtime deps. No other changes.
- **Rationale**: Textual's transitive deps (rich, markdown-it-py, etc.) are already in the project's tree or aligned with it. No forbidden-dep conflicts.
- **Source**: Textual install footprint confirmed via current docs (https://github.com/textualize/textual).

## Items NOT requiring research

- File picker: Textual's `DirectoryTree` handles it.
- Tab navigation: `TabbedContent` + `TabPane` (note: spec uses top-of-screen tab bar; Textual's `TabbedContent` puts tabs on top — matches).
- Filter list: OptionList with disable/enable per FR group + reactive list rebuild on input change.
- DataTable for past reviews / clause list: built-in.
- Global search: `ModalScreen` with `Input` + filter pattern.
- Navigation: `app.push_screen()` / `app.pop_screen()` for screen stack management.

## Risks

1. **Textual memory overhead**: Need to measure. SC-005 sets <30MB target.
2. **Pilot test flakiness**: Some Textual tests are timing-sensitive. Use `pilot.pause()` and explicit assertions.
3. **Cross-platform terminal differences**: Textual normalizes most, but Windows Console Host has quirks. v1 targets modern terminals (Windows Terminal, iTerm2, gnome-terminal).
