# Research Document — Product Modes Batch 2

**Date**: 2026-07-08
**Feature**: Five new L-4b product modes + nine orphan mode CLI wiring

---

## 1. PreCheck CLI Subcommand Pattern (app.py:931-1105)

**Decision**: Use `_register_product_mode` helper at `src/openreview_cli/app.py:2255`

**Rationale**: The precheck subcommand at lines 931-1105 uses a standalone `typer.Typer` sub-app. However, modes wired after PreCheck (licensecheck, leasecheck, privacycheck, dealcheck, hirecheck, and the six spec-028 modes) all use the `_register_product_mode` helper. This helper standardizes flag parsing across all modes and reduces per-mode wiring to a single function call + 3 lines. The helper supports: `--no-pii`, `--playbook`, `--format`, `--output`, `--memo-format`, `--output-dir`, `--verbose`, `--confidence-threshold`/`-ct`.

Confirmed: helper is at line 2255, uses `@app.command(name=name, help=help_text)` internally, delegates to `_run_product_review()` which calls `run_review()` with the mode-appropriate playbook.

**Alternatives considered**: Standalone `typer.Typer` sub-app per mode (as PreCheck does). Rejected: 14 sub-apps would duplicate flag definitions 14 times (~50 lines each). The helper is the established pattern for all modes after PreCheck.

## 2. Playbook YAML Schema

**Decision**: Follow the existing 3-position schema (preferred/acceptable/walkaway) as demonstrated by `precheck-nda-v1.yaml`.

**Rationale**: All 12 existing playbooks use this schema. Schema verification from `playbook.py`:
- Root keys: `id`, `mode`, `metadata` (version/description/author), `categories` (list)
- Each category: `id`, `name`, `description`, `preferred`/`acceptable`/`walkaway` (each with `description` + `exemplars` list), `default_position`
- Loaded via `yaml.safe_load` → `_parse_playbook()` → `Category` dataclass
- Validated automatically by `load_playbook()` — no manual schema check needed

**Alternatives considered**: Extended schema with mode-specific fields. Rejected: all 12 existing modes work with the same schema. Adding fields breaks backward compat and adds no value for these contract types.

## 3. Prompt Template Pattern

**Decision**: Add entries to `MODE_VOCABULARY` dict in `src/openreview_cli/review/prompts.py`.

**Rationale**: The extraction prompt system uses `BASE_SYSTEM_PROMPT` with `{specialization}`, `{domain}`, and `{vocabulary}` format variables drawn from `MODE_VOCABULARY[mode]`. Each mode gets a dict entry. The shared `_build_extraction_messages_common()` function handles message construction. The QA prompt (`build_qa_messages()`) is identical across modes — no per-mode customization needed.

Confirmed: `MODE_VOCABULARY` already has entries for 12 modes. Five new entries follow the same pattern.

**Alternatives considered**: Per-mode prompt template files. Rejected: the format-variable injection pattern handles domain tuning without file proliferation.

## 4. run_review() Public API

**Decision**: All modes use `from openreview_cli.review import run_review` with `mode` parameter.

**Rationale**: `run_review()` in `review/__init__.py` accepts `paths`, `playbook_path`, `playbook_id`, `extraction_model`, `qa_model`, `no_pii`, `verbose`, `grounding_mode`, `confidence_threshold`, and `mode`. The `mode` parameter controls prompt template selection. The function returns `list[ReviewReport]`. Each report has `document`, `assessments`, `summary`, `playbook_id`, `generated_at`, `confidence_threshold`, `mode`.

Confirmed: `_run_product_review()` in app.py calls `run_review()` with `mode=mode` and resolves the playbook path from `BUNDLED_PLAYBOOKS[mode]`.

## 5. Memory and Performance Constraints

**Decision**: No new memory pressure from this spec. Target machine: 8 GB RAM, 2-core CPU, no GPU. Pipeline peak <100 MB (110 MB hard floor). NLP model memory exempt per constitution §III.

**Rationale per existing constraints:**
- Playbook YAML files: ~2-5 KB each, loaded once per invocation, discarded after parse
- MODE_VOCABULARY entries: ~200 bytes per mode in a dict already housing 12 entries
- BUNDLED_PLAYBOOKS entries: one Path per mode (~50 bytes)
- CLI registration: one function call per mode, no runtime allocation
- Fixture documents for tests: 1-3 page PDFs, loaded only during test execution
- No new parsers, no new in-memory collections, no new streaming changes

**Confirmed baseline**: Existing pipeline already operates within memory budget. Adding 5 YAML files + 5 dict entries is negligible (<100 KB total).

## 6. Orphan Mode Status — Confirmed on Disk

**Decision**: All 9 orphan playbook YAMLs exist at `src/openreview_cli/review/playbooks/`. All 9 have entries in `BUNDLED_PLAYBOOKS` and `MODE_VOCABULARY`.

**Inventory (12 YAMLs on disk):**
- `precheck-nda-v1.yaml` — wired in app.py (precheck sub-app pattern)
- `dealcheck-v1.yaml` — wired in app.py (via _register_product_mode, line 2325)
- `hirecheck-v1.yaml` — wired in app.py (via _register_product_mode, line 2331)
- `saas-license-v1.yaml` — **orphan** (not wired in app.py)
- `commercial-lease-v1.yaml` — **orphan** (not wired in app.py)
- `dpa-v1.yaml` — **orphan** (not wired in app.py)
- `indemnification-v1.yaml` — **orphan** (not wired in app.py)
- `consulting-agreement-v1.yaml` — **orphan** (not wired in app.py)
- `work-for-hire-v1.yaml` — **orphan** (not wired in app.py)
- `letter-of-intent-v1.yaml` — **orphan** (not wired in app.py)
- `subcontractor-agreement-v1.yaml` — **orphan** (not wired in app.py)
- `settlement-agreement-v1.yaml` — **orphan** (not wired in app.py)

**Confirmed**: 9 playbooks are orphaned. DealCheck and HireCheck were wired in spec 028 (verified in app.py). Twelve total YAMLs on disk; 3 wired (precheck, dealcheck, hirecheck); 9 orphaned.

## 7. BUNDLED_PLAYBOOKS Registration Requirement

**Decision**: New mode playbooks must be registered in `BUNDLED_PLAYBOOKS` dict in `playbook.py`.

**Rationale**: `_run_product_review()` resolves the default playbook via `BUNDLED_PLAYBOOKS[mode]`. Without registration, the lookup raises `KeyError`. Existing 12 entries correspond to the 12 YAMLs on disk. Five new entries needed.

## 8. API Key and Auth Requirements

**Decision**: No changes to authentication. All modes use existing gateway configuration.

**Rationale**: No new network paths, no new API endpoints, no new authentication mechanisms. The gateway handles all AI provider configuration. The privacy tier model (maximum, balanced, performance) applies identically to all modes.
