# Quickstart: CLI Wizard UX Redesign

**Phase 1 output** | **Date**: 2026-06-27

## Prerequisites

- Python 3.12, `uv` installed
- Project cloned and `git submodule update --init && uv sync` done
- Feature branch: `feat/005-cli-wizard-redesign`

## Setup

```bash
# Add the new dependency
uv add questionary

# Sync environment
uv sync
```

## Validation Scenarios

### 1. Gateway wizard refactored (arrow-key navigation)

```bash
uv run openreview gateway setup
```

**Expected**: Arrow keys work for provider/model selection. Summary table shown before save. Ctrl+C cancels with confirmation. Config is saved only after confirmation.

### 2. Review wizard (first run)

```bash
uv run openreview review tests/fixtures/sample_contract.pdf
```

**Expected**: Pre-flight check → mode selection → jurisdiction/format selection → summary table → confirmation. Config returned to caller (no review execution yet).

### 3. Review wizard (risk scan only)

```bash
uv run openreview review tests/fixtures/sample_contract.pdf
```

Select "Risk scan" at mode prompt.

**Expected**: Skips jurisdiction, format, and clauses prompts. Goes straight to summary.

### 4. Non-interactive mode

```bash
uv run openreview review tests/fixtures/sample_contract.pdf \
  --non-interactive \
  --mode full \
  --jurisdiction us-de \
  --output json
```

**Expected**: No wizard prompts. Exits immediately with config or prints error if required flags are missing.

### 5. Gateway not ready

```bash
# Temporarily move config
mv ~/.config/openreview/auth.json ~/.config/openreview/auth.json.bak
mv ~/.config/openreview/config.yml ~/.config/openreview/config.yml.bak

uv run openreview review tests/fixtures/sample_contract.pdf
```

**Expected**: Warning shown: "Gateway not ready: missing chat model or embedding slot." Offers "Run `openreview gateway setup` now?" Accept → runs setup wizard. Decline → continues with defaults.

### 6. Missing file argument

```bash
uv run openreview review
```

**Expected**: Prints usage: `Usage: openreview review [OPTIONS] FILE` and exits.

### 7. SSH session

```bash
ssh -t user@localhost "cd ~/lab/openreview && .venv/bin/openreview gateway setup"
```

**Expected**: Arrow-key navigation works correctly over SSH with PTY.

### 8. Ctrl+C handling

```bash
uv run openreview review tests/fixtures/sample_contract.pdf
```

Press Ctrl+C during any prompt.

**Expected**: Confirmation dialog: "Cancel? Yes/No." Yes → exits. No → returns to current step.

## Run tests

```bash
# Existing gateway tests (must pass after refactor)
uv run pytest tests/ -k gateway -v

# New wizard tests
uv run pytest tests/ -k "wizard or review" -v
```

## Key interfaces

- `ReviewWizard.__init__(file_path, non_interactive=False, mode=None, jurisdiction=None, output_format=None)`
- `ReviewWizard.run() -> ReviewConfiguration`
- `SetupWizard.run() -> None` (unchanged public interface)

See `contracts/review_wizard.md` and `contracts/gateway_wizard.md` for full interface details.
