# ConsultCheck CLI Contract

**Mode**: `consultcheck`
**Spec Ref**: [S-028]

## Command Definition

```
openreview consultcheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to consulting services agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `consulting-agreement-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `consulting-agreement-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: statement of work, deliverable, scope creep, IP assignment, work product, non-solicit, change order, independent contractor.

## Output

### text (default)

```
ConsultCheck — Consulting Services Agreement Review
═════════════════════════════════════════════════════

Favorable to You (Consultant):
  ✅ q1: Clear SOW with change-order process (GREEN, 0.90)
  ✅ q2: IP assignment upon full payment (GREEN, 0.88)

Neutral / Standard:
  ⚠️ q3: Limitation of liability at 1x fees (AMBER, 0.60)

Adverse to You:
  ❌ q4: Non-solicit clause extends 18 months post-term (RED, 0.82)

Overall: AMBER
```

### json

```json
{"mode": "consultcheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/engagement-consultcheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-consultcheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |
