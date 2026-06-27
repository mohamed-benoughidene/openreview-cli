# CLI Wizard UX Redesign

**Feature**: CLI Wizard UX Redesign  
**Version**: 0.1  
**Created**: 2026-06-27  

## Overview

The `openreview` CLI wizard (used in `gateway setup` and planned for `review`) relies on `rich.prompt.Prompt.ask()` — a text-input-only prompt. Users must **type** their choice from a list rather than navigating with arrow keys. This creates three pain points:

1. **No arrow-key navigation** — users must type exact choice strings from a list of 15+ models or 30+ jurisdictions
2. **No multi-select** — no way to select 5 clauses from a list of 20 in one interaction
3. **No fuzzy filtering** — when picking a model, the user must type the exact name with no substring matching

The existing `wizard.py` also lacks: a summary-before-save step, inline input validation, progressive disclosure (questions conditioned on prior answers), and non-interactive terminal guards.

## User Scenarios

### Scenario A: First-time Gateway Setup

**Actor**: Legal professional setting up the AI Gateway

**Flow**:
1. Runs `openreview gateway setup`
2. Sees a welcome message and the 5 slots to configure
3. For each slot, selects a provider from a list using arrow keys
4. For Ollama, sees available models with fuzzy filtering
5. For cloud providers, enters an API key with inline validation feedback
6. At the reasoning slot, is asked "Apply to extraction and graph too?" — if yes, those slots are skipped
7. After all slots, sees a summary table and confirms before saving
8. Config is saved and summary is shown

**Verifiable outcomes**:
- User completes setup in under 2 minutes without typing model names from memory
- User makes ≤1 typo-related error
- Config is not saved if the user says "no" at the summary prompt

### Scenario B: Contract Review Wizard

**Actor**: Legal professional reviewing a contract

**Flow**:
1. Runs `openreview review contract.pdf`
2. If file doesn't exist or is unsupported, exits immediately with a clear error
3. Selects review mode: Full / Clause-by-clause / Risk scan
4. If "Risk scan only": jumps directly to summary
5. If "Full" or "Clause-by-clause": prompted for jurisdiction and output format
6. If "Clause-by-clause": additionally prompted to multi-select clauses to review
7. Sees a summary table and confirms or cancels
8. On confirm, review begins

**Verifiable outcomes**:
- User reaches summary screen in ≤30 seconds
- Conditional questions only appear when relevant
- Multi-select clause picker lets user select 5 of 20 clauses in ≤10 seconds

### Scenario C: Non-Interactive Fallback

**Actor**: Developer or CI pipeline

**Flow**:
1. Runs `openreview review contract.pdf --mode full --jurisdiction us-de --output json --non-interactive`
2. No wizard appears; review starts immediately
3. If required flags are missing, prints an error and exits 1

**Verifiable outcomes**:
- Command completes without hanging when stdin is not a TTY
- Missing flags produce a descriptive error

### Scenario D: SSH Session

**Actor**: Legal professional connected via SSH

**Flow**:
1. Connects with `ssh -t user@host`
2. Runs `openreview gateway setup`
3. Arrow keys, fuzzy filter, and multi-select all work as expected

**Verifiable outcomes**:
- All interactive prompts function correctly over SSH with a PTY
- If connected without `-t`, prints a clear message

## Functional Requirements

| ID | Requirement | Priority |
|----|------------|----------|
| FR-01 | All single-choice prompts use arrow-key navigation with a visual highlight | P0 |
| FR-02 | Multi-select prompts support Space-to-toggle with a visible marker and Enter-to-confirm | P0 |
| FR-03 | Free-text choice prompts support inline fuzzy filtering as the user types | P1 |
| FR-04 | Input validation errors appear inline on the same prompt screen | P1 |
| FR-05 | A summary table is displayed before any configuration is saved or review is launched | P0 |
| FR-06 | Later wizard steps are conditionally shown or hidden based on earlier answers | P1 |
| FR-07 | The wizard supports cancellation at any step via Ctrl+C | P0 |
| FR-08 | Every interactive prompt displays a brief instruction hint | P2 |
| FR-09 | The wizard detects non-interactive terminals and falls back to flag-based mode | P0 |
| FR-10 | All wizard flows have a non-interactive mode accepting all parameters as CLI flags | P1 |
| FR-11 | A `review` command exists as `openreview review <file>` with the 3-step wizard flow | P0 |
| FR-12 | The existing `gateway setup` wizard is migrated to the new interaction patterns | P0 |
| FR-13 | The "back" navigation pattern is preserved or replaced with an equivalent mechanism | P2 |
| FR-14 | Config file writes remain atomic via `atomic_write` | P0 |

## Success Criteria

| ID | Criterion | Measurement |
|----|-----------|------------|
| SC-01 | First-time user completes gateway setup in under 2 minutes | Timed user test, N=5 |
| SC-02 | Typed inputs reduced by ≥60% compared to current wizard | Count typed-vs-selected per flow |
| SC-03 | 100% of interactive prompts degrade gracefully when stdin is not a TTY | Automated test: pipe input |
| SC-04 | Review wizard completes in ≤30 seconds for a typical user | Timed user test, N=5 |
| SC-05 | All existing `gateway setup` integration tests pass after migration | Run `uv run pytest tests/ -k gateway` |
| SC-06 | Arrow-key navigation works on Linux, macOS, Windows Terminal, WSL, and SSH | Manual smoke test matrix |

## Key Entities

- **Wizard Step**: A single question in the wizard flow with a prompt message, input type, optional choices, validation, and a `when` condition
- **Wizard Flow**: A sequence of steps with branching via `when` conditions, producing an `answers` dictionary
- **Review Configuration**: Aggregated result of the review wizard with `file_path`, `mode`, `jurisdiction`, `output_format`, and optional `clauses` list
- **Gateway Slot Configuration**: The existing 5-slot config with `primary` model string and optional `params`

## Assumptions

1. `questionary` will be added as a runtime dependency (MIT-licensed, actively maintained, `prompt_toolkit` as transitive dep)
2. The existing `SetupWizard` class will be refactored to use `questionary` primitives internally, but its public interface remains unchanged
3. The `review` command does not yet exist — this spec defines it from scratch
4. The review engine (Phase 5+) is out of scope — the wizard produces a config dict and hands it off
5. Terminal compatibility targets terminals with ANSI escape code support; `TERM=dumb` falls back to monochrome with typed choices
6. The existing `auth.json` chmod 600 behavior and `atomic_write` pattern are preserved as-is

## Edge Cases

| Case | Handling |
|------|----------|
| User resizes terminal mid-wizard | `questionary`/`prompt_toolkit` handles resize natively |
| 0 models available in Ollama | Show "No models found. Pull one with `ollama pull <model>`" and allow manual entry |
| API key validation fails | Show inline red error; offer "skip validation" without losing the entered key |
| User presses Ctrl+C during step 3 of 5 | Show confirmation "Cancel?"; on yes, exit; on no, return to current step |
| File provided to `review` is encrypted/damaged | Pre-flight check catches this before the wizard starts |
| User runs `openreview review` with no file argument | Print usage and exit |
| User provides conflicting flags without `--non-interactive` | Pre-flight validation catches missing required flags |

## Out of Scope

- Full TUI application (no Textual app class as the main shell)
- Web-based UI
- Persistent wizard state across sessions
- Custom keybinding configuration by users
- Internationalization / localization
- The actual review execution engine (this spec covers the wizard only)
