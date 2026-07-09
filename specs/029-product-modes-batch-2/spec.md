# Spec 029 — Product Modes Batch 2: AssetCheck, BuyCheck, EngageCheck, GuaranteeCheck, LoanCheck

**Status**: Draft — 0 NEEDS CLARIFICATION markers remain
**Author**: Speckit Specify
**Date**: 2026-07-08

---

## Overview

Add five new product modes to the `openreview` CLI for transaction and finance contract types: **AssetCheck** (asset transfer/assignment agreements), **BuyCheck** (asset purchase and business acquisition agreements), **EngageCheck** (professional services engagement letters), **GuaranteeCheck** (personal guarantees and suretyship agreements), and **LoanCheck** (loan agreements and promissory notes). These are the second batch of the product-mode expansion (the 22 product modes capability — 12 built across prior specs, 5 delivered here, 5 remaining for Batch 3).

Additionally, this spec unblocks nine orphan product modes from prior batches (from product modes Batch 1 and the License/Lease/Privacy batch) by adding CLI subcommands for them. These nine modes already have domain-specific playbook YAML files on disk but no CLI invocation — they are effectively unusable. Unblocking them requires only CLI wiring (the same `_register_product_mode` pattern) and does not require new playbooks, prompts, or per-mode tests.

Each of the five new modes reuses the existing single-party review pipeline (the three-agent review capability — extraction, verification, and reporting — with the three-position playbook format and three-color confidence output) with a domain-specific playbook YAML and extraction prompt template. This follows the pattern established by all twelve prior modes.

### Orphan modes unblocked

| Spec Source | Mode | Playbook File |
|------------|------|---------------|
| Spec 027 | licensecheck | `saas-license-v1.yaml` |
| Spec 027 | leasecheck | `commercial-lease-v1.yaml` |
| Spec 027 | privacycheck | `dpa-v1.yaml` |
| Spec 028 | indemnitycheck | `indemnification-v1.yaml` |
| Spec 028 | consultcheck | `consulting-agreement-v1.yaml` |
| Spec 028 | workcheck | `work-for-hire-v1.yaml` |
| Spec 028 | loicheck | `letter-of-intent-v1.yaml` |
| Spec 028 | subcheck | `subcontractor-agreement-v1.yaml` |
| Spec 028 | settlementcheck | `settlement-agreement-v1.yaml` |

### New L-4b modes

| Mode | Contract Type | Playbook File |
|------|---------------|---------------|
| AssetCheck | Asset transfer/assignment agreements | `asset-transfer-v1.yaml` |
| BuyCheck | Asset purchase / business acquisition agreements | `asset-purchase-v1.yaml` |
| EngageCheck | Professional services engagement letters | `engagement-letter-v1.yaml` |
| GuaranteeCheck | Personal guarantees, suretyship agreements | `personal-guarantee-v1.yaml` |
| LoanCheck | Loan agreements, promissory notes | `loan-agreement-v1.yaml` |

## Clarifications

### Session 2026-07-08

- Q: What scope of integration test is required for the 9 orphan modes (Success Criteria row contradicted per-mode smoke test section)? → A: CLI routing test only — subcommand registers, --help works, invokes correct playbook, exits cleanly. No new fixture documents or run_review() assertions required for orphan modes.

## Why

The single-party review pipeline is production-ready and has been demonstrated across twelve prior modes (PreCheck, DealCheck, HireCheck, LicenseCheck, LeaseCheck, PrivacyCheck, IndemnityCheck, ConsultCheck, WorkCheck, LOICheck, SubCheck, SettlementCheck). Each new mode validates that the architecture scales across contract domains without per-mode pipeline changes. Each new mode requires only:

- A domain-specific playbook YAML (3-position categories — preferred, acceptable, walkaway — with confidence thresholds)
- An extraction prompt template tuned to the domain's vocabulary
- A CLI subcommand wiring (minimal routing)

Shipping five modes in one batch continues the pattern established by the prior batch (six modes in spec 028). The five modes chosen here target transaction and finance use cases — the next-highest-priority contract types for solo practitioners and small-business owners after the general, employment, and general-business modes shipped previously.

The orphan unblocking is pure tech debt repayment: the playbooks and prompts already exist but are inaccessible because no CLI command invokes them. Wired as part of this spec, they become usable with zero additional development effort beyond the CLI routing code.

## User Scenarios

### S1: Business owner assigns business assets (AssetCheck)

A small-business owner is selling a piece of equipment or transferring IP assets to another party. They run:

```
openreview assetcheck asset-transfer.pdf
```

The tool parses the document, runs the three-agent extraction and verification pipeline with the asset-transfer playbook, and outputs a three-color assessment: Green (clear asset description, defined transfer date, mutual representations), Amber (ambiguous asset scope, missing warranties or exclusions), Red (no purchase price, broad "as-is" without defect disclosure, missing regulatory compliance language). A memo is exported to `./memo/asset-transfer-assetcheck.pdf`.

**Why this priority**: Asset transfer agreements are common in business sales, equipment financing, and IP licensing. Small-business owners often underestimate the importance of precise asset description and disclaimer language.

### S2: Entrepreneur reviews an asset purchase agreement (BuyCheck)

An entrepreneur is acquiring a small business through an asset purchase. They run:

```
openreview buycheck purchase-agreement.pdf
```

The playbook covers purchase price and payment structure, asset list (included and excluded assets), assumption of liabilities, representations and warranties, closing conditions, indemnification, non-compete, and bulk-sale compliance. The tool flags a Red clause (broad liability assumption covering all seller debts including unknown ones) and an Amber clause (vague asset description that could exclude key operating assets).

**Why this priority**: Asset purchase agreements are the most common vehicle for small-business acquisitions. The distinction between purchased assets and assumed liabilities is often the most consequential financial decision in the transaction.

### S3: Consultant reviews an engagement letter (EngageCheck)

A professional consultant receives an engagement letter from a new client. They run:

```
openreview engagecheck engagement-letter.pdf
```

The playbook covers scope of services, fees and billing terms, expense reimbursement, IP ownership of deliverables, confidentiality obligations, limitation of liability, termination provisions, and non-solicitation clauses. The tool flags an Amber clause (IP assignment upon creation without payment carve-out) and a Green clause (clear statement of work with defined deliverables).

**Why this priority**: Engagement letters are the standard starting point for professional services relationships. They are often signed quickly without close review of boilerplate terms like automatic renewal, binding arbitration, or broad indemnification.

### S4: Small-business owner signs a personal guarantee (GuaranteeCheck)

A small-business owner is asked to sign a personal guarantee for a business loan or commercial lease. They run:

```
openreview guaranteecheck guarantee.pdf
```

The playbook covers guarantee type (limited vs. unlimited, continuing vs. specific), triggers for personal liability, waiver of defenses and rights of subrogation, confession of judgment clauses, cross-collateralization, and release conditions. The tool flags a Red clause (unlimited continuing guarantee with automatic renewal and no monetary cap) and an Amber clause (guarantee of all existing and future obligations without a defined maximum amount).

**Why this priority**: Personal guarantees are the most consequential personal financial commitment a business owner can make. The differences between limited guarantees, continuing guarantees, and demand guarantees have profoundly different risk profiles.

### S5: Startup founder reviews a loan agreement (LoanCheck)

A startup founder receives a loan agreement or promissory note from a lender. They run:

```
openreview loancheck loan.pdf
```

The playbook covers loan amount and disbursement terms, interest rate (fixed vs. variable, APR), repayment schedule, maturity date, prepayment penalties, default and acceleration clauses, security/collateral provisions, personal guarantee requirements, covenants (affirmative and negative), and events of default. The tool flags a Red clause (cross-default provision tying the loan to unrelated obligations) and an Amber clause (broad negative covenant restricting the borrower from incurring any additional debt).

**Why this priority**: Loan agreements contain heavily one-sided default language that can accelerate repayment or trigger default on technicalities. Small-business borrowers need to understand which provisions are negotiable and which carry material risk.

### S6: Solo practitioner uses an orphan mode (all 9 orphan modes)

A solo practitioner who relies on a previously shipped mode (e.g., LicenseCheck or IndemnityCheck) finds it now works via the CLI. They run:

```
openreview licensecheck license.pdf
openreview indemnitycheck indemnity.pdf
```

Both commands execute the same pipeline as other modes — the only difference is that the CLI subcommand now exists. This scenario applies to all nine orphan modes.

**Why this priority**: Orphan modes represent sunk development effort that delivers no value until the CLI wiring exists. Unblocking them is the highest-ROI work in this spec.

## Functional Requirements

### FR1: CLI subcommands for 5 new modes

Five new subcommands on the `openreview` CLI:
- `openreview assetcheck <path>`
- `openreview buycheck <path>`
- `openreview engagecheck <path>`
- `openreview guaranteecheck <path>`
- `openreview loancheck <path>`

Each subcommand accepts the same flags as existing modes via the `_register_product_mode` helper in `app.py`:
- `--no-pii` — skip PII stripping
- `--playbook` — override the default playbook
- `--format` — output format (default: `text`; values: `text`, `json`, `memo`)
- `--output` — file path for memo output
- `--memo-format` — memo format(s) as list (e.g. `docx`, `json`, `md`)
- `--output-dir` — output directory for memo exports
- `--verbose` — increase output verbosity
- `--confidence-threshold` / `-ct` — minimum confidence score (default: `0.7`)

### FR2: CLI subcommands for 9 orphan modes

Nine CLI subcommands wired for existing playbooks:

| CLI Subcommand | Existing Playbook File |
|----------------|----------------------|
| `openreview licensecheck <path>` | `saas-license-v1.yaml` |
| `openreview leasecheck <path>` | `commercial-lease-v1.yaml` |
| `openreview privacycheck <path>` | `dpa-v1.yaml` |
| `openreview indemnitycheck <path>` | `indemnification-v1.yaml` |
| `openreview consultcheck <path>` | `consulting-agreement-v1.yaml` |
| `openreview workcheck <path>` | `work-for-hire-v1.yaml` |
| `openreview loicheck <path>` | `letter-of-intent-v1.yaml` |
| `openreview subcheck <path>` | `subcontractor-agreement-v1.yaml` |
| `openreview settlementcheck <path>` | `settlement-agreement-v1.yaml` |

Each orphan subcommand supports the same flag set as FR1. The mode name in CLI help text and JSON output matches the subcommand name (e.g., `licensecheck` for LicenseCheck).

### FR3: Domain-specific playbooks for 5 new modes

Each new mode bundles a default playbook YAML in `src/openreview_cli/review/playbooks/`:
- `asset-transfer-v1.yaml` (AssetCheck)
- `asset-purchase-v1.yaml` (BuyCheck)
- `engagement-letter-v1.yaml` (EngageCheck)
- `personal-guarantee-v1.yaml` (GuaranteeCheck)
- `loan-agreement-v1.yaml` (LoanCheck)

Each playbook follows the established 3-position category schema from the single-party review capability. Categories cover the highest-risk clauses for each transaction/finance domain.

### FR4: Extraction prompt templates for 5 new modes

Each new mode provides a domain-tuned extraction prompt template. Templates inject domain vocabulary:

- **AssetCheck**: "asset", "assignment", "bill of sale", "as-is", "warranty", "encumbrance", "transfer", "delivery", "excluded assets", "purchase price"
- **BuyCheck**: "purchase price", "asset list", "assumed liabilities", "representations", "warranties", "indemnification", "non-compete", "bulk sale", "earn-out", "closing conditions"
- **EngageCheck**: "scope of services", "deliverables", "fees", "expenses", "IP ownership", "work product", "confidentiality", "limitation of liability", "non-solicit", "termination"
- **GuaranteeCheck**: "personal guarantee", "limited guarantee", "continuing guarantee", "waiver of defenses", "subrogation", "confession of judgment", "maximum liability", "survival"
- **LoanCheck**: "principal", "interest", "APR", "maturity", "prepayment", "default", "acceleration", "collateral", "security interest", "covenant", "cross-default", "events of default"

### FR5: Reuse existing pipeline

All fourteen modes (5 new + 9 orphan) reuse the existing `run_review()` entry point from the single-party review package. No changes to:
- The three-agent pipeline (extraction, verification, report generation)
- The citation grounding mechanism
- The three-color confidence output (Green/Amber/Red)
- The memo export capability
- The prompt management system

All modes use the same model slot configuration as existing modes.

### FR6: Memo export

Each mode supports memo export (markdown, JSON, DOCX via the memo export capability) with the mode name in the filename prefix (e.g., `assetcheck-`, `buycheck-`). Memo content includes the playbook questions, three-color assessments, citations, and overall confidence.

### FR7: Playbook override

Users may supply a custom playbook via `--playbook` for any mode (both new and orphan). The CLI validates the playbook against the established schema before running.

### FR8: Output consistency

JSON output schema is identical across all product modes. The `mode` field in the JSON envelope distinguishes the mode. For orphan modes, the mode name matches the existing spec convention (e.g., `licensecheck`, `indemnitycheck`).

### FR9: PII handling

PII stripping operates identically across all fourteen modes. The `--no-pii` flag disables stripping as in existing modes.

### FR10: Orphan modes — no new playbook or prompt needed

The nine orphan modes do NOT require new playbook YAML files or extraction prompt templates. Their existing playbook YAMLs (listed in FR2) and existing extraction prompts (created as part of specs 027 and 028) are reused directly. Only CLI wiring is needed.

### FR11: Help text for each subcommand

Every subcommand surfaces mode-specific help text describing the contract type, typical use cases, and a brief disclaimer about the tool's limitations. Orphan mode help text references the mode's original spec and states that the playbook was previously validated.

## Success Criteria

| Criterion | Measure |
|-----------|---------|
| 14 CLI subcommands exist and route correctly (5 new + 9 orphan) | Each subcommand's `--help` shows mode-specific help text |
| 5 new playbooks load without error | All 5 new playbook YAML files pass schema validation (same validator used by existing modes) |
| Each of 5 new modes produces a non-empty ReviewReport | Integration test with a fixture document per mode produces Green/Amber/Red assessments |
| Each of 9 orphan modes registers CLI subcommand | CLI routing test only — subcommand registers, --help works, invokes correct playbook, exits cleanly (no new fixture documents required) |
| 5 new playbook YAMLs exist on disk | `ls src/openreview_cli/review/playbooks/asset-transfer-v1.yaml` etc. |
| Memo export produces valid output for each new mode | File size > 1 KB, contains mode name and at least one assessment |
| JSON output includes correct `mode` field | `openreview <mode> --format json` returns `{"mode": "<mode>", ...}` matching the invoked subcommand |
| Playbook override works for each new mode | Each new mode's `--playbook custom.yaml` option uses a custom playbook and produces different assessments |
| Orphan modes produce same output as their original spec validation | Validation performed in prior specs; no new integration test — CLI routing sufficient |
| CLI discoverable without documentation | `openreview --help` lists all 14 subcommands in the product-modes section |

### Per-mode smoke test requirements

#### 5 new L-4b modes (full smoke test)

Each of the 5 new modes must have a smoke test that validates:
- Subcommand exists and accepts `--help`
- Default playbook loads and passes schema validation
- `run_review()` returns a non-empty report with at least one clause assessment

#### 9 orphan modes (CLI routing test only)

Each of the 9 orphan modes requires only a CLI routing smoke test that validates:
- Subcommand registers in the CLI
- `--help` displays mode-specific help text
- Subcommand invokes the correct playbook
- Subcommand exits cleanly

No new fixture documents or run_review() assertions required for orphan modes.

## Assumptions

1. Each mode's target document is written in English.
2. Documents are well-formed PDFs or DOCXs (no scanned images without OCR).
3. The user has at least one AI provider configured in the gateway.
4. PII stripping operates identically across all modes.
5. The three-position playbook format (preferred/acceptable/walkaway) is sufficient for useful first-pass review of these transaction/finance contract types.
6. Orphan modes' existing playbooks and prompts are correct and need no modification — only CLI wiring is required.
7. The `_register_product_mode` helper in `app.py` supports registering all fourteen modes without structural changes to the app's command tree (no refactoring needed).
8. Users are solo practitioners or small-business owners who may not have dedicated legal counsel.

## Scope Boundaries

### In scope
- 5 new playbook YAML files (asset-transfer, asset-purchase, engagement-letter, personal-guarantee, loan-agreement)
- 5 extraction prompt templates with domain vocabulary
- 5 new CLI subcommands (assetcheck, buycheck, engagecheck, guaranteecheck, loancheck)
- 9 orphan CLI subcommands (licensecheck, leasecheck, privacycheck, indemnitycheck, consultcheck, workcheck, loicheck, subcheck, settlementcheck)
- Prompt registry entries for each new mode
- Unit tests for 5 new playbook schema validations
- Integration tests (smoke tests) for 5 new modes confirming end-to-end pipeline execution
- CLI-routing tests for 9 orphan modes (subcommand parses, calls playbook, exits cleanly)
- Help text per subcommand

### Out of scope (this spec)
- Benchmark whitelist updates (deferred to a follow-up spec)
- CUAD/MAUD accuracy benchmark runs (deferred to follow-up)
- Orphan-mode accuracy re-validation (playbooks already validated in prior specs — no re-run needed)
- Multi-party or bilateral comparison review
- Domain-specific PII recognizers beyond extraction prompt vocabulary injection
- Custom output templates per mode
- Non-English document support
- Mode-specific confidence thresholds
- No changes to the underlying three-agent pipeline, citation grounding, three-color confidence, or memo export logic
- No refactoring of `app.py` subcommand registration (the helper pattern is sufficient)

## Dependencies

- **Requires**: Single-party review pipeline — production-ready, complete
- **Requires**: Three-color confidence output — functional, complete
- **Requires**: Memo export capability — production-ready, complete
- **Requires**: Prompt management / registry — functional, complete
- **Requires**: Playbook versioning capability — enables future playbook updates without pipeline changes
- **Requires**: `_register_product_mode` helper in `app.py` — pattern established by PreCheck, must support 14 additional modes without structural refactoring
- **Extends**: Existing product-mode pattern (12 prior modes across PreCheck, DealCheck, HireCheck, and specs 027/028)

## Risks

1. **CLI command tree size**. Adding 14 subcommands in one spec significantly expands the command tree. At 18 total product modes (3 pre-existing + 9 orphan + 5 L-4b + 1 placeholder), the help output becomes long. Mitigation: group modes into logical categories in help text. The `_register_product_mode` helper pattern keeps per-mode registration at ~10 lines each.

2. **Playbook coverage for transaction/finance modes**. The five new modes cover contract types (loan agreements, asset purchases, personal guarantees) that have more complex legal structures than the general-business modes shipped previously. The 3-category, 3-5 question playbook format may not capture all material terms for structured finance transactions. Mitigation: target the most common small-business scenarios first. Complex structured transactions remain out of scope for v1.

3. **Personal Guarantee complexity**. Guarantees vary significantly by jurisdiction (anti-deficiency laws, one-action rules, community property considerations in certain jurisdictions). The playbook cannot provide jurisdiction-specific analysis. Mitigation: flag jurisdiction-dependent provisions and note the limitation in assessment output. The Amber defaults handle cases where the language could be interpreted differently in different jurisdictions.

4. **Loan agreement terminology variance**. Loan agreements use overlapping terminology ("default" vs. "event of default," "cross-default" vs. "cross-acceleration," "covenant" vs. "condition precedent") that extraction models may misinterpret. Mitigation: prompt templates inject precise terminology and few-shot examples distinguishing these concepts. Default uncertain matches to Amber.

5. **14-subcommand maintenance surface**. Each mode adds maintenance surface for playbook updates and accuracy validation. If all 14 modes require prompt tuning after model updates, the maintenance burden grows linearly. Mitigation: orphan modes' prompts were validated in prior specs and should not need retuning. The five new modes share prompt structure with prior modes, reducing the per-mode prompt engineering surface. The benchmark infrastructure supports batch re-validation.

6. **DealCheck and HireCheck wiring status unknown**. The codebase inventory shows playbook YAMLs for DealCheck and HireCheck but their CLI wiring status is unconfirmed. If they are also orphaned, the total orphan count rises to 11. Mitigation: this spec treats the confirmed 9 listed orphans as the minimum unblock set. If DealCheck or HireCheck are also unwired, they can be added to the orphan list at implementation time without spec amendment — the pattern is identical.

## Open Questions

No remaining open questions.

## Assumptions and References — Contract Type Research

The following research informed the playbook category selection for each new mode. Sources are publicly available educational materials collected for clause-category identification only. Orphan modes reuse categories validated in their respective specs.

### AssetCheck
- **Key clause categories**: Asset description and identification; exclusions and excluded assets; representations and warranties (seller and buyer); purchase price and allocation; transfer of title and risk of loss; as-is vs. warranted condition; regulatory compliance; governing law.
- **Sources**: Practical Law Asset Transfer Agreement (content.next.westlaw.com); LegalZoom Asset Purchase Agreement Guide (legalzoom.com); Thomson Reuters Asset Sale Agreement Guide (reuters.com).

### BuyCheck
- **Key clause categories**: Purchase price (cash, stock, earn-out); included and excluded assets; assumed and excluded liabilities; seller representations and warranties; buyer representations and warranties; pre-closing covenants; closing conditions; indemnification and escrow; non-compete and non-solicit; bulk sales compliance.
- **Sources**: Practical Law Asset Purchase Agreement (content.next.westlaw.com); Corporate Finance Institute Asset Purchase (corporatefinanceinstitute.com); American Bar Association Asset Acquisition Guide (americanbar.org).

### EngageCheck
- **Key clause categories**: Scope of services and deliverables; fees, billing, and payment schedule; expense reimbursement; IP ownership (work product vs. pre-existing); confidentiality and data protection; limitation of liability; indemnification; termination for convenience and for cause; non-solicitation; independent contractor status; dispute resolution.
- **Sources**: Practical Law Consulting Agreement (content.next.westlaw.com); Freelancers Union Engagement Letter Guide (freelancersunion.org); American Institute of Architects Contract Documents (aiacontracts.org).

### GuaranteeCheck
- **Key clause categories**: Guarantee type (limited/unlimited, continuing/specific, demand/absolute); guaranteed obligations (specific vs. all); maximum liability amount and duration; waiver of defenses; waiver of subrogation and contribution; confession of judgment; acceleration and demand provisions; revocation; release conditions; governing law and jurisdiction.
- **Sources**: Practical Law Personal Guarantee (content.next.westlaw.com); National Association of Credit Management Guarantee Guide (nacm.org); UCC Article 3 (suretyship provisions); Uniform Commercial Code.

### LoanCheck
- **Key clause categories**: Loan amount and disbursement; interest rate and APR; repayment schedule; maturity; prepayment; default and acceleration; collateral and security interest; personal guarantee; affirmative and negative covenants; cross-default; events of default; remedies and enforcement; governing law.
- **Sources**: Practical Law Commercial Loan Agreement (content.next.westlaw.com); UCC Article 9 Secured Transactions (law.cornell.edu); Small Business Administration Loan Guide (sba.gov); Federal Reserve Commercial Lending Guide (federalreserve.gov).

### Orphan modes
- All nine orphan modes reuse the clause category research already documented in their respective specs (027 and 028). The playbook YAML files on disk and prompt templates in the prompt registry are the reference artifacts. No additional research is required for CLI wiring.

---

**Note**: All sources are publicly available educational materials and contract databases. They were used solely for identifying common clause categories, not for legal interpretation. No source constitutes legal advice.
