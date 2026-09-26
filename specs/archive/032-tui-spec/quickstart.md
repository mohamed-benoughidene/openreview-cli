# Quickstart: Interactive TUI

**Audience**: developers and testers validating the TUI end-to-end.

## Prerequisites

- Python 3.12 (matches constitution)
- `uv` package manager installed
- A POSIX terminal with 256-color support (gnome-terminal, iTerm2, Windows Terminal, kitty, alacritty)
- For memory tests: a quiet machine (8 GB RAM minimum) and the ability to run pytest in isolation

## Setup

```bash
git clone <repo>
cd openreview
git submodule update --init
uv sync
```

## Launch the TUI

```bash
uv run openreview
```

Expected: the TUI launches with the Home tab. The tab bar shows five tabs: Home, Review, Clients, Playbooks, Settings. The status bar at the bottom shows "Client: — │ Privacy: maximum │ Gateway: ⚠ No providers configured │ Tier: —".

## Validate User Story 1 (first-time review)

1. Click Settings tab.
2. Pick "Gateway" section. Click "Run setup wizard".
3. Pick a slot (e.g., reasoning). Pick a provider. Pick a model. Enter an API key. Save.
4. Click Home tab. Click "New review".
5. Step 1: type "pre" in the mode filter; pick "PreCheck (NDA)".
6. Step 2: navigate to a PDF; pick it.
7. Step 3: leave "Use default for PreCheck" selected.
8. Step 4: confirm. Click "Run review".
9. Watch the progress screen. On completion, the result screen appears with split view.
10. Toggle layout with the layout toggle key (e.g., `l`).
11. Click "Export memo". Choose Markdown. Save to `/tmp/result.md`.
12. Open `/tmp/result.md` and confirm it shows clause-level output.

Expected outcome: a non-technical user can complete steps 1-12 in under 5 minutes.

## Validate non-TTY exit

```bash
echo "" | uv run openreview
```

Expected: a friendly one-line message explaining the TUI needs an interactive terminal and pointing to `openreview --help`. Exit code 0. No stack trace.

## Run the test suite

```bash
# Unit tests (sync)
uv run pytest tests/unit/ -q

# Integration tests (async, Pilot)
uv run pytest tests/integration/tui/ -q

# Memory test (standalone, due to AGENTS.md caveat)
uv run pytest -m memory -q --timeout=300
```

## TUI entry points

| Entry | Behavior |
|---|---|
| `openreview` (TTY) | Launch TUI |
| `openreview` (no TTY) | Friendly message, exit 0 |
| `openreview --no-tui` | Force CLI behavior, exit 0 |
| `openreview <subcommand>` | Run subcommand (unchanged) |
| `openreview <subcommand> --help` | Subcommand help |

## Accessibility note

The TUI supports full keyboard navigation (Tab, Shift+Tab, number keys 1-5, arrow keys, Enter, Escape, `/`, `Ctrl-C`). Screen reader optimization is NOT supported in v1. The About section in Settings displays this note.
