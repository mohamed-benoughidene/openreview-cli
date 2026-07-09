# Data Model — Product Modes Batch 2

**Date**: 2026-07-08
**Feature**: Five new product modes (AssetCheck, BuyCheck, EngageCheck, GuaranteeCheck, LoanCheck) + nine orphan mode CLI wiring

---

## Entity: Product Mode

A product mode is a CLI subcommand that wraps the single-party review pipeline with a domain-specific playbook and prompt template.

### Fields

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `name` | `str` | Spec FR1/FR2 | CLI subcommand name (e.g., `assetcheck`, `buycheck`, `licensecheck`) |
| `playbook_file` | `str` | Spec FR3 | Relative path in `playbooks/` (e.g., `asset-transfer-v1.yaml`) |
| `prompt_vocabulary` | `dict[str, str]` | Spec FR4 | Entry in `MODE_VOCABULARY` with specialization, domain, vocabulary |
| `cli_wired` | `bool` | Implementation | Whether `_register_product_mode()` is called for this mode |

### Validation Rules

- Mode names are lowercase, alphanumeric, no hyphens or underscores (per existing convention)
- Each mode must have exactly one playbook YAML file
- Each mode must have exactly one `MODE_VOCABULARY` entry
- Each mode must have exactly one `BUNDLED_PLAYBOOKS` entry
- The playbook YAML `mode` field must match the mode name
- Mode names must be unique across the CLI command tree

### State Transitions

Not applicable — modes are stateless configuration, not runtime entities.

## Entity: Playbook YAML

A YAML file following the 3-position category schema.

### Fields (from Category dataclass in models.py)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique playbook identifier (e.g., `asset-transfer-v1`) |
| `mode` | `str` | Yes | Corresponding mode name |
| `metadata.version` | `str` | Yes | Semver version string |
| `metadata.description` | `str` | Yes | Human-readable description |
| `metadata.author` | `str` | Yes | Author name |
| `categories` | `list[Category]` | Yes | Array of clause categories (minimum 1) |
| `categories[].id` | `str` | Yes | Category identifier (lowercase-with-dashes) |
| `categories[].name` | `str` | Yes | Display name |
| `categories[].description` | `str` | Yes | What this category evaluates |
| `categories[].preferred` | `PositionDef` | Yes | Preferred position definition |
| `categories[].acceptable` | `PositionDef` | Yes | Acceptable position definition |
| `categories[].walkaway` | `PositionDef` | Yes | Walkaway position definition |
| `categories[].default_position` | `str` | Yes | Default: `preferred`, `acceptable`, or `walkaway` |

### PositionDef Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | `str` | Yes | What this position means for this category |
| `exemplars` | `list[str]` | Yes | Example clause text snippets (minimum 1) |

## Entity: MODE_VOCABULARY Entry

A key-value pair in the `MODE_VOCABULARY` dict.

| Field | Type | Description |
|-------|------|-------------|
| Key | `str` | Mode name (e.g., `assetcheck`) |
| `specialization` | `str` | LLM role specialization (empty string or prefix with comma) |
| `domain` | `str` | Contract domain description for the extraction prompt |
| `vocabulary` | `str` | Domain-specific vocabulary terms for prompt injection |

## Entity: BUNDLED_PLAYBOOKS Entry

A key-value pair in the `BUNDLED_PLAYBOOKS` dict in `playbook.py`.

| Field | Type | Description |
|-------|------|-------------|
| Key | `str` | Mode name (e.g., `assetcheck`) |
| Value | `Path` | Absolute path to YAML file in `playbooks/` directory |

## Entity: CLI Subcommand Registration

A call to `_register_product_mode()` in `app.py`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `app` | `typer.Typer` | The Typer app instance |
| `name` | `str` | CLI subcommand name |
| `help_text` | `str` | Short help text for `--help` output |
| `path_help` | `str` | Help text for the document path argument |

## Relationships

```
Product Mode (1) ──── has ────> Playbook YAML (1)
Product Mode (1) ──── has ────> MODE_VOCABULARY entry (1)
Product Mode (1) ──── has ────> BUNDLED_PLAYBOOKS entry (1)
Product Mode (1) ──── has ────> CLI subcommand registration (1)
```

## Data Flow for a Mode Invocation

```
CLI input: openreview assetcheck document.pdf
         │
         v
app.py: _register_product_mode("assetcheck", ...)
         │ resolves mode="assetcheck"
         v
_run_product_review(mode="assetcheck", path="document.pdf", ...)
         │
         ├── BUNDLED_PLAYBOOKS["assetcheck"] → Path to asset-transfer-v1.yaml
         │
         ├── run_review(paths=[...], playbook_path=..., mode="assetcheck")
         │        │
         │        ├── MODE_VOCABULARY["assetcheck"] → specialization, domain, vocabulary
         │        │
         │        ├── load_playbook(asset-transfer-v1.yaml) → Playbook object
         │        │
         │        └── Pipeline: ParseStage → StripStage → ReviewStage
         │                 │
         │                 └── ReviewReport with mode="assetcheck"
         │
         └── _emit_reviews(reports, format, output, ...)
```

## Schema Compliance

All 14 modes (5 new + 9 orphan) comply with the above data model. The 9 orphan modes are pre-compliant — their entities (playbook YAML, MODE_VOCABULARY entry, BUNDLED_PLAYBOOKS entry) already exist. They need only the CLI subcommand registration entity.
