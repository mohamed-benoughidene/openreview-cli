# SettlementCheck CLI Contract

**Mode**: `settlementcheck`
**Spec Ref**: [S-028]

## Command Definition

```
openreview settlementcheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to settlement and release agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `settlement-agreement-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `settlement-agreement-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: general release, specific release, non-disparagement, non-admission, waiver, unknown claims, confidentiality, Civil Code 1542.

## Output

### text (default)

```
SettlementCheck — Settlement and Release Agreement Review
═══════════════════════════════════════════════════════════

Favorable to You (Settling Party):
  ✅ q1: Specific release limited to dispute at hand (GREEN, 0.92)
  ⚠️ q2: Payment terms structured over 90 days (AMBER, 0.60)

Neutral / Standard:
  ⚠️ q3: Non-disparagement clause mutual (AMBER, 0.65)
  ⚠️ q4: Non-admission of liability clause present (AMBER, 0.70)

Adverse to You:
  ❌ q5: Broad confidentiality prevents reporting regulatory violations (RED, 0.85)

Overall: AMBER
```

### json

```json
{"mode": "settlementcheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/settlement-settlementcheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-settlementcheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |
