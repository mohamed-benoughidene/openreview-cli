# Research: Product Modes Batch 1 — IndemnityCheck, ConsultCheck, WorkCheck, LOICheck, SubCheck, SettlementCheck

**Date**: 2026-07-08
**Phase**: Phase 0 (Research)
**Status**: Complete — no NEEDS CLARIFICATION remaining

## Method

Per-mode research conducted via public legal-education sources, contract-playbook databases, and small-business legal guides. Sources are educational only, not legal advice. Clause categories identified per mode from [spec.md](./spec.md) assumptions and references section.

## Research Questions

### Q1: What are the highest-risk clause categories for each mode?

Answered by synthesizing sources listed in spec.md §"Assumptions and References — Contract Type Research". Each mode targets 3-5 categories (simpler than enterprise modes per FR9).

| Mode | Categories | Source |
|------|-----------|--------|
| IndemnityCheck | Mutual vs. one-sided indemnity; liability cap; survival period; defense obligations; exclusions | DocJuris, Practical Law |
| ConsultCheck | Scope-of-work specificity; payment terms; IP ownership; confidentiality; limitation of liability; termination; non-solicit | Daeryun Law, Jones Spross |
| WorkCheck | Worker classification language; work-for-hire vs. assignment; payment terms; non-compete; termination | Xero, US Chamber, FormSwift |
| LOICheck | Binding vs. non-binding provisions; exclusivity/no-shop; breakup fees; due diligence access; expiration | Good Pine Law, Hecht Schondorf |
| SubCheck | Flow-through clauses; pay-if-paid vs. pay-when-paid; broad-form indemnity; no-damages-for-delay; change-order; termination | Simon Law, Adams & Reese |
| SettlementCheck | General vs. specific release; payment terms; confidentiality/non-disparagement; non-admission of liability; waiver of unknown claims (§1542-type) | Buchanan Williams, Practical Law |

### Q2: What three-position playbook question format fits each mode?

Following the established 3-position format (preferred/acceptable/walkaway) with small-business-friendly defaults per FR9. Each playbook 3-5 categories. Three-position format confirmed sufficient for first-pass review per Assumption 5 in spec.md.

Design decision: 3-position format validated by PreCheck/DealCheck/HireCheck/LicenseCheck/LeaseCheck/PrivacyCheck. No reason to change.

### Q3: What domain vocabulary does each mode's extraction prompt need?

From spec.md FR3 — vocabulary already identified per mode. Augmented with:

- **IndemnityCheck**: "indemnify", "hold harmless", "defense", "liability cap", "survival", "third-party claim", "broad form", "limited form", "mutual", "sole"
- **ConsultCheck**: "statement of work", "deliverable", "scope creep", "IP assignment", "work product", "non-solicit", "change order", "independent contractor"
- **WorkCheck**: "work for hire", "independent contractor", "classification", "commissioned work", "assignment", "non-compete", "IRS factors", "scope of services"
- **LOICheck**: "non-binding", "exclusivity", "no-shop", "breakup fee", "due diligence", "confidentiality", "binding provisions", "purchase price"
- **SubCheck**: "flow-through", "pay-if-paid", "pay-when-paid", "broad form indemnity", "no-damages-for-delay", "change order", "prime contract", "incorporation by reference"
- **SettlementCheck**: "general release", "specific release", "non-disparagement", "non-admission", "waiver", "unknown claims", "confidentiality", "Civil Code 1542"

All vocabulary terms are publicly known legal terms, not proprietary. No customer-specific data involved.

### Q4: Are there PII considerations specific to any of these modes?

Per FR8, all modes use identical PII stripping. Each mode's document type typically contains different PII entity types:

| Mode | Common PII Entities | Notes |
|------|-------------------|-------|
| IndemnifyCheck | Party names, addresses, financial amounts | Standard PII |
| ConsultCheck | Party names, addresses, payment info, SOW-specific identifiers | Standard PII |
| WorkCheck | Party names, addresses, SSN/TIN (if contractor), financial terms | May include tax identifiers |
| LOICheck | Party names, business addresses, proposed financial terms | Lower PII density |
| SubCheck | Party names, addresses, insurance info, financial amounts | May include policy numbers |
| SettlementCheck | Party names, addresses, financial settlement amounts, alleged misconduct details | Highest sensitivity — may include sensitive allegations |

No mode-specific PII recognizers needed beyond what extraction prompt templates inject (FR8 boundary). The `--no-pii` flag works identically across all modes.

### Q5: Does each mode need its own pipeline variant?

**No.** Per FR4, all modes reuse `run_review()`. No changes to the three-agent pipeline, citation grounding, three-color confidence, or memo export. Each mode is just a playbook YAML + prompt template registration + CLI wiring.

### Q6: What are the per-mode model routing implications?

Per spec.md FR4: "All modes use the same model slot configuration as existing modes. Per-mode model routing is not supported — the gateway uses task-level routing, not document-type routing." Confirmed — no changes.

### Q7: How do playbook names and IDs follow the existing convention?

Established convention: `{domain}-v1.yaml` with `id: "{domain}-v1"` and `mode: "{command-name}"`:
- `precheck-nda-v1.yaml` → mode: `precheck`
- `saas-license-v1.yaml` → mode: `licensecheck`

New playbooks follow same pattern:

| Mode | Playbook File | Playbook ID |
|------|--------------|-------------|
| indemnitycheck | `indemnification-v1.yaml` | `indemnification-v1` |
| consultcheck | `consulting-agreement-v1.yaml` | `consulting-agreement-v1` |
| workcheck | `work-for-hire-v1.yaml` | `work-for-hire-v1` |
| loicheck | `letter-of-intent-v1.yaml` | `letter-of-intent-v1` |
| subcheck | `subcontractor-agreement-v1.yaml` | `subcontractor-agreement-v1` |
| settlementcheck | `settlement-agreement-v1.yaml` | `settlement-agreement-v1` |

## Architecture Implications

| Implication | Source | Impact |
|-------------|--------|--------|
| Pipeline reuse confirmed for all 6 modes | FR4 | No pipeline changes needed |
| Playbook-only changes: no new deps | FR2 | Zero new runtime dependencies |
| Task-level model routing unchanged | FR4 | All modes share model slot config |
| Comparison accuracy ceiling same as existing modes | FR1, FR4 | Amber as default uncertain match |
| Memo export uses mode prefix | FR5 | `indemnitycheck-`, `consultcheck-`, etc. |
| PII stripping identical across all modes | FR8 | No per-mode PII config needed |
| Simple playbooks for small-business audience | FR9 | 3-5 categories per mode (vs. 7-9 for enterprise) |

## Sources

Sources listed in spec.md §"Assumptions and References — Contract Type Research" are sufficient. No additional research needed. All sources are publicly available educational materials, not legal advice.

## Decisions

1. **3-position playbook format**: Carry forward from existing modes. Confirmed sufficient for small-business audience.
2. **3-5 categories per playbook**: Simpler than enterprise modes per FR9.
3. **Default positions favor smaller party**: Per FR9 and Assumption 6.
4. **No per-mode PII recognizers**: Out of scope per FR8.
5. **No per-mode model routing**: Confirmed by FR4.
6. **Memo export uses mode prefix**: Per FR5.
