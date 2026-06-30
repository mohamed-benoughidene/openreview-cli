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
# Spec Analysis — Part 2 (S-4 through S-6)

Generated 2026-06-28. Extracted from spec directory files in `/specs/004-ai-gateway/`, `/specs/005-cli-wizard-redesign/`, `/specs/006-cli-ux-specification/`.

═══════════════════════════════════════════
SPEC S-4: 004-ai-gateway
───────────────────────────────────────────

FEATURE / DOMAIN
An AI Gateway model routing layer connecting the openreview review engine to AI
providers (cloud and local), with 5 task-specific slots, fallback chains, cost
tracking, interactive setup, and BYOK key management.
___

DEFINED CAPABILITIES
CAP1: Route requests through 5 task-specific slots (reasoning, extraction,
      embedding, reranking, graph) via a single `route_request()` function.
CAP2: Support 8+ providers: OpenAI, Anthropic, Google, Ollama, OpenRouter,
      Cohere, HuggingFace, and Custom (OpenAI-compatible endpoint).
CAP3: Chat completion routing (reasoning, extraction, graph slots).
CAP4: Embedding routing (embedding slot).
CAP5: Reranking routing (reranking slot).
CAP6: Interactive first-time setup wizard (SetupWizard class) walking through
      all 5 slots with provider selection, model selection, API key entry,
      and summary-before-save.
CAP7: Non-interactive setup via command-line flags (--<slot> <provider/model>).
CAP8: Automatic fallback and retry on provider failure (exponential backoff,
      configurable retry count, fallback model per slot, on-failure modes:
      error/skip/warn).
CAP9: Cost tracking per API call (token counts input/output, estimated cost
      USD) aggregated by review session (UUID auto-generated per invocation).
CAP10: Cost limit enforcement (per-review and daily ceilings, pre-call check).
CAP11: CLI management subcommands: status, providers, models, set, test,
       refresh, costs, install-models.
CAP12: YAML configuration import (5-slot-keyed format, all errors reported at
      once, env-var-based API key references only, no inline keys).
CAP13: API key storage in dedicated auth.json with chmod 600, overridable by
      environment variables.
CAP14: Atomic config file writes (temp file → fsync → rename).
CAP15: Local model discovery via Ollama API (`GET /api/tags`).
CAP16: Model registry cache with remote refresh, built-in minimal fallback.
CAP17: Three-tier logging (console INFO, debug file, no body logs unless
      --debug-unsafe).
CAP18: API key redaction in all log output and CLI display.
CAP19: Gateway routing overhead benchmark <50ms per request.
CAP20: Network isolation test (respx mock, all calls to user-configured
      providers only).
CAP21: Slot parameter injection (temperature, max_tokens, dimensions from
      slot config).
CAP22: Response metadata including which model served and whether fallback
      was used.
CAP23: Slots skippable during setup (unconfigured slots raise clear errors
      on use).
CAP24: Provider grouping offer during wizard ("Apply this provider to
      extraction and graph too?").
CAP25: API key validation during setup via `GET /v1/models` or 1-token
      fallback.
CAP26: YAML import validation before write (report-all-errors-at-once).
CAP27: Overwrite confirmation prompt for YAML import.
CAP28: Route-through-flag and env-var API key resolution.
CAP29: Ollama empty-state handling (not running, no models, timeout).
CAP30: Wizard progress indicator ("Step X of 5"), back navigation,
      cancel-with-save.
CAP31: Built-in default config (all slots default to Ollama models).
___

TECH DECISIONS
TD1: LiteLLM as provider abstraction layer for chat completion, embedding,
     and reranking.
TD2: Pydantic v2 for configuration validation (BaseSettings, YamlConfig-
     SettingsSource).
TD3: questionary v2.1.1 for interactive wizard prompts.
TD4: Rich for CLI tables, progress, spinner, summary UI.
TD5: SQLite for cost records and session state (existing storage/ module).
TD6: YAML for config file (~/.config/openreview/config.yml).
TD7: JSON for auth file (~/.config/openreview/auth.json, chmod 600).
TD8: JSON for model registry cache (~/.cache/openreview/model_registry.json).
TD9: Dataclass models for runtime types (SlotConfig, ModelParams, etc.) with
     @dataclass(slots=True).
TD10: Pydantic models for config validation only.
TD11: Atomic file writes (temp → fsync → rename).
TD12: Lazy imports for heavy dependencies (litellm, rich).
TD13: Exceptions use GatewayError dataclass (exit_code, slot, message, action).
TD14: Typer for CLI framework, Typer sub-apps for gateway command group.
TD15: httpx for HTTP requests (Ollama discovery, API key validation).
TD16: Provider model format: `provider/model-id` (e.g. openai/gpt-4o).
TD17: Env var overrides for API keys (OPENAI_API_KEY, etc.) take precedence
     over auth file.
TD18: Config env var overrides use OPENREVIEW_GATEWAY__ prefix (double
     underscore for nesting).
TD19: Reserved exit codes: 0=success, 1=general, 5=config, 6=cost limit,
     7=gateway.
TD20: Wide- (≥80) and narrow- (<80) column terminal adaptation for Rich
     tables.
TD21: Five-slot-keyed YAML import schema with separate api_key_env block.
TD22: Model registry entries include slot_compatibility, context_window,
     ram_required_mb, pricing info.
___

IMPLEMENTATION STATUS
All tasks (T001–T069) marked [X] completed in tasks.md. Phases:
Phase 1 (Setup), Phase 2 (Foundational), Phase 3 (US1 Routing), Phase 4
(US2 Setup Wizard), Phase 5 (US3 Fallback), Phase 6 (US4 Cost Tracking),
Phase 7 (US5 CLI Management), Phase 8 (US6 YAML Import), Phase 9 (Polish)
— all marked complete.

CAP1: BUILT
CAP2: BUILT
CAP3: BUILT
CAP4: BUILT
CAP5: BUILT
CAP6: BUILT
CAP7: BUILT
CAP8: BUILT
CAP9: BUILT
CAP10: BUILT
CAP11: BUILT
CAP12: BUILT
CAP13: BUILT
CAP14: BUILT
CAP15: BUILT
CAP16: BUILT
CAP17: BUILT
CAP18: BUILT
CAP19: BUILT
CAP20: BUILT
CAP21: BUILT
CAP22: BUILT
CAP23: BUILT
CAP24: BUILT
CAP25: BUILT
CAP26: BUILT
CAP27: BUILT
CAP28: BUILT
CAP29: BUILT
CAP30: BUILT
CAP31: BUILT
___

INTERFACES / CONTRACTS
I1: `route_request(slot, messages, input_text, query, documents, session_id,
    **kwargs) -> GatewayResponse` — core routing function.
I2: `SetupWizard.__init__() -> None`, `SetupWizard.run() -> None` — setup
    wizard class.
I3: CLI: `openreview gateway setup [--<slot> <p/m>] [--no-interactive]`
I4: CLI: `openreview gateway status`
I5: CLI: `openreview gateway providers`
I6: CLI: `openreview gateway models <provider>`
I7: CLI: `openreview gateway set <slot> <provider/model> [--fallback]
    [--temperature] [--max-tokens] [--dimensions]`
I8: CLI: `openreview gateway test <slot>`
I9: CLI: `openreview gateway refresh`
I10: CLI: `openreview gateway costs [--session] [--days] [--clear] [--json]`
I11: CLI: `openreview gateway import <file> [--force] [--dry-run]`
I12: CLI: `openreview gateway install-models <model>...`
I13: `GatewayResponse` dataclass — content, input_tokens, output_tokens,
     cost_usd, model, provider, slot, fallback_used, latency_ms, raw_response.
I14: `RerankResult` dataclass — index, score, document.
I15: `GatewayError` exception — exit_code, slot, message, action.
I16: `GatewayEngine` class — internal engine with `route_request()`.
I17: `CostStore` class — SQLite CRUD for cost records and sessions.
I18: `ModelRegistry` class — cache management, remote fetch, built-in
     fallback.
I19: `ImportValidator` class — YAML import parsing, validation, env var
     resolution.
I20: Auth file format: `{"openai": "...", "anthropic": "..."}`
I21: Config file YAML schema: `gateway.models.<slot>.primary/.fallback/.params`
     plus `gateway.fallback`, `gateway.cost_limits`, `gateway.registry`,
     `gateway.logging`.
I22: Import file YAML schema: five top-level slot keys (reasoning, extraction,
     embedding, reranking, graph) + optional `api_key_env` block.
___

DEPENDENCIES
DEP1: LiteLLM (provider abstraction) — new dependency.
DEP2: Pydantic v2 + pydantic-settings (config validation) — already
     permitted in constitution.
DEP3: httpx (HTTP client) — already in deps.
DEP4: Rich (CLI UI) — already in deps.
DEP5: Typer (CLI framework) — already in deps.
DEP6: PyYAML (YAML loading) — already in deps.
DEP7: SQLite (cost/session storage) — stdlib, existing storage/ module.
DEP8: S-2 (Document Parsing) — PII stripping runs before gateway, but
     gateway does not depend on parsing directly.
DEP9: config/loader.py extensions (Pydantic models for gateway section).
DEP10: config/auth.py extensions (get_api_key() function).
DEP11: Ollama (local model server) — external dependency, user-managed.
___

GAPS / TODOS
G1: Spec defers response caching, multi-user API key management, and
    automatic model selection based on contract complexity — explicitly
    out of scope.
G2: Cost estimates based on provider-published pricing tables; actual costs
    may vary.
G3: Provider API version compatibility managed by LiteLLM — the gateway
    delegates this.
G4: Spec notes 3 deferred tasks (T033, T034, T035) blocked by downstream
    infrastructure that does not exist yet (review command, config change
    detection).
G5: The cloud model registry URL in defaults is placeholder
    (`https://example.com/models.json`).
════════════════════════════════════════════

═══════════════════════════════════════════
SPEC S-5: 005-cli-wizard-redesign
───────────────────────────────────────────

FEATURE / DOMAIN
Redesign CLI wizard UX by replacing `rich.prompt.Prompt.ask()` with
`questionary` interactive prompts (arrow-key navigation, checkbox, autocomplete)
across the gateway setup wizard and a new review wizard.
___

DEFINED CAPABILITIES
CAP1: Arrow-key navigable single-select prompts (questionary.select) for all
      wizard choices.
CAP2: Multi-select with space-to-toggle and Enter-to-confirm for selecting
      multiple items (e.g., clauses).
CAP3: Free-text prompt with inline fuzzy filtering (questionary.autocomplete)
      for long lists (e.g., model selection, jurisdiction).
CAP4: Inline input validation feedback on the same prompt screen (red error
      text beneath input).
CAP5: Summary-before-save Rich Table confirmation in gateway setup wizard.
CAP6: Non-interactive terminal detection (piped stdin, `TERM=dumb`,
      `sys.stdin.isatty()`) with graceful fallback to flag-based mode.
CAP7: Ctrl+C graceful exit at any wizard step (questionary returns None,
      clean "Cancelled by user." message).
CAP8: "Back" navigation via a "← Back" choice in select prompts.
CAP9: Pre-flight gateway readiness check for review wizard (≥1 chat model +
      ≥1 embedding configured).
CAP10: New `ReviewWizard` class (separate from `SetupWizard`) that returns a
       `ReviewConfiguration` bundle.
CAP11: New `openreview review <file>` Typer command with 3-step wizard flow
       (mode → jurisdiction/output → confirm) plus clause multi-select for
       clause-by-clause mode.
CAP12: Conditional step branching in review wizard (risk-scan mode skips
       jurisdiction/output/clauses prompts).
CAP13: Instruction hints on all wizard prompts (FR-08).
CAP14: File integrity validation before review wizard starts (readable
       PDF/DOCX).
CAP15: Prompt helper wrappers in `cli/utils.py` (shared between both wizards):
       _select, _checkbox, _autocomplete, _confirm, _text, _password.
CAP16: Review wizard non-interactive mode with --non-interactive, --mode,
       --jurisdiction, --output, --clauses flags.
CAP17: Gateway setup wizard refactored to use questionary internally while
       preserving public API unchanged.
CAP18: API key entry via questionary.password() with inline validation.
___

TECH DECISIONS
TD1: questionary v2.1.1 as the interactive prompt library (arrow-key select,
     checkbox, autocomplete, confirm, text, password).
TD2: Rich for summary tables and styled output (already in deps).
TD3: Typer for CLI framework (already in deps).
TD4: prompt_toolkit (transitive via questionary, BSD-3) for SSH/PTY support.
TD5: Separate `ReviewWizard` and `SetupWizard` classes (different contracts).
TD6: ReviewWizard returns `ReviewConfiguration` dataclass to caller; does not
     call parse or gateway engines.
TD7: Shared prompt helper functions in `cli/utils.py` with consistent styling.
TD8: questionary defaults for styling (ansidark theme, ◉/○ markers, default
     instruction hints).
TD9: Back navigation via "← Back" choice in select prompts (not text-based
     matching).
TD10: Terminal compatibility targets: ANSI-capable terminals; `TERM=dumb`
      falls back to typed choices with monochrome.
TD11: questionary's built-in Ctrl+C handling (`.ask()` returns None safely).
TD12: Jurisdiction codes as a fixed module-level constant list (12 codes for
      MVP).
___

IMPLEMENTATION STATUS
All tasks (T001–T032) marked [X] completed in tasks.md. Phases 1–7 all
complete.

CAP1: BUILT
CAP2: BUILT
CAP3: BUILT
CAP4: BUILT
CAP5: BUILT
CAP6: BUILT
CAP7: BUILT
CAP8: BUILT
CAP9: BUILT
CAP10: BUILT
CAP11: BUILT
CAP12: BUILT
CAP13: BUILT
CAP14: BUILT
CAP15: BUILT
CAP16: BUILT
CAP17: BUILT
CAP18: BUILT
___

INTERFACES / CONTRACTS
I1: `SetupWizard.__init__() -> None`, `SetupWizard.run() -> None` — public
    API unchanged from S-4.
I2: `ReviewWizard.__init__(file_path, non_interactive=False, mode=None,
    jurisdiction=None, output_format=None, clauses=None)`.
I3: `ReviewWizard.run() -> ReviewConfiguration`.
I4: `ReviewConfiguration` dataclass — file_path, mode (ReviewMode enum),
    jurisdiction (str|None), output_format (OutputFormat|None),
    clauses (list[str]|None).
I5: CLI: `openreview review <file> [--non-interactive] [--mode <mode>]
    [--jurisdiction <code>] [--output <format>] [--clauses <ids>]`
I6: CLI: `openreview gateway setup [--non-interactive] [--<slot> <p/m>]...`
    (unchanged from S-4).
I7: `_select()`, `_checkbox()`, `_autocomplete()`, `_confirm()`, `_text()`,
    `_password()` wrappers in `src/openreview_cli/cli/utils.py`.
I8: `_is_interactive()` terminal detection function in `cli/utils.py`.
I9: `ReviewMode` enum: FULL, CLAUSE_BY_CLAUSE, RISK_SCAN.
I10: `OutputFormat` enum: JSON, TEXT, HTML.
I11: Jurisdiction constant list (12 codes: us-de, us-ca, us-ny, us-tx,
     us-il, uk, eu-gdpr, eu-de, eu-fr, ca, au, sg).
___

DEPENDENCIES
DEP1: questionary v2.1.1 — new runtime dependency.
DEP2: Rich (summary tables) — already in deps.
DEP3: Typer (CLI) — already in deps.
DEP4: prompt_toolkit (transitive via questionary) — new transitive dep.
DEP5: S-4 (AI Gateway) — review wizard depends on gateway configuration for
     pre-flight readiness check.
DEP6: Config module (src/openreview_cli/config/) — for reading existing
     gateway config.
DEP7: File system — local PDF/DOCX file for review command.
___

GAPS / TODOS
G1: S-5 spec explicitly says the review engine (Phase 5+) is out of scope —
     the wizard produces a config dict and hands it off.
G2: Persistent wizard state across sessions is out of scope.
G3: Custom keybinding configuration by users is out of scope.
G4: Internationalization / localization is out of scope.
G5: Full TUI application (no Textual app class as main shell) is out of scope.
G6: The spec notes its interaction patterns are superseded by S-6 (006-cli-ux-
     specification) which covers the same domain but with broader UX scope.
G7: Pre-flight check is basic (file validation only); encrypted/damaged file
     detection is marked as partial in T031.
G8: Fuzzy filtering uses questionary.autocomplete (substring match), not true
     fuzzy (typo-tolerant) matching.
════════════════════════════════════════════

═══════════════════════════════════════════
SPEC S-6: 006-cli-ux-specification
───────────────────────────────────────────

FEATURE / DOMAIN
Comprehensive CLI UX layer for openreview-cli: semantic design tokens, a Rich/
questionary component library (11 interactive components), multi-step wizard
state machine, verb-noun command structure, structured error/warning/success
feedback, terminal compatibility detection, and configuration UX.
___

DEFINED CAPABILITIES
CAP1: Semantic color palette (7 roles: primary, success, warning, error,
      muted, accent, code) with NO_COLOR fallbacks and Rich style strings.
CAP2: Icon system with Unicode default and ASCII fallback mapping for all
      9 states (success, error, warning, info, pending, running, step_marker,
      file_path, lock).
CAP3: Spacing rules (1 blank line between paragraphs, 2 between sections,
      etc.).
CAP4: Typography rules (bold for headings, dim for secondary, italic
      sparingly, no underline for non-links).
CAP5: 11 UI components: Selection Menu, Multi-select, Fuzzy Search Select,
      Confirmation Dialog, Text Input with Validation, Spinner, Progress Bar,
      Live Panel, Result Table, Error Panel, Step Indicator.
CAP6: SGRenderer singleton wrapping Rich Console (NO_COLOR, --no-color,
      --no-unicode, terminal width, TTY detection).
CAP7: Three-part error format panel (what failed / why / how to fix) with
      red border, formatting error_panel(), warning_panel(), info_panel(),
      success_panel().
CAP8: Structured exit code map (0=success, 1=general, 2=usage, 3=config,
      4=input file, 5=network, 6=AI error, 7=interrupted, 8=unknown).
CAP9: Wizard state machine (Entry → ModeSelection → Configuration → Confirm
      → Processing → Results) with forward/back/cancel transitions.
CAP10: Keyboard shortcut map (↑↓ Enter Space Esc Ctrl-C / Tab Shift+Tab
       Home/End).
CAP11: Non-interactive mode (all prompts disabled when !isatty, exit code 2
       for missing required flags).
CAP12: --yes flag auto-confirms all prompts with safe defaults.
CAP13: --output flag (table/json/plain) — JSON to stdout, messaging to stderr.
CAP14: Verb-noun command structure (openreview setup, review, config, list,
       version) with --kebab-case flags.
CAP15: Global flags on all subcommands: --verbose, --quiet, --no-color,
       --no-unicode, --no-spinner, --output, --config.
CAP16: First-run detection (no config file) with welcome panel + privacy
       notice + auto-enter setup wizard.
CAP17: Config subcommands (show, get, set, unset, path) with inline
       validation and error panels.
CAP18: Config env var overrides (OPENREVIEW_<KEY>) that override
       config.json values.
CAP19: Config validation on startup (corrupted JSON = exit code 3, unknown
       keys = warning panel, continue).
CAP20: Terminal width adaptation (≥80 full table, 60–79 proportional shrink,
       <60 key-value pairs, <40 warning).
CAP21: Non-TTY component degradation matrix (spinner → label once, progress
       bar → periodic [N/total] text, error panel → plain text, etc.).
CAP22: Streaming AI output via Rich Live panel for token-by-token display.
CAP23: Spinner at 500ms threshold for indeterminate operations.
CAP24: Progress bar for determinate operations with clause-by-clause labeling.
CAP25: Cancel during processing: "Review cancelled. Partial results not saved."
       exit code 7.
CAP26: Background task labeling in plain English ("Analyzing clause 3 of 12
       — Indemnification...").
CAP27: Tab completion via Typer built-in (bash/zsh/fish/powershell).
CAP28: Typo suggestion for commands ("Unknown command 'reviw'. Did you mean
       'review'?").
CAP29: Shell completion auto-install during setup wizard.
CAP30: --quiet flag suppresses all non-error output (spinner remains visible).
CAP31: --no-spinner flag disables all animated output.
CAP32: --verbose flag with PII-redacted detail.
CAP33: Flesch-Kincaid grade level < 10 for all user-facing text.
CAP34: First-render latency <100ms (corrected from spec's 200ms).
___

TECH DECISIONS
TD1: Rich v15.0.0 for all output rendering (Console singleton, Table, Panel,
     Progress, Live, Status, Markdown).
TD2: questionary v2.1.1 for all interactive prompts (select, checkbox,
     confirm, text, password, autocomplete).
TD3: Typer v0.26.8 for CLI framework, command structure, help, exit codes,
     shell completion (vendored Click 8.x).
TD4: shellingham for shell detection during completion install (already
     transitive via Typer).
TD5: SGRenderer singleton wrapping Rich Console in src/openreview_cli/ui/.
TD6: Semantic ColorRole NamedTuple (color, no_color, icon, icon_ascii).
TD7: Design tokens as module-level Python constants in colors.py.
TD8: UI components isolated in src/openreview_cli/ui/components/ sub-package.
TD9: Wizard state machine in src/openreview_cli/ui/components/wizard.py.
TD10: Config file at $XDG_CONFIG_HOME/openreview/config.json (JSON format).
TD11: Auth file at same dir, chmod 600.
TD12: Env var prefix OPENREVIEW_ for config overrides (dots → underscores).
TD13: First-run detection by checking config file existence.
TD14: 3-part error panel format with error_panel() raising SystemExit.
TD15: SGTable wrapping Rich Table with output_format (table/json/plain).
TD16: Non-TTY detection via sys.stdin.isatty() and sys.stdout.isatty().
TD17: Icon maps in console.py: ICONS dict (Unicode), ICONS_ASCII dict,
      get_icon() function.
TD18: Keyboard shortcuts as module-level frozendict in key_bindings.py.
TD19: difflib.get_close_matches() for fuzzy search on lists >8 items.
TD20: Progress update rate capped at 10Hz max.
TD21: Lazy imports for heavy modules behind command callbacks.
TD22: Max clause label length = 60 characters.
TD23: JSON output structure: {"status": "...", "document": {...}, "findings":
      [...], "summary": {...}}.
___

IMPLEMENTATION STATUS
All tasks (T001–T087) marked [X] completed. 8 phases + 1 convergence phase.
Phase 1 Setup, Phase 2 Foundational (33 tasks across 15 components), Phase 3
US1 First-Run, Phase 4 US2 Interactive Review, Phase 5 US3 CI/Automation,
Phase 6 US4 Configuration Management, Phase 7 US5 Help Discoverability,
Phase 8 Polish & Hardening, Phase 9 Convergence (12 gap-closure tasks).

CAP1: BUILT
CAP2: BUILT
CAP3: BUILT
CAP4: BUILT
CAP5: BUILT
CAP6: BUILT
CAP7: BUILT
CAP8: BUILT
CAP9: BUILT
CAP10: BUILT
CAP11: BUILT
CAP12: BUILT
CAP13: BUILT
CAP14: BUILT
CAP15: BUILT
CAP16: BUILT
CAP17: BUILT
CAP18: BUILT
CAP19: BUILT
CAP20: BUILT
CAP21: BUILT
CAP22: BUILT
CAP23: BUILT
CAP24: BUILT
CAP25: BUILT
CAP26: BUILT
CAP27: BUILT
CAP28: BUILT
CAP29: BUILT
CAP30: BUILT
CAP31: BUILT
CAP32: BUILT
CAP33: BUILT
CAP34: BUILT
___

INTERFACES / CONTRACTS
I1: Root: `openreview [--verbose] [--quiet] [--no-color] [--no-unicode]
    [--no-spinner] [--output <fmt>] [--config <path>] [--help] [--version]`
I2: `openreview setup [--no-interactive]`
I3: `openreview review <file> [--mode <mode>] [--output <fmt>]
    [--clauses <list>] [--jurisdiction <code>] [--yes] [--no-pii]`
I4: `openreview config show [--output <fmt>]`
I5: `openreview config get <key>`
I6: `openreview config set <key> <value>`
I7: `openreview config unset <key>`
I8: `openreview config path`
I9: `openreview list providers [--output <fmt>]`
I10: `openreview list models [--output <fmt>]`
I11: `openreview list jurisdictions [--output <fmt>]`
I12: `openreview models list [--output <fmt>]`
I13: `openreview models pull <name>`
I14: `openreview models info <name>`
I15: Exit code constants: SUCCESS=0, GENERAL_ERROR=1, USAGE_ERROR=2,
     CONFIG_ERROR=3, INPUT_ERROR=4, NETWORK_ERROR=5, AI_ERROR=6,
     INTERRUPTED=7, UNKNOWN=8.
I16: SGRenderer class (console.py) — singleton, properties: console,
     is_interactive, supports_unicode, supports_color, get_icon().
I17: WizardState data model (current_step, total_steps, mode, clauses,
     jurisdiction, config_values, validation_errors, allow_back,
     last_transition).
I18: WizardStep protocol: render(), validate(), resolve_next().
I19: 4 panel functions: info_panel(), warning_panel(), error_panel(),
     success_panel().
I20: SGTable class: constructor(title, columns, rows, output_format) →
     render().
I21: Spinner class (context manager): label, spinner type, non-TTY fallback.
I22: Progress class (context manager): total, description, advance(n),
     update(desc), cancel().
I23: Prompt wrappers: select(), checkbox(), fuzzy_select(), confirm(),
     text(), password().
I24: Key bindings constants: KEY_BINDINGS frozendict mapping key →
     (action, description, component).
I25: StatusLine class (context manager): update(message), 60-char truncation.
I26: 3 header functions: separator(), breadcrumb(), step_indicator().
I27: render_markdown(text) → Rich Text (line-by-line parser, no AST).
I28: Validation functions: validate_path(), validate_config_key(),
     validate_range(), validate_not_empty(), validate_enum().
I29: Feedback functions: format_error(what, why, fix, exit_code),
     format_success(message, detail).
I30: DesignToken data model: color_roles, no_color_fallbacks, icon_map,
     ascii_icon_map, spacing, panel_padding, typography, width_thresholds,
     min_supported_width.
I31: ConfigPath data model: config_dir, config_file, auth_file, file_mode,
     env_prefix, exists, first_run.
I32: TerminalCapabilities data model: width, is_tty_stdin, is_tty_stdout,
     supports_color, supports_unicode, detected_shell.
I33: FeedbackPayload data model: what_happened, why, what_to_do, exit_code,
     severity, panel_title.
I34: OutputFormat type: table/json/plain with is_default and
     is_machine_readable booleans.
___

DEPENDENCIES
DEP1: Rich v15.0.0 (already transitive via Typer).
DEP2: questionary v2.1.1 (new dependency).
DEP3: Typer v0.26.8 (already installed).
DEP4: shellingham (already transitive via Typer).
DEP5: Existing config module (src/openreview_cli/config/) for loading/saving
      JSON config.
DEP6: Existing errors.py (extended with exit codes 0–5, 6–8).
DEP7: Existing cli/utils.py (refactored to delegate to ui/components/prompt.py).
DEP8: S-5 (CLI Wizard Redesign) — S-6 supersedes interaction patterns but
      preserves S-5's command structure and configuration logic.
DEP9: S-4 (AI Gateway) — review wizard depends on gateway configuration.
DEP10: S-2/document parsing — review processing uses parsed clauses.
DEP11: textstat (dev dependency only) — for Flesch-Kincaid readability
       validation.
___

GAPS / TODOS
G1: Spec explicitly supersedes S-5's interaction patterns but preserves its
    command structure and config logic.
G2: Section 4 UNVERIFIED items: InquirerPy fuzzy matching (deferred),
    opencode selection menu visual appearance (not replicated), config set
    model validation API (depends on gateway registry), man-page generation
    (deferred).
G3: Spec notes "Web docs and man pages" are deferred open questions.
G4: Full TUI application (Textual) explicitly out of scope.
G5: Internationalization / localization out of scope.
G6: Convergence tasks T076–T087 show gaps closed during implementation:
    some were marked "partial" or "missing" before convergence (global flags,
    setup summary, --no-pii, autocomplete, icon meanings, config set old/new
    value display, --no-spinner, help examples placement, error help suffix,
    zero-clause warning, --mode [required] marking, first-run cancel message).
G7: The spec's original 200ms first-output target was corrected to 100ms
    based on research (clig.dev/Miller 1968).
G8: Spec supersedes existing exit code scheme (5=config, 6=cost, 7=gateway,
    9=PII) with new scheme (0–8 codes).
G9: Config file format changes from YAML (S-4) to JSON (S-6) — this is a
    format divergence between specs.
════════════════════════════════════════════
