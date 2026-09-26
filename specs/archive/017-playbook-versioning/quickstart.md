# Quickstart: NX-3 Validation Scenarios

Run these scenarios to prove NX-3 works end-to-end. Each scenario assumes a clean test database.

## Prerequisites

```bash
# From repo root, after NX-3 implementation
uv sync
# Set up a test database (implementations should provide --db-path for testing or use a temp database)
```

## Scenario 1: Import a YAML Playbook (SC-001)

```bash
# 1. Import the bundled playbook
openreview playbook import src/openreview_cli/review/playbooks/precheck-nda-v1.yaml
# Expected: "Imported playbook 'precheck-nda-v1' as version 1."

# 2. List playbooks
openreview playbook list
# Expected:
# ID                Description           Latest Version   Imported
# ────────────────────────────────────────────────────────────────────
# precheck-nda-v1   PreCheck NDA v1                      1   2026-07-03

# 3. Show the imported version
openreview playbook show precheck-nda-v1 1
# Expected: Full playbook content displayed, with renamed positions (preferred/acceptable/walkaway)
```

## Scenario 2: Version Increment (SC-002)

```bash
# 1. Import the same playbook again
openreview playbook import src/openreview_cli/review/playbooks/precheck-nda-v1.yaml
# Expected: "Imported playbook 'precheck-nda-v1' as version 2 (previous version: 1)."

# 2. Show both versions — they should both be valid
openreview playbook show precheck-nda-v1 1
openreview playbook show precheck-nda-v1 2
# Expected: Both display valid content. Content is identical for the same YAML imported twice.

# 3. List shows latest version
openreview playbook list
# Expected: Latest version column shows 2 for precheck-nda-v1
```

## Scenario 3: Error Handling (SC-008)

```bash
# 1. Import nonexistent file
openreview playbook import /nonexistent/playbook.yaml
# Expected: Error: File not found: /nonexistent/playbook.yaml

# 2. Show nonexistent playbook
openreview playbook show nonexistent 1
# Expected: Error: Playbook 'nonexistent' not found.

# 3. Show nonexistent version
openreview playbook show precheck-nda-v1 99
# Expected: Error: Version 99 not found for playbook 'precheck-nda-v1'.

# 4. Empty database list
# (start with a fresh database)
openreview playbook list
# Expected: No playbooks saved yet.
```

## Scenario 4: Review with Database Playbook (SC-003)

```bash
# 1. Import a playbook
openreview playbook import src/openreview_cli/review/playbooks/precheck-nda-v1.yaml

# 2. Run a review with --playbook
openreview precheck tests/fixtures/sample-nda.pdf --playbook precheck-nda-v1
# Expected: Review completes. Output contains playbook_id and playbook_version in metadata.
```

## Scenario 5: Version Stamp Correctness (SC-004)

```bash
# 1. Import playbook (version 1), run review
openreview playbook import src/openreview_cli/review/playbooks/precheck-nda-v1.yaml
openreview precheck tests/fixtures/sample-nda.pdf --playbook precheck-nda-v1
# Verify: playbook_version = 1 in output

# 2. Import again (version 2), re-run review
openreview playbook import src/openreview_cli/review/playbooks/precheck-nda-v1.yaml
openreview precheck tests/fixtures/sample-nda.pdf --playbook precheck-nda-v1
# Verify: playbook_version = 2 in output
```

## Scenario 6: Legacy YAML Backward Compatibility (SC-006)

```bash
# 1. Create a test playbook with legacy keys
cat > /tmp/legacy-playbook.yaml << 'EOF'
id: legacy-test
mode: precheck
metadata:
  version: "1.0"
  description: Legacy key test
  author: Test
categories:
  - id: test-cat
    name: Test Category
    description: A test category with legacy keys
    favorable:
      description: Favorable outcome
      exemplars: ["Example 1"]
    neutral:
      description: Neutral outcome
      exemplars: ["Example 2"]
    unfavorable:
      description: Unfavorable outcome
      exemplars: ["Example 3"]
    default_position: favorable
EOF

# 2. Import via --playbook-path (file-based loading, unchanged)
openreview precheck tests/fixtures/sample-nda.pdf --playbook-path /tmp/legacy-playbook.yaml
# Expected: Deprecation warning about legacy keys, review completes normally
```

## Scenario 7: --playbook and --playbook-path Precedence

```bash
# Import a playbook to the database first
openreview playbook import src/openreview_cli/review/playbooks/precheck-nda-v1.yaml

# Run with both flags
openreview precheck tests/fixtures/sample-nda.pdf \
  --playbook precheck-nda-v1 \
  --playbook-path /tmp/legacy-playbook.yaml
# Expected: Warning printed: "Both --playbook and --playbook-path provided.
#            Using database playbook 'precheck-nda-v1'."

# Run with --playbook-path only (unchanged)
openreview precheck tests/fixtures/sample-nda.pdf --playbook-path /tmp/legacy-playbook.yaml
# Expected: File-based playbook loaded, no database interaction, version_stamp absent
```

## Automated Test Checklist

These should pass after implementation:

```bash
# Unit tests
uv run pytest tests/unit/test_playbook_versioning.py -v
uv run pytest tests/unit/test_position_rename.py -v

# Integration tests
uv run pytest tests/integration/test_playbook_commands.py -v

# Existing tests (no regression)
uv run pytest tests/unit/ -q
uv run pytest tests/integration/ -q

# Full pre-commit suite
uv run pre-commit run --all-files
```
