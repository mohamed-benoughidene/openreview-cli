# Implementation Plan: Complete PII Stripping Integration

**Branch**: `feat/complete-pii-stripping` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-complete-pii-stripping/spec.md`

## Summary

Complete PII stripping integration by wiring the existing PII detection engine (Presidio, Phase 3) to the first review subcommand (`precheck`). This includes: automatic PII stripping with Fernet-encrypted reversible mapping, `--no-pii` CLI flag for opting out, config change detection via threshold hash comparison, GDPR-aligned data retention (30-day expiry), fail-fast error recovery with partial result preservation, and accuracy/memory validation suites (recall ≥90%, precision ≥95%, <100MB peak memory, <30s for 500-page documents).

## Technical Context

**Language/Version**: Python 3.12 (per constitution constraint)

**Primary Dependencies**:
- `presidio-analyzer` + `presidio-anonymizer` (PII detection and replacement, already in Phase 3)
- `cryptography` (Fernet encryption for PII mapping, new dependency justified by security requirement)
- `PyMuPDF` (PDF parsing, already in Phase 2)
- `python-docx` (DOCX parsing, already in Phase 2)
- `docling` (OCR for scanned PDFs, already in Phase 2)
- `spaCy` (NLP model for Presidio, `en_core_web_lg`, constitutionally exempt from memory budget)

**Storage**:
- SQLite (audit trail, config hash storage, review metadata)
- Filesystem (encrypted PII mapping files alongside review results, Fernet-encrypted JSON)

**Testing**: pytest (unit + integration), tracemalloc (memory profiling), pytest-cov (coverage)

**Target Platform**: Linux/macOS CLI (local-first, no server, offline-capable)

**Project Type**: CLI tool (Typer-based, single-command invocation)

**Performance Goals**:
- <30 seconds PII processing time for 500-page document
- <100 MB peak memory (excluding NLP model ~500MB)
- PII recall ≥90%, precision ≥95% on validation corpus

**Constraints**:
- Peak memory <100 MB (excluding NLP model, per constitution Principle III)
- Offline-capable (no network calls required for PII stripping)
- Privacy-first (all PII stripped before any external API call)
- GDPR-aligned data retention (30-day expiry, user-deletable)

**Scale/Scope**:
- Up to 500 pages per document (linear scaling from 50-page baseline)
- 50+ contracts in validation corpus (ground truth annotated)
- 16 PII placeholder types (party names, dates, amounts, addresses, etc.)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | PASS | PII stripping runs locally before any API call. Fernet encryption provides authenticated, tamper-evident storage. Audit trail logs per-document summary (not per-entity detail) to avoid exposing PII patterns. GDPR-aligned retention (30-day expiry, user-deletable). |
| II. Local-First, CLI-Only | PASS | No server, no daemon, no telemetry. PII stripping is fully local. `--no-pii` flag supports all-local setup. |
| III. Hardware-Bounded | PASS | Peak memory <100 MB (excluding NLP model). Streaming parsers (PyMuPDF page-by-page, python-docx paragraph-by-paragraph). Lazy imports for heavy dependencies. NLP model exempt per constitution v1.2.0. |
| IV. Dependency Minimalism | PASS | `cryptography` is a new dependency but justified by Fernet encryption requirement (no stdlib alternative for authenticated encryption). All other dependencies already in Phase 3. No forbidden dependencies introduced. |
| V. Spec-Driven, YAGNI | PASS | Spec exists (spec.md). Scope is minimal: wire existing PII engine to first review command, add `--no-pii` flag, config change detection, validation suites. No speculative abstractions. |

**Gate Result**: PASS (no violations)

## Project Structure

### Documentation (this feature)

```text
specs/004-complete-pii-stripping/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output (research decisions)
├── data-model.md        # Phase 1 output (entity model)
├── quickstart.md        # Phase 1 output (validation guide)
├── contracts/           # Phase 1 output (CLI schema, config schema)
│   ├── cli-schema.md    # CLI command schema for review commands
│   └── config-schema.md # config.yml PII section schema
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── pii/
│   ├── __init__.py
│   ├── engine.py              # PiiEngine (already in Phase 3)
│   ├── encryption.py          # Fernet encryption/decryption for PII mapping
│   ├── mapping.py             # Encrypted mapping file I/O
│   ├── audit.py               # Audit trail logging (per-document summary)
│   ├── config_hash.py         # Config hash comparison for change detection
│   └── retention.py           # GDPR retention (30-day expiry, deletion)
├── review/
│   ├── __init__.py
│   ├── precheck.py            # PreCheck review command (first review subcommand)
│   └── base.py                # Base review command with PII integration
└── app.py                     # Typer app (add `precheck` subcommand)

tests/
├── unit/
│   ├── test_pii_encryption.py # Fernet encryption unit tests
│   ├── test_pii_mapping.py    # Mapping file I/O unit tests
│   └── test_pii_audit.py      # Audit trail unit tests
├── integration/
│   ├── test_precheck_pii.py   # PreCheck + PII integration
│   ├── test_no_pii_flag.py    # --no-pii flag integration (T033)
│   ├── test_config_change.py  # Config change detection (T034)
│   ├── test_pii_accuracy.py   # Accuracy validation (T049)
│   ├── test_pii_memory.py     # Memory validation (T050)
│   └── test_pii_retention.py  # GDPR retention integration
└── fixtures/
    └── pii/
        ├── ground_truth.json  # Validation corpus (50+ contracts)
        └── synthetic_500page.pdf # 500-page test document

scripts/
└── benchmark_pii_stripping.py # PII stripping benchmark (already in Phase 3)
```

**Structure Decision**: Single CLI project (Option 1). PII module extends existing Phase 3 structure. Review module is new (first review subcommand).

## Complexity Tracking

> **No violations to justify. All constitution principles pass.**
