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

Pre-alpha. Foundation shipped: document parsing (PDF/DOCX, clause detection),
PII stripping (Presidio, 16 entity types, encrypted mapping), AI provider gateway
(33 models, 8 providers, routing + cost tracking + health check), and SLM
provider-specific pass-through params (`extra_params` in config.yml). The package
is not yet on PyPI. APIs and the underlying spec are preliminary and will change.

| Metric                      | Value                     |
|-----------------------------|---------------------------|
| Unit + integration tests    | 262                       |
| CLI commands                | 19                        |
| SQLite tables               | 7                         |
| CI jobs                     | 4 (lint, types, test, memory) |
| Memory budget (processing)  | < 100 MB (NLP model exempt) |
| Startup (warm)              | < 0.3 s                   |
| PII entity types detected   | 16                        |
| AI provider models          | 33 (across 8 providers)   |

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

### PII stripping performance (real-world benchmark)

Tested against real legal contracts from the [CUAD](https://www.atticusprojectai.org/cuad) dataset
(SEC EDGAR filings — service agreements, license agreements, employment contracts):

| Metric | Value |
|--------|-------|
| Contracts tested | 10 (random sample from CUAD) |
| Avg entities per contract | 25.7 |
| Entity types found | 7 (ORGANIZATION, DATE_TIME, PERSON, LOCATION, EMAIL_ADDRESS, PHONE_NUMBER, IBAN_CODE) |
| No-PII pass-through | 0 false positives on clean text |
| Processing time (per contract, warm) | ~5 s |
| Peak memory (processing only) | 14.5 MB |
| Peak memory (incl. NLP model) | ~500 MB |

**Key findings on real contracts:**
- **The engine works on real legal text** — finds people, companies, dates, addresses, emails, phone numbers, and IBAN codes in genuine SEC filings. No crashes, no garbage output.
- **Clean text stays clean** — zero false positives on a document with no PII.
- **Memory is well under budget** — processing overhead is only 14.5 MB, leaving ~85 MB of the 100 MB headroom available.

### Accuracy

We don't report recall/precision percentages because the CUAD contracts lack
human-annotated PII ground truth — asserting "90% recall" against unlabeled data
is meaningless. What we measured instead:

| Check | Result |
|-------|--------|
| Crashes on real legal text | 0 / 10 contracts |
| Zero false positives on clean text | Passed |
| Entities found per contract (avg) | 25.7 |
| Entity types detected | 7 distinct types |
| PII placeholders inserted into output | Every entity → placeholder |

**Why the old synthetic corpus was wrong:** The auto-generated test data used
patterns like `AutoName1 Smith` that spaCy doesn't recognize as real names.
Real contracts contain *"I-ESCROW, INC., with its principal place of business at
1730 S. Amphlett Blvd., Suite 233, San Mateo, California"* — exactly what the
NLP model was trained on. The old 53% "recall" number measured how well the
engine detected robot-speak, not how well it strips real PII.

To get real accuracy numbers, you'd need human annotators to label every PII
entity in a sample of CUAD contracts, then run the engine against them. That's
future work.

### PII stripping at scale (synthetic stress test)

A 500-page synthetic document with 2,000 PII entities pushes the engine to its limits:

| Metric | Value |
|--------|-------|
| Pages | 500 |
| PII entities | 2,000 |
| Processing time (CPU) | ~45 s |
| Processing time (GPU) | < 30 s (estimated) |
| Peak memory (processing) | 14.5 MB |

Entity type distribution across the 10 real CUAD contracts:

| Type | Avg per contract | Detection method |
|------|-----------------|-----------------|
| ORGANIZATION | 15.2 | NLP (spaCy `en_core_web_lg`) |
| DATE_TIME | 3.8 | NLP + regex |
| PERSON | 2.9 | NLP |
| LOCATION | 2.1 | NLP |
| EMAIL_ADDRESS | 0.7 | Regex + Presidio built-in |
| PHONE_NUMBER | 0.6 | Regex + Presidio built-in |
| IBAN_CODE | 0.4 | Presidio built-in |

### Integration with Phase 2

PII stripping sits between document parsing and all downstream processing.
The privacy gate is available as a Python API and via CLI:

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

**CLI integration** — the `precheck` review command strips PII automatically:

```bash
# Default: PII stripped before review
openreview precheck contract.pdf
# → PII-Stripped review memo with encrypted mapping

# Opt out for fully local setups
openreview precheck --no-pii contract.pdf
# → Raw text review memo, warning logged

# Manage PII data (GDPR-compliant retention)
openreview pii list              # List documents with PII data
openreview pii delete abc123     # Delete all PII data for a document
```

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
| `src/openreview_cli/app.py`                         | Typer app — `config`, `client`, `parse`, `precheck`, `pii`, `gateway` commands |
| `src/openreview_cli/config/paths.py`                | platformdirs paths (config, data, log)     |
| `src/openreview_cli/config/loader.py`               | Pydantic model, YAML r/w, env merge        |
| `src/openreview_cli/config/auth.py`                 | `auth.json` handler, chmod 600             |
| `src/openreview_cli/storage/database.py`            | SQLite, migrations, cost tracking, clients |
| `src/openreview_cli/storage/migrations/001_initial.sql` | 5 tables DDL                           |
| `src/openreview_cli/errors.py`                      | Exit codes (5 = config, 6 = cost limit, 8 = parse error) |
| `src/openreview_cli/parsing/`                       | Document parser — PDF, DOCX, clause detection |
| `src/openreview_cli/pii/`                           | PII stripping engine — Presidio, recognizers, encrypted mapping, audit trail |
| `src/openreview_cli/gateway/`                       | AI Gateway — router, registry, cost, models, redaction, wizard |
| `tests/unit/test_app.py`                            | 5 tests (import, version, help, memory)    |
| `tests/unit/test_config_loader.py`                  | 6 tests (create, merge, env override)      |
| `tests/unit/test_auth.py`                           | 5 tests (create, load, perms, providers)   |
| `tests/unit/test_database.py`                       | 7 tests (init, cost, limits, clients)      |
| `tests/unit/test_cli_config.py`                     | 8 tests (show, get, set, validation)       |
| `tests/unit/test_cli_client.py`                     | 5 tests (add, list, delete, --force)       |
| `tests/unit/test_pdf_parser.py`                     | 11 tests (PDF parsing, headings, metadata) |
| `tests/unit/test_docx_parser.py`                    | 7 tests (DOCX parsing, tracked changes)    |
| `tests/unit/test_clause_detector.py`                | 18 tests (clause detection, hierarchy)     |
| `tests/unit/test_models.py`                         | 20 tests (Clause, Document, ParseError)    |
| `tests/unit/test_pii_*.py`                          | 38 tests (models, recognizers, placeholders, mapping, audit, engine) |
| `tests/unit/test_gateway_models.py`                 | 10 tests (ModelEntry, ProviderInfo)        |
| `tests/unit/test_gateway_router.py`                 | 25 tests (chat, embed, rerank, extra_params, health check) |
| `tests/unit/test_gateway_registry.py`               | 8 tests (registry load, Ollama discovery)  |
| `tests/unit/test_gateway_cost.py`                   | 5 tests (per-token pricing)                |
| `tests/unit/test_gateway_redaction.py`              | 8 tests (key redaction, RedactingFilter)   |
| `tests/unit/test_gateway_wizard.py`                 | 2 tests (interactive setup)                |
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
openreview parse contract.pdf         # Parse a contract into clauses
openreview parse contract.pdf --summary    # One-line summary
openreview parse contract.pdf --format json  # JSON output

# Review (PII is stripped automatically)
openreview precheck contract.pdf           # NDA review with PII stripping
openreview precheck --no-pii contract.pdf  # Skip PII stripping
openreview precheck --pii-threshold 0.7 contract.pdf  # Tune sensitivity
openreview precheck --force-reprocess contract.pdf    # Bypass cache

# PII management
openreview pii list              # Documents with PII data
openreview pii delete abc123     # Delete PII data for a document
openreview pii cleanup           # Delete expired PII data

# AI Gateway
openreview gateway providers            # List supported providers
openreview gateway models openai        # List models for a provider
openreview gateway setup                # Interactive setup wizard
openreview gateway status               # Show configured slots
openreview gateway set reasoning gpt-4  # Assign model to a slot
openreview gateway test reasoning       # Send a test request
openreview gateway costs --today        # Show daily cost summary
openreview gateway refresh              # Refresh model registry
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
| `openreview parse <path>`              | Parse a PDF or DOCX into numbered clauses  |
| `openreview parse <path> --summary`    | One-line parse summary                     |
| `openreview parse <path> --format json`| JSON output with all metadata              |
| `openreview precheck <path>`           | NDA review with automatic PII stripping    |
| `openreview precheck --no-pii <path>`  | NDA review, skip PII (raw text in output)  |
| `openreview pii list`                  | List documents with stored PII data        |
| `openreview pii delete <hash>`         | Delete all PII data for a document (GDPR)  |
| `openreview pii cleanup`              | Delete documents with expired PII retention |
| `openreview gateway providers`         | List all supported providers               |
| `openreview gateway models <provider>` | List available models for a provider       |
| `openreview gateway setup`             | Interactive provider/model configuration   |
| `openreview gateway status`            | Show configured slots and reachability     |
| `openreview gateway set <slot> <model>`| Assign a model to a named slot             |
| `openreview gateway test <slot>`       | Send a test request to a slot's model      |
| `openreview gateway costs --today`     | Show daily cost summary                    |
| `openreview gateway costs --session <id>` | Show per-session cost breakdown        |
| `openreview gateway refresh`           | Refresh model registry from remote source  |

## Configuration

Config lives at `config.yml` (platformdirs: `~/.config/openreview/` on Linux).
Secrets (API keys) live in `auth.json` at the same path.

| Section              | What it controls              | Example keys                       |
|----------------------|-------------------------------|------------------------------------|
| `privacy`            | PII stripping, log retention  | `tier`, `strip_pii`, `log_ttl_days`|
| `gateway.models`     | LLM provider/model per task   | `reasoning.primary`, `extraction.params.temperature`, `reasoning.extra_params` |
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
| Benchmark        | `uv run python scripts/benchmark_legalbenchrag.py` |
| Lint             | `uv run ruff check .`           |
| Format           | `uv run ruff format --check .`  |
| Types            | `uv run mypy src/ tests/`       |
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
