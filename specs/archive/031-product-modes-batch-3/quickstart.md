# Quickstart: Product Modes Batch 3

**Date**: 2026-07-09
**Phase**: Phase 1 (Design)
**Status**: All 5 batch-3 modes defined

## Prerequisites

- openreview CLI installed (`uv run openreview --version`)
- At least one AI provider configured in gateway (`openreview gateway wizard`)
- A test document per mode (PDF or DOCX) — synthetic fixtures in `tests/fixtures/`

## Validation Scenarios

### 1. FranchiseCheck

```bash
# Basic usage
uv run openreview franchisecheck tests/fixtures/franchise-agreement.pdf

# JSON output
uv run openreview franchisecheck tests/fixtures/franchise-agreement.pdf --format json

# Memo export
uv run openreview franchisecheck tests/fixtures/franchise-agreement.pdf --memo-format md

# Skip PII stripping
uv run openreview franchisecheck tests/fixtures/franchise-agreement.pdf --no-pii

# Custom playbook override
uv run openreview franchisecheck tests/fixtures/franchise-agreement.pdf --playbook custom-franchise.yaml

# Expected outcome:
# - Parses the franchise agreement
# - Assesses franchise fee, territory, renewal/termination, advertising fund, transfer
# - Produces Green/Amber/Red assessments — at minimum Amber (territory vague) + Red (unilateral termination)
# - FDD-like sections parsed (Item 5 franchise fee, Item 12 territory, Item 17 renewal/termination)
# - Memo exported to ./memo/{filename}-franchisecheck.pdf
```

### 2. OpCheck

```bash
# Basic usage
uv run openreview opcheck tests/fixtures/operating-agreement.pdf

# JSON output
uv run openreview opcheck tests/fixtures/operating-agreement.pdf --format json

# Memo export
uv run openreview opcheck tests/fixtures/operating-agreement.pdf --memo-format md

# Verify help text shows "Operating Agreement"
uv run openreview opcheck --help
# Expected first line: "Review an Operating Agreement (LLC governance document)"

# Expected outcome:
# - Parses the operating agreement
# - Assesses membership structure, capital contributions, profit/loss allocation, voting, transfer/dissolution
# - Produces Green/Amber/Red assessments — at minimum Green (member-managed with equal voting) + Red (disproportionate voting)
# - Memo exported to ./memo/{filename}-opcheck.pdf
```

### 3. PartnerCheck

```bash
# Basic usage
uv run openreview partnercheck tests/fixtures/partnership-agreement.pdf

# JSON output
uv run openreview partnercheck tests/fixtures/partnership-agreement.pdf --format json

# Memo export
uv run openreview partnercheck tests/fixtures/partnership-agreement.pdf --memo-format md

# Expected outcome:
# - Parses the partnership agreement
# - Assesses capital contributions, management, withdrawal, liability, dispute resolution
# - Produces Green/Amber/Red assessments — at minimum Green (clear profit allocation) + Red (joint/several liability)
# - Memo exported to ./memo/{filename}-partnercheck.pdf
```

### 4. SponsorCheck

```bash
# Basic usage
uv run openreview sponsorcheck tests/fixtures/sponsorship-agreement.pdf

# JSON output
uv run openreview sponsorcheck tests/fixtures/sponsorship-agreement.pdf --format json

# Memo export
uv run openreview sponsorcheck tests/fixtures/sponsorship-agreement.pdf --memo-format md

# Expected outcome:
# - Parses the sponsorship agreement
# - Assesses fee, benefits, IP, termination, indemnification
# - Produces Green/Amber/Red assessments — at minimum Green (mutual termination) + Amber (broad exclusivity)
# - Memo exported to ./memo/{filename}-sponsorcheck.pdf
```

### 5. DistroCheck

```bash
# Basic usage
uv run openreview distrocheck tests/fixtures/distribution-agreement.pdf

# JSON output
uv run openreview distrocheck tests/fixtures/distribution-agreement.pdf --format json

# Memo export
uv run openreview distrocheck tests/fixtures/distribution-agreement.pdf --memo-format md

# Verify franchise-classification boundary flag appears
uv run openreview distrocheck tests/fixtures/distribution-agreement.pdf --format json | grep FRANCHISE_BOUNDARY
# Expected: contains "FRANCHISE_BOUNDARY:" for at least one clause

# Expected outcome:
# - Parses the distribution agreement
# - Assesses territory, minimums, pricing, IP, termination
# - Produces Green/Amber/Red assessments — at minimum Amber (minimum purchase) + Red (no market adjustment)
# - At least one clause flagged [FRANCHISE_BOUNDARY: borderline] (pricing control or operating standards)
# - Memo exported to ./memo/{filename}-distrocheck.pdf
```

## Cross-Cutting Scenarios

### Verify CLI discoverability

```bash
uv run openreview --help
# Expected: lists all 5 new subcommands in product-modes section:
#   franchisecheck    Review a franchise agreement or franchise disclosure document
#   opcheck           Review an Operating Agreement (LLC governance document)
#   partnercheck      Review a general or limited partnership agreement
#   sponsorcheck      Review a sponsorship agreement
#   distrocheck       Review a distribution or reseller agreement
```

### Verify per-subcommand help

```bash
uv run openreview franchisecheck --help
# Expected: shows franchise-specific help text

uv run openreview opcheck --help
# Expected: shows "Operating Agreement" in first line

uv run openreview distrocheck --help
# Expected: mentions franchise-classification boundary flag
```

### Verify JSON output consistency

```bash
uv run openreview franchisecheck test.pdf --format json | jq '.mode'
# Expected: "franchisecheck"

uv run openreview opcheck test.pdf --format json | jq '.mode'
# Expected: "opcheck"

# All modes produce identical JSON schema with mode field distinguishing source
```

### Verify VALID_MODES frozenset completeness

```bash
uv run python -c "
from openreview_cli.benchmark.cli import VALID_MODES
for m in ['franchisecheck', 'opcheck', 'partnercheck', 'sponsorcheck', 'distrocheck']:
    assert m in VALID_MODES, f'{m} not in VALID_MODES'
    print(f'{m}: PASS')
print('All 5 modes in VALID_MODES: PASS')
"
```

### Verify baseline JSON files exist

```bash
for m in franchisecheck opcheck partnercheck sponsorcheck distrocheck; do
    if [ -f "docs/benchmarks/$m.json" ]; then
        echo "$m.json: EXISTS"
    else
        echo "$m.json: MISSING"
    fi
done
```

### Verify --no-pii flag works across modes

```bash
uv run openreview franchisecheck tests/fixtures/franchise-agreement.pdf --no-pii --format json
# Expected: PII stripping skipped, assessment matches non-flag invocation
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
| OpCheck help text | OpCheck | "Operating Agreement" in first line |
| FRANCHISE_BOUNDARY flag | DistroCheck | Flag appears in output |
| FRANCHISE_BOUNDARY flag | FranchiseCheck | Flag appears in output for non-franchise clauses |
| VALID_MODES | All | All 5 keys in frozenset |
| Baseline JSON | All | `docs/benchmarks/<mode>.json` exists |
