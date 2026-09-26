# PrivacyCheck CLI Contract

**Mode**: `privacycheck`
**Spec Ref**: [S-027] [S-011]

## Command Definition

```
openreview privacycheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to data processing agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format |
| `--playbook` | Path | No | `dpa-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser [S-002]
2. Strip PII (unless `--no-pii` flag) [S-003]
3. Load default playbook `dpa-v1.yaml` (or custom via `--playbook`) [S-024]
4. Run extraction agent with domain-specific prompt template [S-009]
5. Run QA agent to verify extraction [S-011]
6. Generate ReviewReport with three-color confidence output [S-013]
7. Output formatted result (text/json/memo) [S-021]

## Output

### text (default)

```
PrivacyCheck — Data Processing Agreement Review
═══════════════════════════════════════════════

Favorable to Data Controller:
  ✅ q1: Processing scope clearly limited (GREEN, 0.94)
  ✅ q2: Sub-processor notification adequate (GREEN, 0.88)
  ⚠️ q3: Breach notification 48 hours (AMBER, 0.55)
  ...

Neutral / Standard:
  ✅ q4: Data retention timeline specified (GREEN, 0.91)
  ⚠️ q5: Audit right included with limitations (AMBER, 0.62)
  ✅ q6: DPA termination tied to agreement (GREEN, 0.85)
  ...

Adverse to Data Controller:
  ❌ q8: No right to object to sub-processor changes (RED, 0.78)
  ...

Overall: AMBER
```

### json

```json
{"mode": "privacycheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/dpa-privacycheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-privacycheck.pdf` [S-021]

## Error Codes

Same as LicenseCheck (see LICENSECHECK.md).
