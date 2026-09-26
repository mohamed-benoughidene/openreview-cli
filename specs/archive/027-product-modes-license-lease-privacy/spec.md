# Spec 027 — LicenseCheck, LeaseCheck, PrivacyCheck

**Status**: Draft — clarified, 0 NEEDS CLARIFICATION markers remain
**Author**: Speckit Specify
**Date**: 2026-07-07

---

## Overview

Add three new product modes to the openreview CLI: **LicenseCheck** (SaaS/software license agreements), **LeaseCheck** (commercial lease agreements), and **PrivacyCheck** (data processing agreements / DPAs). Each mode reuses the existing single-party review pipeline (3-agent PAKTON design, 3-position playbook, three-color confidence output, memo export) with a domain-specific playbook YAML and extraction prompt template. Follows the pattern established by PreCheck, DealCheck, and HireCheck.

## Why

The existing single-party review pipeline (spec 011) is production-ready — citation-grounded review with three-agent extraction, QA, and report generation. Three product modes (PreCheck, DealCheck, HireCheck) prove the pattern. Adding three more modes validates that the architecture scales across contract domains without per-mode pipeline changes. Each new mode requires only:
- A domain-specific playbook YAML (3 positions, 3 questions, confidence thresholds)
- An extraction prompt template tuned to the domain's language
- A CLI subcommand wiring (minimal routing)

This demonstrates that the product line can reach 22+ modes without linear cost growth in pipeline maintenance.

## User Scenarios

### S1: Legal counsel reviews a SaaS license agreement (LicenseCheck)
A lawyer receives a SaaS terms-of-service and license agreement from a vendor. They run:
```
openreview licensecheck agreement.pdf
```
The tool parses the document, runs the PAKTON pipeline with the SaaS-license playbook, and outputs a three-color assessment: Green (auto-renewal clause is standard), Amber (liability cap at 1x fees — below market), Red (no data-deletion obligation on termination). A memo PDF is exported to `./memo/agreement-licensecheck.pdf`.

### S2: Tenant reviews a commercial lease (LeaseCheck)
A business owner receives a 50-page commercial lease. They run:
```
openreview leasecheck lease.pdf
```
The playbook covers rent-escalation clauses, maintenance obligations, subletting restrictions, and termination rights. The tool highlights a Red clause (landlord-only termination for convenience) and an Amber clause (triple-net maintenance with no cap).

### S3: Startup reviews a data processing agreement (PrivacyCheck)
A startup signs up with a new CRM vendor and receives a DPA. They run:
```
openreview privacycheck dpa.pdf
```
The playbook covers data-processing scope, sub-processor notification, breach notification timelines, and termination / return-of-data clauses. The tool flags a non-standard 72-hour breach notification (exceeds GDPR's 48-hour expectation in the playbook) as Amber.

## Functional Requirements

### FR1: CLI subcommands [S-011]
Three new subcommands on the `openreview` CLI:
- `openreview licensecheck <path>`
- `openreview leasecheck <path>`
- `openreview privacycheck <path>`

Each subcommand accepts the same flags as `precheck`, `dealcheck`, `hirecheck`:
- `--no-pii` to skip PII stripping
- `--output` (text, json, memo) for output format
- `--playbook` to override the default playbook
- Standard shared flags (verbosity, config path)

### FR2: Domain-specific playbooks [S-011] [S-024]
Each mode bundles a default playbook YAML in `src/openreview_cli/review/playbooks/`:
- `saas-license-v1.yaml` (LicenseCheck)
- `commercial-lease-v1.yaml` (LeaseCheck)
- `dpa-v1.yaml` (PrivacyCheck)

Each playbook follows the established 3-position, 3-question schema from spec 011. Questions cover the highest-risk clauses for each domain.

### FR3: Extraction prompt templates [S-009]
Each mode provides a domain-tuned extraction prompt template registered in the prompt registry. Templates override the default extraction prompt to inject domain vocabulary (e.g., "SaaS", "license grant", "royalty" for LicenseCheck; "lease", "rent", "CAM charges" for LeaseCheck; "data controller", "processing purpose", "sub-processor" for PrivacyCheck).

### FR4: Reuse existing pipeline [S-011] [S-013] [S-021]
All three modes reuse the existing `run_review()` entry point from `src/openreview_cli/review/__init__.py`. No changes to the PAKTON three-agent pipeline, citation grounding, three-color confidence, or memo export. Per-mode model routing overrides are deferred as out of scope — all three modes use the same model slot configuration as PreCheck/DealCheck/HireCheck. Task-level routing (not document-type routing) is the established pattern and is sufficient for this spec.

### FR5: Memo export [S-021]
Each mode supports memo PDF export with the domain name in the filename prefix (e.g., `licensecheck-`, `leasecheck-`, `privacycheck-`). Memo content includes the playbook questions, the three-color assessments, citations, and overall confidence.

### FR6: Playbook override [S-024] [S-011]
Users may supply a custom playbook via `--playbook` for any mode. The CLI validates the playbook against the established schema before running.

### FR7: Output consistency [S-013] [S-011]
JSON output schema is identical across all product modes. The `mode` field in the JSON envelope distinguishes the mode. Downstream tooling (e.g., memo templates, CI pipelines) does not need per-mode adaptations.

## Success Criteria

| Criterion | Measure |
|-----------|---------|
| Three CLI subcommands exist and route correctly | `openreview licensecheck --help`, `openreview leasecheck --help`, `openreview privacycheck --help` each show their mode-specific help text |
| Each mode parses and assesses a valid document | E2E test with a fixture document per mode produces a non-empty ReviewReport with Green/Amber/Red assessments |
| Default playbooks load without error | Playbook YAML files pass schema validation (same validator used by PreCheck/DealCheck/HireCheck) |
| Accuracy within 5% of PreCheck baseline | F1 score on a held-out test corpus per mode is no more than 5 percentage points below PreCheck's measured F1 |
| Memo export produces a valid PDF | File size > 1 KB, PDF mime type confirmed, contains mode name and at least one assessment |
| JSON output includes correct `mode` field | `openreview <mode> --output json` returns `{"mode": "<mode>", ...}` matching the invoked subcommand |
| Playbook override works | `openreview licensecheck --playbook custom.yaml` uses the custom playbook and produces different assessments |

## Assumptions

1. Each mode's target document is written in English.
2. Documents are well-formed PDFs or DOCXs (no scanned images without OCR).
3. The user has at least one AI provider configured in the gateway.
4. PII stripping (when not disabled via `--no-pii`) operates identically across all modes.
5. The three-question-per-playbook format is sufficient for useful first-pass review. PrivacyCheck uses 3 questions for consistency with the existing mode pattern. Cross-border transfer and sub-processor questions are folded into the 3 high-level questions or deferred to PrivacyCheck v2.

## Scope Boundaries

### In scope
- Three CLI subcommands (licensecheck, leasecheck, privacycheck)
- Three default playbook YAML files
- Three extraction prompt templates
- Prompt registry entries for each mode
- Unit tests for each playbook schema validation
- Integration tests for each mode (E2E with fixture documents)
- Accuracy benchmark per mode (at least 10 test documents each)

### Out of scope (this spec)
- Multi-party review (e.g., comparing two leases)
- Domain-specific PII recognizers (e.g., lease-specific entity types)
- Custom output templates per mode (all modes use the standard memo)
- Non-English document support
- Mode-specific confidence thresholds — all modes share the same initial thresholds. Deferred until the shared-threshold pattern is validated.

## Clarifications

### Session 2026-07-07

- **FR4 (per-mode model routing overrides)**: Deferred as out of scope. The blueprint specifies task-level routing, not document-type routing. All three modes use the same model slot configuration as PreCheck/DealCheck/HireCheck.
- **Assumptions #5 (PrivacyCheck question count)**: Resolved to 3 questions for consistency with the existing mode pattern. Cross-border transfer and sub-processor questions are folded into the 3 high-level questions or deferred to a future PrivacyCheck v2.
- **Scope Boundaries (mode-specific confidence thresholds)**: All modes share the same thresholds initially. Mode-specific thresholds are deferred until the pattern is validated.

## Open Questions

All open questions resolved in the Clarifications section above. No remaining open questions.

## Dependencies

- **Requires**: spec 011 (single-party review pipeline) — production-ready, complete
- **Requires**: spec 013 (three-color confidence output) — functional, complete
- **Requires**: spec 021 (memo export) — production-ready, complete
- **Requires**: spec 009 (prompt management / registry) — functional, complete
- **Extends**: Existing PreCheck/DealCheck/HireCheck product-mode pattern

## Risks

1. **Accuracy ceiling limited by F1 ≤ 64% threshold**. The pipeline's measured accuracy ceiling (approx 60-64% F1) means many assessments will be Amber rather than Green or Red. Users may perceive this as low confidence. Mitigation: document accuracy expectations in each mode's help text and memo output.

2. **Domain vocabulary gap**. The extraction LLM may misinterpret domain-specific terms (e.g., "CAM charges" in leases, "personal data" scope definitions in DPAs). Mitigation: prompt templates inject domain vocabulary and few-shot examples.

3. **22-mode sustainability**. At three modes per spec, reaching 22 modes requires 7 additional specs. Each mode adds maintenance surface for playbook updates and accuracy validation. Mitigation: validate the pattern now with three modes; if playbook-only changes suffice, the remaining modes can be shipped faster.
