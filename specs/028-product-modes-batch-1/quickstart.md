# Quickstart: Product Modes Batch 1

**Date**: 2026-07-08
**Phase**: Phase 9 (Cross-Cutting Polish)
**Status**: All 6 batch-1 modes + 2 remediation modes verified

## Prerequisites

- openreview CLI installed (`uv run openreview --version`)
- At least one AI provider configured in gateway (`openreview gateway wizard`)
- A test document per mode (PDF or DOCX)

## Validation Scenarios

### 1. IndemnityCheck

```bash
# Basic usage
uv run openreview indemnitycheck indemnity.pdf

# JSON output
uv run openreview indemnitycheck indemnity.pdf --format json

# Memo export
uv run openreview indemnitycheck indemnity.pdf --memo-format md

# Skip PII stripping (local, no external API)
uv run openreview indemnitycheck indemnity.pdf --no-pii

# Custom playbook override
uv run openreview indemnitycheck indemnity.pdf --playbook custom-indemnity-playbook.yaml

# Expected outcome:
# - Parses the indemnification agreement
# - Assesses indemnity scope, liability cap, survival period, defense obligations
# - Produces Green/Amber/Red assessments per category
# - Memo exported to ./memo/{filename}-indemnitycheck.pdf
```

### 2. ConsultCheck

```bash
# Basic usage
uv run openreview consultcheck consulting-agreement.pdf

# JSON output
uv run openreview consultcheck consulting-agreement.pdf --format json

# Memo export
uv run openreview consultcheck consulting-agreement.pdf --memo-format md

# Expected outcome:
# - Parses the consulting services agreement
# - Assesses SOW specificity, payment terms, IP ownership, confidentiality, termination
# - Memo exported to ./memo/{filename}-consultcheck.pdf
```

### 3. WorkCheck

```bash
# Basic usage
uv run openreview workcheck contractor-agreement.pdf

# JSON output
uv run openreview workcheck contractor-agreement.pdf --format json

# Memo export
uv run openreview workcheck contractor-agreement.pdf --memo-format md

# Expected outcome:
# - Parses the independent contractor agreement
# - Assesses worker classification, IP ownership, payment, non-compete, termination
# - Memo exported to ./memo/{filename}-workcheck.pdf
```

### 4. LOICheck

```bash
# Basic usage
uv run openreview loicheck LOI.pdf

# JSON output
uv run openreview loicheck LOI.pdf --format json

# Memo export
uv run openreview loicheck LOI.pdf --memo-format md

# Expected outcome:
# - Parses the letter of intent
# - Assesses binding provisions, exclusivity, breakup fees, due diligence, expiration
# - Memo exported to ./memo/{filename}-loicheck.pdf
```

### 5. SubCheck

```bash
# Basic usage
uv run openreview subcheck subcontract.pdf

# JSON output
uv run openreview subcheck subcontract.pdf --format json

# Memo export
uv run openreview subcheck subcontract.pdf --memo-format md

# Expected outcome:
# - Parses the subcontractor agreement
# - Assesses flow-through, payment terms, indemnity, change-order, termination
# - Memo exported to ./memo/{filename}-subcheck.pdf
```

### 6. SettlementCheck

```bash
# Basic usage
uv run openreview settlementcheck settlement.pdf

# JSON output
uv run openreview settlementcheck settlement.pdf --format json

# Memo export
uv run openreview settlementcheck settlement.pdf --memo-format md

# Expected outcome:
# - Parses the settlement and release agreement
# - Assesses release scope, payment terms, confidentiality, unknown claims, breach
# - Memo exported to ./memo/{filename}-settlementcheck.pdf
```

## Cross-Cutting Scenarios

### Verify CLI discoverability

```bash
uv run openreview --help
# Expected: lists all 6 new subcommands in product-modes section:
#   indemnitycheck    Review an indemnification agreement
#   consultcheck      Review a consulting services agreement
#   workcheck         Review an independent contractor agreement
#   loicheck          Review a letter of intent or MOU
#   subcheck          Review a subcontractor agreement
#   settlementcheck   Review a settlement and release agreement
```

### Verify per-subcommand help

```bash
uv run openreview indemnitycheck --help
# Expected: shows mode-specific help text describing contract type and typical use
```

### Verify JSON output consistency

```bash
uv run openreview indemnitycheck test.pdf --format json | jq '.mode'
# Expected: "indemnitycheck"

uv run openreview consultcheck test.pdf --format json | jq '.mode'
# Expected: "consultcheck"
# All modes produce identical JSON schema with mode field distinguishing source
```

### Verify PII consistency

```bash
# Run two modes on same document with PII content
uv run openreview indemnitycheck test-with-pii.pdf --output json > output1.json
uv run openreview consultcheck test-with-pii.pdf --output json > output2.json
# Expected: PII placeholders identical across modes (anonymized text same)
```

### Verify playbook override

```bash
# Run with custom playbook that has different default positions
uv run openreview indemnitycheck test.pdf --playbook custom.yaml --output json
# Expected: different assessments from default playbook run
```

## Expected Outcomes Summary

| Scenario | Mode | Expected Outcome |
|----------|------|-----------------|
| Basic review | All | Non-empty ReviewReport with assessments |
| JSON output | All | Valid JSON with correct `mode` field |
| Memo export | All | File > 1 KB in `./memo/` |
| PII stripping | All | PII placeholders in output |
| Playbook override | All | Different assessments when custom playbook used |
| --no-pii | All | Raw text preserved, no PII placeholders |
| CLI help | All | Mode-specific help text displayed |
