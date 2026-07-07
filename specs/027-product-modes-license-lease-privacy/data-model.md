# Phase 1: Data Model — LicenseCheck, LeaseCheck, PrivacyCheck

**Date**: 2026-07-07
**Spec**: [spec.md](./spec.md)

## Data Model Design

### Existing models (reused, no changes)

All data models from the single-party review pipeline [S-011] are reused without modification:

| Model | File | Purpose |
|-------|------|---------|
| `ClauseAssessment` | `src/openreview_cli/review/models.py` | Per-clause assessment with position, confidence, citations |
| `Playbook` | `src/openreview_cli/review/models.py` | 3-position, 3-question domain schema |
| `ReviewReport` | `src/openreview_cli/review/models.py` | Complete review output with all assessments |
| `Position` | `src/openreview_cli/review/models.py` | Position with question list |
| `Question` | `src/openreview_cli/review/models.py` | Individual question with threshold and weight |
| `ConfidenceLevel` | `src/openreview_cli/review/models.py` | GREEN / AMBER / RED enum |

### No new data models needed

This spec introduces zero new data models. All three modes produce output in the same schema. Per-clause assessment, confidence, citations, and memo formatting are identical across modes. The `mode` field in the output JSON envelope distinguishes the origin [S-013] [S-021].

### New playbook YAML definitions

Each playbook YAML follows the schema established by precheck-nda-v1.yaml [S-024].

#### saas-license-v1.yaml

```yaml
version: "1.0"
name: "SaaS License Review"
id: "saas-license-v1"
description: "Standard SaaS/software license agreement review playbook"
mode: "licensecheck"
positions:
  - id: "favorable"
    label: "Favorable to Licensee"
    questions:
      - id: "q1"
        text: "Is the license grant perpetual and sufficient for stated use?"
        threshold: 0.6
        weight: 1.0
      - id: "q2"
        text: "Are auto-renewal terms transparent with adequate notice period?"
        threshold: 0.6
        weight: 1.0
      - id: "q3"
        text: "Is the liability cap reasonable (multiples of fees, not 1x)?"
        threshold: 0.6
        weight: 1.0
  - id: "neutral"
    label: "Neutral / Standard"
    questions:
      - id: "q4"
        text: "Are data-deletion obligations on termination standard?"
        threshold: 0.5
        weight: 0.8
      - id: "q5"
        text: "Are IP ownership terms clear (no grant-back clause)?"
        threshold: 0.5
        weight: 0.8
      - id: "q6"
        text: "Is the indemnification scope mutual?"
        threshold: 0.5
        weight: 0.8
  - id: "adverse"
    label: "Adverse to Licensee"
    questions:
      - id: "q7"
        text: "Does the agreement allow unilateral price increases without notice?"
        threshold: 0.6
        weight: 1.0
      - id: "q8"
        text: "Is there no data-deletion obligation on termination?"
        threshold: 0.6
        weight: 1.0
      - id: "q9"
        text: "Is the liability cap at 1x fees or below?"
        threshold: 0.6
        weight: 1.0
```

#### commercial-lease-v1.yaml

```yaml
version: "1.0"
name: "Commercial Lease Review"
id: "commercial-lease-v1"
description: "Standard commercial lease agreement review playbook"
mode: "leasecheck"
positions:
  - id: "favorable"
    label: "Favorable to Tenant"
    questions:
      - id: "q1"
        text: "Is rent escalation tied to CPI with a cap?"
        threshold: 0.6
        weight: 1.0
      - id: "q2"
        text: "Are maintenance obligations clearly landlord's responsibility?"
        threshold: 0.6
        weight: 1.0
      - id: "q3"
        text: "Is there a reasonable subletting/assignment clause?"
        threshold: 0.6
        weight: 1.0
  - id: "neutral"
    label: "Neutral / Standard"
    questions:
      - id: "q4"
        text: "Is the term length and renewal option standard for the market?"
        threshold: 0.5
        weight: 0.8
      - id: "q5"
        text: "Are operating expense / CAM charges reasonable and auditable?"
        threshold: 0.5
        weight: 0.8
      - id: "q6"
        text: "Is the security deposit amount standard?"
        threshold: 0.5
        weight: 0.8
  - id: "adverse"
    label: "Adverse to Tenant"
    questions:
      - id: "q7"
        text: "Is there a landlord-only termination-for-convenience clause?"
        threshold: 0.6
        weight: 1.0
      - id: "q8"
        text: "Is there a triple-net maintenance clause with no cap?"
        threshold: 0.6
        weight: 1.0
      - id: "q9"
        text: "Are there use restrictions that unreasonably limit business operations?"
        threshold: 0.6
        weight: 1.0
```

#### dpa-v1.yaml

```yaml
version: "1.0"
name: "Data Processing Agreement Review"
id: "dpa-v1"
description: "Standard DPA review playbook covering GDPR-aligned clauses"
mode: "privacycheck"
positions:
  - id: "favorable"
    label: "Favorable to Data Controller"
    questions:
      - id: "q1"
        text: "Is the data processing scope clearly limited to stated purposes?"
        threshold: 0.6
        weight: 1.0
      - id: "q2"
        text: "Are sub-processor change notification/consent requirements adequate?"
        threshold: 0.6
        weight: 1.0
      - id: "q3"
        text: "Is the breach notification timeline <= 48 hours?"
        threshold: 0.6
        weight: 1.0
  - id: "neutral"
    label: "Neutral / Standard"
    questions:
      - id: "q4"
        text: "Are data retention and deletion timelines clearly specified?"
        threshold: 0.5
        weight: 0.8
      - id: "q5"
        text: "Is the audit / inspection right included?"
        threshold: 0.5
        weight: 0.8
      - id: "q6"
        text: "Is DPA termination tied to the master agreement?"
        threshold: 0.5
        weight: 0.8
  - id: "adverse"
    label: "Adverse to Data Controller"
    questions:
      - id: "q7"
        text: "Is data processing scope overly broad (e.g., 'any business purpose')?"
        threshold: 0.6
        weight: 1.0
      - id: "q8"
        text: "Is there no right to object to sub-processor changes?"
        threshold: 0.6
        weight: 1.0
      - id: "q9"
        text: "Is breach notification timeline > 72 hours?"
        threshold: 0.6
        weight: 1.0
```

### Prompt template registry entries

Each mode gets a prompt template entry in the prompt registry [S-009]:

| Mode | Template Key | Domain Vocabulary |
|------|-------------|-------------------|
| LicenseCheck | `licensecheck` | SaaS, license grant, royalty, subscription, auto-renewal, liability cap, IP ownership, indemnification |
| LeaseCheck | `leasecheck` | commercial lease, rent escalation, CAM charges, triple-net, subletting, security deposit, termination for convenience |
| PrivacyCheck | `privacycheck` | data controller, data processor, processing purpose, sub-processor, breach notification, data retention, DPA |

### CLI command parameters

Each mode follows the same parameter schema as PreCheck/DealCheck/HireCheck [S-015]:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | Path argument | required | Document path (PDF or DOCX) |
| `--no-pii` | Flag | `False` | Skip PII stripping |
| `--output` | Choice | `text` | Output format: `text`, `json`, `memo` |
| `--playbook` | Path | default playbook | Custom playbook override |
| `--verbose` | Flag | `False` | Verbose output |
| `--config` | Path | default config | Config file path |

### Output schema

JSON output follows the same schema as existing modes [S-013] with the `mode` field identifying the source:

```json
{
  "mode": "licensecheck",
  "document": {"filename": "agreement.pdf", "pages": 15},
  "assessments": [
    {
      "question_id": "q7",
      "question": "Does the agreement allow unilateral price increases without notice?",
      "position": "Adverse to Licensee",
      "confidence": "RED",
      "score": 0.85,
      "citations": [{"text": "...", "page": 12, "clause": "Section 4.3"}]
    }
  ],
  "overall_confidence": "AMBER",
  "memo_path": "./memo/agreement-licensecheck.pdf"
}
```
