# Data Model: Product Modes Batch 3 — FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, DistroCheck

**Date**: 2026-07-09
**Phase**: Phase 1 (Design)
**Status**: Complete

## Overview

No new database tables, entity types, or data structures. Batch 3 reuses the same four entity types established by the single-party review pipeline and validated across 17 prior modes. Each entity is described below with its batch-3-specific values.

## Entities

### 1. Mode

An enumeration of product mode identifiers. Batch 3 adds five new values to the existing registry.

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Lowercase identifier, e.g. `"franchisecheck"` |
| `display_name` | String | Human-readable name, e.g. `"FranchiseCheck"` |
| `description` | String | One-line CLI help text |
| `playbook_id` | String | Default bundled playbook ID |
| `prompt_key` | String | Key into `MODE_VOCABULARY` dict |

**Existing values**: `precheck`, `dealcheck`, `hirecheck`, `licensecheck`, `leasecheck`, `privacycheck`, `indemnitycheck`, `consultcheck`, `workcheck`, `loicheck`, `subcheck`, `settlementcheck`, `assetcheck`, `buycheck`, `engagecheck`, `guaranteecheck`, `loancheck` (17 modes built across spec 028, 029, and initial 6)

**New values**:

| `id` | `display_name` | `playbook_id` | Contract Type |
|------|---------------|---------------|---------------|
| `franchisecheck` | FranchiseCheck | `franchise-v1` | Franchise agreement / FDD |
| `opcheck` | OpCheck | `operating-agreement-v1` | LLC operating agreement |
| `partnercheck` | PartnerCheck | `partnership-v1` | Partnership agreement |
| `sponsorcheck` | SponsorCheck | `sponsorship-v1` | Sponsorship agreement |
| `distrocheck` | DistroCheck | `distribution-v1` | Distribution / reseller agreement |

**Storage**: In-memory mapping (dict in `MODE_VOCABULARY` in `prompts.py` + `app.py` subcommand function). No database storage.

**Relationships**: A Mode has one default Playbook (1:1). A Mode has one PromptTemplate (1:1). A ReviewReport references a Mode (N:1).

### 2. Playbook

A YAML document defining clause categories and three-position positions. Already defined in `src/openreview_cli/review/playbook.py` as `Playbook` dataclass. Batch 3 adds 5 new playbook YAML files following the existing schema.

**Key fields** (from existing schema):

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique playbook identifier, e.g. `"franchise-v1"` |
| `mode` | String | Matching mode identifier |
| `metadata.version` | String | Semantic version, e.g. `"1.0.0"` |
| `metadata.description` | String | Human-readable description |
| `metadata.author` | String | Always `"openreview"` for bundled |
| `categories` | Array[Category] | 3-5 clause categories |

**Category fields** (from existing schema):

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique within playbook, e.g. `"territory-rights"` |
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

**Validation**: Schema validated by existing `playbook.py` `load_playbook()` function. All 5 new playbooks must pass.

**New playbooks**:

| File | ID | Categories |
|------|----|-----------|
| `franchise-v1.yaml` | `franchise-v1` | Franchise fee structure, Territory rights and exclusivity, Renewal and termination, Advertising and marketing fund, Transfer/assignment restrictions |
| `operating-agreement-v1.yaml` | `operating-agreement-v1` | Membership structure (member-managed vs. manager-managed), Capital contributions and additional calls, Profit/loss allocation (IRC §704(b)), Voting rights and decision-making, Transfer restrictions and dissolution |
| `partnership-v1.yaml` | `partnership-v1` | Capital contributions and profit/loss allocation, Management authority and decision-making, Withdrawal/expulsion/dissolution, Liability allocation and indemnification, Dispute resolution (mediation/arbitration) |
| `sponsorship-v1.yaml` | `sponsorship-v1` | Sponsorship fee and payment schedule, Sponsorship rights and benefits (logo/recognition/exclusivity), IP license (use of sponsor's trademarks), Termination for breach or force majeure, Indemnification and non-disparagement |
| `distribution-v1.yaml` | `distribution-v1` | Territory definition and exclusivity, Minimum purchase requirements and cure periods, Pricing/payment/inventory terms, IP license (manufacturer's trademarks), Termination rights/non-compete/channel restrictions |

### 3. PromptTemplate

Mode-specific extraction system prompts defined in `MODE_VOCABULARY` dict in `prompts.py`. Batch 3 adds 5 new entries.

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

**New entries**: 5 entries added to `MODE_VOCABULARY`, one per mode.

**Special notes for batch 3**:

- **DistroCheck vocabulary** MUST include the `[FRANCHISE_BOUNDARY: yes|no|borderline]` instruction in the prompt template (FR-09).
- **FranchiseCheck vocabulary** MUST also include the `[FRANCHISE_BOUNDARY: yes|no|borderline]` instruction (spec A-04, both modes get the flag).
- **OpCheck specialization** MUST use "Operating Agreement" as the domain name, not "OpCheck" (FR-10, Assumption A-03).

**Storage**: In-memory dict. No database storage.

### 4. ReviewReport

The pipeline's output data structure. Already defined in `src/openreview_cli/review/models.py` as `ReviewReport` dataclass. Batch 3 makes no changes to this entity.

**Key fields**:

| Field | Type | Description |
|-------|------|-------------|
| `mode` | String | Mode identifier, e.g. `"franchisecheck"` |
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

**Output format**: Identical JSON schema across all modes, with `mode` field distinguishing the source mode.

### 5. Fixture

A test document (PDF) used for E2E testing. Batch 3 adds 5 new fixtures.

| Field | Type | Description |
|-------|------|-------------|
| `mode_key` | String | Associated mode, e.g. `"franchisecheck"` |
| `file_path` | String | Relative path in `tests/fixtures/` |
| `page_count` | Integer | Pages, ≤5 per spec FR-07 |
| `expected_assessment` | Object | Expected per-category colors |
| `contains_pii` | Bool | `False` (synthetic, no real PII) |

**New fixtures**:

| File | Mode | Pages | Expected Overall |
|------|------|-------|-----------------|
| `franchise-agreement.pdf` | FranchiseCheck | 3-5 | AMBER |
| `operating-agreement.pdf` | OpCheck | 3-5 | AMBER |
| `partnership-agreement.pdf` | PartnerCheck | 3-5 | AMBER |
| `sponsorship-agreement.pdf` | SponsorCheck | 2-3 | AMBER |
| `distribution-agreement.pdf` | DistroCheck | 3-5 | AMBER |

### 6. Baseline

A JSON record of expected performance and accuracy for a mode on a fixture. Format defined by `src/openreview_cli/benchmark/baseline.py`.

| Field | Type | Description |
|-------|------|-------------|
| `mode_key` | String | Mode identifier |
| `display_name` | String | Human-readable name |
| `fixture` | String | Path to fixture document |
| `expected_assessment` | Object | Expected overall color and per-category positions |
| `time_budget_s` | Integer | End-to-end processing budget (30s) |
| `pii_time_budget_s` | Integer | PII stripping budget (3s) |
| `page_count` | Integer | Number of pages |

**New baselines**:

| File | Mode Key | Fixture | Expected Overall |
|------|----------|---------|-----------------|
| `franchisecheck.json` | `franchisecheck` | `tests/fixtures/franchise-agreement.pdf` | AMBER |
| `opcheck.json` | `opcheck` | `tests/fixtures/operating-agreement.pdf` | AMBER |
| `partnercheck.json` | `partnercheck` | `tests/fixtures/partnership-agreement.pdf` | AMBER |
| `sponsorcheck.json` | `sponsorcheck` | `tests/fixtures/sponsorship-agreement.pdf` | AMBER |
| `distrocheck.json` | `distrocheck` | `tests/fixtures/distribution-agreement.pdf` | AMBER |

## Validation Rules

1. **Playbook schema**: Must match existing `Playbook` dataclass schema. Validated by `load_playbook()`.
2. **Mode identifiers**: Must match `MODE_VOCABULARY` keys. No duplicate keys.
3. **CLI subcommand names**: Must be valid Typer subcommand names (lowercase, no hyphens, single word).
4. **Prompt template vocabulary**: Must be non-empty; must include boundary flag terms for DistroCheck and FranchiseCheck.
5. **Memo export prefix**: Must match mode identifier (e.g., `franchisecheck-`).
6. **VALID_MODES**: All 5 mode keys must be in the frozenset in `benchmark/cli.py`.
7. **Fixture PII**: Must not contain real PII (use placeholder names and addresses).
8. **OpCheck help text**: Must contain "Operating Agreement" — verified by integration test.

## Relationships

```
Mode 1──1 Playbook (default)
Mode 1──1 PromptTemplate (via MODE_VOCABULARY)
Mode 1──1 Fixture (E2E test document)
Mode 1──1 Baseline (benchmark JSON)
Mode 1──N ReviewReport (per invocation)
ReviewReport N──1 Mode (via mode field)
ReviewReport 1──N Assessment
Assessment N──1 Category (via category_id)
```

## Key Design Decisions

1. **No new tables**: All data lives in YAML files, in-memory dicts, and existing SQLite tables. No migrations needed.
2. **No cross-mode relationships**: Modes are independent. No shared state.
3. **Playbook versioning**: Existing versioning mechanism (playbook metadata.version) applies. No per-mode versioning changes.
4. **Prompt templates**: Follow exact existing `MODE_VOCABULARY` pattern. Boundary flag adds a prompt instruction but no new infrastructure.
5. **Output consistency**: JSON schema identical across all 22 modes. Downstream tooling does not need per-mode adaptations.
6. **Fixture design**: Synthetic with precise color triggers. Ensures deterministic assessment without reliance on LLM output variation.
7. **Baseline scope**: Regression detection only. No generalization claims per Assumption A-06.
