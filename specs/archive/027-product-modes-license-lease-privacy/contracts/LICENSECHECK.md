# LicenseCheck CLI Contract

**Mode**: `licensecheck`
**Spec Ref**: [S-027] [S-011]

## Command Definition

```
openreview licensecheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to SaaS license agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format |
| `--playbook` | Path | No | `saas-license-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser [S-002]
2. Strip PII (unless `--no-pii` flag) [S-003]
3. Load default playbook `saas-license-v1.yaml` (or custom via `--playbook`) [S-024]
4. Run extraction agent with domain-specific prompt template [S-009]
5. Run QA agent to verify extraction [S-011]
6. Generate ReviewReport with three-color confidence output [S-013]
7. Output formatted result (text/json/memo) [S-021]

## Output

### text (default)

```
LicenseCheck — SaaS License Agreement Review
════════════════════════════════════════════

Favorable to Licensee:
  ✅ q1: License grant is perpetual (GREEN, 0.92)
  ⚠️ q2: Auto-renewal notice period unclear (AMBER, 0.55)
  ✅ q3: Liability cap reasonable (GREEN, 0.88)

Neutral / Standard:
  ⚠️ q4: Data-deletion obligations partially specified (AMBER, 0.60)
  ...

Adverse to Licensee:
  ❌ q8: No data-deletion obligation (RED, 0.85)
  ...

Overall: AMBER
```

### json

```json
{"mode": "licensecheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/agreement-licensecheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-licensecheck.pdf` [S-021]

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |
