# Implementation Plan: PII Stripping

**Branch**: `feat/003-pii-stripping` | **Date**: 2026-06-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-pii-stripping/spec.md`

## Summary

Build a PII stripping engine that sits between Phase 2 (document parsing) and all downstream processing (chunking, embedding, API calls). The engine uses Microsoft Presidio (analyzer + anonymizer) backed by spaCy `en_core_web_lg` for named entity recognition and built-in regex recognizers for structured PII (emails, phone numbers, amounts, tax IDs). Custom recognizers extend coverage to contract-specific entity types (dollar amounts with legal notation, company registration numbers). The system produces outputs per document: (a) stripped text with deterministic typed placeholders (`[PARTY_A]`, `[AMOUNT_1]`, etc.), and (b) an AES-encrypted JSON mapping file for later restoration. A `pii_audit.json` file records detection metadata (counts, confidence ranges, duration) without any actual PII values. PII stripping is configurable via `privacy.strip_pii` / `--no-pii` and respects a `privacy.pii_threshold` confidence filter (default 0.7). Processing is page-sequential with a 50-character overlap buffer and Rich progress display.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**:
- `presidio-analyzer` ≥2.2.362 — PII detection engine, NLP + regex recognizers, `score_threshold` filtering
- `presidio-anonymizer` ≥2.2.362 — Anonymization operators including `encrypt` (AES-CBC with PKCS#7 padding)
- `spacy` (transitive via presidio-analyzer) — NLP engine for NER; `en_core_web_lg` model (~788 MB on disk, ~600-800 MB loaded)
- `rich` ≥15 — Progress bars for page-by-page display (already in project)
- `typer` ≥0.26 — CLI framework, `--no-pii` flag (already in project)
- `pyyaml` ≥6.0 — Config loading (already in project)

**Storage**: JSON files on disk — `pii_map.json` (encrypted values, chmod 600) and `pii_audit.json` per document, stored at `~/.local/share/openreview/reviews/[review_id]/`

**Testing**: pytest ≥9.1 (already in project)

**Target Platform**: Linux, macOS, Windows (cross-platform via platformdirs)

**Project Type**: CLI tool

**Performance Goals**:
- Strip PII from a 50-page document in <3 seconds (warm, after model load)
- NLP model cold-start time documented separately (expected 3-8 seconds)

**Constraints**:
- Peak memory <100 MB (110 MB floor) for processing overhead — the spaCy `en_core_web_lg` model (~600-800 MB loaded) is **exempt** per constitution amendment v1.2.0 (Principle III)
- Page-sequential processing with 50-character overlap buffer
- AES encryption of PII mapping values at rest (128/192/256-bit key, Presidio's built-in `encrypt` operator uses AES-CBC with PKCS#7 padding, random 16-byte IV per operation)
- Synchronous processing — PII stripping is a local CPU operation before any network calls
- Lazy imports for presidio-analyzer, presidio-anonymizer, and spaCy

**Scale/Scope**:
- Documents from 1 page to 500+ pages
- 11 PII entity types: party names, individual names, emails, phone numbers, addresses, DOB, amounts, tax IDs, bank accounts, passport/DL numbers, company registration numbers
- 4 metadata field types: filename, author, title, company

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | ✅ Pass | PII stripping is the implementation of Principle I. All stripping runs locally before any external API call. PII mapping encrypted at rest (AES, chmod 600). Raw contract text never written to logs — only placeholder tokens appear. |
| **II. Local-First, CLI-Only** | ✅ Pass | All processing is local. No web server, no daemon. Presidio and spaCy run in-process. The only disk I/O is writing the encrypted mapping and audit files to the user's local data directory. |
| **III. Hardware-Bounded** | ✅ Pass (with exemption) | The spaCy `en_core_web_lg` model (~600-800 MB loaded) is exempt per constitution v1.2.0 amendment. All other processing overhead (Presidio framework, regex recognizers, document text buffers, output mapping) must stay under 100 MB. Page-sequential processing ensures document size does not affect peak memory. Lazy imports keep startup <1s when PII stripping is not invoked. |
| **IV. Dependency Minimalism** | ✅ Pass | `presidio-analyzer` and `presidio-anonymizer` are the spec-mandated PII solution. spaCy is a transitive dependency of Presidio (not a direct import for PII — Presidio wraps it). No forbidden dependencies added. `cryptography` is a transitive dependency of `presidio-anonymizer` (required for the encrypt operator). |
| **V. Spec-Driven, YAGNI** | ✅ Pass | Implementation follows the clarified spec exactly. No speculative abstractions. TDD approach. Context-aware disambiguation deferred per spec ("future enhancement"). Cross-document entity alignment deferred per spec. |

**Gate Result**: ✅ PASS — No violations. The NLP model memory exemption is pre-authorized by constitution v1.2.0.

## Project Structure

### Documentation (this feature)

```text
specs/003-pii-stripping/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── strip_pii.md     # PII stripping function contract
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── __init__.py
├── __main__.py
├── app.py                    # Typer app — adds --no-pii flag to review commands
├── errors.py                 # Add pii_error() for PII-specific exit code
├── config/
│   ├── __init__.py
│   ├── auth.py
│   ├── loader.py             # Add privacy.pii_threshold field (default 0.7)
│   └── paths.py              # Add get_review_dir(review_id) helper
├── storage/
│   ├── __init__.py
│   ├── database.py
│   └── migrations/
├── parsing/                  # Existing Phase 2 module (consumed by PII stripping)
│   ├── __init__.py
│   ├── models.py
│   ├── pdf_parser.py
│   ├── docx_parser.py
│   ├── clause_detector.py
│   └── stream.py
└── pii/                      # NEW: PII stripping module
    ├── __init__.py            # Exports: strip_pii, PiiResult, PiiEntity, PiiError
    ├── models.py              # PiiEntity, PiiResult, PiiAudit, PiiError dataclasses
    ├── engine.py              # PiiEngine — wraps Presidio AnalyzerEngine + AnonymizerEngine
    ├── recognizers.py         # Custom Presidio recognizers (amounts, tax IDs, registration numbers)
    ├── placeholders.py        # Placeholder assignment: entity type → [TYPE_N], deterministic sorting
    ├── mapping.py             # PII mapping I/O: write/read encrypted JSON, chmod 600
    └── audit.py               # PII audit file: entity counts, confidence ranges, duration

tests/
├── unit/
│   ├── test_pii_models.py          # PiiEntity, PiiResult, PiiAudit dataclass tests
│   ├── test_pii_engine.py          # PiiEngine unit tests (mocked Presidio)
│   ├── test_pii_recognizers.py     # Custom recognizer tests
│   ├── test_pii_placeholders.py    # Placeholder assignment, deterministic ordering
│   ├── test_pii_mapping.py         # Mapping I/O, encryption, file permissions
│   └── test_pii_audit.py           # Audit file generation, no-PII-leakage checks
├── integration/
│   ├── test_pii_strip_command.py   # End-to-end CLI PII stripping flow
│   ├── test_pii_accuracy.py        # Recall/precision against seeded test corpus
│   ├── test_pii_error_handling.py  # Crash recovery, missing model, graceful halts
│   ├── test_pii_config.py          # Privacy tier, --no-pii flag, threshold changes
│   └── test_pii_memory.py          # Peak memory assertion (processing overhead <100 MB)
└── fixtures/
    └── pii/                        # PII test fixtures
        ├── seeded_contracts/       # 25 auto-generated + 25 manually annotated
        ├── no_pii_document.txt     # Document with zero PII
        ├── multi_occurrence.txt    # Same entity 50+ times
        └── non_english_mixed.txt   # Mixed English + non-English sections
```

**Structure Decision**: New `pii/` module under `src/openreview_cli/`. This keeps PII stripping isolated from parsing (Phase 2) and CLI glue (`app.py`). The module has clear boundaries: `engine.py` owns the Presidio interaction, `placeholders.py` owns the naming scheme, `mapping.py` owns disk I/O, and `audit.py` owns the audit trail. Downstream phases import `strip_pii()` from `pii/__init__.py`.

## Key Technical Decisions

### 1. Presidio as PII Detection Engine

**Decision**: Use `presidio-analyzer` ≥2.2.362 with `presidio-anonymizer` ≥2.2.362 for PII detection and placeholder replacement.

**Rationale**: Presidio is the spec-mandated solution. It provides:
- Built-in recognizers for PERSON, PHONE_NUMBER, EMAIL_ADDRESS, LOCATION, DATE_TIME, IBAN_CODE, CREDIT_CARD, IP_ADDRESS via NLP + regex
- `score_threshold` parameter on `analyzer.analyze()` to filter low-confidence detections
- `OperatorConfig("encrypt", {"key": crypto_key})` for AES encryption of mapping values
- Extensible recognizer registry for custom entity types
- Python 3.12 compatible (tested with v2.2.362)

**Implementation**:
```python
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import SpacyNlpEngine, NerModelConfiguration

model_config = [{"lang_code": "en", "model_name": "en_core_web_lg"}]
nlp_engine = SpacyNlpEngine(models=model_config)
analyzer = AnalyzerEngine(nlp_engine=nlp_engine)

results = analyzer.analyze(
    text=clause_text,
    language="en",
    score_threshold=0.7,  # configurable via privacy.pii_threshold
)
```

**Gotcha**: Presidio's default `score_threshold` is 0 (returns everything). The spec requires 0.7 default. The threshold only applies to NLP-based recognizers — regex recognizers (emails, phone numbers) return scores of 1.0 and are unaffected.

### 2. spaCy en_core_web_lg Model

**Decision**: Use `en_core_web_lg` as the NLP backend for Presidio's named entity recognition.

**Rationale**: The spec mandates this model. It provides PERSON, ORG, LOCATION entity detection. The ~600-800 MB RAM footprint is exempt per constitution v1.2.0.

**Implementation**: The model is loaded once per CLI session via Presidio's `SpacyNlpEngine`. Lazy import ensures the model is not loaded until PII stripping is actually invoked.

**Cold-Start**: Model load takes 3-8 seconds on the reference machine (8 GB RAM, 2-core CPU). This is documented separately from the 3-second per-document target.

### 3. Custom Recognizers for Contract-Specific Entities

**Decision**: Build custom Presidio `PatternRecognizer` instances for entity types not covered by Presidio defaults.

**Entities requiring custom recognizers**:

| Entity Type | Presidio Default? | Custom Recognizer Approach |
|------------|-------------------|---------------------------|
| Party names (ORG) | ✅ ORGANIZATION | NLP-based, no custom needed |
| Individual names (PERSON) | ✅ PERSON | NLP-based, no custom needed |
| Email addresses | ✅ EMAIL_ADDRESS | Regex, no custom needed |
| Phone numbers | ✅ PHONE_NUMBER | Regex, no custom needed |
| Physical addresses | ✅ LOCATION | NLP-based, no custom needed |
| Dates of birth | ✅ DATE_TIME | Regex, no custom needed |
| Generic dates (non-DOB) | ✅ DATE_TIME | NLP-based, no custom needed |
| Dollar amounts | ❌ | Custom regex: `\$[\d,]+(?:\.\d{2})?|\$\d+[MBKmk]` |
| Tax IDs (EIN, SSN) | Partial (US_SSN) | Custom regex for EIN: `\d{2}-\d{7}` |
| Bank account numbers | ✅ IBAN_CODE (partial) | Custom regex for domestic account numbers |
| Passport/DL numbers | ❌ | Custom regex per common formats |
| Company registration numbers | ❌ | Custom regex: state-specific patterns |

**Implementation**:
```python
from presidio_analyzer import PatternRecognizer, Pattern

amount_recognizer = PatternRecognizer(
    supported_entity="AMOUNT",
    patterns=[
        Pattern("dollar_amount", r"\$[\d,]+(?:\.\d{2})?", 1.0),
        Pattern("dollar_shorthand", r"\$\d+(?:\.\d+)?[MBKmk]\b", 1.0),
    ],
)
analyzer.registry.add_recognizer(amount_recognizer)
```

### 4. Deterministic Placeholder Assignment

**Decision**: Sort detected entity values alphabetically before numbering. Same entity → same placeholder across re-runs.

**Rationale**: Spec FR-002 requires deterministic, reproducible placeholders regardless of detection order.

**Implementation**:
1. Collect all detected entities from the full document
2. Group by entity type
3. Within each type, sort unique values alphabetically
4. Assign sequential numbers: `[TYPE_1]`, `[TYPE_2]`, …
5. Build replacement mapping
6. Apply replacements to text (longest-first to avoid substring collisions)

**Entity type → placeholder prefix mapping**:

| Spec Entity | Presidio Entity Type | Placeholder Prefix |
|------------|---------------------|-------------------|
| Party names | ORGANIZATION | PARTY |
| Individual names | PERSON | NAME |
| Email addresses | EMAIL_ADDRESS | EMAIL |
| Phone numbers | PHONE_NUMBER | PHONE |
| Physical addresses | LOCATION | ADDRESS |
| Dates of birth | DATE_TIME | DOB or DATE |
| Dollar amounts | AMOUNT (custom) | AMOUNT |
| Tax IDs | TAX_ID (custom) | TAX_ID |
| Bank account numbers | IBAN_CODE / ACCT (custom) | ACCT |
| Passport/DL numbers | ID_DOC (custom) | ID |
| Company registration numbers | REG_NUMBER (custom) | REG |
| Filename (metadata) | — | FILENAME |
| Author (metadata) | — | AUTHOR |
| Title (metadata) | — | TITLE |
| Company (metadata) | — | COMPANY |

### 5. Page-Sequential Processing with Overlap Buffer

**Decision**: Process pages sequentially with a 50-character overlap buffer between consecutive pages.

**Rationale**: Spec FR-019 requires this approach to catch entities that span page breaks.

**Implementation**:
```python
overlap_buffer = ""  # Last 50 chars of previous page
for page_num, page_text in enumerate(pages):
    combined = overlap_buffer + page_text
    results = analyzer.analyze(text=combined, ...)
    # Adjust offsets for overlap region
    # Only emit entities whose start is >= len(overlap_buffer)
    # (entities in overlap were already emitted from previous page)
    overlap_buffer = page_text[-50:] if len(page_text) >= 50 else page_text
```

### 6. AES Encryption for PII Mapping

**Decision**: Use Presidio's built-in `encrypt` operator (AES-CBC, PKCS#7 padding, random 16-byte IV) to encrypt mapping values before writing to disk.

**Rationale**: Spec FR-015 requires encryption at rest. Using Presidio's built-in operator avoids introducing additional cryptography dependencies (the `cryptography` package is already a transitive dependency of `presidio-anonymizer`).

**Key Management**: The encryption key (128/192/256-bit string) is stored in the user's `config.yml` under `privacy.pii_encryption_key`. If not present, the system generates a random 256-bit key on first use and writes it to config.

**Implementation**:
```python
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

engine = AnonymizerEngine()
# Encrypt each mapping value individually
encrypted_value = engine.anonymize(
    text=original_value,
    analyzer_results=[RecognizerResult(...)],
    operators={"DEFAULT": OperatorConfig("encrypt", {"key": crypto_key})}
)
```

### 7. Non-English Text Handling

**Decision**: Run regex recognizers only on non-English sections. Skip NLP NER. Display warning.

**Rationale**: Spec FR-016 and the clarifications explicitly state that the English NLP model does not run on non-English text. Regex recognizers still catch structured PII (emails, phone numbers, amounts, tax IDs).

**Implementation**: The Phase 2 parser already detects non-English text. The PII engine checks each clause's language flag and selects the appropriate recognizer set.

### 8. Error Handling Strategy

**Decision**: Halt review on PII stripping failure. Include clause heading + processing phase in error. No offsets, no text snippets.

**Rationale**: Spec FR-010 explicitly states the review must not proceed silently with unstripped text.

**Error categories**:
| Error | Detection | Exit Code | Message |
|-------|-----------|-----------|---------|
| Presidio crash during analysis | Exception in `analyzer.analyze()` | 9 | "PII detection failed while processing clause '{clause_title}' ({phase}). Run with --no-pii to skip stripping. Report this bug." |
| spaCy model not found | `OSError` during model load | 9 | "PII detection model not found. Run: python -m spacy download en_core_web_lg" |
| Encryption key invalid | Key length check | 5 | "Config error: privacy.pii_encryption_key must be 16, 24, or 32 characters." |

## Progress Display

**Decision**: Use Rich `Progress` with page-level updates matching spec FR-019.

**Implementation**:
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[bold]{task.description}"),
    BarColumn(),
    TextColumn("{task.completed}/{task.total} pages"),
    transient=True,
) as progress:
    task = progress.add_task("Stripping PII...", total=page_count)
    for page_num, page_text in enumerate(pages):
        # Process page
        progress.update(task, description=f"Stripping PII... page {page_num + 1}/{page_count}")
        progress.advance(task)
```

## Testing Strategy

### Unit Tests
- `test_pii_models.py`: PiiEntity, PiiResult, PiiAudit dataclass creation and validation
- `test_pii_engine.py`: PiiEngine with mocked Presidio — entity detection, threshold filtering, non-English handling
- `test_pii_recognizers.py`: Custom recognizers for amounts, tax IDs, registration numbers (regex correctness)
- `test_pii_placeholders.py`: Deterministic ordering, type mapping, alphabetical sorting, repeated entity consistency
- `test_pii_mapping.py`: JSON write/read round-trip, encryption, chmod 600, overwrite-on-re-strip
- `test_pii_audit.py`: Audit file generation, zero PII values assertion, count correctness

### Integration Tests
- `test_pii_strip_command.py`: End-to-end from parsed document → stripped text + mapping + audit
- `test_pii_accuracy.py`: 90% recall, 95% precision against 50 seeded documents
- `test_pii_error_handling.py`: Presidio crash simulation, missing model, graceful halt
- `test_pii_config.py`: `--no-pii` flag, `privacy.strip_pii: false`, threshold changes trigger re-strip
- `test_pii_memory.py`: Processing overhead <100 MB on a 50-page document (model load exempt)

### TDD Workflow
1. Write unit tests first (they FAIL because no PII module exists)
2. Implement PII dataclasses to make model tests PASS
3. Implement engine with mocked Presidio to make engine tests PASS
4. Write integration tests (they FAIL)
5. Wire up real Presidio to make integration tests PASS
6. Validate accuracy and memory targets

## Dependencies to Add

```bash
uv add presidio-analyzer presidio-anonymizer
# Then download the spaCy model:
uv run python -m spacy download en_core_web_lg
```

**Note**: `spacy` is a transitive dependency of `presidio-analyzer` — do not add it directly. `cryptography` is a transitive dependency of `presidio-anonymizer`. `rich`, `typer`, and `pyyaml` are already in the project.

## Constitution Check — Post-Design Re-evaluation

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | ✅ Pass | PII stripping runs before any downstream processing. Mapping encrypted at rest. Audit file contains zero PII. Logs only show placeholder tokens. |
| **II. Local-First, CLI-Only** | ✅ Pass | All processing local. No server. Presidio and spaCy run in-process. |
| **III. Hardware-Bounded** | ✅ Pass (with exemption) | Model exempt per constitution v1.2.0. Processing overhead stays under 100 MB via page-sequential processing, lazy imports, and no full-document loads. |
| **IV. Dependency Minimalism** | ✅ Pass | Only spec-mandated dependencies added. No forbidden deps. |
| **V. Spec-Driven, YAGNI** | ✅ Pass | No speculative abstractions. Context-aware disambiguation and cross-document alignment explicitly deferred. |

**Post-Design Gate Result**: ✅ PASS — No violations.

## Next Steps

After this plan is approved:
1. Run `/speckit.tasks` to break implementation into tasks
2. Run `/speckit.implement` to execute tasks with TDD workflow
3. Install dependencies: `uv add presidio-analyzer presidio-anonymizer`
4. Download spaCy model: `uv run python -m spacy download en_core_web_lg`
5. Implement PII dataclasses → engine → recognizers → placeholders → mapping → audit
6. Add `privacy.pii_threshold` to config schema
7. Wire `--no-pii` flag to CLI
8. Validate accuracy, memory, and performance targets
