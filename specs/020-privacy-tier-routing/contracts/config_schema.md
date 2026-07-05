# Configuration Schema: Privacy Tier

## Key: `privacy.tier`

Part of the existing `config.yml` schema. The privacy tier is a top-level section under the `privacy` key.

### Schema

```yaml
# config.yml
privacy:
  tier: maximum   # string, required. One of: maximum, balanced, performance
```

### Validation

| Rule | Behaviour |
|------|-----------|
| Key is missing entirely | Default to `maximum`. Show warning on first operation. |
| Key present but `null` | Default to `maximum`. Show warning on first operation. |
| Key present with valid value | Use value as-is. |
| Key present with invalid value | Default to `maximum`. Show warning: "Unrecognized privacy tier '<value>'. Valid values: maximum, balanced, performance. Defaulting to Maximum." |
| Multiple YAML documents | Only the first document's `privacy.tier` is read. |

### Display

Tier is displayed in CLI output at two points:

1. **Progress banner** (beginning of every model-call operation):
   ```
   Privacy tier: MAXIMUM — all inference local
   ```
   Descriptions by tier:
   - `maximum` → "all inference local"
   - `balanced` → "local embeddings, cloud LLM (PII stripped)"
   - `performance` → "cloud inference (PII stripped before egress)"

2. **Final report footer** (end of operation):
   ```
   Processed under Maximum privacy tier. No data was sent to external services.
   ```
   Per tier:
   - maximum → "No data was sent to external services."
   - balanced → "Emdeddings processed locally. Cloud LLM received PII-stripped text (<N> entities redacted)."
   - performance → "All inference used cloud providers. PII was stripped before all external calls (<N> entities redacted)."

### CLI Get Command

```
openreview config get privacy.tier
```

Returns the current effective tier value. If defaulting due to missing/invalid config, shows the effective value and a note about the default. Example output:

```
$ openreview config get privacy.tier
maximum  (default: privacy.tier not configured)
```

### Config Set Command

```
openreview config set privacy.tier <value>
```

Validates value before writing. Invalid values produce a CLI error and are not written:

```
$ openreview config set privacy.tier invalid
Error: 'invalid' is not a valid privacy tier. Valid values: maximum, balanced, performance.
```
