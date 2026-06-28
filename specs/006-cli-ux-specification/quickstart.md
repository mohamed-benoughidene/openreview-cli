# Quickstart: CLI UX Validation

**Created**: 2026-06-28
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

Validation scenarios for the CLI UX system design. Each scenario corresponds to one or more user stories, functional requirements (FR-*), and success criteria (SC-*) from the spec. Use this as a runbook to verify the implementation tier by tier.

## Prerequisites

- Python 3.12 (pinned in `.python-version`)
- `uv sync` completed (all deps installed, including `questionary` if interactive prompts are wired)
- Terminal with 80+ column width and color support (some scenarios test degradation)
- `NO_COLOR` and `COLUMNS` env vars are **not set** by default (each scenario specifies when to set them)
- A sample PDF contract document at `tests/fixtures/sample_contract.pdf` for review scenarios

## Validation Scenarios

---

### 1. First-Run Wizard

**Priority**: P1
**User Story**: US-1 — First-time Legal Professional Runs openreview
**Spec links**: §8.4 First-run Detection; FR-FP-001 (200ms first output); FR-IP-005 (Esc/Ctrl-C); SC-001 (setup under 5 min)

**Setup**: Delete (or move aside) the config file to simulate first-run state:

```bash
mv ~/.config/openreview/config.json ~/.config/openreview/config.json.bak
```

**Run**:

```bash
uv run openreview
```

**Expected outcomes**:

1. A welcome message (bordered panel) appears within 200ms explaining what openreview does in 3–4 plain-English sentences.
2. The welcome panel includes a privacy notice: "openreview processes documents entirely on your machine. No contract text ever leaves your computer."
3. The setup wizard auto-enters after the welcome message — no `--setup` flag needed.
4. The wizard displays a step indicator: `▶ ○ ○ ○  Step 1 of 4: Provider Selection`.
5. Press **Esc** at any step → wizard exits with: "Setup was interrupted. Run `openreview setup` to try again later."
6. Press **Ctrl-C** at any step → tool exits with: "Cancelled." (code 1, no stack trace).
7. Complete the wizard (provider → model → jurisdiction → shell completion) → success panel: "✓ Setup complete." with config file path, provider, and suggested next command.

**Restore config after test**:

```bash
mv ~/.config/openreview/config.json.bak ~/.config/openreview/config.json
```

---

### 2. Interactive Legal Review

**Priority**: P1
**User Story**: US-2 — Legal Professional Reviews a Contract Interactively
**Spec links**: §3.1 Multi-step Wizard Flow; FR-FP-002 (step indicator); FR-FP-003 (spinner); FR-FP-004 (progress bar); FR-FP-005 (streaming); FR-FB-003 (success message); FR-OF-001 (Rich Tables); SC-004 (no tracebacks)

**Setup**: Ensure a config file exists with a working provider (e.g., Ollama running locally). Place a 50-page sample contract at `tests/fixtures/sample_contract.pdf`.

**Run**:

```bash
uv run openreview review tests/fixtures/sample_contract.pdf
```

**Expected outcomes**:

1. Step indicator appears: `▶ ○ ○ ○  Step 1 of 4: Review Mode`.
2. Arrow-key navigable menu with mode options: Standard Review, Risk-Focused, Compliance Check.
3. **Esc** on Step 1 → exits with "Setup cancelled." (code 0).
4. Select a mode → advances to Step 2 (Configuration) with multi-select for clause types.
5. **Esc** on Step 2 → goes back to Step 1.
6. Confirm settings (Step 3) → confirmation dialog with `(Y/n)` default (non-destructive).
7. Processing (Step 4) shows: spinner with "Analyzing clause 1 of 47 — Indemnification..." and a determinate progress bar.
8. Results display as a Rich Table with columns: Risk Level, Clause, Finding, Recommendation.
9. Summary panel at bottom: "✓ Review complete. 12 clauses analyzed, 3 findings. [2m 34s]".
10. **Ctrl-C** during processing → exits with "Review cancelled. Partial results were not saved." (code 1).

---

### 3. Non-Interactive / CI Mode

**Priority**: P2
**User Story**: US-3 — Legal Professional Uses Non-Interactive Mode
**Spec links**: §3.3 CI / Non-interactive Mode; FR-IP-006 (Tab completion); FR-TC-004 (non-TTY detection); FR-TC-005 (`--yes` flag); SC-002 (all prompts bypassable); SC-005 (non-TTY function)

**Run (missing required input)**:

```bash
echo "" | uv run openreview review tests/fixtures/sample_contract.pdf
```

**Expected**: Exits with code 2 and stderr message: "Error: --mode is required when running non-interactively. See `openreview review --help`."

**Run (complete pipeline)**:

```bash
uv run openreview review tests/fixtures/sample_contract.pdf \
  --mode standard \
  --output json \
  --clauses indemnification,termination \
  --yes \
  | jq '.findings | length'
```

**Expected outcomes**:

1. No interactive prompts appear — processing proceeds immediately.
2. All human messaging (spinner labels, progress updates, errors) goes to stderr.
3. Valid JSON array of findings on stdout — `jq` pipeline succeeds.
4. Exit code 0 on success, non-zero on failure.

**Run (validation error)**:

```bash
uv run openreview review tests/fixtures/sample_contract.pdf \
  --mode standard \
  --output json \
  --clauses nonexistent_clause \
  --yes
```

**Expected**: Error panel (plain text, no Rich borders in non-TTY): "Clause type 'nonexistent_clause' is not recognized. Run `openreview list clauses` to see available types." Exit code 2.

---

### 4. NO_COLOR Compliance

**Priority**: P2 (edge case)
**Spec links**: FR-TC-001 (NO_COLOR); §7.2 NO_COLOR Compliance; SC-007 (monochrome output)

**Run**:

```bash
NO_COLOR=1 uv run openreview --help
```

**Expected**:

1. No ANSI escape codes in output. Verify with: `NO_COLOR=1 uv run openreview --help | cat -v` — should see no `^[[...m` sequences.
2. All formatting uses bold/underline instead of color (per §1.1 no-color fallback table).
3. Unicode icons remain unless `--no-unicode` is also set.

**Run (full monochrome)**:

```bash
NO_COLOR=1 uv run openreview review tests/fixtures/sample_contract.pdf --mode standard --output table --yes
```

**Expected**:

4. Table renders with ASCII borders only, no green/red/yellow in risk cells.
5. Risk labels are text only (`HIGH`, `MEDIUM`, `LOW`) — no color conveys meaning.
6. Spinners animate but without color.
7. Error/success panels use ASCII borders.

---

### 5. Error Feedback (Three-Part Error)

**Priority**: P2
**Spec links**: FR-FB-001 (three-part error); FR-FB-002 (exit codes); §5.1 Error Message Format; §5.2 Exit Code Map; SC-004 (no tracebacks)

**Run (unknown config key)**:

```bash
uv run openreview config set unknown.key value
```

**Expected**: Error panel (red border) with:
- **Title**: "✗ Error" (red)
- **What failed**: "Unknown configuration key 'unknown.key'."
- **Why**: "The key 'unknown.key' does not match any recognized setting."
- **How to fix**: "Run `openreview config show` to see valid keys."
- Exit code 3 (config error).

**Run (file not found)**:

```bash
uv run openreview review nonexistent.pdf
```

**Expected**: Error panel (red border) with:
- **What failed**: "Cannot open file 'nonexistent.pdf'."
- **Why**: "The file was not found at <resolved absolute path>."
- **How to fix**: "Check the file path and try again:\n  openreview review <correct-path>\nRun `openreview review --help` for usage."
- Exit code 4 (input file error).

**Run (missing required flag, non-TTY)**:

```bash
echo "" | uv run openreview review tests/fixtures/sample_contract.pdf --output json
```

**Expected**: Error panel (plain text, ASCII fallback) with:
- **What failed**: "Missing required option: --mode."
- **Why**: "You're running in non-interactive mode and --mode was not provided."
- **How to fix**: "Run with --mode standard, --mode risk, or --mode compliance. See `openreview review --help`."
- Exit code 2 (usage error).

---

### 6. Configuration Management

**Priority**: P2
**User Story**: US-4 — Legal Professional Configures Tool Settings
**Spec links**: §8.2 Config Command; FR-CF-002 (get/set validation); FR-CF-004 (startup validation); SC-001 (setup under 5 min)

**Setup**: Ensure config file exists.

**Get a value**:

```bash
uv run openreview config get provider.default
```

**Expected**: Displays the current value, e.g.: "provider.default = ollama" (primary color for key, success color for value).

**Set a valid value**:

```bash
uv run openreview config set provider.default ollama
```

**Expected**: Confirmation shows old and new values: "✓ provider.default changed from 'ollama' to 'ollama' (unchanged)" or from previous value to new value.

**Set an invalid model**:

```bash
uv run openreview config set model.standard nonexistent-model
```

**Expected**: Error panel: "Model 'nonexistent-model' is not recognized. Run `openreview list models` to see available models." Exit code 2. Config file is NOT modified.

**Show all config**:

```bash
uv run openreview config show
```

**Expected**: Rich Table with columns: Key, Value, Source (config / env / default). Default values shown as dim/muted.

**Config path**:

```bash
uv run openreview config path
```

**Expected**: Prints the absolute path to the config file, styled as a file path (bold cyan). e.g., "/home/user/.config/openreview/config.json"

**Corrupted config**:

```bash
echo "{invalid json" > ~/.config/openreview/config.json
uv run openreview --help
```

**Expected**: Warning (yellow panel) on startup: "Config file at ~/.config/openreview/config.json is invalid. Run `openreview setup` to fix it." Tool exits with code 3.

**Restore after test**:

```bash
# restore valid config from backup or re-run setup
```

---

### 7. Narrow Terminal

**Priority**: P3 (edge case)
**Spec links**: §7.3 Width Handling; FR-TC-003 (terminal width adaptation); Edge Cases in spec

**Run (below 80 columns)**:

```bash
COLUMNS=70 uv run openreview review tests/fixtures/sample_contract.pdf --mode standard --output table --yes
```

**Expected**:

1. Table columns auto-shrink proportionally; text wraps within cells.
2. Step indicator uses compact format: `[2/4]` instead of `Step 2 of 4`.
3. No horizontal overflow — terminal width is respected.

**Run (below 60 columns)**:

```bash
COLUMNS=55 uv run openreview review tests/fixtures/sample_contract.pdf --mode standard --output table --yes
```

**Expected**:

4. Table switches to key-value paired lines (each finding row becomes a multi-line block).
5. Risk label remains visible but inline rather than in a dedicated column.

**Run (below 40 columns)**:

```bash
COLUMNS=35 uv run openreview review tests/fixtures/sample_contract.pdf --mode standard --output table --yes
```

**Expected**:

6. Yellow warning: "Terminal too narrow for optimal display. Increase width for best experience."
7. Output continues, degraded but functional.

---

### 8. Help Discoverability

**Priority**: P3
**User Story**: US-5 — Legal Professional Seeks Help
**Spec links**: FR-HS-001 to FR-HS-005; §4.3 Global Flags; SC-004 (no tracebacks)

**Run (top-level help)**:

```bash
uv run openreview --help
```

**Expected**:

1. Help text leads with real examples (plain English, contract scenarios) before the flag listing.
2. Subcommands are grouped under descriptive headers: "Review Commands", "Configuration Commands".
3. No developer jargon — all text at Flesch-Kincaid grade level < 10.

**Run (subcommand help)**:

```bash
uv run openreview review --help
```

**Expected**:

4. Required flags are marked with `[required]` label.
5. Examples section shows real-looking usage: `openreview review contract.pdf --mode standard`.
6. Sensible defaults are documented for optional flags.

**Run (typo suggestion)**:

```bash
uv run openreview reviw contract.pdf
```

**Expected**: "Unknown command 'reviw'. Did you mean 'review'?" Exit code 2.

**Run (version)**:

```bash
uv run openreview --version
```

**Expected**: Prints semantic version from `src/openreview_cli/__init__.py`, e.g., "openreview 0.1.0". Exit code 0.

---

### 9. Shell Completion

**Priority**: P3
**Spec links**: FR-IP-006 (Tab completion); §8.4 item 5 (auto-install during setup); §4.3 (global flags)

**Run (manual install)**:

```bash
uv run openreview --install-completion
```

**Expected**:

1. Detects current shell (bash/zsh/fish/powershell via shellingham).
2. Writes completion file to the appropriate location for the detected shell.
3. Prints success: "✓ Shell completion installed for <shell>. Restart your shell or run `source <file>` to activate."

**Run (test completion works)**:

```bash
# Source the completion file (shell-dependent) then type:
uv run openreview rev<tab>
```

**Expected**: Completes to `openreview review`. Subcommand flags also complete (e.g., `openreview review --mo<tab>` → `--mode`).

---

### 10. Success Message Format

**Priority**: P2
**Spec links**: FR-FB-003 (success message); §5.3 Success Message Format

**Run (config set)**:

```bash
uv run openreview config set provider.default ollama
```

**Expected**: Green checkmark with value: "✓ provider.default set to 'ollama'."

**Run (review complete)**:

```bash
uv run openreview review tests/fixtures/sample_contract.pdf --mode standard --output json --yes 2>/dev/null | head -1
```

**Expected** (stdout has JSON; stderr has success message):
- Green checkmark: "✓ Review complete. N clauses analyzed, N findings. [Xm Ys]"
- Followed by next-step suggestion: "View the full report:\n  openreview review <file>"

**Rule**: Never silent on success. Every completed operation produces a success line.

---

### 11. Warning vs Error Distinction

**Priority**: P2
**Spec links**: §5.4 Warning vs Error; FR-FB-004 (warnings yellow, errors red)

**Run (unknown config key — warning)**:

```bash
# Add an unknown key to the config file manually, then run any command
uv run openreview config show
```

**Expected**: Yellow warning panel: "⚠ Unknown config key(s) found: 'unknown_key'. They will be preserved but ignored."

**Run (model registry refresh failure — warning)**:

```bash
# Simulate by running with an unreachable provider
OPENREVIEW_PROVIDER_OLLAMA_BASE_URL=http://localhost:19999 \
  uv run openreview config set model.standard llama3.2
```

**Expected**: Operation completes but yellow warning is shown about the model registry being unreachable. Exit code 0 (warning, not error).

**Run (corrupted config — error)**:

```bash
echo "not json" > ~/.config/openreview/config.json
uv run openreview config show
```

**Expected**: Red error panel, exit code 3 (halt, no recovery).
Restore config after test.

---

## Implementation Tier Mapping

Scenarios are ordered by implementation tier from the plan:

| Tier | Scenarios | What's Being Validated |
|------|-----------|----------------------|
| 1 — Foundation | 4, 5, 10, 11 | Console singleton, error panels, exit codes, design tokens |
| 2 — Core Interaction | 2, 6, 7 | Step indicator, spinner/progress, result table, success/warning format |
| 3 — Interactive Prompts | 1, 2, 3 | Selection menu, confirmation, fuzzy search, multi-select |
| 4 — Polish | 4, 8, 9 | Live panel, NO_COLOR/TTY degradation, first-run, config UX, help text |

## Quick Smoke Test

To validate the entire UX layer end-to-end in under 30 seconds:

```bash
# Verify help and version render immediately
uv run openreview --help
uv run openreview --version

# Verify error display (no tracebacks)
uv run openreview review nonexistent.pdf 2>&1 | head -20

# Verify non-interactive mode works
uv run openreview review tests/fixtures/sample_contract.pdf \
  --mode standard --output json --yes 2>/dev/null | jq '.' > /dev/null && echo "JSON OK"

# Verify NO_COLOR
NO_COLOR=1 uv run openreview --help | cat -v | grep -c '\\\[\\\[\\' || echo "NO_COLOR OK"

# Verify config commands
uv run openreview config get provider.default
uv run openreview config path
```
