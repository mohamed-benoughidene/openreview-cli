# OpCheck CLI Contract

**Mode**: `opcheck`
**Spec Ref**: [S-031]

## Command Definition

```
openreview opcheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to operating agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `operating-agreement-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `operating-agreement-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: operating agreement, LLC, member, manager, capital contribution, capital call, profit share, distribution, voting, transfer, buy-sell, dissolution, indemnification, IRC 704(b).

## Output

### text (default)

```
OpCheck — Operating Agreement Review
═════════════════════════════════════

Favorable to You (LLC Member):
  ✅ q1: Member-managed with equal voting rights per member (GREEN, 0.93)
  ✅ q2: Profit/loss allocation per capita proportional to capital contribution (GREEN, 0.90)

Neutral / Standard:
  ⚠️ q3: Capital calls require majority member consent (AMBER, 0.68)

Adverse to You:
  ❌ q4: Manager has sole authority to incur debt above $50k without member approval (RED, 0.82)
  ❌ q5: Transfer restrictions include right of first refusal with no price floor (RED, 0.77)

Overall: AMBER
```

### json

```json
{"mode": "opcheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/operating-agreement-opcheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-opcheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |

## Notes

- The command name "opcheck" is shorthand. Help text spells out "Operating Agreement (LLC governance document)".
- Reviews from the perspective of a single LLC member. Multi-member rights and obligations beyond the member's role default to AMBER.
- Does not provide tax advice. IRC §704(b) references are clause-recognition features only.
