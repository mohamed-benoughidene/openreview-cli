# WorkCheck CLI Contract

**Mode**: `workcheck`
**Spec Ref**: [S-028]

## Command Definition

```
openreview workcheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to independent contractor agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `work-for-hire-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `work-for-hire-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: work for hire, independent contractor, classification, commissioned work, assignment, non-compete, IRS factors, scope of services.

## Output

### text (default)

```
WorkCheck — Independent Contractor Agreement Review
══════════════════════════════════════════════════════

Favorable to You (Contractor):
  ✅ q1: Clear independent contractor status with IRS factors (GREEN, 0.85)
  ⚠️ q2: Payment terms 30 days net — standard (AMBER, 0.65)

Neutral / Standard:
  ⚠️ q3: Work-for-hire designation but scope unclear (AMBER, 0.55)

Adverse to You:
  ❌ q4: Broad non-compete covering all client business activities (RED, 0.90)

Overall: AMBER
```

### json

```json
{"mode": "workcheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/contractor-agreement-workcheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-workcheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |
