# FranchiseCheck CLI Contract

**Mode**: `franchisecheck`
**Spec Ref**: [S-031]

## Command Definition

```
openreview franchisecheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to franchise agreement or FDD (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `franchise-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `franchise-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template (includes franchise-classification boundary flag)
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: franchise, franchisor, franchisee, FDD, territory, royalty, advertising fund, renewal, termination, non-compete, transfer, right of first refusal, franchise fee.
Franchise-classification boundary flag: `[FRANCHISE_BOUNDARY: yes|no|borderline]` per clause.

## Output

### text (default)

```
FranchiseCheck — Franchise Agreement Review
═══════════════════════════════════════════════

Favorable to You (Franchisee):
  ✅ q1: Exclusive territory with defined geographic boundaries (GREEN, 0.95)
  ✅ q2: Renewal terms with 10-year term + renewal option (GREEN, 0.88)

Neutral / Standard:
  ⚠️ q3: Advertising fund contribution capped at 2% of gross sales (AMBER, 0.72)
  ⚠️ q4: Transfer subject to franchisor's reasonable consent (AMBER, 0.65)

Adverse to You:
  ❌ q5: Unilateral termination by franchisor without cause (RED, 0.91)

Overall: AMBER
```

### json

```json
{"mode": "franchisecheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/franchise-agreement-franchisecheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-franchisecheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |
