<p align="center">
  <img src="assets/logo.png" alt="openreview logo" width="200">
</p>

# openreview-cli

[![CI](https://github.com/mohamed-benoughidene/openreview-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/mohamed-benoughidene/openreview-cli/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](.python-version)

Privacy-first contract review tool. Reads contracts, compares them against
a custom playbook, and produces a structured memo of findings.

## Status

Pre-alpha. 56 spec tasks implemented across the config + storage foundation.
The package is not yet on PyPI. APIs and the underlying spec are preliminary
and will change.

| Metric              | Value                    |
|---------------------|--------------------------|
| Unit tests          | 36 (1.8 s)               |
| CLI commands        | 8                        |
| SQLite tables       | 5                        |
| CI jobs             | 4 (lint, types, test, memory) |
| Memory budget       | < 110 MB                 |
| Startup (warm)      | < 0.3 s                  |
| Spec tasks tracked  | 56 (all complete)        |
| Dead code cut       | −120 lines, −5 files     |

## Installation

```bash
uv tool install openreview-cli
```

> Not yet on PyPI. The command above documents the intended install path. Today the only way to run the tool is from a checkout:

```bash
git clone https://github.com/mohamed-benoughidene/openreview-cli
cd openreview-cli
git submodule update --init
uv sync
uv run openreview --version
```

## Where things live

| Path                                                | Purpose                                    |
|-----------------------------------------------------|--------------------------------------------|
| `src/openreview_cli/__init__.py`                    | Exposes `__version__`                      |
| `src/openreview_cli/__main__.py`                    | Entry point: `python -m openreview_cli`    |
| `src/openreview_cli/app.py`                         | Typer app — `config` + `client` commands   |
| `src/openreview_cli/config/paths.py`                | platformdirs paths (config, data, log)     |
| `src/openreview_cli/config/loader.py`               | Pydantic model, YAML r/w, env merge        |
| `src/openreview_cli/config/auth.py`                 | `auth.json` handler, chmod 600             |
| `src/openreview_cli/storage/database.py`            | SQLite, migrations, cost tracking, clients |
| `src/openreview_cli/storage/migrations/001_initial.sql` | 5 tables DDL                           |
| `src/openreview_cli/errors.py`                      | Exit codes (5 = config, 6 = cost limit)    |
| `tests/unit/test_app.py`                            | 5 tests (import, version, help, memory)    |
| `tests/unit/test_config_loader.py`                  | 6 tests (create, merge, env override)      |
| `tests/unit/test_auth.py`                           | 5 tests (create, load, perms, providers)   |
| `tests/unit/test_database.py`                       | 7 tests (init, cost, limits, clients)      |
| `tests/unit/test_cli_config.py`                     | 8 tests (show, get, set, validation)       |
| `tests/unit/test_cli_client.py`                     | 5 tests (add, list, delete, --force)       |
| `tests/conftest.py`                                 | Memory tracker fixture (< 110 MB)          |
| `.pre-commit-config.yaml`                           | 10 hooks (ruff, mypy, pytest, hygiene)     |
| `.github/workflows/ci.yml`                          | 4 parallel CI jobs                         |
| `specs/001-config-storage-foundation/`              | Spec, plan, and 56-task checklist          |

## Quick start

```bash
openreview --help                     # Show all commands
openreview --debug -h                 # Debug-mode help
openreview config show                # View config as a table
openreview config get privacy.tier    # Read one setting
openreview config set privacy.tier balanced  # Change a setting
openreview client add acme-corp "Acme Corp"  # Register a client
openreview client list                # List clients
openreview client delete acme-corp --force   # Remove client
```

| Command                                    | What it does                               |
|--------------------------------------------|--------------------------------------------|
| `openreview --version`                     | Print version and exit                     |
| `openreview --debug`                       | Enable debug-level logging                 |
| `openreview config show`                   | Print full configuration as a Rich table   |
| `openreview config get <key>`              | Read one setting by dotted path            |
| `openreview config set <key> <value>`      | Write a setting (creates `.bak` backup)    |
| `openreview client add <id> <name>`        | Register an API client                     |
| `openreview client list`                   | List all registered clients                |
| `openreview client delete <id> [--force]`  | Remove a client (`--force` = cascade)      |

## Configuration

Config lives at `config.yml` (platformdirs: `~/.config/openreview/` on Linux).
Secrets (API keys) live in `auth.json` at the same path.

| Section              | What it controls              | Example keys                       |
|----------------------|-------------------------------|------------------------------------|
| `privacy`            | PII stripping, log retention  | `tier`, `strip_pii`, `log_ttl_days`|
| `gateway.models`     | LLM provider/model per task   | `reasoning.primary`, `extraction.params.temperature` |
| `gateway.fallback`   | Retry and timeout behavior    | `retries`, `timeout`, `on_failure` |
| `gateway.cost_limits`| Spending caps                 | `per_review_cents`, `daily_cents`  |
| `storage`            | Data retention                | `reviews_keep_forever`, `logs_keep_days` |

### Environment variable overrides

Any config key can be overridden via env vars without touching `config.yml`.
Prefix with `OPENREVIEW_`, use `__` for nested keys:

```bash
# Override a top-level key
OPENREVIEW_PROVIDER=ollama openreview config show

# Override a deeply nested key
OPENREVIEW_GATEWAY__COST_LIMITS__PER_REVIEW_CENTS=300 openreview config show

# Provider API key env vars (picked up by auth)
OPENAI_API_KEY=sk-...  ANTHROPIC_API_KEY=sk-ant-...  OLLAMA_HOST=http://...
```

Priority: `config.yml` < env var < CLI flag (future).

## Development

```bash
git clone https://github.com/mohamed-benoughidene/openreview-cli
cd openreview-cli
git submodule update --init
uv sync

# Pre-commit checks (run before every commit)
uvx pre-commit run --all-files

# Or install git hooks once
uvx pre-commit install
```

| Check            | Command                         |
|------------------|---------------------------------|
| Tests            | `uv run pytest tests/unit/ -q`  |
| Memory budget    | `uv run pytest -m memory`       |
| Lint             | `uv run ruff check .`           |
| Format           | `uv run ruff format --check .`  |
| Types            | `uv run mypy src/ tests/`       |
| All hooks        | `uvx pre-commit run --all-files`|

## Contributing

By contributing, you agree to the [CLA](CLA.md). All contributions are subject to the project's [Code of Conduct](.github/CODE_OF_CONDUCT.md). Bug reports and feature requests use the templates in [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/).

## License

Dual-licensed:

- [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0)
- [Commercial License](COMMERCIAL_LICENSE.md) — for organizations that want to avoid AGPL-3.0's source-disclosure obligations

See [NOTICE.md](NOTICE.md) for trademarks and licensing details.

## Contact

- Issues: [GitHub Issues](https://github.com/mohamed-benoughidene/openreview-cli/issues)
- Twitter: [@mohamedbeno22](https://x.com/mohamedbeno22)
