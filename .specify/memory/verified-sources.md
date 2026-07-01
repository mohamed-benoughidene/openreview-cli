# Verified Sources

**Generated**: 2026-07-01 | **Phase**: speckit.research-grounding | **Feature**: 007-chunking-strategy

## Dependencies

### Python 3.12
- SOURCE: Runtime `python3 --version`
- VERSION: 3.12.3
- KEY FACTS:
  - `@dataclass(slots=True)` available since 3.10
  - `collections.abc.Iterator` available in stdlib
  - `re`, `itertools`, `typing` all stdlib
  - `pathlib` stdlib
- STATUS: CONFIRMED

### pytest
- SOURCE: `uv pip freeze`
- VERSION: 9.1.1
- KEY FACTS:
  - `pytest -k "chunking"` filters by test name
  - No special config needed for chunking tests — existing `pyproject.toml` covers
- STATUS: CONFIRMED

### Rich
- SOURCE: `uv pip freeze` + `python3 -c "import rich"`
- VERSION: 15.0.0
- KEY FACTS:
  - `rich.progress.Progress` for progress indicators
  - `rich.console.Console` for formatted output
  - Already installed in project as existing dependency
- STATUS: CONFIRMED

### Click / Typer
- SOURCE: `uv pip freeze`
- VERSION: Click 8.4.2 (Typer depends on Click)
- KEY FACTS:
  - Typer CLI framework used for all commands
  - Existing `app.py` uses Typer pattern
- STATUS: CONFIRMED

### PyYAML
- SOURCE: `uv pip freeze`
- VERSION: 6.0.3
- KEY FACTS:
  - `yaml.safe_load()` for config.yml parsing
  - Existing config infrastructure already uses PyYAML
- STATUS: CONFIRMED

### Existing Project Modules
- SOURCE: `uv run python3 -c "import openreview_cli.parsing.models; import openreview_cli.parsing.stream; import openreview_cli.config"`
- KEY FACTS:
  - `openreview_cli.parsing.models.Clause` — dataclass with fields: id, text, title, level, parent_id, article_number
  - `openreview_cli.parsing.stream.stream_clauses(path) -> Iterator[Clause]` — streaming clause parser
  - `openreview_cli.config` — config.yml loader with per-mode support
- STATUS: CONFIRMED

## Behavioral Claims

### RCTS Algorithm
- SOURCE: Spec.md FR-002, Research.md "RCTS Algorithm" section
- CLAIM: Recursive Character Text Splitting with clause-boundary awareness
- CLAIM: Split on `["\n\n", "\n", " ", ""]` at token boundaries
- CLAIM: Implement from scratch (no LangChain dependency)
- STATUS: CONFIRMED — pure Python, stdlib only, no external dependency

### Tokenization
- SOURCE: Spec.md FR-007, Research.md "Token Counting" section
- CLAIM: Whitespace + punctuation splitter (±5% vs GPT tokenizer)
- CLAIM: No tiktoken dependency
- STATUS: CONFIRMED — stdlib `re.split(r'\b|(?=[.,;!?])')` or similar

### Memory Strategy
- SOURCE: Spec.md FR-009, Research.md "Memory Strategy" section
- CLAIM: Streaming generator — one chunk at a time, never accumulate
- CLAIM: Peak memory for chunking logic <10 MB
- STATUS: CONFIRMED — Constitution III mandates <100 MB total, chunking gets <10 MB

### Hierarchical Chunking
- SOURCE: Spec.md FR-006, Research.md "Hierarchical Chunking" section
- CLAIM: parent_chunk_id references (no summary chunks)
- CLAIM: structural_location metadata per chunk
- CLAIM: 5× Recall@1 improvement per P-13 (PAKTON)
- STATUS: CONFIRMED — PAKTON approach validated in research

### Configuration
- SOURCE: Spec.md FR-013, Research.md "Configuration" section
- CLAIM: config.yml with per-mode overrides
- CLAIM: Default chunk_size=512, chunk_overlap=50
- STATUS: CONFIRMED — config.yml infrastructure exists in project

## Items with No External Dependency

The following requirements have zero external dependency impact — pure Python or existing project code:

| Item | Location | Implementation |
|------|----------|----------------|
| Chunk dataclass | data-model.md | `@dataclass(slots=True)` — stdlib |
| ChunkConfig dataclass | data-model.md | `@dataclass` — stdlib |
| Tokenizer | FR-007 | `re` module — stdlib |
| Empty clause skip | FR-016 | `if not clause.text.strip(): continue` |
| Config validation | FR-014 | `if config.overlap >= config.size: raise ValueError` |
| Short clause grouping | FR-015 | Simple accumulation logic |
| Ctrl+C handling | FR-017 | `except KeyboardInterrupt` |
| Progress indicator | FR-018 | `rich.progress.Progress` — already installed |
| Memory-efficient data class | FR-020 | `@dataclass(slots=True)` — stdlib |
| Table detection | FR-021 | Regex on line patterns — `re` module |
