# NX-3 Implementation Checklist

Use this checklist to track completion of each implementation task.

## Position Rename (FR-007, FR-008)

- [ ] Rename `Position` enum values in `src/openreview_cli/review/models.py`
  - [ ] `favorable` → `preferred`
  - [ ] `neutral` → `acceptable`
  - [ ] `unfavorable` → `walkaway`
  - [ ] `uncertain` (unchanged — verify)
- [ ] Rename `Category` dataclass attributes: `favorable`→`preferred`, `neutral`→`acceptable`, `unfavorable`→`walkaway`
- [ ] Update `colors.py` label strings for renamed positions (colour logic unchanged)
- [ ] Update prompt templates in `prompts.py` — replace `favorable`/`neutral`/`unfavorable` references
- [ ] Update `Playbook` YAML schema in `playbook.py`: expect `preferred`/`acceptable`/`walkaway` keys
- [ ] Add legacy-key aliasing to `load_playbook()` with `DeprecationWarning`
- [ ] Update bundled playbook `precheck-nda-v1.yaml` to use new keys
- [ ] Update `__init__.py` exports if needed
- [ ] **Test**: `tests/unit/test_position_rename.py` — enum values, legacy key mapping, deprecation warning
- [ ] **Test**: Grep sweep — verify no `favorable`/`neutral`/`unfavorable` remain (except legacy compat path)
- [ ] **Test**: All existing unit/integration tests pass (no regression from rename)

## Database Migration (FR-001)

- [ ] Create `src/openreview_cli/storage/migrations/006_playbooks.sql`
  - [ ] `CREATE TABLE playbook_versions`
  - [ ] `CREATE INDEX idx_playbook_versions_lookup`
  - [ ] `PRAGMA user_version = 6`
- [ ] Update `src/openreview_cli/storage/database.py`
  - [ ] Register migration 006
  - [ ] Bump `SCHEMA_VERSION` constant from 5 to 6
- [ ] **Test**: Migration runs without error on existing database
- [ ] **Test**: Re-running migration is idempotent (IF NOT EXISTS)

## Database Operations (shared storage layer)

- [ ] Create storage functions (in `database.py` or new `playbook_storage.py`):
  - [ ] `get_playbook_version(playbook_id: str, version: int) -> Playbook | None`
  - [ ] `get_latest_playbook_version(playbook_id: str) -> tuple[Playbook, int] | None`
  - [ ] `save_playbook_version(playbook: Playbook) -> int` (returns new version number)
  - [ ] `list_playbooks() -> list[VersionedPlaybookSummary]`
- [ ] **Test**: `tests/unit/test_playbook_versioning.py` — CRUD operations on `playbook_versions`

## CLI Commands (FR-002, FR-003, FR-004)

- [ ] Add `playbook` Typer group to `app.py`
- [ ] Implement `playbook import <yaml-path>`:
  - [ ] Validate file exists
  - [ ] Parse YAML via existing `load_playbook()`
  - [ ] Compute next version number
  - [ ] Serialise to JSON and insert into DB
  - [ ] Print confirmation with version info
  - [ ] Error handling for bad YAML, unknown categories, DB errors
- [ ] Implement `playbook list`:
  - [ ] Query latest version per playbook
  - [ ] Display as Rich table (ID, description, latest version, date)
  - [ ] Handle empty database with helpful message
- [ ] Implement `playbook show <id> <version>`:
  - [ ] Validate positive integer version
  - [ ] Query specific version from DB
  - [ ] Display full playbook content (formatted human-readable)
  - [ ] Error handling for missing ID, missing version
- [ ] **Test**: `tests/integration/test_playbook_commands.py` — CLI smoke tests

## --playbook Flag on Review (FR-005, FR-006)

- [ ] Add `--playbook <id>` option to `precheck` command in `app.py`
- [ ] Implement `load_playbook_from_db(playbook_id: str) -> tuple[Playbook, int]` in `playbook.py`
- [ ] Update `ReviewCommand.__init__()` to accept `playbook_id` parameter
- [ ] Precedence logic: `--playbook` > `--playbook-path` > bundled (with warning for both flags)
- [ ] Wire database-sourced playbook into review pipeline
- [ ] Add `playbook_version: int | None` field to `ReviewReport`
- [ ] Stamp `ReviewReport.playbook_id` and `ReviewReport.playbook_version` when DB-sourced
- [ ] Ensure JSON and terminal output both include version stamp
- [ ] **Test**: Review with `--playbook` produces correct version stamp (SC-003, SC-004)
- [ ] **Test**: Both flags provided → DB playbook wins + warning (SC-003)
- [ ] **Test**: Nonexistent `--playbook` ID → clear error (SC-008)
- [ ] **Test**: `--playbook-path` only → `playbook_version` absent/None (SC-007)

## Edge Cases

- [ ] Import same YAML twice → two versions (no dedup)
- [ ] YAML with legacy keys → imports with deprecation warning
- [ ] YAML with unknown categories → validation error, zero rows written
- [ ] Empty database list → "No playbooks saved yet." message
- [ ] Show nonexistent ID → clear error message
- [ ] Show nonexistent version → clear error message
- [ ] Review with `--playbook` pointing to empty DB → clear error message
- [ ] Concurrent imports not tested (single-user CLI — not a concern)

## Quality Gates

- [ ] `uv run ruff check src/ tests/` — no new lint errors
- [ ] `uv run ruff format --check` — no formatting issues
- [ ] `uv run mypy src/ tests/` — no new type errors
- [ ] `uv run pytest tests/unit/ -q` — all unit tests pass
- [ ] `uv run pytest tests/integration/ -q` — all integration tests pass
- [ ] `uv run pre-commit run --all-files` — all hooks pass
- [ ] Grep sweep: verify `favorable` and `unfavorable` only appear in legacy compat path

## Deferred (not in scope)

- [ ] Bilateral comparison playbook support (R-7)
- [ ] Playbook deletion, editing, or rollback (append-only)
- [ ] Semantic version diff tooling
- [ ] Cloud sync or sharing
- [ ] Auto-updating playbooks / AI-suggested changes
- [ ] New product modes (HireCheck, DealCheck, etc.)
- [ ] Position model rebuild (renamed only, not rebuilt)
