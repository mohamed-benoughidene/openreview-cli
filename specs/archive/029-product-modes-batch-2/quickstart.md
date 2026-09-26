# Quickstart Validation Guide — Product Modes Batch 2

**Date**: 2026-07-08
**Feature**: Five new product modes + nine orphan mode CLI wiring

---

## Prerequisites

- Python 3.12 installed
- `uv` installed
- Dependencies installed: `uv sync`
- At least one AI provider configured in the gateway

## Setup

```bash
# Ensure you're on the right branch
git checkout feat/029-product-modes-batch-2

# Install dependencies
uv sync

# Verify the CLI builds
uv run openreview --version

# Verify the pre-commit hook configuration
uv run pre-commit run --all-files
```

## Validation Scenarios

### V1: New Modes — CLI Registration (5 tests)

```bash
# AssetCheck
uv run openreview assetcheck --help
# Expected: Shows "Review an asset transfer/assignment agreement with AssetCheck."
# and lists: --no-pii, --playbook, --format, --output, --memo-format, --output-dir, --verbose, --confidence-threshold/-ct

# BuyCheck
uv run openreview buycheck --help
# Expected: Shows "Review an asset purchase/business acquisition agreement with BuyCheck."

# EngageCheck
uv run openreview engagecheck --help
# Expected: Shows "Review a professional services engagement letter with EngageCheck."

# GuaranteeCheck
uv run openreview guaranteecheck --help
# Expected: Shows "Review a personal guarantee/suretyship agreement with GuaranteeCheck."

# LoanCheck
uv run openreview loancheck --help
# Expected: Shows "Review a loan agreement/promissory note with LoanCheck."
```

### V2: Orphan Modes — CLI Registration (9 tests)

```bash
# LicenseCheck
uv run openreview licensecheck --help
# Expected: Shows "Review a SaaS/software license agreement with LicenseCheck."

# LeaseCheck
uv run openreview leasecheck --help
# Expected: Shows "Review a commercial lease agreement with LeaseCheck."

# PrivacyCheck
uv run openreview privacycheck --help
# Expected: Shows "Review a Data Processing Agreement with PrivacyCheck."

# IndemnityCheck
uv run openreview indemnitycheck --help
# Expected: Shows "Review an indemnification agreement with IndemnityCheck."

# ConsultCheck
uv run openreview consultcheck --help
# Expected: Shows "Review a consulting services agreement with ConsultCheck."

# WorkCheck
uv run openreview workcheck --help
# Expected: Shows "Review a work-for-hire/independent contractor agreement with WorkCheck."

# LOICheck
uv run openreview loicheck --help
# Expected: Shows "Review a letter of intent or MOU with LOICheck."

# SubCheck
uv run openreview subcheck --help
# Expected: Shows "Review a subcontractor agreement with SubCheck."

# SettlementCheck
uv run openreview settlementcheck --help
# Expected: Shows "Review a settlement/release agreement with SettlementCheck."
```

### V3: Global CLI Discoverability

```bash
uv run openreview --help
# Expected: The "Product Modes" section lists all 14 subcommands
# (5 new + 9 orphan + precheck + dealcheck + hirecheck = what's already registered)
# At minimum: assetcheck, buycheck, engagecheck, guaranteecheck, loancheck,
# licensecheck, leasecheck, privacycheck, indemnitycheck, consultcheck,
# workcheck, loicheck, subcheck, settlementcheck
```

### V4: Playbook Schema Validation (5 tests)

```bash
# Each new playbook must load without error
uv run python3 -c "
from pathlib import Path
from openreview_cli.review.playbook import load_playbook
playbooks = [
    'asset-transfer-v1.yaml',
    'asset-purchase-v1.yaml',
    'engagement-letter-v1.yaml',
    'personal-guarantee-v1.yaml',
    'loan-agreement-v1.yaml',
]
base = Path('src/openreview_cli/review/playbooks')
for p in playbooks:
    playbook = load_playbook(base / p)
    print(f'OK: {p} ({len(playbook.categories)} categories)')
"
# Expected: All 5 playbooks load without PlaybookLoadError
```

### V5: Orphan Playbook Validation (9 existing — should still load)

```bash
uv run python3 -c "
from pathlib import Path
from openreview_cli.review.playbook import load_playbook
orphans = [
    'saas-license-v1.yaml',
    'commercial-lease-v1.yaml',
    'dpa-v1.yaml',
    'indemnification-v1.yaml',
    'consulting-agreement-v1.yaml',
    'work-for-hire-v1.yaml',
    'letter-of-intent-v1.yaml',
    'subcontractor-agreement-v1.yaml',
    'settlement-agreement-v1.yaml',
]
base = Path('src/openreview_cli/review/playbooks')
for p in orphans:
    playbook = load_playbook(base / p)
    print(f'OK: {p}')
"
# Expected: All 9 orphan playbooks load without error
```

### V6: BUNDLED_PLAYBOOKS Registration Check

```bash
uv run python3 -c "
from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS
assert 'assetcheck' in BUNDLED_PLAYBOOKS
assert 'buycheck' in BUNDLED_PLAYBOOKS
assert 'engagecheck' in BUNDLED_PLAYBOOKS
assert 'guaranteecheck' in BUNDLED_PLAYBOOKS
assert 'loancheck' in BUNDLED_PLAYBOOKS
print('All 5 new modes registered in BUNDLED_PLAYBOOKS')
"
```

### V7: MODE_VOCABULARY Registration Check

```bash
uv run python3 -c "
from openreview_cli.review.prompts import MODE_VOCABULARY
assert 'assetcheck' in MODE_VOCABULARY
assert 'buycheck' in MODE_VOCABULARY
assert 'engagecheck' in MODE_VOCABULARY
assert 'guaranteecheck' in MODE_VOCABULARY
assert 'loancheck' in MODE_VOCABULARY
print('All 5 new modes registered in MODE_VOCABULARY')
"
```

### V8: Unit Tests

```bash
# Run only the playbook schema tests
uv run pytest tests/unit/test_playbook_schema.py -v -k "asset-transfer or asset-purchase or engagement-letter or personal-guarantee or loan-agreement"
# Expected: 5 tests pass
```

### V9: Integration Smoke Tests (5 new modes)

```bash
# Run smoke tests for new modes
uv run pytest tests/integration/test_assetcheck.py -v
uv run pytest tests/integration/test_buycheck.py -v
uv run pytest tests/integration/test_engagecheck.py -v
uv run pytest tests/integration/test_guaranteecheck.py -v
uv run pytest tests/integration/test_loancheck.py -v
# Expected: Each test validates subcommand --help, playbook schema, run_review non-empty
```

### V10: Orphan Mode CLI Routing Tests

```bash
uv run pytest tests/integration/test_orphan_modes.py -v
# Expected: 9 test cases pass — subcommand registers, --help works, invokes correct playbook, exits cleanly
```

### V11: Full Test Suite (excluding memory tests)

```bash
uv run pytest tests/unit/ tests/integration/ -k 'not memory' -q
# Expected: All existing + new tests pass
```

### V12: Code Quality

```bash
uv run ruff check src/openreview_cli/
uv run mypy src/openreview_cli/ --strict
# Expected: No new lint or type errors
```

## Expected Behavior Details

### JSON Output Schema (all modes)

```json
{
  "mode": "assetcheck",
  "document": {"filename": "document.pdf", "page_count": 5, "clause_count": 12, "pii_stripped": true},
  "assessments": [
    {
      "clause_id": "clause_1",
      "position": "preferred",
      "confidence": 0.92,
      "color": "green",
      "citation": "...",
      "playbook_category": "asset-description"
    }
  ],
  "summary": {"preferred_count": 2, "acceptable_count": 1, "walkaway_count": 0, "green_count": 2, "amber_count": 1, "red_count": 0},
  "confidence_threshold": 0.7
}
```

The `mode` field in JSON output distinguishes which mode produced the report.

### Memo Export Filename Convention

All modes use the mode name as a filename prefix:
- `assetcheck-<document-name>-memo.md`
- `buycheck-<document-name>-memo.json`
- `licensecheck-<document-name>-memo.md`
- etc.

### Error Conditions

- Missing document path → Exit code 1 with error message
- Invalid playbook YAML → `PlaybookLoadError` with details
- No AI provider configured → Gateway error propagated to user
- Orphan mode without fixture → Exit cleanly if --help, error if no path provided (same as all modes)

## Links

- [CLI contract: ASSETCHECK.md](./contracts/ASSETCHECK.md)
- [CLI contract: BUYCHECK.md](./contracts/BUYCHECK.md)
- [CLI contract: ENGAGECHECK.md](./contracts/ENGAGECHECK.md)
- [CLI contract: GUARANTEECHECK.md](./contracts/GUARANTEECHECK.md)
- [CLI contract: LOANCHECK.md](./contracts/LOANCHECK.md)
- [Orphan mode contracts](./contracts/) (9 files)
- [Data model](./data-model.md)
- [Implementation plan](./plan.md)
