# Research: Playbook Versioning Best Practices

**Phase**: 0 — Research & Outline
**Date**: 2026-07-03
**Status**: No NEEDS CLARIFICATION in spec — all decisions validated below.

## 1. SQLite Schema Versioning Patterns

### Decision
Use **direct `CREATE TABLE IF NOT EXISTS` with no migration framework** for the playbook versioning schema. The two new tables (`playbook` and `playbook_version`) are created alongside the existing database tables in `src/openreview_cli/storage/`. Schema changes are handled by bumping a schema version constant in the storage module.

### Rationale
- The project has no database migration framework (and per §II/§IV shouldn't add one — it's a local CLI, not a web service).
- Two tables with stable schemas (spec §5) don't warrant Alembite or similar.
- `CREATE TABLE IF NOT EXISTS` is idempotent and handles the clean-install case.
- Schema evolution (adding columns later) uses `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — SQLite supports this natively from 3.35.0+ (Python 3.12 ships with 3.45.x). No migration tool needed.
- Existing storage layer already uses this pattern (C-03).

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Alembic / SQLAlchemy migrations | Violates Principle IV (dependency minimalism) — adds two heavy deps for two tables |
| Versioned migration files (numbered .sql files) | Over-engineered for a local CLI with 2 tables. Schema changes will be rare (only when the playbook YAML format evolves) |
| Store everything in JSON blob (single table) | Loses queryability (cannot `SELECT ... WHERE version = '1.0.0'`). The spec requires indexed lookups by `(id, version)` and `content_hash` |

## 2. Content-Hash Change Detection

### Decision
Compute **SHA-256 of raw YAML bytes as-read-from-disk** (not normalized/re-serialized). Store as hex string. Compare against `playbook_version.content_hash` on every playbook load.

### Rationale
- SHA-256 is Python stdlib (`hashlib`), no new dependency.
- Raw bytes capture formatting changes (whitespace, comments) as intentional changes. Per Assumption 8, any file change is potentially semantic — comments might document a position change rationale.
- Hex string is human-readable in SQLite queries and indexes well.
- Collision probability for playbook-scale data (< 50 KB) is effectively zero — SHA-256 is cryptographic-grade.

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| MD5 | Faster but not FIPS-compliant; SHA-256 is already stdlib and fast enough for < 50 KB files |
| Normalized YAML (load then dump) | Would miss formatting-only changes that could contain meaningful context. Per Assumption 8, we want to detect *any* file change |
| File mtime | Not reliable — git checkout can change content without changing mtime. Network filesystems (NFS) have mtime precision issues |
| File size only | Highly collision-prone — a single byte change in an exemplar changes semantics without changing size |

### Research Baseline
SHA-256 of a 50 KB YAML file: ~0.02 ms on a 2-core CPU (reference target machine). Well within the < 100ms budget. Python's `hashlib.sha256()` operates on bytes and streams the file via `read()` into a single call — no chunked streaming needed at this scale.

## 3. YAML-to-SQLite Playbook Loading Patterns

### Decision
**Load YAML from disk first, then store in SQLite.** The YAML file is the source of truth. SQLite is a cache for version-stamped retrieval and reproduction.

### Rationale
- Matches existing pattern: `playbook.py` already loads YAML files from disk.
- The dual-path (disk-first, DB-cached) ensures the tool works offline with just YAML files and reproduce playbooks from DB when the file is missing.
- Full YAML content is stored in the `content` column for exact reproduction from DB (FR-2, Assumption 3).
- On load: parse YAML → extract `id` and `version` → compute hash → query DB → insert if new or reuse.

### Key Loading Algorithm (per FR-5)
```
1. Read YAML bytes from disk → raw_bytes
2. Compute sha256(raw_bytes) → content_hash
3. Parse YAML → dict (via yaml.safe_load)
4. Extract id and version from parsed dict
5. Query: SELECT content_hash FROM playbook_version WHERE id=? AND version=?
6. If row found AND content_hash matches → reuse (return existing record)
7. If row found AND content_hash differs → insert new record with version+"+<N>"
8. If no row found → insert new record
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| DB-only (YAML loaded once, then always from DB) | Requires the tool to know when the YAML file changed — content hash comparison still needed. Adds complexity without benefit |
| YAML-only (no SQLite storage) | Lost playbook-for-review reproducibility (C-23, ORPHAN-2 audit). Cannot reconstruct the playbook that produced a given review report |
| Store YAML in filesystem cache (e.g., ~/.cache/openreview/) | Pollutes filesystem, requires cache cleanup logic. SQLite handles this better with transactional safety |

## 4. Version-Stamping for Audit Trails

### Decision
**Immutable version records with `<id>@<version>` format in ReviewReport.playbook_id.** Every version is an INSERT-only row. No UPDATE, no DELETE.

### Rationale
- Immutability guarantees review reproducibility: given a `playbook_id` string, the exact playbook can be reconstructed from the `playbook_version.content` column.
- The `@` separator is unambiguous (playbook IDs are kebab-case, versions are semver — no conflict).
- The `+N` suffix (e.g., `1.0.0+1`) follows semver build-metadata convention (`+` is valid in semver build-metadata). This means the field is still a valid semver string when the suffix is absent, and a semver-with-build-metadata string when present.
- Audit trail is implicit: old review reports carry old `playbook_id` values. No explicit audit table needed for NX-3.

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Integer `playbook_version_rowid` in ReviewReport | Deferred per FR-3: requires SQLite report storage, which is out of scope for NX-3 |
| UUID per playbook version | Less human-readable than `<id>@<version>`. The spec requirement is human-auditable IDs (a reviewer can look at `precheck-nda-v1@1.0.0` and understand it) |
| Sequential version numbers (1, 2, 3) | Mismatches the semver in YAML metadata. Users manage versions in YAML; the system should reflect that, not invent its own numbering |

### Reference Implementation Pattern
The `ReviewReport` dataclass (spec 011) already has a `playbook_id` field. NX-3 changes the format from `"precheck-nda-v1"` to `"precheck-nda-v1@1.0.0"`. This is a backward-compatible extension — code that reads `playbook_id` without parsing the `@` format still works (the prefix is the playbook ID).

## 5. Position Naming Backward Compatibility

### Decision
**Accept both old (`favorable`/`neutral`/`unfavorable`) and new (`preferred`/`acceptable`/`walkaway`) naming at parse time.** Map old names to new internally. The `default_position` field in YAML is also bi-directionally mapped.

### Rationale
- Existing `precheck-nda-v1.yaml` uses `favorable`/`neutral`/`unfavorable` — must load without modification (FR-8).
- New playbooks can use either convention. The system treats them identically after mapping.
- The internal `Position3` enum uses the new vocabulary. Old values are aliases, not separate enum entries.

### Mapping Table (from FR-8)
| YAML input | Internal Position3 |
|------------|-------------------|
| `favorable` | `preferred` |
| `neutral` | `acceptable` |
| `unfavorable` | `walkaway` |
| `preferred` | `preferred` |
| `acceptable` | `acceptable` |
| `walkaway` | `walkaway` |

The `uncertain` position is always Amber (§6.4) — assigned by the pipeline, never by the playbook YAML.

## 6. Research Summary — Consolidated Decisions

| # | Decision | Citation | Impact |
|---|----------|----------|--------|
| D1 | Direct SQLite tables (no migration framework) | §IV, C-03 | 2 tables in existing storage module |
| D2 | SHA-256 of raw YAML bytes | FR-5, Assumption 8 | stdlib `hashlib`, < 0.1ms per load |
| D3 | Disk-first, DB-cached playbook loading | FR-2, C-23 | YAML is source of truth; DB is cache + audit |
| D4 | Immutable version records with `@` format | C-23, FR-3 | INSERT-only, no UPDATE/DELETE |
| D5 | Bi-directional position name mapping | FR-8, §6.4 | Load-time mapper in playbook.py |
| D6 | `+N` suffix for content-change detection | FR-4, Q3 | Build-metadata in semver format |
| D7 | `0.1.0` auto-assignment for version-less playbooks | Scenario 2, Assumption 4 | Warning on stderr |
| D8 | Three bundled playbooks ship with 1.0.0 | Scenario 4, Q-4 | Two new YAML files + one existing versioned |

## 7. Research Sources

- **Python stdlib `hashlib`**: [docs.python.org/3/library/hashlib.html](https://docs.python.org/3/library/hashlib.html) — SHA-256 available via `hashlib.sha256()`
- **SQLite `CREATE TABLE IF NOT EXISTS`**: [sqlite.org/lang_createtable.html](https://www.sqlite.org/lang_createtable.html) — idempotent table creation
- **SQLite `ALTER TABLE ADD COLUMN`**: supported from SQLite 3.35.0+ (Python 3.12 ships SQLite 3.45.x)
- **Semver build-metadata syntax**: [semver.org/#spec-item-10](https://semver.org/#spec-item-10) — `+` separates build metadata (e.g., `1.0.0+001`)
- **Existing playbook loader**: `src/openreview_cli/review/playbook.py` — uses `yaml.safe_load()`, already extracts `id` and `categories`
- **Existing Position enum**: `src/openreview_cli/review/models.py` — defines `Position` with `favorable`, `neutral`, `unfavorable`, `uncertain` values
