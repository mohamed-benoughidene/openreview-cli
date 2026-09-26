# Spec 028 — Product Modes Batch 1: IndemnityCheck, ConsultCheck, WorkCheck, LOICheck, SubCheck, SettlementCheck

**Status**: Draft — 0 NEEDS CLARIFICATION markers remain
**Author**: Speckit Specify
**Date**: 2026-07-08

---

## Overview

Add six new product modes to the openreview CLI for solo/small-business contract types: **IndemnityCheck** (indemnification agreements), **ConsultCheck** (consulting services agreements), **WorkCheck** (work-for-hire and independent contractor agreements), **LOICheck** (letters of intent and memoranda of understanding), **SubCheck** (subcontractor agreements), and **SettlementCheck** (settlement and release agreements).

Each mode reuses the existing single-party review pipeline (the three-agent review capability — extraction, verification, and reporting — with the three-position playbook format and three-color confidence output) with a domain-specific playbook YAML and extraction prompt template. This follows the pattern established by the four wired modes (PreCheck, LicenseCheck, LeaseCheck, PrivacyCheck), with DealCheck and HireCheck being wired concurrently in this batch to close a pre-existing spec/code gap (scope expansion B).

These six modes complete the first batch of the roadmap's product-mode expansion. They target solo practitioners and small-business owners who regularly encounter these contract types but lack in-house legal review. The playbooks are simpler than enterprise-oriented modes — each focuses on the highest-risk clauses for a small-business party.

## Why

The single-party review pipeline is production-ready. Each new mode validates that the architecture scales across contract domains without per-mode pipeline changes. Each new mode requires only:

- A domain-specific playbook YAML (3-position categories — preferred, acceptable, walkaway — with confidence thresholds)
- An extraction prompt template tuned to the domain's vocabulary
- A CLI subcommand wiring (minimal routing)

Shipping six modes in one batch demonstrates that the product line can reach 22+ modes without linear cost growth in pipeline maintenance. The batch structure — grouping by user segment (solo/small-business) — keeps per-mode cost low.

## User Scenarios

### S1: Small business signs an indemnification agreement (IndemnityCheck)

A small business is asked to sign an indemnification agreement by a larger customer. The business owner runs:

```
openreview indemnitycheck indemnity.pdf
```

The tool parses the document, runs the three-agent extraction and verification pipeline with the indemnification playbook, and outputs a three-color assessment: Green (mutual indemnification with reasonable liability cap), Amber (broad-form indemnification requiring indemnification even for the other party's negligence), Red (uncapped indemnification with no survival limit). A memo is exported to `./memo/indemnity-indemnitycheck.pdf`.

**Why this priority**: Indemnification agreements are common in B2B relationships. Small businesses often sign them without understanding the scope of liability they assume.

### S2: Consultant reviews a consulting services agreement (ConsultCheck)

A freelance consultant receives a consulting agreement from a new client. They run:

```
openreview consultcheck engagement.pdf
```

The playbook covers scope-of-work specificity, payment terms, IP ownership, confidentiality, limitation of liability, termination rights, and non-solicit clauses. The tool flags an Amber clause (IP assignment upon creation rather than upon payment) and a Green clause (clear statement of work with change-order process). A memo is exported to `./memo/engagement-consultcheck.pdf`.

**Why this priority**: Consulting agreements are the most common contract type for solo professionals. Scope creep and IP ownership disputes are the top risks.

### S3: Freelancer reviews an independent contractor agreement (WorkCheck)

A freelance developer receives an independent contractor agreement that includes a work-for-hire clause. They run:

```
openreview workcheck contractor-agreement.pdf
```

The playbook covers worker classification language, IP ownership (work-for-hire vs. assignment), payment terms, confidentiality, non-compete restrictions, and termination provisions. The tool flags a Red clause (broad non-compete covering all client business activities) and an Amber clause (work-for-hire designation without specifying what constitutes commissioned work).

**Why this priority**: Worker misclassification is a significant legal risk for both hiring parties and contractors. Clear playbook guidance on classification language protects both sides.

### S4: Startup reviews a letter of intent before an acquisition (LOICheck)

A startup founder receives a letter of intent from a potential acquirer. They run:

```
openreview loicheck LOI.pdf
```

The playbook covers binding vs. non-binding provisions, exclusivity (no-shop) clauses, confidentiality, breakup fees, due diligence access, and expiration terms. The tool flags a Red clause (broad binding language that could make the entire LOI enforceable as a purchase agreement) and an Amber clause (90-day exclusivity period that may be too long for a small startup).

**Why this priority**: LOIs are often treated as non-binding formalities, but specific provisions (confidentiality, exclusivity, breakup fees) can be legally binding. Small-business signers need to know which provisions carry weight.

### S5: Trade contractor reviews a subcontractor agreement (SubCheck)

A small trade contractor receives a subcontractor agreement from a general contractor. They run:

```
openreview subcheck subcontract.pdf
```

The playbook covers flow-through clauses (incorporating prime contract terms by reference), scope-of-work definition, payment terms (including pay-if-paid vs. pay-when-paid), indemnification (broad vs. limited form), change-order process, no-damages-for-delay clauses, and termination rights. The tool flags a Red clause (broad-form indemnification requiring the subcontractor to indemnify the GC even for the GC's own negligence) and an Amber clause (pay-if-paid provision shifting owner credit risk to the subcontractor).

**Why this priority**: Subcontractor agreements heavily favor the general contractor by default. Small trade contractors need to identify shifted risks before signing.

### S6: Small business resolves a dispute with a settlement agreement (SettlementCheck)

A small business settles a dispute with a former vendor and receives a settlement and release agreement. They run:

```
openreview settlementcheck settlement.pdf
```

The playbook covers release scope (general vs. specific), payment terms and timing, confidentiality and non-disparagement clauses, non-admission of liability, waiver of unknown claims (Civil Code section 1542-type waivers), and enforcement/breach consequences. The tool flags a Green clause (specific release limited to the dispute at hand) and an Amber clause (broad confidentiality provision that prevents the business from reporting regulatory violations).

**Why this priority**: Settlement agreements contain permanent relinquishments of rights. Small-business owners need to understand the scope of claims they are releasing.

## Functional Requirements

### FR1: CLI subcommands

Six new subcommands on the `openreview` CLI:
- `openreview indemnitycheck <path>`
- `openreview consultcheck <path>`
- `openreview workcheck <path>`
- `openreview loicheck <path>`
- `openreview subcheck <path>`
- `openreview settlementcheck <path>`

Each subcommand accepts the same flags as existing modes via the `_register_product_mode` helper in `app.py`:
- `--no-pii` — skip PII stripping (privacy-first requirement — PII stripped before any external API call)
- `--playbook` — override the default playbook
- `--format` — output format (default: `text`; values: `text`, `json`, `memo`)
- `--output` — file path for memo output
- `--memo-format` — memo format(s) as list (e.g. `pdf`, `docx`, `md`)
- `--output-dir` — output directory for memo exports
- `--verbose` — increase output verbosity
- `--confidence-threshold` / `-ct` — minimum confidence score (default: `0.7`)


### FR2: Domain-specific playbooks

Each mode bundles a default playbook YAML in `src/openreview_cli/review/playbooks/`:
- `indemnification-v1.yaml` (IndemnityCheck)
- `consulting-agreement-v1.yaml` (ConsultCheck)
- `work-for-hire-v1.yaml` (WorkCheck)
- `letter-of-intent-v1.yaml` (LOICheck)
- `subcontractor-agreement-v1.yaml` (SubCheck)
- `settlement-agreement-v1.yaml` (SettlementCheck)

Each playbook follows the established 3-position category schema from the single-party review capability. Categories (clause topics) cover the highest-risk clauses for each domain. Playbooks for solo/small-business modes may be simpler (fewer categories) than enterprise-oriented modes.


### FR3: Extraction prompt templates

Each mode provides a domain-tuned extraction prompt template. Templates override the default extraction prompt to inject domain vocabulary for each contract type:

- **IndemnityCheck**: "indemnify", "hold harmless", "defense", "liability cap", "survival", "third-party claim", "broad form", "limited form"
- **ConsultCheck**: "statement of work", "deliverable", "scope creep", "IP assignment", "work product", "non-solicit", "change order"
- **WorkCheck**: "work for hire", "independent contractor", "classification", "commissioned work", "assignment", "non-compete", "IRS factors"
- **LOICheck**: "non-binding", "exclusivity", "no-shop", "breakup fee", "due diligence", "confidentiality", "binding provisions"
- **SubCheck**: "flow-through", "pay-if-paid", "pay-when-paid", "broad form indemnity", "no-damages-for-delay", "change order", "prime contract"
- **SettlementCheck**: "general release", "specific release", "non-disparagement", "non-admission", "waiver", "unknown claims", "confidentiality"


### FR4: Reuse existing pipeline

All six modes reuse the existing `run_review()` entry point from the single-party review package. No changes to:
- The three-agent pipeline (extraction, verification, report generation)
- The citation grounding mechanism
- The three-color confidence output (Green/Amber/Red)
- The memo export capability

All modes use the same model slot configuration as existing modes. Per-mode model routing is not supported — the gateway uses task-level routing, not document-type routing.


### FR5: Memo export

Each mode supports memo export (markdown, JSON, DOCX via the memo export capability) with the mode name in the filename prefix (e.g., `indemnitycheck-`, `consultcheck-`, `workcheck-`). Memo content includes the playbook questions, three-color assessments, citations, and overall confidence.


### FR6: Playbook override

Users may supply a custom playbook via `--playbook` for any mode. The CLI validates the playbook against the established schema before running. Custom playbooks allow law firms and in-house teams to encode their own preferred positions.


### FR7: Output consistency

JSON output schema is identical across all product modes. The `mode` field in the JSON envelope distinguishes the mode. Downstream tooling (e.g., memo templates, CI pipelines, integration with document management systems) does not need per-mode adaptations.


### FR8: PII handling

PII stripping (via the PII detection and anonymization capability) operates identically across all six modes. Each mode's extraction prompt template includes domain-specific PII categories if appropriate (e.g., names of parties, business addresses, financial terms in settlement agreements). The `--no-pii` flag disables stripping as in existing modes.


### FR9: Playbook simplicity for small-business audience

Each playbook is designed for a solo/small-business user rather than an enterprise legal team. This means:
- Fewer categories per playbook (3-5 instead of 7-9)
- Plain-language category descriptions
- Default positions that favor the smaller party (e.g., "preferred" reflects a small-business-friendly position)


## Success Criteria

| Criterion | Measure |
|-----------|---------|
| Six CLI subcommands exist and route correctly | Each subcommand's `--help` shows mode-specific help text |
| Each mode parses and assesses a valid document | E2E test with a fixture document per mode produces a non-empty ReviewReport with Green/Amber/Red assessments |
| Default playbooks load without error | All 6 playbook YAML files pass schema validation (same validator used by existing modes) |
| Each new mode produces a non-empty ReviewReport with Green/Amber/Red assessments | Integration test with sample fixture exits 0 and yields `ReviewReport` containing at least one assessment of each color |
| Memo export produces a valid output file | File size > 1 KB, contains mode name and at least one assessment |
| JSON output includes correct `mode` field | `openreview <mode> --format json` returns `{"mode": "<mode>", ...}` matching the invoked subcommand |
| Playbook override works per mode | Each mode's `--playbook custom.yaml` option uses a custom playbook and produces different assessments |
| PII stripping operates identically across modes | Documents with identical PII content produce identical anonymized output regardless of which mode processes them |
| CLI discoverable without documentation | `openreview --help` lists all 6 new subcommands in the product-modes section |

## Assumptions

1. Each mode's target document is written in English.
2. Documents are well-formed PDFs or DOCXs (no scanned images without OCR).
3. The user has at least one AI provider configured in the gateway.
4. PII stripping operates identically across all modes. Each mode's extraction prompt template may add domain-specific PII recognizer hints, but the underlying detection pipeline is unchanged.
5. The three-position playbook format (preferred/acceptable/walkaway) is sufficient for useful first-pass review of these simpler contract types.
6. Users are solo practitioners or small-business owners who may not have dedicated legal counsel. The output language and recommendations should be accessible to non-lawyers.
7. CLI subcommands follow the established naming pattern (lowercase, single word, no hyphens).

## Scope Boundaries

### In scope
- Six CLI subcommands (indemnitycheck, consultcheck, workcheck, loicheck, subcheck, settlementcheck)
- Six default playbook YAML files with 3-5 categories each
- Six extraction prompt templates
- Prompt registry entries for each mode
- Unit tests for each playbook schema validation
- Integration tests for each mode (E2E with fixture documents)
- Accuracy benchmark per mode (at least 5 test documents each, reflecting smaller contract types)
- PII benchmark note per mode (documenting which PII entity types each contract type typically contains)
- Help text per subcommand describing the mode's contract type and typical use

### Out of scope (this spec)
- Multi-party or bilateral comparison review (e.g., comparing two versions of a settlement agreement)
- Domain-specific PII recognizers beyond what the extraction prompt templates inject
- Custom output templates per mode (all modes use the standard memo format)
- Non-English document support
- Mode-specific confidence thresholds — all modes share the same initial thresholds
- Enterprise-oriented features for these modes (e.g., multi-tier indemnification review for large corporates)
- No changes to the underlying three-agent pipeline, citation grounding, three-color confidence, or memo export logic
- Bilateral comparison between LOI and final agreement (deferred to a future capability)
- Document generation or template filling

## Dependencies

- **Requires**: Single-party review pipeline — production-ready, complete
- **Requires**: Three-color confidence output — functional, complete
- **Requires**: Memo export capability — production-ready, complete
- **Requires**: Prompt management / registry — functional, complete
- **Requires**: Playbook versioning capability — enables future playbook updates without pipeline changes
- **Extends**: Existing product-mode pattern (4 wired: PreCheck, LicenseCheck, LeaseCheck, PrivacyCheck; 2 being wired concurrently: DealCheck, HireCheck scope-expansion B)

## Risks

1. **Accuracy ceiling limits confidence**. The pipeline's measured accuracy ceiling (approximately 60-64% F1) means many assessments will be Amber rather than Green or Red. Users may perceive this as low confidence, especially for high-stakes contract types (indemnification, settlement releases). Mitigation: document accuracy expectations in each mode's help text and memo output. Default uncertain matches to Amber as established.

2. **Domain vocabulary gap**. The extraction LLM may misinterpret domain-specific terms — e.g., "broad form" vs. "limited form" in indemnification agreements, "pay-if-paid" vs. "pay-when-paid" in subcontracts, "work for hire" vs. "assignment" in contractor agreements. Mitigation: prompt templates inject domain vocabulary and few-shot examples. The comparison accuracy guideline — default uncertain matches to Amber — provides a safety net.

3. **Settlement agreement complexity**. Settlement agreements vary widely — from simple mutual releases to complex structured settlements with ongoing obligations. The three-question-per-playbook format may not capture all material terms. Mitigation: target the most common small-business settlement scenarios first. Complex settlements remain out of scope for v1.

4. **LOI binding provision ambiguity**. Whether an LOI provision is binding depends on jurisdiction-specific case law. The playbook cannot provide legal advice on enforceability. Mitigation: the playbook flags provisions that are commonly binding (confidentiality, exclusivity, breakup fees) and notes jurisdiction dependence in the assessment output.

5. **22-mode sustainability**. At six modes per batch, reaching 22 modes requires 3-4 batches. Each mode adds maintenance surface for playbook updates and accuracy validation. Mitigation: the simpler playbook format (fewer categories) for small-business modes reduces maintenance burden. If playbook-only changes suffice, the remaining modes can be shipped faster.

## Clarifications

No clarifications needed at this stage. All functional requirements trace to established blueprint origins as documented above. Open questions from prior specs remain resolved: the minimum mode set has been exceeded, task-level model selection is confirmed as the routing strategy, and tracked-changes document support remains deferred in favor of memo export coverage.

## Open Questions

No remaining open questions.

## Assumptions and References — Contract Type Research

The following research informed the playbook category selection for each mode. Sources are public, non-legal-reference materials collected for clause-category identification only.

### IndemnityCheck
- **Key clause categories**: Mutual vs. one-sided indemnification; broad-form vs. limited-form; liability caps; survival periods; defense obligations; third-party claim coverage; exclusions and exceptions.
- **Sources**: DocJuris Contract Playbook Template (docjuris.com/playbook-template/indemnification-provisions); Promise Legal Blog (blog.promise.legal); Practical Law by Thomson Reuters (content.next.westlaw.com).

### ConsultCheck
- **Key clause categories**: Scope of work / statement of work; payment terms; IP ownership / work product assignment; confidentiality; limitation of liability; termination rights; non-solicit; integration clause.
- **Sources**: Daeryun Law Consulting Agreements Analysis (daeryunlaw.com); Jones Spross IP Ownership in Consulting Agreements (jonesspross.com); Small Business Legal Tips — 8 Essential Clauses (youtube.com/@SmallBusinessLegalTips).

### WorkCheck
- **Key clause categories**: Worker classification / independent contractor status; work-for-hire vs. IP assignment; payment terms; confidentiality; non-compete restrictions; scope of services; termination; IRS classification factors.
- **Sources**: Xero Independent Contractor Agreement Guide (xero.com); US Chamber of Commerce Contractor Agreements (uschamber.com); FormSwift Independent Contractor Template (formswift.com); Decimal Work-for-Hire Guide (decimal.com).

### LOICheck
- **Key clause categories**: Binding vs. non-binding provisions; confidentiality; exclusivity / no-shop; breakup fees / expense reimbursement; due diligence access; expiration; governing law; purchase price structure.
- **Sources**: Good Pine Law LOI Analysis (goodpinelaw.com); Hecht Schondorf Binding vs. Non-Binding LOIs (hechtschondorf.com); Goosmann Law Key LOI Terms (blog.goosmannlaw.com); B&P Law LOI Guide (b-p-law.com).

### SubCheck
- **Key clause categories**: Flow-through / incorporation by reference; scope of work; payment terms (pay-if-paid vs. pay-when-paid); indemnification (broad vs. limited form); change-order process; no-damages-for-delay; termination; insurance requirements.
- **Sources**: Simon Law Subcontract Provisions (simonlawky.com); Adams and Reese Subcontractor Key Provisions (adamsandreese.com); Sprinkler Age — Nine Subcontract Provisions (sprinklerage.com); Less Accounting Subcontractor Guide (lessaccounting.com).

### SettlementCheck
- **Key clause categories**: General vs. specific release; payment terms and timing; confidentiality / non-disparagement; non-admission of liability; waiver of unknown claims (Civil Code 1542-type); breach consequences; surviving obligations; tax treatment.
- **Sources**: Buchanan Williams & O'Brien Settlement Confidentiality (bwoattorneys.com); Simon Law P.C. Confidentiality in Settlements (simonlawpc.com); Practical Law Settlement Agreement (anzlaw.thomsonreuters.com); California AG Sample Settlement (oag.ca.gov/prop65).

---

**Note**: All sources are publicly available educational materials and contract databases. They were used solely for identifying common clause categories, not for legal interpretation. No source constitutes legal advice.
