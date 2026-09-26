# Interface Contract: Real Baseline One-Shot (FR-5)

**Spec ref**: spec 030 FR-5
**New function**: `_build_gateway_pipeline()` in `benchmark/cli.py`

## Interface

```python
def _build_gateway_pipeline(mode: str) -> PipelineFn:
    """Build a real AI gateway pipeline for the given mode.

    Returns a PipelineFn that routes text+category through the AI Gateway
    using the configured model slot for *mode* (falling back to "default").
    """
```

## PipelineFn Contract

```python
# Type alias (unchanged from runner.py:24)
PipelineFn = Callable[[str, str], dict[str, Any]]
#                       text    category   → prediction dict
```

## Prediction Dict

| Key | Type | Description |
|-----|------|-------------|
| `start` | int | Span start (CUAD) |
| `end` | int | Span end (CUAD) |
| `category` | str | Pass-through from input |
| `label` | str | Classification: entailment/contradiction/neutral (ContractNLI) or attention (MAUD) |
| `match` | bool | Whether clause matches (MAUD) |
| `mode` | str | Mode name (for report metadata) |

## Behaviour

| Aspect | Value |
|--------|-------|
| Provider | Configured AI Gateway (Ollama or cloud slot) |
| Model slot | Mode-specific if configured, else "default" |
| Network calls | One per dataset item |
| Baseline output | JSON at `docs/benchmarks/baseline-YYYY-MM-DD.json` |
| CI automation | None — manual one-shot only |
| Cost | Provider-dependent (Ollama free, cloud slots bill tokens) |

## Output JSON Structure

```json
{
  "mode_results": [
    {
      "mode": "precheck",
      "dataset": "cuad",
      "extraction_f1": 0.72,
      "comparison_f1": null,
      "classification_f1": null,
      "hallucination_rate": 0.05,
      "latency_ms": 3421.0,
      "peak_memory_mb": 45.2
    }
  ],
  "git_commit": "a1b2c3d",
  "git_branch": "feat/030-benchmark-mode-validation",
  "provider": "ollama",
  "model": "llama3.2:3b",
  "timestamp": "2026-07-09T12:00:00+00:00"
}
```

## Workflow

```bash
openreview benchmark run --all --save-baseline --format json \
  --output docs/benchmarks/baseline-$(date +%F).json
```
