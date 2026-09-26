# Implementation Plan: Config + Storage Foundation

**Branch**: `001-config-storage-foundation` | **Date**: 2026-06-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-config-storage-foundation/spec.md`

## Summary

Phase 1 delivers the configuration and storage foundation for openreview: a `config.yml` loader with Pydantic v2 validation, `auth.json` handler with secure permissions (chmod 600 on Unix, warning on Windows), SQLite schema for persistent data (clients, reviews, costs, per-review DB), and CLI commands for config management (`show`/`get`/`set`). All built on stdlib + 2 new deps (`PyYAML`, `platformdirs`). No network calls, no AI, no parsing — just the plumbing every later phase needs.

## Technical Context

| Field | Value |
|-------|-------|
| **Language/Version** | Python 3.12 — pinned in `.python-version` |
| **Primary Dependencies** | `PyYAML` (YAML parsing via `yaml.safe_load`), `platformdirs` (cross-platform paths), `pydantic` (config validation, already installed), `typer` (CLI, already installed), `rich` (output, already installed) |
| **Storage** | SQLite via stdlib `sqlite3` — main DB (`openreview.db`) + per-review DB (`reviews/<review_id>/review.db`) |
| **Testing** | `pytest` (unit tests), `mypy --strict` (type checking), `ruff` (linting) |
| **Target Platform** | Linux, macOS, Windows — cross-platform via `platformdirs` |
| **Project Type** | CLI tool — local-only, no server, no daemon |
| **Performance Goals** | Config ops <500ms, DB init <2s on reference hardware (8GB RAM, 2-core CPU), cost logging <100ms per API call |
| **Constraints** | Peak memory <100MB, no network calls in Phase 1, forward-only migrations |
| **Scale/Scope** | Single user, ~50 clients, ~200 reviews/year, ~25MB/year persistent storage |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | ✅ Pass | `auth.json` chmod 600, no secrets in `config.yml`, no network calls, no logging of raw keys |
| **II. Local-First, CLI-Only** | ✅ Pass | No server, no daemon, no telemetry, no long-running process |
| **III. Hardware-Bounded** | ✅ Pass | SQLite for all data (no in-memory dicts for persistent state), lazy imports (platformdirs/pyyaml loaded only when config paths are accessed), stdlib logging |
| **IV. Dependency Minimalism** | ✅ Pass | Only 2 new deps: `PyYAML` (YAML config parsing) and `platformdirs` (cross-platform path resolution). Both are small, mature, and widely used. `pydantic-settings` is NOT added — env var overrides are handled manually to avoid extra dep |
| **V. Spec-Driven, YAGNI** | ✅ Pass | Every feature traces to spec FRs (FR-001 to FR-021). No speculative abstractions — no base class, no factory pattern, no config knob for a value that never changes |

**Gate: PASS** — zero violations. Re-check after Phase 1 design.

## Research Findings

See [research.md](research.md) for the full consolidated research document. Key decisions:

1. **PyYAML**: `yaml.safe_load()` / `yaml.safe_dump()` — never `yaml.load()` (security)
2. **platformdirs**: `user_config_dir("openreview")` + `user_log_dir("openreview")` — auto-creates directories
3. **Pydantic v2**: `BaseModel` for config models — env var overrides handled manually (no `pydantic-settings` dep)
4. **Typer**: `app.add_typer()` for command groups — `config` and `client` subcommand groups
5. **sqlite3**: stdlib module — context manager for transactions, `schema_version` table for migrations
6. **logging**: stdlib `FileHandler` + `StreamHandler` — dual output to file and stderr
7. **os.chmod**: Unix-only — `os.chmod(path, 0o600)`. Windows: warning only, no enforcement

## Project Structure

### Documentation (this feature)

```text
specs/001-config-storage-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 — research decisions
├── data-model.md        # Phase 1 — entity definitions
├── quickstart.md        # Phase 1 — validation guide
├── contracts/           # Phase 1 — interface contracts
│   ├── config-schema.yml
│   ├── auth-schema.json
│   └── sqlite-schema.sql
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── spec.md              # Feature specification
```

### Source Code (repository root)

```text
src/openreview_cli/
├── __init__.py
├── __main__.py
├── _version.py
├── app.py                 # Typer app — registers config/client commands
├── config/
│   ├── __init__.py
│   ├── loader.py          # Config model (Pydantic) + load from YAML
│   ├── auth.py            # Auth JSON handler + permission check
│   └── paths.py           # platformdirs path resolution
├── storage/
│   ├── __init__.py
│   ├── database.py        # SQLite connection + migration runner
│   └── migrations/
│       └── 001_initial.sql
└── errors.py              # Exit-code helpers

tests/
├── unit/
│   ├── test_app.py
│   ├── test_auth.py
│   ├── test_cli_client.py
│   ├── test_cli_config.py
│   ├── test_config_loader.py
│   └── test_database.py
└── conftest.py
```

**Structure Decision**: Single project with `src/` layout (already in place). Two new packages under `src/openreview_cli/`: `config/` (configuration handling) and `storage/` (database operations). Tests mirror the source structure — one test file per module.

## Complexity Tracking

> **No violations** — all constitution principles pass. Complexity tracking is empty.
