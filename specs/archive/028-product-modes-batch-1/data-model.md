# Data Model: Product Modes Batch 1

**Date**: 2026-07-08
**Phase**: Phase 1 (Design)
**Status**: Complete

## Overview

No new database tables or entity types. Batch 1 reuses four existing entity types from the single-party review pipeline. Each entity is described below with its role in the batch-1 modes.

## Entities

### 1. Mode

An enumeration of product mode identifiers. Batch 1 adds six new values.

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Lowercase identifier, e.g. `"indemnitycheck"` |
| `display_name` | String | Human-readable name, e.g. `"IndemnityCheck"` |
| `description` | String | One-line CLI help text |
| `playbook_id` | String | Default bundled playbook ID |
| `prompt_key` | String | Key into `MODE_VOCABULARY` dict |

**Existing values**: `precheck`, `dealcheck`, `hirecheck`, `licensecheck`, `leasecheck`, `privacycheck`

**New values**:

| `id` | `display_name` | `playbook_id` | Contract Type |
|------|---------------|---------------|---------------|
| `indemnitycheck` | IndemnityCheck | `indemnification-v1` | Indemnification agreement |
| `consultcheck` | ConsultCheck | `consulting-agreement-v1` | Consulting services agreement |
| `workcheck` | WorkCheck | `work-for-hire-v1` | Work-for-hire / independent contractor agreement |
| `loicheck` | LOICheck | `letter-of-intent-v1` | Letter of intent / MOU |
| `subcheck` | SubCheck | `subcontractor-agreement-v1` | Subcontractor agreement |
| `settlementcheck` | SettlementCheck | `settlement-agreement-v1` | Settlement and release agreement |

**Storage**: In-memory mapping (dict in `MODE_VOCABULARY` in `prompts.py` + app.py subcommand function). No database storage.

**Relationships**: A Mode has one default Playbook (1:1). A Mode has one PromptTemplate (1:1). A ReviewReport references a Mode (N:1).

### 2. Playbook

A YAML document defining clause categories and three-position positions. Already defined in `src/openreview_cli/review/playbook.py` as `Playbook` dataclass. Batch 1 adds 6 new playbook YAML files following the existing schema.

**Key fields** (from existing schema):

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique playbook identifier, e.g. `"indemnification-v1"` |
| `mode` | String | Matching mode identifier |
| `metadata.version` | String | Semantic version, e.g. `"1.0.0"` |
| `metadata.description` | String | Human-readable description |
| `metadata.author` | String | Always `"openreview"` for bundled |
| `categories` | Array[Category] | 3-5 clause categories |

**Category fields** (from existing schema):

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique within playbook, e.g. `"indemnity-scope"` |
| `name` | String | Human-readable name |
| `description` | String | Plain-language description of the clause |
| `preferred` | PositionDefinition | Small-business-friendly outcome |
| `acceptable` | PositionDefinition | Neutral / standard outcome |
| `walkaway` | PositionDefinition | Adverse outcome |
| `default_position` | Enum | `"preferred"` | `"acceptable"` | `"walkaway"` |

**PositionDefinition fields**:

| Field | Type | Description |
|-------|------|-------------|
| `description` | String | What this position means for the user |
| `exemplars` | Array[String] | Example clause language |

**File location**: `src/openreview_cli/review/playbooks/{id}.yaml`

**Validation**: Schema validated by existing `playbook.py` `load_playbook()` function. All 6 new playbooks must pass.

**New playbooks**:

| File | ID | Categories |
|------|----|-----------|
| `indemnification-v1.yaml` | `indemnification-v1` | Indemnity scope, liability cap, survival period, defense obligations |
| `consulting-agreement-v1.yaml` | `consulting-agreement-v1` | SOW specificity, payment terms, IP ownership, confidentiality, termination |
| `work-for-hire-v1.yaml` | `work-for-hire-v1` | Worker classification, IP ownership, payment, non-compete, termination |
| `letter-of-intent-v1.yaml` | `letter-of-intent-v1` | Binding provisions, exclusivity, breakup fees, due diligence, expiration |
| `subcontractor-agreement-v1.yaml` | `subcontractor-agreement-v1` | Flow-through, payment terms, indemnity, change-order, termination |
| `settlement-agreement-v1.yaml` | `settlement-agreement-v1` | Release scope, payment terms, confidentiality, unknown claims, breach |

### 3. PromptTemplate

Mode-specific extraction system prompts defined in `MODE_VOCABULARY` dict in `prompts.py`. Batch 1 adds 6 new entries.

**Existing schema** (from `prompts.py`):

```python
MODE_VOCABULARY: dict[str, dict[str, str]] = {
    "<mode>": {
        "specialization": " specializing in <domain-specific-area>",
        "domain": "<document type name>",
        "vocabulary": "Domain vocabulary: <comma-separated terms>. ",
    },
}
```

**New entries**: 6 entries added to `MODE_VOCABULARY`, one per mode.

**Storage**: In-memory dict. No database storage.

### 4. ReviewReport

The pipeline's output data structure. Already defined in `src/openreview_cli/review/models.py` as `ReviewReport` dataclass. Batch 1 makes no changes to this entity.

**Key fields**:

| Field | Type | Description |
|-------|------|-------------|
| `mode` | String | Mode identifier, e.g. `"indemnitycheck"` |
| `assessments` | List[Assessment] | Per-category assessments |
| `document` | Document | Parsed document metadata |
| `overall_confidence` | Enum | GREEN | AMBER | RED |
| `memo_path` | Optional[Path] | Path to exported memo if any |

**Assessment fields**:

| Field | Type | Description |
|-------|------|-------------|
| `category_id` | String | Matching playbook category |
| `position` | Enum | `"preferred"` | `"acceptable"` | `"walkaway"` | `"no-match"` |
| `confidence` | Float | 0.0-1.0 |
| `citation` | String | Exact clause text supporting assessment |
| `qa_verdict` | Enum | `"agree"` | `"disagree"` | `"uncertain"` |
| `color` | Enum | GREEN | AMBER | RED |

**Output format**: Identical JSON schema across all modes, with `mode` field distinguishing the source mode (FR7).

### 5. JSON Output Envelope

The JSON serialization of a `ReviewReport` follows a stable envelope schema shared across all product modes. This schema is the contract for downstream tooling (CI pipelines, document management integration, memo templates).

**Envelope fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | String | Yes | Mode identifier, e.g. `"indemnitycheck"`. Matches invoked subcommand. |
| `playbook_version` | String | Yes | Playbook metadata version, e.g. `"1.0.0"`. |
| `assessments` | Array[Object] | Yes | List of per-category assessment objects. Non-empty for a successful review. |
| `overall_confidence` | Float | Yes | Aggregate confidence score (0.0–1.0). Computed from per-assessment scores. |
| `memo_path` | String or null | Yes | File system path to exported memo, or `null` if export was skipped. |
| `pii_stripped` | Boolean | Yes | `true` if PII stripping was applied before assessment. |

**Assessment object fields** (within `assessments` array):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category_id` | String | Yes | Playbook category ID, e.g. `"indemnity-scope"`. |
| `position` | String | Yes | One of: `"preferred"`, `"acceptable"`, `"walkaway"`, `"no-match"`. |
| `confidence` | Float | Yes | Per-assessment confidence (0.0–1.0). |
| `citation` | String | Yes | Excerpt from the document supporting this assessment. |
| `qa_verdict` | String | Yes | One of: `"agree"`, `"disagree"`, `"uncertain"`. |
| `color` | String | Yes | One of: `"GREEN"`, `"AMBER"`, `"RED"`. |

**Example JSON**:

```json
{
  "mode": "indemnitycheck",
  "playbook_version": "1.0.0",
  "assessments": [
    {
      "category_id": "indemnity-scope",
      "position": "acceptable",
      "confidence": 0.72,
      "citation": "Party A shall indemnify Party B against all third-party claims...",
      "qa_verdict": "agree",
      "color": "AMBER"
    },
    {
      "category_id": "liability-cap",
      "position": "preferred",
      "confidence": 0.91,
      "citation": "Liability shall not exceed the total fees paid...",
      "qa_verdict": "agree",
      "color": "GREEN"
    },
    {
      "category_id": "survival-period",
      "position": "walkaway",
      "confidence": 0.65,
      "citation": "Indemnification obligations survive termination indefinitely...",
      "qa_verdict": "agree",
      "color": "RED"
    },
    {
      "category_id": "defense-obligations",
      "position": "no-match",
      "confidence": 0.0,
      "citation": "",
      "qa_verdict": "uncertain",
      "color": "AMBER"
    }
  ],
  "overall_confidence": 0.57,
  "memo_path": "./memo/indemnity-indemnitycheck.pdf",
  "pii_stripped": true
}
```

## Validation Rules

1. **Playbook schema**: Must match existing `Playbook` dataclass schema. Validated by `load_playbook()`.
2. **Mode identifiers**: Must match `MODE_VOCABULARY` keys. No duplicate keys.
3. **CLI subcommand names**: Must be valid Typer subcommand names (lowercase, no hyphens, single word).
4. **Prompt template vocabulary**: Must be non-empty, but all entries can be empty strings.
5. **Memo export prefix**: Must match mode identifier (e.g., `indemnitycheck-`).

## Relationships

```
Mode 1──1 Playbook (default)
Mode 1──1 PromptTemplate (via MODE_VOCABULARY)
Mode 1──N ReviewReport (per invocation)
ReviewReport N──1 Mode (via mode field)
ReviewReport 1──N Assessment
Assessment N──1 Category (via category_id)
```

## Key Design Decisions

1. **No new tables**: All data lives in YAML files, in-memory dicts, and existing SQLite tables. No migrations needed.
2. **No cross-mode relationships**: Modes are independent. No shared state.
3. **Playbook versioning**: Existing versioning mechanism (playbook metadata.version) applies. No per-mode versioning changes.
4. **Prompt templates**: Follow exact existing `MODE_VOCABULARY` pattern. No new prompt management infrastructure.
5. **Output consistency**: JSON schema identical across modes. Downstream tooling does not need per-mode adaptations (FR7).
