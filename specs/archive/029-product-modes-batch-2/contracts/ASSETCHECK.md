# CLI Subcommand Contract: AssetCheck

**Mode name**: `assetcheck`
**Spec ref**: Spec 029 FR1
**Playbook file**: `asset-transfer-v1.yaml`
**BUNDLED_PLAYBOOKS key**: `assetcheck`
**MODE_VOCABULARY key**: `assetcheck`

## Interface

```bash
openreview assetcheck <path> [options]
```

`<path>`: Path to an asset transfer/assignment agreement (PDF or DOCX).

## Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--no-pii` | flag | `False` | Skip PII stripping |
| `--playbook` | str | bundled | Path to custom YAML playbook override |
| `--format` | str | `text` | Output format: `text` or `json` |
| `--output` | str | stdout | Write output to file instead of stdout |
| `--memo-format` | list | `[]` | Export format(s): `md`, `json`, `docx` |
| `--output-dir` | str | `review_results/` | Directory for memo files |
| `--verbose` | flag | `False` | Show per-clause progress |
| `--confidence-threshold` / `-ct` | float | `0.7` | Confidence threshold (0.0-1.0) |

## Help text

```
Review an asset transfer/assignment agreement with AssetCheck.
```

## Mode routing

- Registered via `_register_product_mode(app, name="assetcheck", ...)`
- `_run_product_review(mode="assetcheck", ...)` resolves `BUNDLED_PLAYBOOKS["assetcheck"]`
- `run_review(mode="assetcheck", ...)` uses `MODE_VOCABULARY["assetcheck"]`

## JSON output mode field

```json
{"mode": "assetcheck", ...}
```

## Memo export prefix

`assetcheck-`
