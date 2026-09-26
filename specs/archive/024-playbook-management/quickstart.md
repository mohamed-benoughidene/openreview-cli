# Quickstart: Playbook Management Validation

**Feature**: 024-playbook-management | **Use**: Run these scenarios after implementation to validate correctness.

See [contracts/cli-commands.md](contracts/cli-commands.md) for full CLI reference and [contracts/storage-api.md](contracts/storage-api.md) for storage API contracts.

---

## Prerequisites

- Project cloned, `uv sync` complete
- Existing test fixtures playbook YAML at `tests/fixtures/precheck-nda-v1.yaml`
- Playbook already imported (run `uv run openreview playbook import tests/fixtures/precheck-nda-v1.yaml`)

---

## Scenario 1: Playbook Export (P1)

### Setup
```bash
# Import 3 versions to ensure version selection works
uv run openreview playbook import tests/fixtures/precheck-nda-v1.yaml
uv run openreview playbook import tests/fixtures/precheck-nda-v1.yaml
uv run openreview playbook import tests/fixtures/precheck-nda-v1.yaml
```

### Test: Export latest (no version flag)
```bash
uv run openreview playbook export precheck-nda-v1 --output /tmp/export-latest.yaml
```
**Expected**: File written, no errors. File parses as valid YAML.

### Test: Export specific version
```bash
uv run openreview playbook export precheck-nda-v1 --version 2 --output /tmp/export-v2.yaml
```
**Expected**: File written with version 2 data (older than latest).

### Test: Round-trip fidelity
```bash
diff <(yq eval -o=j tests/fixtures/precheck-nda-v1.yaml) <(yq eval -o=j /tmp/export-latest.yaml) && echo "IDENTICAL" || echo "DIFFERS"
```
**Expected**: IDENTICAL (modulo YAML normalisation — use `yq` or Python comparison).

### Test: Invalid playbook ID
```bash
uv run openreview playbook export bad-id --output /tmp/out.yaml; echo "Exit: $?"
```
**Expected**: Stderr `"Error: Playbook 'bad-id' not found."`. Exit code 1. No file written.

### Test: Invalid version
```bash
uv run openreview playbook export precheck-nda-v1 --version 99 --output /tmp/out.yaml; echo "Exit: $?"
```
**Expected**: Stderr `"Error: Version 99 not found for playbook 'precheck-nda-v1' (latest: 3)."`. Exit code 1.

---

## Scenario 2: Version Diff (P1)

### Setup
Create two versions with known structural differences:
```bash
# Import baseline, then modify, then import again
uv run openreview playbook import tests/fixtures/precheck-nda-v1.yaml
# (second import with deliberately different content — needs a modified fixture)
```

### Test: Diff with changes
```bash
uv run openreview playbook diff precheck-nda-v1 1 2
```
**Expected**: Terminal output showing category-level and field-level changes between versions.

### Test: Diff equal versions
```bash
uv run openreview playbook diff precheck-nda-v1 1 1
```
**Expected**: Stderr `"No changes between version 1 and version 1."`. Exit code 0.

### Test: Diff normalised order
```bash
uv run openreview playbook diff precheck-nda-v1 3 1
```
**Expected**: Same output as `diff precheck-nda-v1 1 3` (v1 < v2 order normalised internally).

### Test: Diff invalid version
```bash
uv run openreview playbook diff precheck-nda-v1 1 99; echo "Exit: $?"
```
**Expected**: Error message. Exit code 1.

---

## Scenario 3: Set Current Version (P2)

### Test: Set version
```bash
uv run openreview playbook set-current precheck-nda-v1 2
```
**Expected**: `"Set current version of 'precheck-nda-v1' to 2."`

### Test: List reflects change
```bash
uv run openreview playbook list
```
**Expected**: Current column shows version 2.

### Test: Idempotent
```bash
uv run openreview playbook set-current precheck-nda-v1 2
```
**Expected**: `"Version 2 is already the current version of 'precheck-nda-v1'."`

### Test: Invalid version
```bash
uv run openreview playbook set-current precheck-nda-v1 99; echo "Exit: $?"
```
**Expected**: Error. Exit code 1.

---

## Scenario 4: Soft-Delete (P2)

### Test: Delete playbook
```bash
uv run openreview playbook delete precheck-nda-v1
```
**Expected**: `"Deleted playbook 'precheck-nda-v1'."`

### Test: Hidden from list
```bash
uv run openreview playbook list
```
**Expected**: precheck-nda-v1 no longer appears.

### Test: Visible with --include-deleted
```bash
uv run openreview playbook list --include-deleted
```
**Expected**: precheck-nda-v1 appears, marked as deleted.

### Test: Idempotent
```bash
uv run openreview playbook delete precheck-nda-v1
```
**Expected**: `"Playbook 'precheck-nda-v1' is already deleted."`

### Test: Re-activate via set-current
```bash
uv run openreview playbook set-current precheck-nda-v1 3
uv run openreview playbook list
```
**Expected**: precheck-nda-v1 reappears in list (current version 3).

---

## Scenario 5: Version History (P2)

### Test: Full timeline
```bash
uv run openreview playbook history precheck-nda-v1
```
**Expected**: Rich Table with all versions, current marked, latest marked.

### Test: Deleted playbook still shows history
```bash
uv run openreview playbook delete precheck-nda-v1
uv run openreview playbook history precheck-nda-v1
```
**Expected**: Timeline still displayed, marked as deleted.

### Test: Invalid playbook
```bash
uv run openreview playbook history bad-id; echo "Exit: $?"
```
**Expected**: Error. Exit code 1.

---

## Scenario 6: Precedence Warning (P1 — T055/T056)

### Test: Both flags set
```bash
uv run openreview precheck --playbook precheck-nda-v1 --playbook-path /tmp/some.yaml some-doc.pdf 2>&1
```
**Expected**: Stderr contains `"Warning: Both --playbook (precheck-nda-v1) and --playbook-path"`. Command proceeds.

### Test: Only one flag
```bash
uv run openreview precheck --playbook precheck-nda-v1 some-doc.pdf 2>&1
```
**Expected**: No warning about precedence.

---

## Running Tests

### Unit tests
```bash
uv run pytest tests/unit/test_playbook_export.py tests/unit/test_playbook_diff.py tests/unit/test_playbook_set_current.py tests/unit/test_playbook_delete.py tests/unit/test_playbook_history.py tests/unit/test_playbook_precedence.py -v
```
**Expected**: All pass.

### Integration tests
```bash
uv run pytest tests/integration/test_playbook_export.py tests/integration/test_playbook_diff.py tests/integration/test_playbook_management.py -v
```
**Expected**: All pass.

### Full pre-commit
```bash
uv run pre-commit run --all-files
```
**Expected**: All checks pass.
