# SubCheck CLI Contract

**Mode**: `subcheck`
**Spec Ref**: [S-028]

## Command Definition

```
openreview subcheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to subcontractor agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `subcontractor-agreement-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `subcontractor-agreement-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: flow-through, pay-if-paid, pay-when-paid, broad form indemnity, no-damages-for-delay, change order, prime contract, incorporation by reference.

## Output

### text (default)

```
SubCheck — Subcontractor Agreement Review
═══════════════════════════════════════════

Favorable to You (Subcontractor):
  ✅ q1: Clear change-order process with mutual agreement (GREEN, 0.87)

Neutral / Standard:
  ⚠️ q2: Flow-through clause with reasonable notice of prime terms (AMBER, 0.60)
  ⚠️ q3: Pay-when-paid provision — standard in industry (AMBER, 0.65)

Adverse to You:
  ❌ q4: Broad-form indemnity for GC's own negligence (RED, 0.85)
  ❌ q5: No-damages-for-delay clause with no exceptions (RED, 0.88)

Overall: RED
```

### json

```json
{"mode": "subcheck", "assessments": [...], "overall_confidence": "RED", "memo_path": "./memo/subcontract-subcheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-subcheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |
