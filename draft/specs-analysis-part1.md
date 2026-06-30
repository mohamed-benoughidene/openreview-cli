# Spec Group Analysis — Extracted Implementation Specs

**Generated**: 2026-06-28
**Source**: All files under `specs/001-config-storage-foundation/`, `specs/002-document-parsing/`, `specs/003-pii-stripping/`
**Method**: Read every file in each group — spec.md, plan.md, tasks.md, data-model.md, research.md, quickstart.md, checklists/requirements.md, contracts/

═══════════════════════════════════════════
SPEC S-1: 001-config-storage-foundation
───────────────────────────────────────────

FEATURE / DOMAIN
Configuration management and SQLite storage foundation for the openreview CLI tool: YAML config loading with Pydantic v2 validation, auth.json secure storage, SQLite schema with forward-only migrations, CLI config/client commands, env var overrides, cost tracking, and cross-platform path resolution.
___

DEFINED CAPABILITIES
CAP1: YAML config file loading (`config.yml`) with Pydantic v2 `BaseModel` validation
CAP2: Auth JSON file (`auth.json`) creation with chmod 600 on Unix, permission warning on Windows
CAP3: SQLite database initialization (`openreview.db`) with WAL mode, foreign keys, and `schema_version`-based forward-only migrations
CAP4: CLI commands `config show`, `config get <key>`, `config set <key> <value>`
CAP5: CLI commands `client add <id> <name>`, `client list`, `client delete <id>` with `--force` flag
CAP6: Environment variable overrides: `OPENREVIEW_*` for config values, provider API keys (`OPENAI_API_KEY`, etc.)
CAP7: Config resolution priority hierarchy: CLI flags > CLI arguments > env vars > `config.yml` > `auth.json` > built-in defaults
CAP8: Config value validation on `config set` with clear error messages and field suggestions
CAP9: Config backup (`config.yml.bak`) before every `config set` operation
CAP10: Cost log insertion to `cost_logs` table on each API call
CAP11: Per-review cost limit enforcement (exit code 6)
CAP12: Daily cost limit enforcement (exit code 6)
CAP13: Platform-aware path resolution via `platformdirs` (`user_config_dir`, `user_log_dir`, `user_data_dir`)
CAP14: Operational logging to file at `~/.config/openreview/logs/openreview.log` using stdlib logging, `--debug` flag for DEBUG level
CAP15: First-run auto-creation of config directory, `config.yml`, `auth.json`, and `openreview.db` on any command
CAP16: Automatic config directory creation (`playbooks/`, `reviews/`, `logs/`) on first run
CAP17: Per-review SQLite database at `reviews/<review_id>/review.db` with `chunks`, `graph_nodes`, `graph_edges` tables (schema defined, creation deferred to downstream phases)
___

TECH DECISIONS
TD1: PyYAML `yaml.safe_load()` / `yaml.safe_dump()` (never `yaml.load()`) for YAML config
TD2: `platformdirs` for cross-platform path resolution — `user_config_dir("openreview")`, `user_log_dir("openreview")`, `user_data_dir("openreview")` with `ensure_exists=True`
TD3: Pydantic v2 `BaseModel` for config validation; env var overrides handled manually (no `pydantic-settings` dep)
TD4: Typer `app.add_typer()` for subcommand groups — `config` and `client`
TD5: SQLite via stdlib `sqlite3` — context manager for transactions, WAL mode, foreign keys ON
TD6: Forward-only migrations via `schema_version` table + `.sql` migration files, checked on every command invocation
TD7: Python stdlib `logging` with `FileHandler` + `StreamHandler` (dual output)
TD8: `os.chmod(path, 0o600)` for Unix file permissions; Windows warning only (no enforcement)
TD9: Lazy imports for `platformdirs` and PyYAML (import inside function calls, not at module level)
TD10: Cost tracking uses integer cents (not floating-point dollars)
TD11: Integer schema for `version` field in `config.yml` with `version ≤ app schema version` constraint
TD12: `openreview` config directory enumeration: `config show` renders via Rich table
___

IMPLEMENTATION STATUS
CAP1: BUILT (T010, T013, T016 — `src/openreview_cli/config/loader.py`)
CAP2: BUILT (T014, T017, T018 — `src/openreview_cli/config/auth.py`)
CAP3: BUILT (T007, T008, T009, T015, T020 — `src/openreview_cli/storage/database.py`, `src/openreview_cli/storage/migrations/001_initial.sql`)
CAP4: BUILT (T021–T031 — `src/openreview_cli/app.py` config subcommands)
CAP5: BUILT (T045–T052 — `src/openreview_cli/app.py` client subcommands)
CAP6: BUILT (T032–T037 — `src/openreview_cli/config/loader.py` + `auth.py`)
CAP7: BUILT (T037 — merged into `loader.py` config resolution)
CAP8: BUILT (T025, T030 — validation on set in `loader.py`)
CAP9: BUILT (T024, T029 — backup in `loader.py`)
CAP10: BUILT (T038, T041 — `src/openreview_cli/storage/database.py`)
CAP11: BUILT (T040, T043 — `check_review_limit()` in `database.py`)
CAP12: BUILT (T039, T042 — `check_daily_limit()` in `database.py`)
CAP13: BUILT (T005 — `src/openreview_cli/config/paths.py`)
CAP14: BUILT (T006 — `src/openreview_cli/logging_config.py`)
CAP15: BUILT (T019 — wired into `app.py` startup)
CAP16: BUILT (T005 — `platformdirs` with `ensure_exists=True`)
CAP17: PLANNED (schema defined in spec/data-model.md and `sqlite-schema.sql` but `chunks`, `graph_nodes`, `graph_edges` are in per-review DB created by Phase 2+; `001_initial.sql` migration excludes per-review DB tables — those belong to later phases)
___

INTERFACES / CONTRACTS
I1: CLI command `openreview --version` — smoke test, triggers first-run setup
I2: CLI command `openreview config show` — Rich table of all merged config values
I3: CLI command `openreview config get <key>` — dot-notation lookup, single value output
I4: CLI command `openreview config set <key> <value>` — validates, creates `config.yml.bak`, updates file
I5: CLI command `openreview client add <id> <name>` — inserts into `clients` table
I6: CLI command `openreview client list` — formatted table with id, name, dates
I7: CLI command `openreview client delete <id>` [`--force`] — removes client; `--force` bypasses "has reviews" check
I8: Contract `contracts/config-schema.yml` — authoritative schema for `config.yml`
I9: Contract `contracts/auth-schema.json` — JSON Schema for `auth.json`
I10: Contract `contracts/sqlite-schema.sql` — authoritative schema for `openreview.db` and per-review DB
I11: Exit code 5 — config/storage errors
I12: Exit code 6 — cost limit errors
I13: Environment variables `OPENREVIEW_*` for config overrides
I14: Environment variables `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `COHERE_API_KEY`, `HUGGINGFACE_API_KEY`, `GOOGLE_API_KEY` for auth overrides
___

DEPENDENCIES
DEP1: Python 3.12+ with stdlib `sqlite3` module
DEP2: PyYAML (added via `uv add PyYAML`)
DEP3: `platformdirs` (added via `uv add platformdirs`)
DEP4: Pydantic v2 (already in project)
DEP5: Typer (already in project)
DEP6: Rich (already in project)
DEP7: No dependency on other specs — this is the foundation for all subsequent phases
___

GAPS / TODOS
G1: `gateway.model_registry_refresh_days` field defined in `config-schema.yml` but explicitly marked inactive until Phase 4 — no refresh logic runs in Phase 1
G2: `shared_positions` table referenced in spec FR-009 as deferred to Phase 7 (Playbook)
G3: Per-review DB tables (`chunks`, `graph_nodes`, `graph_edges`) are defined in schema and data model but creation belongs to downstream phases — only the main `openreview.db` is created in Phase 1
G4: Schema rollback is not implemented — "Rollback is done by restoring from backup"
G5: Migration runner refactoring note in AGENTS.md mentions unused `_run_migrations()` function lingering in `database.py` (passed via config/model instead)
════════════════════════════════════════════

═══════════════════════════════════════════
SPEC S-2: 002-document-parsing
───────────────────────────────────────────

FEATURE / DOMAIN
Document parsing system that extracts hierarchical clause structures from PDF and DOCX contracts via streaming parsers, NUPunkt clause boundary detection, and a unified `stream_clauses()` generator interface.
___

DEFINED CAPABILITIES
CAP1: PDF parsing via PyMuPDF with page-by-page streaming — never loads full document
CAP2: DOCX parsing via python-docx with heading style detection and paragraph iteration
CAP3: NUPunkt-based clause boundary detection as primary engine (91.1% precision on legal text)
CAP4: Hierarchy detection from numbering patterns (Article I, Section 3.1, (a), (i), roman numerals)
CAP5: Heading detection via layered approach: TOC extraction → font analysis (size, bold) → numbering patterns
CAP6: Unified `stream_clauses(path) → Iterator[Clause]` generator routing to correct parser by file extension
CAP7: `parse_document(path) → tuple[Document, list[Clause]]` helper collecting all clauses with metadata
CAP8: `openreview parse <path>` CLI command with `--format text|json` and `--summary` flags
CAP9: Text output formatter — indented hierarchical outline with page/paragraph numbers, 200-char truncation
CAP10: JSON output formatter — flat array of clause dicts with `parent_id` references
CAP11: Summary output formatter — single-line: "Parsed N clauses across M pages in T.TTs"
CAP12: Cross-format equivalence verification — same contract in PDF and DOCX produces same clause count (±10%) and same nesting
CAP13: Error handling for 6 categories: file_not_found, unsupported_format, corrupt, password_protected, empty, no_text (all exit code 8)
CAP14: Password prompt for protected PDFs: env var `OPENREVIEW_PDF_PASSWORD` first, interactive `getpass` if stdin is a TTY, otherwise `ParseError`
CAP15: Flat document fallback — split by blank-line-separated paragraphs into sibling clauses at level 0 with warning
CAP16: Non-English text detection via Unicode ranges (Arabic, CJK, Cyrillic) with language warning
CAP17: Tofu/replacement character (`\uFFFD`) detection with warning about unreadable text
CAP18: DOCX tracked changes detection via raw XML (`w:ins` / `w:del`) with warning
CAP19: DOCX embedded image/`w:drawing` element skipping
CAP20: Page-level progress bar via Rich `Progress` with `transient=True`, pulsing animation for unknown page count
CAP21: Memory budget validation — <100 MB peak (110 MB floor) for 500-page document via `tracemalloc`
CAP22: Speed benchmark — <3 seconds for 50-page native PDF
CAP23: Clause boundary accuracy — ≥95% on 75-contract synthetic test set
___

TECH DECISIONS
TD1: PyMuPDF (fitz) ≥1.24 for PDF parsing — `for page in doc:` streaming, `get_text("dict", sort=True)` for structured text + font info
TD2: python-docx ≥1.1 for DOCX parsing — accept full-XML-on-`Document()` limitation, generators to yield immediately
TD3: NUPunkt as primary clause boundary detection engine — `sent_spans()` for character-level positions, `threshold=0.7` default
TD4: NUPunkt boundaries may be refined by supplementary signals (TOC, font, numbering) but never overridden
TD5: PDF TOC extraction (`doc.get_toc()`) → font analysis (`span["flags"] & (1 << 4)` for bold) → numbering patterns (regex)
TD6: DOCX heading style mapping: `Heading 1` → level 0, `Heading 2` → level 1, etc.
TD7: DOCX tracked changes via raw `lxml` — check `body.iter(f"{{{ns}}}ins")` and `body.iter(f"{{{ns}}}del")` with namespace `http://schemas.openxmlformats.org/wordprocessingml/2006/main`
TD8: Rich `Progress` with `SpinnerColumn`, `TextColumn`, `BarColumn`, `transient=True` for progress display
TD9: `@dataclass(slots=True)` for `Clause`, `Document`, `ParseError` to minimize memory
TD10: Clause ID format: `"clause-{n}"` auto-incremented per document
TD11: Lazy imports for PyMuPDF, python-docx, and NUPunkt (loaded only when the relevant parser is invoked)
TD12: Format detection via file extension (`.pdf`, `.docx`), case-insensitive — no content-based detection
TD13: PDF reading order: top-left to bottom-right coordinate sorting (`sort=True` parameter)
TD14: DOCX heading detection as primary for DOCX hierarchy; numbering patterns as supplementary
TD15: Cross-platform path handling reuses Phase 1 `platformdirs`-based path resolution
___

IMPLEMENTATION STATUS
CAP1: BUILT (T012, T014, T016 — `src/openreview_cli/parsing/pdf_parser.py`)
CAP2: BUILT (T019, T020 — `src/openreview_cli/parsing/docx_parser.py`)
CAP3: BUILT (T013 — `src/openreview_cli/parsing/clause_detector.py`)
CAP4: BUILT (T013 — `detect_clause_starts()`, `build_hierarchy()` in `clause_detector.py`)
CAP5: BUILT (T013, T014 — layered heading detection in `pdf_parser.py` and `clause_detector.py`)
CAP6: BUILT (T025, T029 — `src/openreview_cli/parsing/stream.py` + `__init__.py`)
CAP7: BUILT (T026 — `parse_document()` in `stream.py`)
CAP8: BUILT (T038 — `src/openreview_cli/app.py` parse command)
CAP9: BUILT (T039 — `format_text()` in `stream.py` / `formatter.py`)
CAP10: BUILT (T040 — `format_json()` in `stream.py` / `formatter.py`)
CAP11: BUILT (T041 — `format_summary()` in `stream.py` / `formatter.py`)
CAP12: BUILT (T023, T024, T030 — cross-format equivalence tests and verification)
CAP13: BUILT (T031, T033 — `tests/integration/test_error_handling.py` + `stream.py` error wrapping)
CAP14: BUILT (T034 — `pdf_parser.py` password handling: env var, interactive, non-interactive error)
CAP15: BUILT (T013 — flat document fallback in `clause_detector.py`)
CAP16: BUILT (T027 — non-English detection in `clause_detector.py`)
CAP17: BUILT (T028 — tofu detection in `clause_detector.py`)
CAP18: BUILT (T021 — tracked changes detection in `docx_parser.py`)
CAP19: BUILT (T019 — image skipping in `docx_parser.py`)
CAP20: BUILT (T015 — progress bar in `pdf_parser.py`)
CAP21: BUILT (T044 — `@pytest.mark.memory` test)
CAP22: BUILT (T045 — `@pytest.mark.benchmark` speed test)
CAP23: BUILT (T046 — `@pytest.mark.accuracy` clause boundary accuracy test)
___

INTERFACES / CONTRACTS
I1: `stream_clauses(path: str | Path) -> Iterator[Clause]` — core parsing API consumed by downstream pipeline stages
I2: `parse_document(path: str | Path) -> tuple[Document, list[Clause]]` — convenience wrapper that collects all clauses
I3: CLI command `openreview parse <path>` [`--format text|json`] [`--summary`]
I4: Public API exports from `openreview_cli.parsing`: `stream_clauses`, `parse_document`, `Clause`, `Document`, `ParseError`, `ParseErrorCategory`
I5: `Clause` dataclass with fields `id`, `title`, `text`, `level`, `parent_id`, `source_page`, `source_paragraph`, `source_span`
I6: `Document` dataclass with fields `source_path`, `format`, `page_count`, `clause_count`, `parse_duration_seconds`, `warnings`
I7: `ParseError` dataclass with fields `exit_code` (8), `category`, `message`, `action`
I8: `ParseErrorCategory` enum: `file_not_found`, `unsupported_format`, `corrupt`, `password_protected`, `empty`, `no_text`
I9: Contract `contracts/stream_clauses.md` — full API contract with input/output/error/performance specifications
I10: Exit code 8 — all parsing errors
I11: Text output format: indented hierarchical outline, 2 spaces per level, page/paragraph number, 200-char text truncation
I12: JSON output format: flat array of clause dicts, `json.dumps(indent=2, ensure_ascii=False)`
I13: Summary output format: single line "Parsed N clauses across M pages in T.TTs"
I14: Progress bar: Rich `Progress` with page counter "Page 12 of 47", pulsing animation when total unknown
___

DEPENDENCIES
DEP1: Phase 1 (config/storage foundation) — `platformdirs`-based path resolution reused
DEP2: PyMuPDF ≥1.24 (added via `uv add PyMuPDF`)
DEP3: python-docx ≥1.1 (added via `uv add python-docx`)
DEP4: nupunkt (added via `uv add nupunkt`) — zero runtime deps, MIT-licensed
DEP5: Rich ≥13 (already in project) — progress bars, terminal UI
DEP6: Typer ≥0.12 (already in project) — CLI framework
DEP7: NUPunkt model (~432 MB loaded) — loaded lazily, first call caches model reference
___

GAPS / TODOS
G1: Scanned PDF OCR (Docling) explicitly deferred to a later phase — image-only PDFs get `ParseError("no_text")` with OCR install suggestion
G2: Async version `stream_clauses_async()` mentioned as future extension — not in Phase 2
G3: Filtering options (`min_level`, `max_level`, `include_text`) mentioned as future extension — not in Phase 2
G4: Cross-reference detection (`references: list[str]` field on Clause) deferred — "See Section 5.2" tracking
G5: Document metadata extraction (title, author, creation date) deferred — `Document.metadata: dict`
G6: Annotations (tracked changes, comments) support as `list[Annotation]` deferred
G7: Graph structure (`GraphNode`, `GraphEdge`) deferred to Phase 7+
G8: Raw `lxml.etree.iterparse` streaming for large DOCX files (>10MB) is a known mitigation but not implemented — python-docx limitation accepted for Phase 2
G9: Content-based format detection (magic bytes) not needed in Phase 2 — file extension only
══ ════════════════════════════════════════

═══════════════════════════════════════════
SPEC S-3: 003-pii-stripping
───────────────────────────────────────────

FEATURE / DOMAIN
PII stripping engine that detects and replaces personally identifiable information in parsed contract text using Microsoft Presidio (NLP + regex), produces stripped text with deterministic typed placeholders and an encrypted mapping file for value restoration, and runs before any downstream processing.
___

DEFINED CAPABILITIES
CAP1: Detection and replacement of 15 entity types: 11 PII types (party names, individual names, email addresses, phone numbers, physical addresses, dates of birth, dollar amounts, tax IDs, bank account numbers, passport/DL numbers, company registration numbers) + 4 metadata field types (filename, author, title, company)
CAP2: Deterministic, typed placeholders per entity type: `[PARTY_A]`, `[NAME_1]`, `[EMAIL_1]`, `[PHONE_1]`, `[ADDRESS_1]`, `[DOB_1]`, `[AMOUNT_1]`, `[TAX_ID_1]`, `[ACCT_1]`, `[ID_1]`, `[REG_1]`, `[DATE_1]`, `[FILENAME_1]`, `[AUTHOR_1]`, `[TITLE_1]`, `[COMPANY_1]`
CAP3: Placeholder assignment by sorting detected entity values alphabetically before numbering — same entity always receives the same placeholder across re-runs
CAP4: Consistent placeholder assignment — repeated occurrences of same entity map to same placeholder
CAP5: Two outputs from stripping: (a) stripped text with placeholders, (b) mapping dictionary of placeholder → original value
CAP6: AES-encrypted PII mapping file on disk (`pii_map.json`) via Presidio's built-in `encrypt` operator (AES-CBC with PKCS#7 padding, random 16-byte IV)
CAP7: Entity-based NLP detection via Presidio `AnalyzerEngine` backed by spaCy `en_core_web_lg`
CAP8: Custom regex `PatternRecognizer` instances for entity types not covered by Presidio defaults: `AMOUNT` (dollar amounts), `TAX_ID` (EIN, SSN), `ID_DOCUMENT` (passport/DL), `REG_NUMBER` (company registration numbers)
CAP9: Configurable confidence threshold (`privacy.pii_threshold`, default 0.7) — applies only to NLP-based recognizers; regex recognizers always return score 1.0 and are unaffected
CAP10: PII stripping immediately after document parsing, before any chunking, embedding, or API call
CAP11: Respect `privacy.strip_pii` config setting and `--no-pii` CLI flag
CAP12: Warning when PII stripping is disabled: "⚠️ PII stripping disabled. Contract text may be sent to providers as-is."
CAP13: Graceful error handling on failure — halt the review, display actionable error with clause heading + processing phase, no character offsets or text snippets
CAP14: Error categories: `engine_crash` (Presidio exception), `model_not_found` (spaCy model missing), `invalid_key` (encryption key wrong length)
CAP15: Metadata redaction — unconditionally redact filename, author, title, company with typed placeholders
CAP16: PII audit file (`pii_audit.json`) written alongside mapping — contains entity detection counts per type, confidence ranges, processing duration, threshold, non-English section count. Zero actual PII values
CAP17: Page-sequential processing with 50-character overlap buffer between consecutive pages
CAP18: Non-English text handling — regex recognizers only (no NLP NER) on non-English sections, warning displayed
CAP19: PII mapping file deletion when user deletes the associated review
CAP20: Re-stripping from original text from scratch on any config change — no incremental mode
CAP21: Progress display during stripping: "Stripping PII... page 12/50" via Rich
CAP22: Encryption key auto-generation with `secrets.token_urlsafe(32)[:32]` if not present in config
CAP23: PII mapping file created with chmod 600 permissions
CAP24: PII mapping file never sent to any external service (architectural invariant)
CAP25: False replacement rate <5% — legal terms like "Force Majeure", "Indemnification", law firm names are NOT replaced
___

TECH DECISIONS
TD1: Microsoft Presidio — `presidio-analyzer` ≥2.2.362 for detection, `presidio-anonymizer` ≥2.2.362 for encryption
TD2: spaCy `en_core_web_lg` (~600-800 MB loaded) as NLP backend via Presidio's `SpacyNlpEngine` — memory exempt per constitution v1.2.0 amendment
TD3: Presidio `score_threshold=0.7` (configurable via `privacy.pii_threshold`) — built-in filter, not manual post-filtering
TD4: Presidio's built-in `encrypt` operator (`OperatorConfig("encrypt", {"key": crypto_key})`) for AES-CBC encryption of mapping values
TD5: Custom `PatternRecognizer` instances for `AMOUNT`, `TAX_ID`, `ID_DOCUMENT`, `REG_NUMBER` — registered via `analyzer.registry.add_recognizer()`
TD6: `@dataclass(slots=True)` for `PiiEntity`, `PiiResult`, `PiiAudit`, `PiiError`
TD7: Rich `Progress` for page-by-page progress display during stripping
TD8: Synchronous processing — PII stripping is a local CPU operation before any network calls
TD9: Lazy imports for `presidio-analyzer`, `presidio-anonymizer`, and spaCy — loaded only when PII stripping is invoked
TD10: Encryption key: 256-bit (32-byte) generated via `secrets.token_urlsafe(32)[:32]`, stored in `config.yml` under `privacy.pii_encryption_key`
TD11: Metadata redaction uses separate typed placeholders (`[FILENAME_1]`, `[AUTHOR_1]`, `[TITLE_1]`, `[COMPANY_1]`) independent of body text PII
TD12: Text replacement applied longest-first to avoid substring collisions
TD13: Party placeholders use letters (`A`, `B`, `C`, …); all other types use sequential numbers (`1`, `2`, `3`, …)
TD14: CPU is the default fallback for spaCy; GPU auto-detection via Presidio's built-in CUDA/MPS auto-detection
___

IMPLEMENTATION STATUS
CAP1: BUILT (T016, T017, T018, T019, T021, T052 — all recognizers + engine + metadata redaction)
CAP2: BUILT (T020 — `src/openreview_cli/pii/placeholders.py`)
CAP3: BUILT (T020 — alphabetical sorting before numbering in `placeholders.py`)
CAP4: BUILT (T020 — mapping de-duplication in `placeholders.py`)
CAP5: BUILT (T022 — `strip_pii()` in `pii/__init__.py`)
CAP6: BUILT (T028, T029 — `write_pii_mapping()`, `read_pii_mapping()` in `pii/mapping.py`)
CAP7: BUILT (T017 — `PiiEngine` in `pii/engine.py`)
CAP8: BUILT (T016, T018 — `recognizers.py` + registration in `PiiEngine.__init__()`)
CAP9: BUILT (T010 — `privacy.pii_threshold` added to config schema; T019 — `score_threshold` parameter in `detect_on_page()`)
CAP10: BUILT (T036 — skip logic wired in `strip_pii()`)
CAP11: PARTIAL — config flag `privacy.strip_pii` check is built (T036), but `--no-pii` CLI flag is NOT wired to review commands because no review commands exist yet (T035 is not complete — marked [ ] in tasks.md)
CAP12: BUILT (T036 — warning displayed when stripping disabled)
CAP13: BUILT (T042 — `PiiError` raising in `PiiEngine.detect_on_page()`)
CAP14: BUILT (T043, T044 — `model_not_found` and `invalid_key` categories in `PiiError`)
CAP15: BUILT (T021, T052 — metadata redaction in `_redact_metadata()`; T052 completed AUTHOR, TITLE, COMPANY placeholders)
CAP16: BUILT (T026, T030 — `write_pii_audit()` in `pii/audit.py`)
CAP17: BUILT (T023 — 50-character overlap buffer in `detect_all_pages()`)
CAP18: BUILT (T045 — non-English warning in `PiiEngine.detect_on_page()`)
CAP19: BUILT (T047 — `pii_map.json` deletion wired into review-deletion path)
CAP20: BUILT (T020 — always processes from original text, re-strip overwrites existing files)
CAP21: BUILT (T046, T054 — Rich progress display in `detect_all_pages()`; vocabulary refined to "page")
CAP22: BUILT (T053 — encryption key auto-generation with `secrets.token_urlsafe(32)[:32]`)
CAP23: BUILT (T028 — `chmod 600` in `write_pii_mapping()`)
CAP24: BUILT (architectural invariant — mapping file path never sent to HTTP requests; T027 integration test asserts this)
CAP25: BUILT (threshold 0.7 eliminates most false positives; deny-list not implemented but threshold approach is sufficient per spec assumption)
___

INTERFACES / CONTRACTS
I1: `strip_pii(clauses: list[Clause], document: Document, *, threshold: float = 0.7, strip_metadata: bool = True) -> PiiResult` — core public function
I2: `write_pii_mapping(mapping: dict[str, str], review_dir: Path, encryption_key: str) -> Path` — encrypted mapping writer
I3: `read_pii_mapping(review_dir: Path, encryption_key: str) -> dict[str, str]` — encrypted mapping reader
I4: `write_pii_audit(audit: PiiAudit, review_dir: Path) -> Path` — audit file writer
I5: CLI: `--no-pii` flag (defined in spec, not yet wired — no review commands exist)
I6: Public API exports from `openreview_cli.pii.__init__`: `strip_pii`, `PiiResult`, `PiiEntity`, `PiiAudit`, `PiiError`, `write_pii_mapping`, `read_pii_mapping`
I7: `PiiEntity` dataclass — fields: `entity_type`, `original_value`, `start`, `end`, `score`, `placeholder`, `source`
I8: `PiiResult` dataclass — fields: `stripped_text`, `mapping`, `entities`, `page_count`, `duration_seconds`, `warnings`
I9: `PiiAudit` dataclass — fields: `version`, `threshold`, `duration_seconds`, `page_count`, `non_english_sections`, `entity_counts`, `metadata_fields_redacted`; nested `EntityTypeStats(count, min_score, max_score)`
I10: `PiiError(Exception)` — fields: `exit_code` (9), `category`, `clause_heading`, `phase`, `message`, `action`
I11: Exit code 9 — all PII stripping errors
I12: Exit code 5 — config errors (invalid encryption key)
I13: Contract `contracts/strip_pii.md` — full API contract with function signatures, input/output/error specifications, CLI integration, performance targets
I14: `pii_map.json` file format — JSON with `version`, `encrypted`, `entries` keys; values are AES-CBC encrypted and base64-encoded
I15: `pii_audit.json` file format — JSON with `version`, `threshold`, `duration_seconds`, `page_count`, `non_english_sections`, `entities` (per-type stats), `metadata_fields_redacted`; zero actual PII values
I16: Progress display string: "Stripping PII... page 12/50"
I17: Warning display: "⚠️ PII stripping disabled. Contract text may be sent to providers as-is."
___

DEPENDENCIES
DEP1: Phase 1 (config/storage) — `privacy.strip_pii`, `privacy.tier`, `privacy.pii_threshold`, `privacy.pii_encryption_key` fields in config schema; `get_review_dir()` helper in paths
DEP2: Phase 2 (document parsing) — consumes `Clause` and `Document` dataclasses from `openreview_cli.parsing.models`
DEP3: `presidio-analyzer` ≥2.2.362 (added via `uv add presidio-analyzer`)
DEP4: `presidio-anonymizer` ≥2.2.362 (added via `uv add presidio-anonymizer`)
DEP5: spaCy `en_core_web_lg` model (~788 MB on disk, ~600-800 MB loaded) — transitive dependency via `presidio-analyzer`; downloaded via `uv run python -m spacy download en_core_web_lg`
DEP6: `cryptography` — transitive dependency of `presidio-anonymizer` (used for AES encryption)
DEP7: Rich ≥15 (already in project) — progress display
DEP8: Typer ≥0.26 (already in project) — `--no-pii` CLI flag
DEP9: PyYAML ≥6.0 (already in project) — config loading
___

GAPS / TODOS
G1: `--no-pii` CLI flag is defined in spec (FR-008) and contract but NOT wired to any review commands — no review commands exist yet. Listed as deferred work in AGENTS.md (T033, T035)
G2: Config change detection (threshold hash compare, T037) is not implemented — no downstream cache exists to invalidate yet. Listed as deferred in AGENTS.md (T037)
G3: Accuracy validation (`tests/integration/test_pii_accuracy.py`, T031a) is a skeleton — needs populated corpus with ground truth and recall/precision calculation. Deferred per AGENTS.md (T049)
G4: Memory validation (`tests/integration/test_pii_memory.py`, T031b) is a skeleton — needs 50-page seeded document and proper `tracemalloc` isolation. Deferred per AGENTS.md (T050)
G5: Missing-model integration test (T039) needs monkeypatching `spacy.load` at Presidio level — test is not yet implemented. Deferred per AGENTS.md (T039)
G6: Full test suite + pre-commit sweep (T051) not yet done — final gate before Phase 3 completion
G7: Context-aware entity disambiguation (e.g., "Baker McKenzie" as law firm vs. person) deferred — future enhancement
G8: Cross-document entity alignment across multi-document reviews deferred — future enhancement
G9: Non-English NER (Arabic, CJK, Cyrillic) deferred — Phase 3 uses regex-only on non-English sections
G10: Arabic language PII patterns explicitly out of scope for this phase
G11: Re-stripping cache invalidation signal (T037) not implemented — no downstream cache to invalidate yet
G12: `privacy.strip_pii` config field and `privacy.tier` reference Phase 1 config schema — documented dependency
════════════════════════════════════════════
