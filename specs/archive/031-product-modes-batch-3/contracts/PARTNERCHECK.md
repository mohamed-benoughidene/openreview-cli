# PartnerCheck CLI Contract

**Mode**: `partnercheck`
**Spec Ref**: [S-031]

## Command Definition

```
openreview partnercheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to partnership agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `partnership-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `partnership-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: partnership, general partner, limited partner, capital contribution, profit share, loss allocation, management, withdrawal, expulsion, dissolution, joint and several liability, UPA, RUPA, non-compete, non-solicit, mediation, arbitration.

## Output

### text (default)

```
PartnerCheck — Partnership Agreement Review
══════════════════════════════════════════════

Favorable to You (Partner):
  ✅ q1: Profit/loss allocation proportional to capital contribution ratio (GREEN, 0.91)
  ✅ q2: Dispute resolution via binding mediation before litigation (GREEN, 0.87)

Neutral / Standard:
  ⚠️ q3: For-cause expulsion by majority vote with 30-day cure period (AMBER, 0.70)

Adverse to You:
  ❌ q4: Joint and several personal liability for all partnership debts (RED, 0.94)
  ❌ q5: Non-compete extends 2 years post-withdrawal across 200-mile radius (RED, 0.85)

Overall: AMBER
```

### json

```json
{"mode": "partnercheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/partnership-agreement-partnercheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-partnercheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |

## Notes

- Reviews from the perspective of a single partner. Multi-party obligations default to AMBER.
- General partnership liability (joint and several) is distinct from LLC limited liability. Use OpCheck for LLC operating agreements.
- The playbook prioritizes personal liability exposure as the highest-risk category for partners.
