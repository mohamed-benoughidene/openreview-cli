# Phase 0: Research — LicenseCheck, LeaseCheck, PrivacyCheck

**Date**: 2026-07-07
**Spec**: [spec.md](./spec.md)

## Research Topics

### 1. Playbook YAML structure for the three domains

**Finding**: All three domains reuse the existing 3-position, 3-question playbook schema validated by PreCheck [S-011] [S-024]. Schema is defined in `src/openreview_cli/review/playbook.py` (Playbook dataclass with `positions: list[Position]`, each Position has `questions: list[Question]`).

**Domain-specific content**:

#### saas-license-v1.yaml (LicenseCheck)
Target: SaaS/software license agreements (terms of service, EULAs, subscription agreements).

| Position | Questions |
|----------|-----------|
| Favorable to Licensee | 1. Is the license grant perpetual and sufficient for stated use? 2. Are auto-renewal terms transparent with adequate notice period? 3. Is the liability cap reasonable (multiples of fees, not 1x)? |
| Neutral / Standard | 1. Are data-deletion obligations on termination standard? 2. Are IP ownership terms clear (no grant-back clause)? 3. Is the indemnification scope mutual? |
| Adverse to Licensee | 1. Does the agreement allow unilateral price increases without notice? 2. Is there no data-deletion obligation on termination? 3. Is the liability cap at 1x fees or below? |

Sources: Standard SaaS contract clause taxonomy from industry practice (CONFIRMED: domain vocabulary well-documented across legal tech resources).

#### commercial-lease-v1.yaml (LeaseCheck)
Target: Commercial lease agreements (office, retail, industrial).

| Position | Questions |
|----------|-----------|
| Favorable to Tenant | 1. Is rent escalation tied to CPI with a cap? 2. Are maintenance obligations clearly landlord's responsibility? 3. Is there a reasonable subletting/assignment clause? |
| Neutral / Standard | 1. Is the term length and renewal option standard for the market? 2. Are operating expense / CAM charges reasonable and auditable? 3. Is the security deposit amount standard? |
| Adverse to Tenant | 1. Is there a landlord-only termination-for-convenience clause? 2. Is there a triple-net maintenance clause with no cap? 3. Are there use restrictions that unreasonably limit business operations? |

Sources: Commercial lease standard provisions from real estate law practice.

#### dpa-v1.yaml (PrivacyCheck)
Target: Data processing agreements / DPAs.

| Position | Questions |
|----------|-----------|
| Favorable to Data Controller | 1. Is the data processing scope clearly limited to stated purposes? 2. Are sub-processor change notification and consent requirements adequate? 3. Is the breach notification timeline <= 48 hours? |
| Neutral / Standard | 1. Are data retention and deletion timelines clearly specified? 2. Is the audit / inspection right included? 3. Is DPA termination tied to the master agreement? |
| Adverse to Data Controller | 1. Is data processing scope overly broad (e.g., "any business purpose")? 2. Is there no right to object to sub-processor changes? 3. Is breach notification timeline > 72 hours? |

Sources: GDPR Article 28, standard DPA templates, ICO guidance.

### 2. Extraction prompt patterns

**Finding**: Existing extraction prompt template in `src/openreview_cli/review/prompts.py` follows a structure:
- System prompt with mode name, document type, and extraction instructions
- Few-shot examples of clause assessment
- Injection of playbook questions via template variables
- Citation grounding requirement [S-012]

Each new mode needs a prompt template registered in the prompt registry [S-009]. Key difference from existing prompts: domain vocabulary injection (e.g., "SaaS license agreement" vs "non-disclosure agreement") and domain-specific few-shot examples.

No structural changes to the prompt template system needed. The existing prompt rendering engine (`render_prompt()` in prompts.py) accepts a `mode` parameter that selects the template from the registry.

### 3. Reuse of existing review command base class

**Finding**: The existing `ReviewCommand` base class in `src/openreview_cli/review/base.py` provides:
- Document parsing (PDF/DOCX)
- PII orchestration
- Review execution via `run_review()`
- Output formatting (text, json, memo)

Each new mode creates a subclass of `ReviewCommand` with:
- `mode_name` string (e.g., `"licensecheck"`)
- `default_playbook` path
- `prompt_template_name` for the prompt registry

This pattern already proven by PreCheck, DealCheck, HireCheck [S-011].

### 4. Prompt template registration

**Finding**: Prompt registry [S-009] stores named templates keyed by mode name. Registration happens in `src/openreview_cli/gateway/registry.py` or equivalent prompt management module. Adding three new entries (`licensecheck`, `leasecheck`, `privacycheck`) following the existing pattern.

### 5. Domain vocabulary gap risk

**Finding**: The accuracy ceiling (~60-64% F1) [S-013] means domain-specific misclassifications are expected. Mitigations:
- Inject domain-specific glossary terms into extraction prompts
- Use few-shot examples from each domain
- Ensure confidence scoring provides transparency on low-certainty assessments

No additional research needed on LLM domain accuracy — the existing pipeline's performance envelope is established and documented.

## Architecture Implications Summary

| Topic | Finding | Design Decision |
|-------|---------|-----------------|
| Playbook structure | Reuse 3x3 schema | No new schema; just new YAML files |
| Prompt templates | Reuse registry pattern | Three new template entries |
| Base class | Reuse ReviewCommand | Three new subclasses |
| Model routing | SLM-first, task-level | No per-mode overrides |
| Confidence thresholds | Shared across modes | Same thresholds as PreCheck |
| Memory impact | Negligible | No new memory pressure |
