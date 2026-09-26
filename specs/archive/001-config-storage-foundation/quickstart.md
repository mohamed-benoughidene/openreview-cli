# Quickstart: Config + Storage Foundation

**Phase**: 1 (Validation Guide)
**Source**: [spec.md](spec.md), [data-model.md](data-model.md), [contracts/](contracts/)

## Prerequisites

- Python 3.12+ installed
- `uv` installed
- Repository cloned and submodules initialized

## Setup

```bash
# From repo root
uv add PyYAML
uv add platformdirs
uv sync
```

## Verification Scenarios

### Scenario 1: First-Time Config Creation

```bash
# Simulate a fresh install by removing config
rm -rf ~/.config/openreview

# Run any command — config should be auto-created
uv run openreview config show
```

**Expected output**: A complete `config.yml` with default values. The output should show:
- `version: 1`
- `privacy.tier: balanced`
- `gateway.models.embedding.primary: ollama/nomic-embed-text`
- `gateway.cost_limits.per_review_cents: 100`

**Files created**:
- `~/.config/openreview/config.yml` (or platform-equivalent)
- `~/.config/openreview/auth.json` (empty, chmod 600 on Unix)

### Scenario 2: Config Get/Set

```bash
# Get a single value
uv run openreview config get privacy.tier
# Output: balanced

# Change a value
uv run openreview config set privacy.tier maximum
# Output: updated ✓

# Verify the change
uv run openreview config get privacy.tier
# Output: maximum

# Verify backup was created
ls ~/.config/openreview/config.yml.bak
# File exists

# Invalid value
uv run openreview config set privacy.tier invalid
# Output: Error with valid options "maximum | balanced | performance"
```

**Validation checks**:
- `config set` rejects invalid enum values
- `config set` rejects negative cost limits
- `config set` creates `config.yml.bak` before writing
- `config get` with unknown key shows clear error

### Scenario 3: Environment Variable Overrides

```bash
# Override via env var
export OPENREVIEW_PRIVACY_TIER=maximum

# Check merged config
uv run openreview config show
# privacy.tier should show "maximum" (env var wins over file)

# Unset and verify fallback
unset OPENREVIEW_PRIVACY_TIER
uv run openreview config show
# privacy.tier should show the file value
```

### Scenario 4: Client Management

```bash
# Add a client
uv run openreview client add acme "Acme Corp"

# List clients
uv run openreview client list
# Should show: acme - Acme Corp

# Try to delete non-existent client
uv run openreview client delete nonexistent
# Output: Error with "not found" message

# Delete client with --force (after creating reviews in Phase 2+)
uv run openreview client delete acme --force
```

### Scenario 5: Cost Logging

```bash
# Simulate API call cost logging (via test)
uv run pytest tests/unit/test_database.py -k test_cost_logging -v

# Verify cost log entries
# sqlite3 ~/.config/openreview/openreview.db "SELECT * FROM cost_logs;"
```

## Expected Test Results

```bash
# Run all Phase 1 unit tests
uv run pytest tests/unit/ -k "test_config or test_auth or test_database or test_cli_config" -v

# Expected: all tests pass
# - test_config_loader.py: 4+ tests (load, get, set, validation)
# - test_auth.py: 3+ tests (load, permissions, env override)
# - test_database.py: 5+ tests (create tables, migrate, CRUD, cost limits)
# - test_cli_config.py: 3+ tests (show, get, set commands)
```

## Contract Compliance

| Contract | File | Validates Against |
|----------|------|-------------------|
| Config schema | [config-schema.yml](contracts/config-schema.yml) | `src/openreview_cli/config/loader.py` |
| Auth schema | [auth-schema.json](contracts/auth-schema.json) | `src/openreview_cli/config/auth.py` |
| SQLite schema | [sqlite-schema.sql](contracts/sqlite-schema.sql) | `src/openreview_cli/storage/database.py` |

## Memory Budget Verification

```bash
uv run pytest -m memory -v
# Expected: peak memory < 110 MB
```

## Warm Startup Verification

```bash
# Measure startup time on an already-configured system
hyperfine --warmup 3 'uv run openreview --version'
# Expected: < 0.3s (warm startup)

# Alternative without hyperfine
time uv run openreview --version
# Expected: real < 0.3s
```
