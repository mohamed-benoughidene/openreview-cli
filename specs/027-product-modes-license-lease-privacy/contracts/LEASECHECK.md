# LeaseCheck CLI Contract

**Mode**: `leasecheck`
**Spec Ref**: [S-027] [S-011]

## Command Definition

```
openreview leasecheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to commercial lease agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format |
| `--playbook` | Path | No | `commercial-lease-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser [S-002]
2. Strip PII (unless `--no-pii` flag) [S-003]
3. Load default playbook `commercial-lease-v1.yaml` (or custom via `--playbook`) [S-024]
4. Run extraction agent with domain-specific prompt template [S-009]
5. Run QA agent to verify extraction [S-011]
6. Generate ReviewReport with three-color confidence output [S-013]
7. Output formatted result (text/json/memo) [S-021]

## Output

### text (default)

```
LeaseCheck — Commercial Lease Agreement Review
═══════════════════════════════════════════════

Favorable to Tenant:
  ✅ q1: CPI-capped rent escalation (GREEN, 0.90)
  ...

Neutral / Standard:
  ⚠️ q4: Term length and renewal standard (AMBER, 0.65)
  ...

Adverse to Tenant:
  ❌ q7: Landlord-only termination clause present (RED, 0.88)
  ❌ q8: Triple-net maintenance with no cap (RED, 0.82)
  ...

Overall: AMBER
```

### json

```json
{"mode": "leasecheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/lease-leasecheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-leasecheck.pdf` [S-021]

## Error Codes

Same as LicenseCheck (see LICENSECHECK.md).
