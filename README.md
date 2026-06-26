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

Pre-alpha. 229 spec tasks implemented across config + storage foundation,
document parsing engine, PII stripping (Phase 3), and AI Gateway (Phase 4).
The package is not yet on PyPI. APIs and the underlying spec are preliminary
and will change.

| Metric                      | Value                     |
|-----------------------------|---------------------------|
| Unit + integration tests    | 322 (73 s)                |
| Live integration tests      | 12 (11 passed, 1 expected failure) |
| CLI commands                | ~20                       |
| SQLite tables               | 7                         |
| CI jobs                     | 4 (lint, types, test, memory) |
| Memory budget (processing)  | < 100 MB (NLP model exempt) |
| Startup (warm)              | < 0.3 s                   |
| Spec tasks tracked          | 229 (221 done, 8 deferred)|
| Dead code cut               | −190 lines, −7 files      |
| PII entity types detected   | 11 body + 4 metadata      |
| Gateway providers           | 8 (openai, anthropic, google, ollama, openrouter, cohere, huggingface, custom) |
| Gateway routing overhead    | ~6.5 ms (isolation)       |

### Parsing performance (real-world benchmark)

Tested against 860 real legal documents — both native PDFs and text-derived contracts:

| Metric                      | LegalBench-RAG (text→PDF) | CUAD v1 (native PDFs) | CUAD v1 (converted DOCX) |
|-----------------------------|---------------------------|-----------------------|--------------------------|
| Contracts parsed            | 661                       | 199                   | 100                      |
| Success rate                | **100%**                  | **100%**              | **100%**                 |
| Total clauses detected      | 50,378                    | 21,954                | 4,759                    |
| Avg clauses per contract    | 76.2                      | 110.3                 | 47.6                     |
| Avg parse time (warm)       | 0.052 s                   | 0.088 s               | 0.322 s                  |
| Total parse time            | 34.6 s                    | 17.5 s                | 32.2 s                   |
| Avg throughput              | 1.66 M chars/sec          | 2.28 M chars/sec      | —                        |
| Peak RSS                    | 362 MB                    | 362 MB                | 344 MB                   |
| Errors                      | 0                         | 0                     | 0                        |

- **LegalBench-RAG:** 661 contracts from [github.com/zeroentropy-ai/legalbenchrag](https://github.com/zeroentropy-ai/legalbenchrag) (CUAD + MAUD + ContractNLI). Text files converted to PDF for testing.
- **CUAD v1:** 199 native PDF contracts from [zenodo.org/records/4595826](https://zenodo.org/records/4595826) (SEC EDGAR filings — hosting/employment/service/license agreements). Native PDFs, no conversion step.

### PII stripping performance (seeded corpus + synthetic 50-page contract)

Tested against 54 documents: 50 seeded contracts (25 auto-generated + 25 manually annotated),
a multi-occurrence stress test, a no-PII pass-through document, a mixed-language document,
and a synthetic 50-page contract:

| Metric | Seeded (50 docs) | 50-page synthetic |
|--------|-------------------|-------------------|
| Documents processed | 50 | 1 |
| Total entities detected | 1,385 | 345 |
| Avg entities per doc | 27.7 | 6.9 per page |
| Per-doc processing (warm, mean) | < 0.2 s | — |
| Total processing time | 17.4 s | 3.83 s |
| No-PII pass-through | ✅ 0 false positives | — |
| Non-English PII detection | ✅ 14 entities (regex-only) | — |
| Multi-occurrence consistency | ✅ 2.5s for 1,186 entities | — |
| Entity types | 12 (PERSON, ORG, EMAIL, PHONE, LOCATION, AMOUNT, TAX_ID, DATE, REG, ID, ACCT, LICENSE) | 7 |
| Peak RSS (incl. NLP model) | — | 1,273 MB |

**Key takeaways:**
- **No false positives on clean text** — the `no_pii_document.txt` pass-through produces zero entities
- **Non-English text**: 14 entities detected on mixed-language document using regex-only recognizers (emails, phones, amounts — no NLP on non-English sections)
- **Multi-occurrence**: 1,186 entities from 50× repeated PII in a single document, processed in 2.5s
- **50-page target**: 3.83s (near the <3s target; gap is apportioned to Presidio framework overhead, not entity detection itself)

Entity type distribution across all 54 documents:

| Type | Count | Detection method |
|------|-------|-----------------|
| PERSON | 1,225 | 🔬 NLP (spaCy `en_core_web_lg`) |
| ORGANIZATION | 151 | 🔬 NLP |
| DATE_TIME | 72 | 🔬 NLP + Regex |
| LOCATION | 54 | 🔬 NLP |
| EMAIL_ADDRESS | 53 | 🔍 Regex + Presidio built-in |
| AMOUNT | 52 | 🔍 Custom regex (`$5,000,000`, `$1M`) |
| TAX_ID | 50 | 🔍 Custom regex (EIN `12-3456789`) |
| REG_NUMBER | 50 | 🔍 Custom regex (`REG-100001`) |
| ID_DOCUMENT | 17 | 🔍 Custom regex (passport, DL) |
| IBAN_CODE / NRP / MEDICAL_LICENSE | 6 | 🔍 Presidio built-in |

### Integration with Phase 2

PII stripping sits between document parsing and all downstream processing.
The privacy gate is available as a Python API:

```python
>>> from openreview_cli.pii.engine import strip_pii
>>> from openreview_cli.parsing.models import Clause, Document
>>> from pathlib import Path
>>> clause = Clause(id="1", text="John Doe works at Acme Inc. Contact john@acme.com.",
...                 level=1, source_page=1)
>>> doc = Document(source_path=Path("test.pdf"), format="pdf", page_count=1, clause_count=1,
...                parse_duration_seconds=0.0, warnings=[])
>>> result = strip_pii([clause], doc, strip_metadata=False)
>>> result.stripped_text[:80]
'[NAME_1] works at [PARTY_A]. Contact [EMAIL_1].'
```

A CLI `--no-pii` flag and config-driven toggle are defined but deferred until
the review subcommand (Phase 5+) is created — see AGENTS.md deferred-work table.

### AI Gateway (Phase 4)

The gateway routes review requests through task-specific model slots (reasoning,
extraction, embedding, reranking, graph). It supports 8 providers, interactive
and non-interactive setup, fallback chains, cost tracking, and YAML import.

| Feature | Status |
|---------|--------|
| Routing | ✅ All 5 slots via LiteLLM (chat, embed, rerank) |
| Providers | ✅ OpenAI, Anthropic, Google, Ollama, OpenRouter, Cohere, HuggingFace, Custom |
| Interactive wizard | ✅ Rich UI, slot grouping, back/cancel/save, masked key entry |
| CLI setup | ✅ `--non-interactive` flags for all 5 slots |
| Fallback | ✅ Exponential backoff, fallback chain, 3 on_failure modes |
| Cost tracking | ✅ SQLite per-call records, per-review & daily limits |
| CLI subcommands | ✅ 10 commands (`setup`, `status`, `providers`, `models`, `set`, `test`, `refresh`, `costs`, `install-models`, `import`) |
| YAML import | ✅ Full validation, all errors reported at once, `api_key_env` support |
| Model registry | ✅ Remote cache + built-in fallback (14 models across 6 providers) |
| Logging | ✅ Three-tier (console/file), API key redaction, `--debug-unsafe` |
| Live testing | ✅ 11 integration tests via OpenRouter (real API calls) |

**Routing overhead**: ~6.5 ms per request in isolation, <75 ms under full CI load.

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
| `src/openreview_cli/app.py`                         | Typer app — `config`, `client`, `parse` commands |
| `src/openreview_cli/config/paths.py`                | platformdirs paths (config, data, log)     |
| `src/openreview_cli/config/loader.py`               | Pydantic model, YAML r/w, env merge        |
| `src/openreview_cli/config/auth.py`                 | `auth.json` handler, chmod 600             |
| `src/openreview_cli/storage/database.py`            | SQLite, migrations, cost tracking, clients |
| `src/openreview_cli/storage/migrations/001_initial.sql` | 5 tables DDL                           |
| `src/openreview_cli/errors.py`                      | Exit codes (5 = config, 6 = cost limit, 8 = parse error) |
| `src/openreview_cli/parsing/`                       | Document parser — PDF, DOCX, clause detection |
| `src/openreview_cli/pii/`                           | PII stripping engine — Presidio, recognizers, encrypted mapping, audit trail |
| `src/openreview_cli/gateway/`                       | AI Gateway — routing, costs, wizard, registry, importer, logging |
| `tests/unit/test_app.py`                            | 5 tests (import, version, help, memory)    |
| `tests/unit/test_config_loader.py`                  | 6 tests (create, merge, env override)      |
| `tests/unit/test_auth.py`                           | 7 tests (create, load, perms, providers)   |
| `tests/unit/test_database.py`                       | 7 tests (init, cost, limits, clients)      |
| `tests/unit/test_cli_config.py`                     | 8 tests (show, get, set, validation)       |
| `tests/unit/test_cli_client.py`                     | 5 tests (add, list, delete, --force)       |
| `tests/unit/test_pii_*.py`                          | 40 tests (models, recognizers, placeholders, mapping, audit, engine) |
| `tests/unit/test_gateway_*.py`                      | 34 tests (models, engine, costs, registry, wizard, importer, logging) |
| `tests/unit/test_errors.py`                         | 9 tests (exit codes, stderr output)        |
| `tests/unit/test_paths.py`                          | 10 tests (XDG path resolution)            |
| `tests/unit/test_providers.py`                      | 8 tests (Ollama discovery, errors)        |
| `tests/unit/test_utils.py`                          | 6 tests (atomic write, cleanup)           |
| `tests/integration/test_gateway_routing.py`         | 7 tests (mock routing, local mode)        |
| `tests/integration/test_gateway_fallback.py`        | 3 tests (retry, fallback, on_failure)     |
| `tests/integration/test_gateway_cli.py`             | 19 tests (CLI subcommands)                |
| `tests/integration/test_gateway_benchmark.py`       | 1 test (overhead <75 ms)                  |
| `tests/integration/test_gateway_privacy.py`         | 1 test (network isolation)                |
| `tests/integration/test_gateway_live.py`            | 6 tests (OpenRouter real-API, 1 xfail)    |
| `tests/integration/test_gateway_live_cli.py`        | 6 tests (CLI with OpenRouter)             |
| `tests/conftest.py`                                 | Memory tracker fixture (< 110 MB)          |
| `.pre-commit-config.yaml`                           | 10 hooks (ruff, mypy, pytest, hygiene)     |
| `.github/workflows/ci.yml`                          | 4 parallel CI jobs                         |
| `specs/001-config-storage-foundation/`              | Spec, plan, and 56-task checklist          |
| `specs/004-ai-gateway/`                             | Spec, plan, contracts, and 75-task checklist |

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
openreview parse contract.pdf         # Parse a contract into clauses
openreview parse contract.pdf --summary    # One-line summary
openreview parse contract.pdf --format json  # JSON output
openreview gateway setup --non-interactive --reasoning openai/gpt-4o --embedding ollama/nomic-embed-text  # All 5 slots via flags
openreview gateway status              # Show configured slots, health, costs
openreview gateway test reasoning      # Validate API key and provider reachability
openreview gateway providers           # List providers with auth status
openreview gateway models openai       # List models for a provider
openreview gateway costs               # View today's token usage and cost
openreview gateway import config.yaml  # Import YAML config (5 slots at once)

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
| `openreview parse <path>`              | Parse a PDF or DOCX into numbered clauses  |
| `openreview parse <path> --summary`    | One-line parse summary                     |
| `openreview parse <path> --format json`| JSON output with all metadata              |
| `openreview gateway setup [--reasoning ...] [flags]` | Configure all 5 slots (interactive or via flags) |
| `openreview gateway status`            | Show slot models, provider health, cost limits |
| `openreview gateway providers`         | List all supported providers with auth status |
| `openreview gateway models <provider>` | List available models for a provider       |
| `openreview gateway set <slot> <model>` | Change one slot's model (supports `--fallback`, `--temperature`) |
| `openreview gateway test <slot>`       | Test API key and provider connectivity     |
| `openreview gateway refresh`           | Fetch latest model registry from remote    |
| `openreview gateway costs [--days N] [--session ID]` | View or clear cost records |
| `openreview gateway install-models <name> [names...]` | Pull Ollama models via `ollama pull` |
| `openreview gateway import <file> [--force] [--dry-run]` | Import YAML config with validation |

## Configuration

Config lives at `config.yml` (platformdirs: `~/.config/openreview/` on Linux).
Secrets (API keys) live in `auth.json` at the same path.

| Section              | What it controls              | Example keys                       |
|----------------------|-------------------------------|------------------------------------|
| `privacy`            | PII stripping, log retention  | `tier`, `strip_pii`, `log_ttl_days`|
| `gateway.models`     | LLM provider/model per task   | `reasoning.primary`, `extraction.params.temperature` |
| `gateway.fallback`   | Retry and timeout behavior    | `retries`, `timeout`, `on_failure` |
| `gateway.cost_limits`| Spending caps                 | `per_review_cents`, `daily_cents`  |
| `gateway.registry`   | Model registry source         | `refresh_days`, `remote_url`      |
| `gateway.logging`    | Gateway-specific log level    | `level`, `debug_file`             |
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
| Tests (unit)     | `uv run pytest tests/unit/ -q`  |
| Tests (all, no live) | `uv run pytest tests/unit/ tests/integration/ -m "not live"` |
| Memory budget    | `uv run pytest -m memory`       |
| Gateway live     | `OPENROUTER_API_KEY=... uv run pytest tests/integration/test_gateway_live.py -v` |
| Gateway overhead | `uv run pytest tests/integration/test_gateway_benchmark.py -v` |
| Parsing benchmark| `uv run python scripts/benchmark_legalbenchrag.py` |
| Lint             | `uv run ruff check .`           |
| Format           | `uv run ruff format --check .`  |
| Types            | `uv run mypy src/ tests/`       |
| Coverage         | `uv run pytest --cov=openreview_cli --cov-report=term-missing` |
| All hooks        | `uvx pre-commit run --all-files`|

## Benchmarks

The parsing performance numbers in the table above are reproducible:

```bash
# 1. Clone the benchmark corpus
git clone --depth 1 https://github.com/zeroentropy-ai/legalbenchrag.git /tmp/legalbenchrag
wget -qO /tmp/lbr.zip "https://www.dropbox.com/scl/fo/r7xfa5i3hdsbxex1w6amw/AID389Olvtm-ZLTKAPrw6k4?rlkey=5n8zrbk4c08lbit3iiexofmwg&st=0hu354cq&dl=1"
unzip -qo /tmp/lbr.zip -d /tmp/legalbenchrag

# 2. Convert .txt to .pdf (one-time ~30s) and run the benchmark
uv run python scripts/benchmark_legalbenchrag.py
```

The script downloads the corpus, converts each text file to PDF via pymupdf,
runs the parser against every contract, and writes `metrics-v0.1.0.json` with
per-file timing, clause counts, and peak memory.

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
