# IndemnityCheck CLI Contract

**Mode**: `indemnitycheck`
**Spec Ref**: [S-028]

## Command Definition

```
openreview indemnitycheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to indemnification agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `indemnification-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `indemnification-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: indemnify, hold harmless, defense, liability cap, survival, third-party claim, broad form, limited form, mutual, sole.

## Output

### text (default)

```
IndemnityCheck — Indemnification Agreement Review
═══════════════════════════════════════════════════

Favorable to You (Small Business):
  ✅ q1: Mutual indemnification with reasonable liability cap (GREEN, 0.92)
  ⚠️ q2: Survival period indefinite — no fixed limit (AMBER, 0.55)

Neutral / Standard:
  ⚠️ q3: Defense obligations standard but uncapped (AMBER, 0.60)

Adverse to You:
  ❌ q4: Broad-form indemnity for third-party claims (RED, 0.85)

Overall: AMBER
```

### json

```json
{"mode": "indemnitycheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/indemnity-indemnitycheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-indemnitycheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |
