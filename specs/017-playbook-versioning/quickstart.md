# Quickstart: Playbook Versioning Validation

**Phase**: 1 — Quickstart Guide
**Date**: 2026-07-03

## Prerequisites

- Python 3.12 environment with `uv`
- Working `openreview` CLI (`uv run openreview --help` succeeds)
- Empty SQLite database (fresh state) — or a test database at `~/.local/share/openreview/openreview.db`
- Bundled playbook: `src/openreview_cli/review/playbooks/precheck-nda-v1.yaml` — exists and has `version: "1.0.0"`
- Test fixtures directory: `tests/fixtures/`

## Setup

```bash
# From repo root
uv sync
```

## Validation Scenarios

### Scenario 1: First Review Creates Playbook Version Record

**Goal**: Verify that the first review invocation creates a `playbook_version` row in SQLite.

```bash
# Run a review with the bundled PreCheck playbook
uv run openreview precheck review tests/fixtures/sample-nda.docx

# Query the database to confirm a playbook_version row exists
sqlite3 ~/.local/share/openreview/openreview.db \
  "SELECT id, version, content_hash, category_count FROM playbook_version;"
```

**Expected outcome**:
- One row returned: `precheck-nda-v1 | 1.0.0 | <sha256> | <N>`
- `playbook_id` in JSON output: `"precheck-nda-v1@1.0.0"`

**Edge case**: First run with empty DB also creates a `playbook` metadata row. Verify:
```bash
sqlite3 ~/.local/share/openreview/openreview.db \
  "SELECT id, mode, description FROM playbook;"
```

### Scenario 2: Same Playbook Reuses Existing Version

**Goal**: Verify that loading the same playbook YAML (same content, same version) does not create a duplicate row.

```bash
# Run review again with the same playbook
uv run openreview precheck review tests/fixtures/sample-nda.docx

# Verify only one row
sqlite3 ~/.local/share/openreview/openreview.db \
  "SELECT COUNT(*) FROM playbook_version WHERE id='precheck-nda-v1';"
```

**Expected outcome**: `COUNT(*)` is still `1` — no duplicate.

### Scenario 3: Custom Playbook Without Version Gets `0.1.0`

**Goal**: Verify that a playbook YAML without `metadata.version` auto-assigns `"0.1.0"` and emits a warning.

Create a test playbook at `tests/fixtures/custom-no-version.yaml`:
```yaml
id: "test-custom"
mode: "precheck"
metadata:
  description: "Test playbook without version"
  author: "test@example.com"
categories: []
```

```bash
uv run openreview precheck review tests/fixtures/sample-nda.docx \
  --playbook tests/fixtures/custom-no-version.yaml 2>&1
```

**Expected outcome**:
- Stderr contains: `Warning: Playbook "test-custom" has no version — assigned 0.1.0`
- SQLite contains: `test-custom | 0.1.0 | <sha256> | 0`

### Scenario 4: Content Change Without Version Bump

**Goal**: Verify that modifying a playbook YAML without changing the version string creates a `+N` suffixed record.

```bash
# Copy the playbook and modify it
cp src/openreview_cli/review/playbooks/precheck-nda-v1.yaml /tmp/modified-nda.yaml

# Edit a description (e.g., change an exemplar) — keep version as "1.0.0"
# Then run review with the modified playbook
uv run openreview precheck review tests/fixtures/sample-nda.docx \
  --playbook /tmp/modified-nda.yaml 2>&1
```

**Expected outcome**:
- Stderr contains: `Warning: Playbook "precheck-nda-v1" content changed but version "1.0.0" unchanged — storing as 1.0.0+1`
- SQLite contains two rows for `precheck-nda-v1`: one with `1.0.0` and one with `1.0.0+1`
- Both rows have different `content_hash` values

### Scenario 5: `--playbook-version` Pin Reuses Stored Version

**Goal**: Verify that `--playbook-version` reuses a previously stored version.

```bash
# Run with a stored version pin (after Scenario 1 has been run)
uv run openreview precheck review tests/fixtures/sample-nda.docx \
  --playbook src/openreview_cli/review/playbooks/precheck-nda-v1.yaml \
  --playbook-version 1.0.0
```

**Expected outcome**:
- No new `playbook_version` row created
- `playbook_id` in output: `"precheck-nda-v1@1.0.0"`

### Scenario 6: `--playbook-version` Mismatch Error

**Goal**: Verify that mismatched version produces a clear error.

```bash
# Request a version that doesn't exist
uv run openreview precheck review tests/fixtures/sample-nda.docx \
  --playbook src/openreview_cli/review/playbooks/precheck-nda-v1.yaml \
  --playbook-version 99.99.99 2>&1
```

**Expected outcome**:
- Error message: `Error: Requested version 99.99.99 does not match playbook "precheck-nda-v1" version 1.0.0`
- Exit code: non-zero

### Scenario 7: Three Modes Store Independently

**Goal**: Verify that each product mode's bundled playbook stores independently.

```bash
# Run reviews in all three modes
uv run openreview precheck review tests/fixtures/sample-nda.docx
uv run openreview dealcheck review tests/fixtures/sample-nda.docx
uv run openreview hirecheck review tests/fixtures/sample-nda.docx

# Verify three playbook records exist
sqlite3 ~/.local/share/openreview/openreview.db \
  "SELECT id, mode FROM playbook;"
```

**Expected outcome**:
- Three rows in `playbook` table: one for each mode
- Each row has a different `id` and `mode`
- Three or more rows in `playbook_version` (some playbooks may have multiple versions from earlier scenarios)

### Scenario 8: Old Naming Loads Without Error

**Goal**: Verify that the existing `precheck-nda-v1.yaml` (uses `favorable`/`neutral`/`unfavorable`) loads without modification.

```bash
# The bundled playbook uses old naming — this must work
uv run openreview precheck review tests/fixtures/sample-nda.docx

# Inspect the position mapping internally
# (Can verify by checking that categories load with the expected number of exemplars)
```

**Expected outcome**: No errors. Categories load successfully with mapped position names.

### Scenario 9: Version-less Auto-Assignment Is Deterministic

**Goal**: Verify that loading the same version-less playbook twice assigns the same `0.1.0` and only stores one row.

```bash
# Using the custom playbook from Scenario 3
uv run openreview precheck review tests/fixtures/sample-nda.docx \
  --playbook tests/fixtures/custom-no-version.yaml 2>&1

uv run openreview precheck review tests/fixtures/sample-nda.docx \
  --playbook tests/fixtures/custom-no-version.yaml 2>&1

sqlite3 ~/.local/share/openreview/openreview.db \
  "SELECT COUNT(*) FROM playbook_version WHERE id='test-custom';"
```

**Expected outcome**: Warning appears twice (once per invocation) but `COUNT(*)` is `1` — no duplicate row.

### Scenario 10: `--playbook-version` Without `--playbook` Errors

**Goal**: Verify that standalone `--playbook-version` produces an error.

```bash
uv run openreview precheck review tests/fixtures/sample-nda.docx \
  --playbook-version 1.0.0 2>&1
```

**Expected outcome**:
- Error: `--playbook-version requires --playbook <path>`
- Exit code: non-zero

## Running the Validation Suite

The above scenarios can be scripted:

```bash
# Run all unit tests for playbook versioning
uv run pytest tests/unit/test_playbook.py -v

# Run integration tests for the full CLI flow
uv run pytest tests/integration/test_playbook_versioning.py -v

# Run all tests (unit + integration)
uv run pytest -v
```

## Expected Database State After Full Validation

```text
playbook table:
  precheck-nda-v1 | precheck | <description> | <author>
  dealcheck-nda-v1 | dealcheck | <description> | <author>
  hirecheck-terms-v1 | hirecheck | <description> | <author>
  test-custom | precheck | Test playbook without version | test@example.com

playbook_version table:
  precheck-nda-v1 | 1.0.0   | <hash1> | <content> | <timestamp> | <N>
  precheck-nda-v1 | 1.0.0+1 | <hash2> | <content> | <timestamp> | <N>   (from Scenario 4)
  dealcheck-nda-v1 | 1.0.0   | <hash3> | <content> | <timestamp> | <N>
  hirecheck-terms-v1 | 1.0.0 | <hash4> | <content> | <timestamp> | <N>
  test-custom | 0.1.0   | <hash5> | <content> | <timestamp> | 0
```

## Citations

All scenarios map to spec §2 scenarios and acceptance criteria:
- Scenario 1 ↔ §2 Scenario 1 (First Review with Bundled Playbook)
- Scenario 2 ↔ §2 Scenario 1 Acceptance 2 (duplicate prevention)
- Scenario 3 ↔ §2 Scenario 2 (Custom Playbook Auto-Versioning)
- Scenario 4 ↔ §2 Scenario 3 (Playbook Updated Between Reviews)
- Scenario 5 ↔ §2 Scenario 5 Acceptance 1 (version pin reuse)
- Scenario 6 ↔ §2 Scenario 5 Acceptance 2 (version mismatch)
- Scenario 7 ↔ §2 Scenario 4 (Three Modes)
- Scenario 8 ↔ FR-8 (Backward Compatibility)
- Scenario 9 ↔ §2 Scenario 2 Acceptance 2 (deterministic auto-assign)
- Scenario 10 ↔ FR-7 (--playbook-version requires --playbook)
