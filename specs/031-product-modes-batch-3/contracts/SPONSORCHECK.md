# SponsorCheck CLI Contract

**Mode**: `sponsorcheck`
**Spec Ref**: [S-031]

## Command Definition

```
openreview sponsorcheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to sponsorship agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `sponsorship-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `sponsorship-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: sponsorship, sponsor, organizer, fee, payment, exclusivity, logo placement, event recognition, trademark license, termination, force majeure, indemnification, non-disparagement.

## Output

### text (default)

```
SponsorCheck — Sponsorship Agreement Review
═══════════════════════════════════════════════

Favorable to You (Organizer):
  ✅ q1: Mutually agreed fee with 50% upfront, 50% on event date (GREEN, 0.89)
  ✅ q2: Mutual termination rights with 30-day cure period (GREEN, 0.92)

Neutral / Standard:
  ⚠️ q3: Broad exclusivity clause — no competitor sponsors allowed (AMBER, 0.66)

Adverse to You:
  ❌ q4: Unilateral indemnification of sponsor for all claims (RED, 0.83)

Overall: AMBER
```

### json

```json
{"mode": "sponsorcheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/sponsorship-agreement-sponsorcheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-sponsorcheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |
