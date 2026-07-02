# Quickstart — Benchmark Harness Validation Guide

## Prerequisites

- Python 3.12, `uv sync` completed (all deps installed)
- At least one configured model slot in gateway config (`openreview gateway setup`)
- Internet connection (for dataset download on first run)
- Reference hardware: 8 GB RAM, 2-core CPU, no GPU (for budget verification)

## Setup

```bash
# 1. Set up at least one local model slot
openreview gateway setup
# Follow the wizard to configure Ollama with a local model (e.g., llama3.2:3b)

# 2. Download CUAD subset (first run — cached afterward)
openreview benchmark --download-datasets
```

## Validation Scenarios

### Scenario 1: Smoke Test — Single Dataset, Single Slot

```bash
openreview benchmark --datasets cuad --slots default
```

**Expected output**: Terminal table with extraction F1, precision, recall for the default model slot on CUAD subset. Run ID printed. JSON report at `~/.local/share/openreview/benchmark/<run_id>.json`.

**Validates**: FR-1 (dataset integration), FR-2 (accuracy metrics), FR-5 (structured report), FR-3 (model slot routing).

### Scenario 2: Multi-Slot Comparison

```bash
openreview benchmark --datasets cuad --slots default,fast
```

**Expected output**: Side-by-side comparison table, per-slot extraction F1 with confidence intervals.

**Validates**: FR-3 (multi-slot routing), §6.1 (SLM vs cloud comparison), §10 Q-7 (model selection).

### Scenario 3: Hardware Budget Gate

```bash
openreview benchmark --datasets cuad --memory-watch
```

**Expected output**: Per-item peak memory < 100 MB (NLP-exempt areas). If any item exceeds 110 MB, benchmark exits with code 75 and prints failing items.

**Validates**: FR-7 (hardware budget), Principle III, constitution §1.2.0.

### Scenario 4: Regression Baseline

```bash
# Record baseline
openreview benchmark --datasets cuad --slots default --save-baseline

# After changes, compare:
openreview benchmark --datasets cuad --slots default --compare
```

**Expected output**: Delta table showing +0.02 F1 or -0.03 F1. Any drop > 2pp F1 prints WARNING and exits with code 75 if `--ci` flag is set.

**Validates**: FR-4 (regression testing), success criterion "Regression detection".

### Scenario 5: Prompt A/B Test

```bash
openreview benchmark --datasets contract_nli --prompt-variant v1 --prompt-variant v2
```

**Expected output**: Comparison table with per-variant classification F1, p-value from McNemar's test. If p < 0.05, flag "STATISTICALLY SIGNIFICANT DIFFERENCE".

**Validates**: FR-6 (prompt A/B testing), §6.5.

### Scenario 6: Full Suite (CI Mode)

```bash
openreview benchmark --all --ci
```

**Expected output**: Runs CUAD + MAUD + ContractNLI across all configured slots. Compares against last saved baseline. Fails if any metric regresses > 2pp F1 (exit code 75).

**Validates**: FR-4 (CI regression gate), scenario 5 from spec.

### Scenario 7: Multi-Party Experimental Mode

```bash
openreview benchmark --datasets cuad --multi-party
```

**Expected output**: Same metrics as standard run, plus per-role accuracy breakdown. No gate failure — results flagged as EXPERIMENTAL.

**Validates**: FR-8 (multi-party experimental support).

### Scenario 8: PII Recall Benchmark

```bash
openreview benchmark --pii-only
```

**Expected output**: PII recall, precision, F1 per entity type across the seeded corpus. Compares against previous run.

**Validates**: FR-2 (PII recall), T049 placeholder.

## CI Integration

The CI job (`.github/workflows/ci.yml`) runs the benchmark on push to `main`:

```yaml
benchmark:
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - uses: astral-sh/setup-uv@v8.1.0
    - run: uv sync
    - run: uv run openreview benchmark --all --ci --compare HEAD~1
```

Manual trigger on PRs: uncomment `workflow_dispatch` trigger or label-based triggering (future).

## Expected Outcomes

| Scenario | Expected Status | Exit Code | Notes |
|----------|----------------|-----------|-------|
| Smoke test | PASS | 0 | Reports extraction F1 |
| Multi-slot | PASS | 0 | Comparison table printed |
| Memory gate | PASS | 0 (<100 MB) | 75 if budget exceeded |
| Regression | PASS | 0 (< 2pp drop) | 75 if regression detected |
| Prompt A/B | PASS | 0 | p-value reported |
| Full suite | PASS | 0 | All datasets complete |
| Multi-party | PASS | 0 | EXPERIMENTAL label |
| PII recall | PASS | 0 | Per-type metrics |

## Artifacts

- **JSON report**: `~/.local/share/openreview/benchmark/<run_id>.json`
- **SQLite database**: Same directory, `benchmark_runs`, `benchmark_results`, `benchmark_baselines` tables
- **Terminal output**: Rich table with color-coded PASS/WARNING/FAIL per metric
