# Implementation Plan: NX-3 — 3-Position Playbook with Versioning

**Branch**: `feat/017-playbook-versioning` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-playbook-versioning/spec.md` (292 lines, 9 FRs, 9 SCs, 0 NEEDS CLARIFICATION).

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

NX-3 extends the playbook system (spec 011) with **persistent, versioned playbook storage** in the local SQLite database, renames the position vocabulary from `favorable`/`neutral`/`unfavorable` to `preferred`/`acceptable`/`walkaway`, and stamps every review report with the exact playbook version used (C-23 audit trail). Three new CLI commands (`playbook import`, `playbook list`, `playbook show`) plus one new flag (`--playbook <id>` on the existing `precheck` command). No new dependencies — mirrors the append-only `prompt_versions` pattern (migration 004) using stdlib `sqlite3` and existing `PyYAML`.

## Technical Context

**Language/Version**: Python 3.12 (pinned in `.python-version`, `pyproject.toml`)

**Primary Dependencies**: Typer (CLI), stdlib `sqlite3` (storage), `PyYAML` (playbook YAML parsing). All already in the dependency stack — no new deps introduced.

**Storage**: Local SQLite via stdlib `sqlite3`. New migration `006_playbooks.sql` creates `playbook_versions` table (append-only, primary key on `(playbook_id, version)`). Mirrors existing `prompt_versions` pattern from migration `004_prompts.sql`. Bump `PRAGMA user_version` to 6.

**Testing**: pytest (existing). TDD enforced — write failing test before implementation. Key test files:
- `tests/unit/test_playbook_versioning.py` (new) — unit tests for DB storage, YAML import, versioning logic
- `tests/unit/test_position_rename.py` (new) — enum rename, legacy key aliasing, colour mapping
- `tests/integration/test_playbook_commands.py` (new) — CLI smoke tests for import/list/show/flag
- Existing test files updated for rename surface (grep for `favorable`/`neutral`/`unfavorable`)

**Target Platform**: Linux/macOS CLI (same as project baseline)

**Project Type**: CLI tool (Python package `openreview-cli`)

**Performance Goals**: Negligible — playbook storage is a few KB per version, single-user, no in-memory footprint beyond the one playbook loaded at review time. Well within the <100 MB budget.

**Constraints**:
- Local-only (no server, no cloud sync) — Principle II
- No new dependencies — Principle IV
- TDD required — tests before implementation
- Position rename must maintain backward compat for legacy YAML keys

**Scale/Scope**: Single-user CLI. Playbook count expected in tens (not thousands). Version count per playbook in single digits. No sharding, indexing, or concurrency concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Privacy First** | **N/A** | Playbook storage involves no PII, no network calls, no API keys. Playbooks contain category names and position descriptions — no personal data. The existing PII pipeline in review commands is unaffected. |
| **II. Local-First, CLI-Only** | **Pass** | Playbook storage is local SQLite. All three new commands are CLI-only. No server, daemon, or telemetry introduced. |
| **III. Hardware-Bounded** | **Pass** | Append-only playbook store adds negligible storage (KB per version, not MB). One playbook loaded into memory at review time (~10-50KB). No parsers, no large collections, no hot-path data classes introduced. |
| **IV. Dependency Minimalism** | **Pass** | Zero new dependencies. stdlib `sqlite3` for storage, existing `PyYAML` for YAML. No forbidden deps touched. |
| **V. Spec-Driven, YAGNI** | **Pass** | Spec written and reviewed before implementation. Append-only model is minimal — no edit/delete/version-diff commands. Position rename is a one-time reconciliation with the blueprint, not speculative flexibility. |
| **Constitutional Constraints** | **Pass** | Python 3.12 ✓, uv only ✓, AGPL-3.0 ✓, public surface naming ✓, commit conventions ✓. |

**Status**: ✅ PASS (all principles pass or N/A, zero violations)

## Complexity Tracking

> Not required — zero violations.

## Project Structure

### Documentation (this feature)

```text
specs/017-playbook-versioning/
├── plan.md              # This file
├── spec.md              # Feature specification (input)
├── research.md          # Phase 0 — domain research and technical decisions
├── data-model.md        # Phase 1 — entities, relationships, migration SQL
├── quickstart.md        # Phase 1 — runnable validation scenarios
├── checklists/          # Phase 1 — quality checklists
│   └── implementation-checklist.md
└── contracts/           # Phase 1 — CLI command contracts
    ├── playbook-import.md
    ├── playbook-list.md
    ├── playbook-show.md
    └── playbook-flag.md
```

### Source Code (repository root)

```text
src/openreview_cli/
├── app.py                              # Add `playbook` Typer subcommand group (import/list/show)
├── review/
│   ├── __init__.py                     # Export updates for renamed Position
│   ├── models.py                       # Rename Position enum values + PlaybookMetadata defaults
│   ├── playbook.py                     # Add load_playbook_from_db(), legacy-key aliasing in load_playbook()
│   ├── base.py                         # Wire --playbook flag → DB loader in ReviewCommand
│   └── prompts.py                      # Update prompt templates: replace favorable/neutral/unfavorable
├── storage/
│   ├── database.py                     # Schema version 5→6, register migration 006
│   └── migrations/
│       └── 006_playbooks.sql           # NEW: CREATE TABLE playbook_versions
└── review/colors.py                    # Update labels for renamed positions (logic unchanged)

tests/
├── unit/
│   ├── test_playbook_versioning.py     # NEW: unit tests for DB storage, version increment, YAML import
│   └── test_position_rename.py         # NEW: enum rename, legacy-key backward compat, colour mapping
├── integration/
│   └── test_playbook_commands.py       # NEW: CLI smoke tests for import/list/show + --playbook flag
├── fixtures/
│   └── playbooks/                      # Add test fixtures for legacy-key YAML
└── existing test files                 # Updated for Position rename (grep sweep)
```

**Structure Decision**: Single project (existing package layout). No new modules, no new packages. Extensions are additive to existing `storage/`, `review/` modules. The `playbook` CLI group lives in `app.py` (consistent with existing pattern where `precheck` lives there).

## Phase Breakdown

### Phase 0 — Research
Output: `research.md`
- Confirm domain decisions (BATNA, Fisher & Ury, append-only versioning pattern)
- Verify no NEEDS CLARIFICATION remains (spec states zero)
- Document the mirror pattern from `prompt_versions` (migration 004)
- Document the Position rename mapping and backward-compatible YAML key aliasing strategy

### Phase 1 — Design
Outputs: `data-model.md`, `contracts/*.md`, `quickstart.md`
- Define `VersionedPlaybook` entity: `(playbook_id TEXT, version INTEGER, content TEXT/JSON, created_at TEXT)`
- Write migration 006 SQL (mirroring 004_prompts.sql)
- Define Position enum rename mapping (`favorable→preferred`, `neutral→acceptable`, `unfavorable→walkaway`, `uncertain` unchanged)
- Write CLI contracts for `playbook import`, `playbook list`, `playbook show`, `--playbook` flag
- Write quickstart validation scenarios

### Phase 2 — Tasks (separate command: `/speckit.tasks`)
Output: `tasks.md`
- Break into individual implementation tasks with file paths, test requirements, and dependencies

## Blueprint References

| Ref | Location | Description |
|-----|----------|-------------|
| C-22 | §6, line 214 | 3-position playbook persisted + versioned in local database |
| C-23 | §6, line 215 | Reviews stamped with exact playbook version — audit trail |
| C-27 | §6, line 219 | Three-color output G/A/R — Preferred→Green, Acceptable→Amber, Walkaway→Red |
| R-7 | §8, line 465 | Scope limited to single-party review; bilateral excluded |
| ORPHAN-2 | line 52 | C-23 depends on C-22, linked to NX-3 |
| N-4 | §7, line 423 | Versioned playbook is single-party only |
