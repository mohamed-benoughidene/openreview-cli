# Implementation Plan: AssetCheck, BuyCheck, EngageCheck, GuaranteeCheck, LoanCheck + 9 Orphan Mode CLI Wiring

**Branch**: `feat/029-product-modes-batch-2` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/029-product-modes-batch-2/spec.md`

## Summary

Add five new product modes to the openreview CLI for transaction/finance contract types and unblock nine orphan modes from prior specs (027/028) by wiring their CLI subcommands. Each of five new modes reuses the existing single-party review pipeline with a domain-specific playbook YAML and extraction prompt template. The nine orphan modes require only CLI wiring — their playbooks, prompts, and BUNDLED_PLAYBOOKS entries already exist on disk. No pipeline changes required for any mode.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: No new runtime dependencies. Reuses existing stack: httpx, pydantic, rich, typer, PyMuPDF, python-docx, presidio-analyzer, presidio-anonymizer, cryptography, litellm, questionary, platformdirs, pyyaml.

**Storage**: SQLite (existing database layer) — no new tables. Playbooks stored as YAML files in `src/openreview_cli/review/playbooks/`.

**Testing**: pytest (existing suite). Unit tests for 5 new playbook schema validations. Integration smoke tests for 5 new modes with fixture documents. CLI routing tests for 9 orphan modes (no fixture docs required per spec clarification).

**Target Platform**: Linux, macOS, Windows (CLI)

**Project Type**: CLI tool (single-party contract review modes)

**Performance Goals**: <100 MB peak memory budget (110 MB hard floor, per constitution). Playbook + prompt additions add negligible (<1 MB) memory overhead per mode. No new parsers or in-memory collections.

**Constraints**: Same as established single-party review pipeline. No per-mode model routing overrides. No multi-party comparison. SLM-first/task-level model routing.

**Scale/Scope**: Five new CLI subcommands, five playbook YAML files, five extraction prompt templates, five integration smoke tests, five fixture documents. Nine orphan CLI subcommands (CLI wiring only).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **Pass** | All modes reuse existing PII stripping engine identically (per spec FR9). PII stripped before any external API call. No new PII-related code. |
| II. Local-First, CLI-Only | **Pass** | Subcommands on existing CLI-only architecture. No server, daemon, or telemetry. Five new + nine orphan subcommands add no background processes. |
| III. Hardware-Bounded | **Pass** | Playbook YAML files and prompt template additions add negligible memory overhead (<1 MB per mode). No new parsers, in-memory collections, or streaming changes. Existing pipeline peak unchanged. |
| IV. Dependency Minimalism | **Pass** | Zero new runtime dependencies. Reuses pyyaml for playbook parsing, existing prompt management. Each new mode = YAML file + dict entry + CLI registration. |
| V. Spec-Driven, YAGNI | **Pass** | Spec 029 defined before implementation. No speculative abstractions — follows established _register_product_mode pattern exactly. Orphan modes are pure tech-debt repayment (CLI wiring only). No per-mode model overrides, no multi-party review, no custom output templates. |

**Constitution Gate Verdict**: PASS — all five principles satisfied.

## Project Structure

### Documentation (this feature)

```
specs/029-product-modes-batch-2/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 design
├── quickstart.md        # Phase 1 validation scenarios
├── contracts/           # Phase 1 CLI contracts (14 files)
│   ├── ASSETCHECK.md
│   ├── BUYCHECK.md
│   ├── ENGAGECHECK.md
│   ├── GUARANTEECHECK.md
│   ├── LOANCHECK.md
│   ├── LICENSECHECK.md
│   ├── LEASECHECK.md
│   ├── PRIVACYCHECK.md
│   ├── INDEMNITYCHECK.md
│   ├── CONSULTCHECK.md
│   ├── WORKCHECK.md
│   ├── LOICHECK.md
│   ├── SUBCHECK.md
│   └── SETTLEMENTCHECK.md
├── tasks.md             # Phase 2 output (speckit.tasks)
└── spec.md              # Feature specification
```

### Source Code (repository root)

No new source directories. Changes to these existing files:

```
src/openreview_cli/
├── review/
│   ├── playbooks/
│   │   ├── asset-transfer-v1.yaml          # NEW — AssetCheck
│   │   ├── asset-purchase-v1.yaml          # NEW — BuyCheck
│   │   ├── engagement-letter-v1.yaml       # NEW — EngageCheck
│   │   ├── personal-guarantee-v1.yaml      # NEW — GuaranteeCheck
│   │   ├── loan-agreement-v1.yaml          # NEW — LoanCheck
│   │   └── [12 existing playbooks]         # unchanged
│   ├── playbook.py                         # append 5 entries to BUNDLED_PLAYBOOKS
│   └── prompts.py                          # append 5 mode entries to MODE_VOCABULARY
└── app.py                                  # append 14 CLI subcommands (5 new + 9 orphan)

tests/
├── unit/
│   └── test_playbook_schema.py             # add 5 playbook validation tests (new modes only)
├── integration/
│   ├── test_assetcheck.py                  # NEW — full smoke test
│   ├── test_buycheck.py                    # NEW — full smoke test
│   ├── test_engagecheck.py                 # NEW — full smoke test
│   ├── test_guaranteecheck.py              # NEW — full smoke test
│   ├── test_loancheck.py                   # NEW — full smoke test
│   ├── test_orphan_modes.py                # NEW — CLI routing tests for 9 orphan modes
│   └── [existing integration tests]        # unchanged
└── fixtures/
    ├── asset-transfer.pdf                  # NEW
    ├── asset-purchase.pdf                  # NEW
    ├── engagement-letter.pdf               # NEW
    ├── personal-guarantee.pdf              # NEW
    ├── loan-agreement.pdf                  # NEW
    └── [existing fixtures]                 # unchanged
```

**Structure Decision**: Follows existing single-mode pattern. No new directories or abstractions. Each new mode = playbook YAML + prompt template entry + BUNDLED_PLAYBOOKS entry + CLI subcommand. Orphan modes = CLI subcommand only.

## Implementation Order

### New Modes (5) — Playbook + Prompt + CLI + Test

#### Mode 1: AssetCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/asset-transfer-v1.yaml` | Create | 5-category playbook (asset identification, exclusions, representations, price/title, as-is/regulatory) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"assetcheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Add `"assetcheck"` entry to `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `assetcheck` CLI subcommand |
| `tests/fixtures/asset-transfer.pdf` | Create | Test document (minimal, valid PDF) |
| `tests/unit/test_playbook_schema.py` | Modify | Add asset-transfer-v1 schema validation test |
| `tests/integration/test_assetcheck.py` | Create | Smoke test: --help, playbook schema, run_review non-empty |

**Playbook categories**: Asset description and identification, Excluded assets, Seller/buyer reps, Purchase price and title, As-is condition and regulatory compliance

**Prompt vocabulary**: asset, assignment, bill of sale, as-is, warranty, encumbrance, transfer, delivery, excluded assets, purchase price

#### Mode 2: BuyCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/asset-purchase-v1.yaml` | Create | 5-category playbook (price, asset list, liabilities, reps, closing) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"buycheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Add `"buycheck"` entry to `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `buycheck` CLI subcommand |
| `tests/fixtures/asset-purchase.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add asset-purchase-v1 schema validation test |
| `tests/integration/test_buycheck.py` | Create | Smoke test |

**Playbook categories**: Purchase price and payment structure, Included/excluded assets, Assumed/excluded liabilities, Reps and warranties, Closing conditions and indemnification

**Prompt vocabulary**: purchase price, asset list, assumed liabilities, representations, warranties, indemnification, non-compete, bulk sale, earn-out, closing conditions

#### Mode 3: EngageCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/engagement-letter-v1.yaml` | Create | 5-category playbook (SOW, fees, IP, confidentiality, termination) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"engagecheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Add `"engagecheck"` entry to `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `engagecheck` CLI subcommand |
| `tests/fixtures/engagement-letter.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add engagement-letter-v1 schema validation test |
| `tests/integration/test_engagecheck.py` | Create | Smoke test |

**Playbook categories**: Scope of services and deliverables, Fees and billing terms, IP ownership (work product vs. pre-existing), Confidentiality and data protection, Termination and non-solicitation

**Prompt vocabulary**: scope of services, deliverables, fees, expenses, IP ownership, work product, confidentiality, limitation of liability, non-solicit, termination

#### Mode 4: GuaranteeCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/personal-guarantee-v1.yaml` | Create | 5-category playbook (guarantee type, liability scope, waiver, confession, release) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"guaranteecheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Add `"guaranteecheck"` entry to `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `guaranteecheck` CLI subcommand |
| `tests/fixtures/personal-guarantee.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add personal-guarantee-v1 schema validation test |
| `tests/integration/test_guaranteecheck.py` | Create | Smoke test |

**Playbook categories**: Guarantee type (limited vs. unlimited, continuing vs. specific), Scope of guaranteed obligations and max liability, Waiver of defenses and subrogation rights, Confession of judgment and acceleration, Release conditions and revocation

**Prompt vocabulary**: personal guarantee, limited guarantee, continuing guarantee, waiver of defenses, subrogation, confession of judgment, maximum liability, survival

#### Mode 5: LoanCheck

| File | Action | Purpose |
|------|--------|---------|
| `src/openreview_cli/review/playbooks/loan-agreement-v1.yaml` | Create | 5-category playbook (loan terms, default, collateral, covenants, cross-default) |
| `src/openreview_cli/review/prompts.py` | Modify | Add `"loancheck"` entry to `MODE_VOCABULARY` |
| `src/openreview_cli/review/playbook.py` | Modify | Add `"loancheck"` entry to `BUNDLED_PLAYBOOKS` |
| `src/openreview_cli/app.py` | Modify | Add `loancheck` CLI subcommand |
| `tests/fixtures/loan-agreement.pdf` | Create | Test document |
| `tests/unit/test_playbook_schema.py` | Modify | Add loan-agreement-v1 schema validation test |
| `tests/integration/test_loancheck.py` | Create | Smoke test |

**Playbook categories**: Loan amount, interest, and repayment terms, Default and acceleration clauses, Collateral and security interest provisions, Affirmative and negative covenants, Cross-default and events of default

**Prompt vocabulary**: principal, interest, APR, maturity, prepayment, default, acceleration, collateral, security interest, covenant, cross-default, events of default

### Orphan Modes (9) — CLI Wiring Only

These modes already have:
- Playbook YAML on disk (`src/openreview_cli/review/playbooks/`)
- Entry in `BUNDLED_PLAYBOOKS` in `playbook.py`
- Entry in `MODE_VOCABULARY` in `prompts.py`

They need only `_register_product_mode()` calls in `app.py`.

| CLI Subcommand | Playbook File | Help Text |
|----------------|--------------|-----------|
| `licensecheck` | `saas-license-v1.yaml` | Review a SaaS/software license agreement with LicenseCheck. |
| `leasecheck` | `commercial-lease-v1.yaml` | Review a commercial lease agreement with LeaseCheck. |
| `privacycheck` | `dpa-v1.yaml` | Review a Data Processing Agreement with PrivacyCheck. |
| `indemnitycheck` | `indemnification-v1.yaml` | Review an indemnification agreement with IndemnityCheck. |
| `consultcheck` | `consulting-agreement-v1.yaml` | Review a consulting services agreement with ConsultCheck. |
| `workcheck` | `work-for-hire-v1.yaml` | Review an independent contractor/work-for-hire agreement with WorkCheck. |
| `loicheck` | `letter-of-intent-v1.yaml` | Review a letter of intent or MOU with LOICheck. |
| `subcheck` | `subcontractor-agreement-v1.yaml` | Review a subcontractor agreement with SubCheck. |
| `settlementcheck` | `settlement-agreement-v1.yaml` | Review a settlement/release agreement with SettlementCheck. |

## Dependencies

| What | Spec Ref | Status |
|------|----------|--------|
| Single-party review pipeline | Established pattern | Complete, production-ready |
| Three-color confidence | Established pattern | Complete |
| Memo export | Established pattern | Complete |
| Prompt management / registry | Established pattern | Complete |
| Playbook versioning / management | Established pattern | Complete |
| Playbook schema (3-position, 3-5 questions) | Established pattern | Complete |
| `_register_product_mode` helper | spec.md §FR1 | Complete, supports unlimited modes |
| `BUNDLED_PLAYBOOKS` dict | playbook.py | Has 12 entries (9 orphan + 3 wired), needs 5 more |

## Architecture Implications

| Implication | Source | Impact |
|------------|--------|--------|
| Comparison accuracy ceiling (~64% F1) | Established pattern | All new modes use same thresholds as existing modes. No mode-specific threshold tuning. |
| Multi-party comparison is experimental | Established pattern | All new modes default to single-party review. |
| Task-level model routing | Established pattern | All new modes use same model slot config as existing modes. |
| Versioned prompts | Established pattern | Each new mode registered as a named template in MODE_VOCABULARY. |
| Citation grounding required | Established pattern | All new modes reuse existing citation grounding. |
| Playbook-only changes | FR5 | Each new mode adds <1 KB to MODE_VOCABULARY dict, one YAML file, one CLI registration. |
| Orphan modes: no pipeline changes | FR10 | Nine modes need only `_register_product_mode()` calls — no new playbook, prompt, or test document. |

## Known Pre-existing Gap: DealCheck & HireCheck Wiring

As documented in spec 028, `dealcheck` and `hirecheck` have playbook YAMLs and MODE_VOCABULARY entries but their CLI wiring was completed in spec 028. The app.py already registers both (verified at line 2325-2335). No additional work needed for these two modes.

## Risks

1. **CLI command tree size** — 14 new subcommands added in one spec. Mitigation: `_register_product_mode` keeps per-mode registration at ~3 lines each. Total added lines for orphan wiring: ~27 lines (9 × 3).
2. **Transaction/finance playbook coverage** — Loan and guarantee agreements have complex legal structures. Mitigation: target most common small-business scenarios first. Complex structured transactions out of scope for v1.
3. **Loan agreement terminology variance** — Overlapping terms (default vs. event of default, cross-default vs. cross-acceleration). Mitigation: prompt templates inject precise terminology and few-shot examples. Default uncertain matches to Amber.
4. **14-mode maintenance surface** — Each mode adds maintenance burden. Mitigation: orphan playbooks validated in prior specs. Five new modes share prompt structure with prior modes. Benchmark infra supports batch re-validation.

## Test Plan

### Unit Tests

| Test | File | What it validates |
|------|------|-------------------|
| Playbook schema validation (×5 new modes) | `test_playbook_schema.py` | Each new playbook YAML passes `load_playbook()` without error |
| Prompt vocabulary keys (×5 new modes) | Existing prompt tests | Each mode key exists in `MODE_VOCABULARY` with non-empty domain/vocabulary |

### Integration Tests (Smoke Tests)

#### 5 New Modes — Full Smoke Test

| Test | File | What it validates |
|------|------|-------------------|
| AssetCheck smoke | `test_assetcheck.py` | Subcommand exists + --help + playbook schema + run_review non-empty |
| BuyCheck smoke | `test_buycheck.py` | Subcommand exists + --help + playbook schema + run_review non-empty |
| EngageCheck smoke | `test_engagecheck.py` | Subcommand exists + --help + playbook schema + run_review non-empty |
| GuaranteeCheck smoke | `test_guaranteecheck.py` | Subcommand exists + --help + playbook schema + run_review non-empty |
| LoanCheck smoke | `test_loancheck.py` | Subcommand exists + --help + playbook schema + run_review non-empty |

#### 9 Orphan Modes — CLI Routing Test

| Test | File | What it validates |
|------|------|-------------------|
| Orphan modes CLI routing | `test_orphan_modes.py` | Subcommand registers + --help displays text + invokes correct playbook + exits cleanly (no fixture docs, no run_review assertions) |

### Fixture Documents

Five fixture PDFs, each:
- Well-formed, valid PDF (no scanned images)
- 1-3 pages covering the mode's contract type
- Contains at least one clause matching each playbook category
- English language
- Small-business-relevant factual scenario

### Verification Checklist

- [ ] `uv run openreview --help` lists all 14 new subcommands
- [ ] Each subcommand `--help` shows mode-specific help text
- [ ] Each of 5 new playbooks passes schema validation (`load_playbook()`)
- [ ] Each of 5 new modes produces non-empty ReviewReport via run_review()
- [ ] Each of 9 orphan modes registers CLI subcommand and exits cleanly
- [ ] JSON output `mode` field matches invoked subcommand for all modes
- [ ] Memo export produces file > 1 KB with mode name prefix
- [ ] PII stripping produces identical placeholders across modes
- [ ] Playbook override produces different assessments
- [ ] `--no-pii` flag preserves raw text
- [ ] All tests pass in CI environment
