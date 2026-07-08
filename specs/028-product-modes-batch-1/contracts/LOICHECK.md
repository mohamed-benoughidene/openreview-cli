# LOICheck CLI Contract

**Mode**: `loicheck`
**Spec Ref**: [S-028]

## Command Definition

```
openreview loicheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to letter of intent or MOU (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `letter-of-intent-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `letter-of-intent-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: non-binding, exclusivity, no-shop, breakup fee, due diligence, confidentiality, binding provisions, purchase price.

## Output

### text (default)

```
LOICheck — Letter of Intent Review
═══════════════════════════════════════

Favorable to You (Startup):
  ✅ q1: Clear non-binding language for non-P&S provisions (GREEN, 0.92)

Neutral / Standard:
  ⚠️ q2: 90-day exclusivity period — long but negotiable (AMBER, 0.50)
  ⚠️ q3: Breakup fee provision at market rate (AMBER, 0.65)

Adverse to You:
  ❌ q4: Broad binding language could make entire LOI enforceable (RED, 0.88)

Overall: AMBER
```

### json

```json
{"mode": "loicheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/LOI-loicheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-loicheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |
