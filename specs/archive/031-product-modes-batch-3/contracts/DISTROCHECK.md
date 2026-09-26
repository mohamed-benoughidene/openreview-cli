# DistroCheck CLI Contract

**Mode**: `distrocheck`
**Spec Ref**: [S-031]

## Command Definition

```
openreview distrocheck <PATH> [--no-pii] [--output text|json|memo] [--playbook PATH]
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `PATH` | String | Yes | — | Path to distribution or reseller agreement (PDF or DOCX) |
| `--no-pii` | Flag | No | `False` | Skip PII stripping |
| `--output` | Choice | No | `text` | Output format (text, json, memo) |
| `--playbook` | Path | No | `distribution-v1.yaml` | Custom playbook override |
| `--verbose` | Flag | No | `False` | Verbose logging |
| `--config` | Path | No | `~/.config/openreview/auth.json` | Config path |

## Behavior

1. Parse document using existing PDF/DOCX parser
2. Strip PII (unless `--no-pii` flag)
3. Load default playbook `distribution-v1.yaml` (or custom via `--playbook`)
4. Run extraction agent with domain-specific prompt template (includes franchise-classification boundary flag)
5. Run QA agent to verify extraction
6. Generate ReviewReport with three-color confidence output
7. Output formatted result (text/json/memo)

## Extraction Prompt Vocabulary

Domain vocabulary: distribution, distributor, manufacturer, territory, exclusivity, minimum purchase, cure period, pricing, payment, inventory, returns, trademark license, termination, non-compete, channel restriction, jurisdiction, venue.
Franchise-classification boundary flag: `[FRANCHISE_BOUNDARY: yes|no|borderline]` per clause — advisory only, does not constitute legal classification.

## Output

### text (default)

```
DistroCheck — Distribution Agreement Review
══════════════════════════════════════════════

Favorable to You (Distributor):
  ✅ q1: Defined exclusive territory with clear geographic boundaries (GREEN, 0.94)

Neutral / Standard:
  ⚠️ q2: Minimum purchase requirement with 60-day cure period (AMBER, 0.71)
  ⚠️ q3: Non-compete limited to distribution territory (AMBER, 0.68)

Adverse to You:
  ❌ q4: Minimum purchase increases 20% annually with no market-adjustment clause (RED, 0.88)
  ⚠️ ⚠️ q5: Manufacturer controls pricing and operating standards [FRANCHISE_BOUNDARY: borderline] (AMBER, 0.60)

Overall: AMBER
```

### json

```json
{"mode": "distrocheck", "assessments": [...], "overall_confidence": "AMBER", "memo_path": "./memo/distribution-agreement-distrocheck.pdf"}
```

### memo

PDF export to `./memo/{filename}-distrocheck.pdf`

## Error Codes

| Code | Condition |
|------|-----------|
| 1 | Document cannot be parsed |
| 2 | PII engine fails |
| 3 | AI provider unavailable |
| 4 | Invalid playbook schema |

## Notes

- Includes franchise-classification boundary flag per clause. When a distribution agreement term (pricing control, operating standards, mandatory supplier mandates) approaches franchise-like regulation under FTC Franchise Rule 16 CFR §436 or state law, the flag renders as `yes` or `borderline`. This flag is advisory only and does not constitute a legal classification of the relationship.
- Reviews from the perspective of a single distributor. Multi-party obligations (manufacturer-distributor-customer chains) default to AMBER.
