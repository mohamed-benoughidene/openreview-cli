# CLI Contract — `openreview benchmark`

## Command

```text
openreview benchmark [OPTIONS]
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--datasets` | `list[str]` | `["cuad"]` | Datasets to evaluate: `cuad`, `maud`, `contract_nli` |
| `--slots` | `list[str]` | `["default"]` | Model slot names from gateway config |
| `--modes` | `list[str]` | `["precheck"]` | Product modes to evaluate |
| `--prompt-variant` | `list[str]` | `None` | Prompt variant names (A/B test when ≥2 provided) |
| `--all` | `bool` | `False` | Run all datasets, slots, and modes |
| `--ci` | `bool` | `False` | CI mode — strict exit codes, compare to baseline |
| `--compare` | `str` | `None` | Baseline ref to compare against (commit SHA, tag, or `last`) |
| `--save-baseline` | `bool` | `False` | Save this run as the regression baseline |
| `--download-datasets` | `bool` | `False` | Download/refresh dataset corpora |
| `--memory-watch` | `bool` | `False` | Enable per-item memory profiling |
| `--pii-only` | `bool` | `False` | Run only the PII recall benchmark |
| `--multi-party` | `bool` | `False` | Enable experimental multi-party evaluation |
| `--format` | `str` | `"terminal"` | Output format: `terminal` (Rich table), `json` (stdout) |
| `--output` | `str` | `None` | Write JSON report to file path |
| `--verbose` | `bool` | `False` | Detailed per-item progress |
| `--help` | flag | — | Show help message |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All benchmarks passed, no regressions |
| 75 | Regression detected or budget exceeded (CI mode only) |
| 78 | Dataset download or configuration error |
| 1 | Unexpected error |

## Examples

```bash
# Basic smoke test (CUAD, default slot)
openreview benchmark

# Full multi-slot comparison
openreview benchmark --datasets cuad --slots default,fast --format json

# CI regression gate
openreview benchmark --all --ci --compare HEAD~1

# Prompt A/B test on ContractNLI
openreview benchmark --datasets contract_nli --prompt-variant v1 --prompt-variant v2

# Memory and PII validation
openreview benchmark --datasets cuad --memory-watch --pii-only
```

## Configuration

The benchmark reads the following from `~/.config/openreview/benchmark.yml` (optional):

```yaml
benchmark:
  dataset_cache_dir: ~/.local/share/openreview/datasets
  baseline_store: sqlite  # sqlite | json_file
  download_timeout_seconds: 300
  memory_watch: false      # default value for --memory-watch
  exit_on_regression: false  # equivalent to --ci
  regression_threshold_pp: 2.0  # percentage points F1 drop
```

If the config file does not exist, sensible defaults apply.

## JSON Report Schema (stdout / file)

```json
{
  "$schema": "openreview-cli/benchmark-report-v1",
  "run_id": "uuid-string",
  "timestamp": "2026-07-02T12:00:00Z",
  "git_commit": "abc123def",
  "git_branch": "feat/010-benchmark-harness",
  "config": {
    "datasets": ["cuad"],
    "slots": ["default"],
    "modes": ["precheck"],
    "ci_mode": false,
    "baseline_ref": null
  },
  "results": [
    {
      "dataset_name": "cuad",
      "dataset_version": "v1",
      "n_examples": 510,
      "metrics": {
        "extraction_f1": { "value": 0.82, "ci_lower": 0.80, "ci_upper": 0.84, "n": 41, "unit": "f1" },
        "extraction_precision": { "value": 0.85, "ci_lower": 0.83, "ci_upper": 0.87, "n": 41, "unit": "precision" },
        "extraction_recall": { "value": 0.79, "ci_lower": 0.77, "ci_upper": 0.81, "n": 41, "unit": "recall" },
        "hallucination_rate": { "value": 0.03, "ci_lower": null, "ci_upper": null, "n": 510, "unit": "rate" },
        "avg_latency_ms": { "value": 1250, "ci_lower": null, "ci_upper": null, "n": 510, "unit": "ms" },
        "peak_memory_mb": { "value": 12.5, "ci_lower": null, "ci_upper": null, "n": 510, "unit": "MB" }
      }
    }
  ],
  "model_slots": [
    {
      "slot_name": "default",
      "provider": "ollama",
      "model": "llama3.2:3b",
      "metrics": { "cuad": { "extraction_f1": { "value": 0.82, ... } } },
      "total_latency_ms": 637500,
      "peak_memory_mb": 12.5
    }
  ],
  "regression": {
    "baseline_id": "def456abc",
    "deltas": {
      "cuad|precheck|default|extraction_f1": -0.01
    },
    "regressions_detected": false
  }
}
```
