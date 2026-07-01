# Task Context

**Generated**: 2026-07-01 | **Phase**: speckit.task-grounding | **Feature**: 007-chunking-strategy

## Verified Dependencies

- VERIFIED DEP: Python | VERSION: 3.12.3 | SOURCE: runtime
- VERIFIED DEP: pytest | VERSION: 9.1.1 | SOURCE: pip freeze
- VERIFIED DEP: Rich | VERSION: 15.0.0 | SOURCE: pip freeze + import
- VERIFIED DEP: Click | VERSION: 8.4.2 | SOURCE: pip freeze
- VERIFIED DEP: PyYAML | VERSION: 6.0.3 | SOURCE: pip freeze
- VERIFIED DEP: openreview-cli | VERSION: editable install | SOURCE: uv pip freeze
- VERIFIED DEP: httpx | VERSION: 0.28.1 | SOURCE: pip freeze
- VERIFIED DEP: Pydantic | VERSION: 2.13.4 | SOURCE: pip freeze

## Project Structure (actual)

```
src/openreview_cli/
├── __init__.py
├── __main__.py
├── app.py
├── errors.py
├── cli/                          # (empty — only __pycache__/)
├── config/
│   ├── __init__.py               # (empty)
│   ├── auth.py
│   ├── loader.py                 # load_config(), get_config_value(), set_config_value()
│   └── paths.py                  # get_config_dir(), get_log_dir(), get_data_dir()
├── gateway/
│   ├── __init__.py
│   ├── router.py
│   ├── registry.py
│   ├── models.py
│   ├── models.json
│   ├── cost.py
│   ├── errors.py
│   ├── redaction.py
│   └── wizard.py
├── parsing/
│   ├── __init__.py               # Exports: Clause, Document, ParseError, ParseErrorCategory
│   ├── clause_detector.py
│   ├── docx_parser.py
│   ├── models.py                 # Clause(dataclass, slots=True), Document, ParseError(Exception)
│   ├── pdf_parser.py
│   └── stream.py                 # stream_clauses(), parse_document(), format_text(), format_json(), format_summary()
├── pii/
│   ├── __init__.py
│   ├── audit.py
│   ├── cache.py
│   ├── config_hash.py
│   ├── encryption.py
│   ├── engine.py
│   ├── mapping.py
│   ├── models.py
│   ├── placeholders.py
│   ├── recognizers.py
│   └── retention.py
├── retrieval/                    # (empty — only __pycache__/)
├── review/
│   ├── __init__.py
│   └── base.py
├── storage/
│   ├── __init__.py
│   ├── database.py
│   └── migrations/
├── ui/
│   └── components/
tests/
├── __init__.py
├── conftest.py
├── fixtures/
│   ├── __init__.py
│   ├── docx/
│   ├── generate_fixtures.py
│   ├── pdf/
│   ├── pii/
│   └── test.txt
├── integration/
│   ├── __init__.py
│   ├── test_accuracy.py
│   ├── test_benchmark.py
│   ├── test_config_change.py
│   ├── test_docx_parser.py
│   ├── test_error_handling.py
│   ├── test_gateway_cli.py
│   ├── test_memory.py
│   ├── test_no_pii_flag.py
│   ├── test_parse_command.py
│   ├── test_pdf_parser.py
│   ├── test_pii_accuracy.py
│   ├── test_pii_error_handling.py
│   ├── test_pii_memory.py
│   ├── test_pii_strip_command.py
│   ├── test_precheck_pii.py
│   ├── test_retrieval/           # (empty)
│   ├── test_stream_clauses.py
│   └── test_warnings.py
└── unit/
    ├── __init__.py
    ├── test_app.py
    ├── test_auth.py
    ├── test_clause_detector.py
    ├── test_cli_client.py
    ├── test_cli_config.py
    ├── test_config_loader.py
    ├── test_database.py
    ├── test_docx_parser.py
    ├── test_models.py
    ├── test_pdf_parser.py
    ├── test_pii_audit.py
    ├── test_pii_engine.py
    ├── test_pii_mapping.py
    ├── test_pii_models.py
    ├── test_pii_placeholders.py
    ├── test_pii_recognizers.py
    └── test_retrieval/           # (empty)

specs/007-chunking-strategy/
├── checklists/                   # (empty)
├── contracts/
│   └── chunking-api.md
├── data-model.md
├── plan.md
├── quickstart.md
├── research.md
├── spec.md
└── tasks.md
```

## Existing Files — Exports

### src/openreview_cli/parsing/__init__.py
- EXPORTS: Clause, Document, ParseError, ParseErrorCategory

### src/openreview_cli/parsing/models.py
- CLASS: Clause (dataclass, slots=True)
  - FIELDS: id: str, title: str | None, text: str, level: int, parent_id: str | None, source_page: int | None, source_paragraph: int | None, source_span: tuple[int, int] | None
- CLASS: Document (dataclass)
  - FIELDS: source_path, format, page_count, clause_count, parse_duration_seconds, warnings, author, title, company
- CLASS: ParseError (Exception)
  - FIELDS: exit_code, category, message, action

### src/openreview_cli/parsing/stream.py
- FUNCTION: stream_clauses(path: str | Path) -> Iterator[Clause]
- FUNCTION: parse_document(path: str | Path) -> tuple[Document, list[Clause]]
- FUNCTION: format_text(clauses: list[Clause], doc: Document | None = None) -> str
- FUNCTION: format_json(clauses: list[Clause]) -> str
- FUNCTION: format_summary(doc: Document) -> str

### src/openreview_cli/config/loader.py
- FUNCTION: load_config(config_path: Path) -> dict[str, Any]
- FUNCTION: get_config_value(config: dict[str, Any], key: str) -> Any
- FUNCTION: set_config_value(config_path: Path, key: str, value: str) -> dict[str, Any]
- DEFAULT_CONFIG: dict[str, object] — contains version, privacy, gateway, storage

### src/openreview_cli/config/paths.py
- FUNCTION: get_config_dir() -> Path
- FUNCTION: get_log_dir() -> Path
- FUNCTION: get_data_dir() -> Path
- FUNCTION: get_review_dir(review_id: str) -> Path

### src/openreview_cli/app.py (Typer app)
- FUNCTION: app (typer.Typer) — main CLI app
- COMMAND: parse — document parsing
- COMMAND: pii — PII operations (subcommands)
- COMMAND: gateway — gateway setup (wizard)

### src/openreview_cli/errors.py
- Exit code constants and user-facing error formatting

## Plan vs Filesystem

### NEW paths (defined in plan.md, do not exist on filesystem)

| Path | Status |
|------|--------|
| src/openreview_cli/chunking/__init__.py | NEW |
| src/openreview_cli/chunking/models.py | NEW |
| src/openreview_cli/chunking/tokenizer.py | NEW |
| src/openreview_cli/chunking/splitter.py | NEW |
| src/openreview_cli/chunking/stream.py | NEW |
| tests/unit/test_chunking_models.py | NEW |
| tests/unit/test_chunking_tokenizer.py | NEW |
| tests/unit/test_chunking_splitter.py | NEW |
| tests/unit/test_chunking_stream.py | NEW |
| tests/integration/test_chunking_cli.py | NEW |
| tests/integration/test_chunking_performance.py | NEW |
| tests/integration/test_chunking_memory.py | NEW |

### EXISTS paths (plan.md references existing files)

| Path | Status | Notes |
|------|--------|-------|
| src/openreview_cli/app.py | EXISTS | Typer app with parse command |
| src/openreview_cli/parsing/models.py | EXISTS | Clause dataclass with slots |
| src/openreview_cli/parsing/stream.py | EXISTS | stream_clauses() generator |
| src/openreview_cli/config/loader.py | EXISTS | load_config() function |
| tests/fixtures/ | EXISTS | Has pdf/, docx/, pii/ subdirs |
| tests/unit/ | EXISTS | 17 test files |
| tests/integration/ | EXISTS | 18 test files |

### MISMATCH

None — all plan.md paths match either EXISTS or NEW status.

## Clause Model Details

The `Clause` dataclass (from `src/openreview_cli/parsing/models.py`):

```python
@dataclass(slots=True)
class Clause:
    id: str
    title: str | None
    text: str
    level: int           # Hierarchy level (0 = top-level)
    parent_id: str | None  # Reference to parent Clause id
    source_page: int | None
    source_paragraph: int | None
    source_span: tuple[int, int] | None  # (start_char, end_char) within source
```

Key observations:
- `parent_id` is the Clause-level parent reference (not chunk-level)
- `level` is the hierarchy depth (0 = top-level article)
- `text` contains the full clause text (potentially multi-page)
- No `article_number` field — the hierarchy is captured via `level` + `parent_id`

## Config Infrastructure

- `load_config(config_path: Path) -> dict[str, Any]` returns full merged config
- Config is a nested dict with `privacy`, `gateway`, `storage` top-level keys
- No `chunking` section exists in `DEFAULT_CONFIG` yet — will be added by this feature (US3, T015)
- Per-mode overrides are handled via env vars and deep merge
