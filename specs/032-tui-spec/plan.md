# Implementation Plan: Interactive TUI (Terminal User Interface)

**Branch**: `feat/032-tui-spec` | **Date**: 2026-07-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/032-tui-spec/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a full-screen, persistent **Terminal User Interface (TUI)** to the `openreview` CLI using the Textual framework (v8.2.8). When `openreview` is run with no subcommand in a TTY, the TUI launches and provides tab-based navigation (Home, Review, Clients, Playbooks, Settings), two wizards (new-review 4-step, gateway-setup 4-step), a file picker, global search, modal confirmations, persistent status bar and description bar, and a review result screen with split-view. All existing one-shot subcommands continue to work unchanged. TTY detection at the entry point (`sys.stdin.isatty()`) provides a fast exit for non-interactive contexts. The TUI is an additional presentation layer over existing review/gateway/PII infrastructure — no new persistent storage, no background processes, one new runtime dependency (`textual>=8.2.8`).

## Dependency Trade-off

Adding `textual>=8.2.8` as a runtime dependency increases the install size of `openreview-cli` for ALL users, including those who never use the TUI (CI scripts, automation, headless servers). This is mitigated by lazy imports (Textual is only imported inside `launcher.py` after TTY check passes), so the runtime memory and startup cost of non-TUI invocations is unchanged. The trade-off was made because:
1. Textual is a single new dep, the smallest possible addition
2. The lazy-import design ensures no runtime cost for non-TUI users
3. The TUI is the primary interface for the product going forward; making TUI users install Textual is justified
4. A separate `[tui]` extras group was considered and rejected — adds user friction without significant savings

## Technical Context

**Language/Version**: Python 3.12 (matches constitution)

**Primary Dependencies**: Textual 8.2.8 (new), Rich (existing, same author), Questionary (existing, retained for non-TUI subcommands), Pydantic, Typer. No new deps beyond Textual.

**Storage**: SQLite (existing, no schema change for v1 — recent-reviews read from existing review history, clients/playbooks from existing tables)

**Testing**: pytest with pytest-asyncio (for Textual's async Pilot tests via `app.run_test()`). Existing test suite must continue to pass. Memory tests for TUI must be standalone (per existing project convention for memory-budget tests).

**Target Platform**: Linux/macOS/Windows terminal emulators with 256-color and TTY support. Mouse support on by default (Textual default).

**Project Type**: CLI tool with TUI layer (single project, src layout). The TUI lives in a new `src/openreview_cli/tui/` subpackage under the existing `src/openreview_cli/` package.

**Performance Goals**: Cold start <1s (SC-004), TUI memory overhead <30MB on top of CLI baseline (SC-005), total peak memory <110MB (constitution Principle III floor).

**Constraints**: Peak memory <110MB total (constitution Principle III), PII stripping before any external API call (FR-045, FR-047), no background processes (constitution Principle II), local-only (constitution Principle II), no screen reader optimization in v1 (FR-032b), dark mode only for v1 (per TUI-Decisions.md), single-user/single-session.

**Scale/Scope**: 5 tabs, 2 wizards (4 steps each), 1 file picker, ~10 screens total, 22 product modes referenced, 6 gateway slots, unlimited clients/playbooks/reviews in storage (lists with type-to-filter).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Privacy First | PASS | FR-045 to FR-047 enforce PII stripping; no change to existing behavior. TUI reuses existing review pipeline. PII masking in gateway wizard (FR-032a). No raw text logged (FR-047). |
| II. Local-First, CLI-Only | PASS | TUI is in-process; no new server or daemon. Single CLI invocation. Exits on Quit/Ctrl-C. No background workers. |
| III. Hardware-Bounded | PASS | Textual 8.x is built on Rich and uses async I/O. SC-004 (<1s cold start) and SC-005 (<30MB overhead) set hard limits. Heavy imports (PyMuPDF, etc.) remain lazy in existing pipeline. Total peak under 110MB floor. |
| IV. Dependency Minimalism | PASS | Only one new runtime dep: `textual>=8.2.8`. Questionary retained (already in use). Forbidden list (langchain, FAISS, etc.) respected. Textual is built on Rich (already a dep). |
| V. Spec-Driven, YAGNI | PASS | Spec is the source of truth. No speculative features. Bulk ops, multi-session, collaborative features, theme toggle explicitly out of scope for v1. |

## Project Structure

### Documentation (this feature)

```text
specs/032-tui-spec/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output (/speckit.plan)
├── contracts/           # Phase 1 output (/speckit.plan)
├── spec.md              # already exists
├── TUI-Decisions.md     # already exists
├── TUI-Tree.md          # already exists
├── checklists/          # already exists
└── tasks.md             # NOT created by /speckit.plan (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── tui/                          # NEW: TUI package
│   ├── __init__.py              # public API: launch_tui()
│   ├── app.py                   # OpenReviewApp(Textual App) — main entry, tab bar
│   ├── tabs/                    # one module per tab
│   │   ├── __init__.py
│   │   ├── home.py              # HomeTab with recent reviews, quick actions
│   │   ├── review.py            # ReviewTab with new-review wizard
│   │   ├── clients.py           # ClientsTab with CRUD
│   │   ├── playbooks.py         # PlaybooksTab with import/detail/versions
│   │   └── settings.py          # SettingsTab with sections + gateway wizard
│   ├── widgets/                 # reusable widgets
│   │   ├── __init__.py
│   │   ├── status_bar.py        # persistent status bar
│   │   ├── description_bar.py   # one-line description
│   │   ├── filter_list.py       # type-to-filter list (used everywhere)
│   │   └── file_picker.py       # full-screen file picker
│   ├── screens/                 # modal/full-screen overlays
│   │   ├── __init__.py
│   │   ├── confirm.py           # ConfirmModal (delete, cancel review)
│   │   ├── search.py            # global search overlay
│   │   ├── review_wizard.py     # 4-step review wizard
│   │   ├── gateway_wizard.py    # 4-step gateway wizard
│   │   ├── result.py            # review result screen
│   │   └── client_form.py       # add/edit client form
│   ├── domain/                  # thin wrappers over existing domain APIs
│   │   ├── __init__.py
│   │   ├── gateway.py           # call openreview_cli.gateway.router
│   │   ├── review.py            # call openreview_cli.review.run_review
│   │   ├── clients.py           # call openreview_cli.storage.database
│   │   ├── playbooks.py         # call openreview_cli.review.playbook + storage
│   │   └── privacy.py           # read privacy tier from config
│   ├── tcss/                    # Textual CSS files
│   │   ├── app.tcss             # global styles
│   │   ├── tabs.tcss            # tab-specific styles
│   │   └── widgets.tcss         # widget styles
│   └── launcher.py              # launch_tui() — TTY check, exception translation
└── app.py                       # MODIFIED: dispatch to TUI when no subcommand

tests/
├── unit/
│   └── tui/                     # NEW: TUI unit tests (sync, no async)
│       ├── test_launcher.py     # TTY detection
│       ├── test_status_bar.py
│       ├── test_filter_list.py
│       └── test_widgets.py
└── integration/
    └── tui/                     # NEW: TUI integration tests (async, Pilot)
        ├── test_app.py          # launch + quit, tab navigation
        ├── test_review_wizard.py
        ├── test_gateway_wizard.py
        ├── test_clients_tab.py
        ├── test_playbooks_tab.py
        └── test_settings_tab.py
```

Note on integration test file scope:
- `test_app.py` = app-level: launch, tab navigation, quit, search, status-bar click, two-Ctrl-C, cold start
- `test_review_wizard.py` = review-wizard-specific flows
- `test_gateway_wizard.py` = gateway-wizard-specific flows
- `test_clients_tab.py`, `test_playbooks_tab.py`, `test_settings_tab.py` = per-tab flows

**Structure Decision**: Single project (Option 1 in template). TUI lives in a new `tui/` subpackage under existing `src/openreview_cli/`. Existing CLI surface unchanged. New tests in `tests/unit/tui/` (sync) and `tests/integration/tui/` (async with Pilot).

## Complexity Tracking

No violations — all five constitution principles pass. No complexity tracking entries required.
