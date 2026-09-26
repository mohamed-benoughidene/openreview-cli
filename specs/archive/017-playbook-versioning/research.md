# Phase 0 — Research: 3-Position Playbook with Versioning

## 1. Technical Decisions (all resolved in Checkpoint 1 — no NEEDS CLARIFICATION)

### Decision 1: Append-only versioning mirrors the `prompt_versions` pattern

**Context**: The existing `prompt_versions` table (migration `004_prompts.sql`) stores prompt content as an immutable, versioned log. Each row is a complete snapshot identified by `(name, version)`. New imports insert new rows; old rows are never modified.

**Decision**: Mirror this exact pattern for playbook storage. Create a `playbook_versions` table with:
- `playbook_id TEXT NOT NULL` (from YAML `id` field)
- `version INTEGER NOT NULL` (auto-incremented per playbook_id)
- `content TEXT NOT NULL` (JSON-serialized Playbook object)
- `created_at TEXT NOT NULL DEFAULT (datetime('now'))`
- Primary key: `(playbook_id, version)`

**Rationale**: The prompt_versions pattern is proven, tested, and already integrated into the database migration runner. Reusing it avoids design churn and keeps the storage layer uniform. No need for a separate session or audit framework — append-only is the audit.

**Verification**: Existing `test_storage.py` tests for prompt_versions provide the template for `test_playbook_versioning.py`.

### Decision 2: Position rename mapping

**Context**: The Position enum currently has four values: `favorable`, `neutral`, `unfavorable`, `uncertain`. The blueprint (C-22) specifies `preferred`, `acceptable`, `walkaway`, `uncertain`. The YAML schema uses `favorable`/`neutral`/`unfavorable` as section keys.

**Decision**:
- Rename Python enum values: `favorable→preferred`, `neutral→acceptable`, `unfavorable→walkaway`, `uncertain` unchanged.
- YAML loader (`load_playbook()`) accepts both legacy keys (`favorable`/`neutral`/`unfavorable`) and new keys (`preferred`/`acceptable`/`walkaway`). Legacy keys are mapped with a deprecation warning via `warnings.warn()`.
- The `default_position` field in the YAML schema also maps through this mechanism.
- Colour mapping (C-27): the existing `colors.py` maps each position to a colour. Only the label strings change — the colour logic remains identical.

**Backward compatibility**: Existing YAML playbooks on disk remain loadable. The deprecation warning uses Python stdlib `warnings` module (category `DeprecationWarning`), which is visible in CLI output and test fixtures.

**Verification**: SC-006 (legacy YAML loads with deprecation warning), SC-005 (grep-clean source tree).

### Decision 3: Review-report version stamp

**Context**: The `ReviewReport` model already has `schema_version: str = "1.1.0"`, `playbook_id: str`, and `generated_at: datetime`. The database schema has a `playbook_version INTEGER DEFAULT 0` column in the `reviews` table (migration 001).

**Decision**:
- `ReviewReport.playbook_id` is set to the playbook ID (from YAML `id` field or DB record).
- `ReviewReport` gains a `playbook_version: int | None = None` field. When the playbook is loaded from the database, this is set to the actual version number. When loaded from a file, it remains `None` (or absent).
- The terminal output and JSON serialisation both surface this field.
- The existing `reviews` table column `playbook_version` is wired to this value.

**Rationale**: The field already exists in the DB schema at migration 001 but is hard-coded to 0. NX-3 populates it with the real version number. This satisfies C-23 audit trail without a schema change to the reviews table.

### Decision 4: CLI command structure

**Decision**: Add a `playbook` Typer subcommand group with three commands:
- `import` — accepts a YAML path, validates, stores to DB
- `list` — shows all playbooks with latest version
- `show` — accepts `<id> <version>`, shows full content

Add `--playbook <id>` flag to the existing `precheck` command. `--playbook-path` remains functional.

**Rationale**: Typer supports nested subcommand groups natively via the `@app.callback()` decorator on a separate function decorated with `@app.group()`. The existing pattern in `app.py` can be extended or a new `playbook_group` can be added.

### Decision 5: No new dependencies

**Statement**: Zero new runtime or dev dependencies. `sqlite3` is stdlib. `PyYAML` is already in `pyproject.toml`. `json` is stdlib. `datetime` is stdlib. `warnings` is stdlib.

**Verification**: SC-006 and SC-007 confirm no regression.

## 2. Domain Research

### Position rename: Preferred/Acceptable/Walkaway

The three-position vocabulary comes from the negotiation theory framework established by Fisher & Ury in "Getting to Yes" (1981). In that framework:
- **Preferred (Best Alternative to a Negotiated Agreement / BATNA)**: The clause as written delivers the user's ideal outcome. No changes needed.
- **Acceptable (Reservation Price / ZOPA boundary)**: The clause is livable — not ideal but acceptable with minor or no concessions. The user can sign without material harm.
- **Walkaway (Dealbreaker / Red Line)**: The clause as written is unacceptable. If the counterparty insists, the user must exit the deal.

This vocabulary is standard across the contract analysis industry (contractken.com, vallor.ai, pon.harvard.edu) and is the vocabulary used in the blueprint.

### Append-only versioning principle

Append-only storage is a well-established pattern for audit trails and versioned data stores. Each write creates a new immutable row. The existing `prompt_versions` table in this codebase uses exactly this pattern. SQLite handles this efficiently — the primary key index on `(playbook_id, version)` ensures fast lookups for the latest version (`SELECT MAX(version) ...`), and the append-only design avoids write locks for single-user workloads.

### Walkaway false-negative risk

The highest-stakes failure mode in playbook-driven review is a walkaway false negative — the model predicts `acceptable` or `preferred` when the true position is `walkaway`. This is addressed by the existing QA agent (spec 011), which re-verifies low-confidence assessments. NX-3 does not change the confidence or QA logic — it only renames the positions. The QA agent continues to catch false negatives via its disagreement-detection prompt.

## 3. Pre-existing patterns referenced

| Pattern | Location | Used for |
|---------|----------|----------|
| `prompt_versions` table | `src/openreview_cli/storage/migrations/004_prompts.sql` | Template for `playbook_versions` table |
| Migration runner | `src/openreview_cli/storage/database.py` | Register migration 006, bump user_version to 6 |
| `load_playbook()` | `src/openreview_cli/review/playbook.py` | Extend with legacy key aliasing + DB loader |
| `ReviewReport` | `src/openreview_cli/review/models.py` | Add `playbook_version` field |
| `Position` enum | `src/openreview_cli/review/models.py` | Rename values |
| `colors.py` | `src/openreview_cli/colors.py` | Update label strings |
| `app.py` precheck command | `src/openreview_cli/app.py` | Add `--playbook` flag |
| Reviews table | `src/openreview_cli/storage/migrations/001_initial.sql` | Wire existing `playbook_version` column |

## 4. Verified sources

All technical claims in this document reference CONFIRMED items from the existing codebase (verified in `.specify/memory/verified-sources.md` per the Constitutional Research Grounding Rule). No UNVERIFIED claims present.
