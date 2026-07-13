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
PII stripping (Presidio, 16 entity types, encrypted mapping), chunking strategy
(RCTS, clause-boundary-aware, 512-token default, streaming), PII-to-chunk bridge
(`strip_pii_clauses()` per-clause replacement), AI provider gateway (33 models,
8 providers, routing + cost tracking + health check), SLM provider-specific
pass-through params (`extra_params` in config.yml), prompt management
(versioned SQLite-backed storage, model-to-prompt binding, variable substitution,
YAML export/import, A/B testing and GRPO optimization hooks defined), **and
hierarchical retrieval (BM25 + dense embeddings + RRF hybrid fusion, offline
fallback, reranker validation), 5-stage async pipeline framework (Stage ABC,
runner with cancellation and progress tracking, memory budget enforcement,
adapters for parse/strip/chunk/retrieve/generate), and single-party contract
review (PAKTON 3-agent pipeline: extraction, QA
verification, report formatting), citation grounding discriminator
(post-hoc claim verification with strict/lenient modes, CG metrics, JSONL audit trail),
and three-color output with confidence scores (Green/Amber/Red with `--confidence-threshold` flag), playbook versioning (database storage with version tracking, position rename to preferred/acceptable/walkaway with backward compatibility, version-stamped reviews), experimental bilateral comparison (`openreview precheck compare`) with RCBSF 5-dimension divergence detection and paired three-color status, error recovery framework (5 strategies: auto-retry, provider fallback, graceful degradation, stage isolation, user-guided recovery; coordinator orchestrates strategy chains, pipeline integration with pre-stage memory check and post-stage failure handling), **privacy tier routing with three tiers (Maximum all-local, Balanced local embeddings + cloud reasoning, Performance cloud with PII stripped), TierRouter enforcement layer with PII fail-closed, and memo export for review results (Markdown, JSON, DOCX formats with color-coded clauses, confidence scores, citation provenance, citation relevance/locality metrics, and playbook metadata), contract graph modeling (directed clause graph, 0–100 heuristic health score, tree view), and game-theoretic negotiation assistant (Nash/QRE/Level-k solvers for modeling counterparty behavior, advisory Amber-confidence output), and **22 product-mode subcommands** — PreCheck (NDA), LicenseCheck, LeaseCheck, PrivacyCheck, DealCheck, HireCheck, IndemnityCheck, ConsultCheck, WorkCheck, LOICheck, SubCheck, SettlementCheck, AssetCheck, BuyCheck, EngageCheck, GuaranteeCheck, LoanCheck, FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, and DistroCheck — each with a bundled 3-position playbook, mode-specific prompt vocabulary, full CLI wiring, and memo export support.**
The package is not yet on PyPI. APIs and the underlying spec are preliminary and
will change.

**Spec 029 — Product modes Batch 2:** 5 new modes (AssetCheck, BuyCheck, EngageCheck, GuaranteeCheck, LoanCheck) shipped alongside 9 previously-orphaned modes from specs 027/028. Each mode has a bundled 3-position playbook, mode-specific prompt vocabulary, and full CLI wiring.

**Spec 030 — Benchmark mode validation:** `openreview benchmark run --modes` now validates against a whitelist of the 22 product modes, rejecting unknown modes with exit code 78. New `openreview benchmark baseline` subcommand produces accuracy baselines across modes and datasets with mock/live provider support. 9 orphan E2E tests added for mode validation coverage.

**Spec 031 — Product modes Batch 3 (L-4c):** 5 new modes (FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, DistroCheck) shipped as the final product-mode batch, bringing the total to 22 product-mode subcommands. All 22 modes have bundled 3-position playbooks, mode-specific prompt vocabulary, and full CLI wiring.

| Metric                      | Value                     |
|-----------------------------|---------------------------|
| Unit + integration tests    | 2,007                    |
| CLI commands                | 77                        |
| SQLite tables               | 13                        |
| Migrations                  | 7                         |
| CI jobs                     | 5 (lint, types, test, memory, benchmark) |
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

Accuracy against our seeded validation corpus (50+ contracts with ground truth
annotations) now meets the 95% recall and 95% precision threshold across all
entity types. The benchmark harness validates this on every run via
`openreview benchmark --pii-only` and blocks regressions in CI.

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

**Per-clause bridge** — `strip_pii_clauses()` strips PII while preserving clause
structure, enabling a parse → strip → chunk pipeline:

```python
>>> from openreview_cli.pii.engine import strip_pii_clauses
>>> from openreview_cli.parsing.models import Clause, Document
>>> clauses = [Clause(id="1", text="John Doe works at Acme Inc. Contact john@acme.com.",
...                   level=1, source_page=1)]
>>> doc = Document(source_path=Path("test.pdf"), format="pdf", page_count=1, clause_count=1,
...                parse_duration_seconds=0.0, warnings=[])
>>> stripped_clauses, pii_result = strip_pii_clauses(clauses, doc)
>>> stripped_clauses[0].text
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

### Chunking strategy

The chunking engine splits parsed clauses into retrieval-ready chunks using
RCTS (Recursive Character Text Splitting):

1. **Clause boundaries first** — clauses are never split mid-clause
2. **Paragraph boundaries** — within a clause, split at paragraph breaks
3. **Sentence boundaries** — within a paragraph, split at sentence boundaries
4. **Word boundaries** — oversize sentences are split at word boundaries

Default config: **512 tokens** per chunk, **50-token overlap**, streaming
(yield-based, <10 MB processing memory). Short adjacent clauses are grouped
to avoid tiny fragments. Each chunk carries structural metadata (parent
clause ID, title, level, structural location).

The PII-to-chunk bridge (`strip_pii_clauses()`) enables a clean three-stage
pipeline: **parse → strip PII → chunk**, with no raw PII in any chunk output.

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
| `src/openreview_cli/app.py`                         | Typer app — 37 top-level commands: `parse`, `chunk`, `ingest`, `retrieve`, `index-status`, `index-clear`, `negotiate`, `precheck`, `licensecheck`, `leasecheck`, `privacycheck`, `dealcheck`, `hirecheck`, `indemnitycheck`, `consultcheck`, `workcheck`, `loicheck`, `subcheck`, `settlementcheck`, `assetcheck`, `buycheck`, `engagecheck`, `guaranteecheck`, `loancheck`, `franchisecheck`, `opcheck`, `partnercheck`, `sponsorcheck`, `distrocheck`, `client`, `config`, `pii`, `playbook`, `gateway`, `graph`, `benchmark`, `prompt` |
| `src/openreview_cli/config/paths.py`                | platformdirs paths (config, data, log)     |
| `src/openreview_cli/config/loader.py`               | Pydantic model, YAML r/w, env merge        |
| `src/openreview_cli/config/auth.py`                 | `auth.json` handler, chmod 600             |
| `src/openreview_cli/storage/database.py`            | SQLite, migrations, cost tracking, clients, playbook storage |
| `src/openreview_cli/storage/migrations/001_initial.sql` | 5 tables DDL                           |
| `src/openreview_cli/storage/migrations/002_pii_tables.sql` | 2 tables DDL                     |
| `src/openreview_cli/storage/migrations/003_gateway.sql` | Gateway schema updates                  |
| `src/openreview_cli/storage/migrations/004_prompts.sql` | 2 tables DDL (prompt_versions, prompt_bindings) |
| `src/openreview_cli/storage/migrations/005_benchmark.sql` | 3 tables DDL                       |
| `src/openreview_cli/storage/migrations/006_playbooks.sql` | 1 table DDL (playbook_versions, append-only) |
| `src/openreview_cli/storage/migrations/007_playbook_meta.sql` | 1 table DDL (playbook_meta, soft-delete, current version) |
| `src/openreview_cli/errors.py`                      | Exit codes (5 = config, 6 = cost limit, 8 = parse error) |
| `src/openreview_cli/parsing/`                       | Document parser — PDF, DOCX, clause detection, paragraph count per clause |
| `src/openreview_cli/pii/`                           | PII stripping engine — Presidio, recognizers, encrypted mapping, audit trail, `strip_pii_clauses()` bridge |
| `src/openreview_cli/chunking/`                      | Chunking engine — RCTS splitting, clause-boundary-aware, streaming |
| `src/openreview_cli/gateway/`                       | AI Gateway — router, registry, cost, models, redaction, wizard |
| `src/openreview_cli/retrieval/`                     | Retrieval pipeline — BM25 (FTS5), dense embeddings (Ollama), RRF fusion, reranker, ingest, storage |
| `src/openreview_cli/graph/`                         | Contract graph modeling — directed clause graph, structural metrics, 0–100 heuristic health score, ASCII tree view |
| `src/openreview_cli/grounding/`                    | Citation grounding discriminator — post-hoc claim verification, strict/lenient modes, CG metrics, JSONL audit trail, corruption generators |
| `src/openreview_cli/pipeline/`                      | 5-stage async pipeline — Stage ABC, runner with cancellation/progress/memory enforcement, adapters (parse/strip/chunk/retrieve/generate), error hierarchy, progress events |
| `src/openreview_cli/recovery/`                      | Error recovery framework — 5 strategies (auto-retry, provider fallback, graceful degradation, stage isolation, user-guided), coordinator, strategy chains, pipeline integration |
| `src/openreview_cli/review/`                       | Single-party review package (PAKTON 3-agent pipeline, delegates through async pipeline) |
| `src/openreview_cli/review/memo/`                  | Memo export — Markdown, JSON, DOCX formatters, filename generator, models, citation metrics in summary |
| `src/openreview_cli/review/pipeline.py`            | ReviewStage — wraps extraction/QA agents as a pipeline stage |
| `src/openreview_cli/review/playbook.py`            | Playbook loader — YAML parsing, validation, DB-backed load via `load_playbook_from_db()` |
| `src/openreview_cli/review/playbooks/`             | Bundled YAML playbooks: `precheck-nda-v1.yaml`, `saas-license-v1.yaml`, `commercial-lease-v1.yaml`, `dpa-v1.yaml`, `dealcheck-v1.yaml`, `hirecheck-v1.yaml`, `indemnification-v1.yaml`, `consulting-agreement-v1.yaml`, `work-for-hire-v1.yaml`, `letter-of-intent-v1.yaml`, `subcontractor-agreement-v1.yaml`, `settlement-agreement-v1.yaml`, `asset-transfer-v1.yaml`, `asset-purchase-v1.yaml`, `engagement-letter-v1.yaml`, `personal-guarantee-v1.yaml`, `loan-agreement-v1.yaml` |
| `src/openreview_cli/prompts/`                       | Prompt management — versioned storage, binding, CLI |
| `src/openreview_cli/prompts/models.py`              | Pydantic models (Prompt, PromptVersion, PromptBinding) |
| `src/openreview_cli/prompts/store.py`               | PromptStore — SQLite CRUD, versioning, resolve() |
| `src/openreview_cli/prompts/cli.py`                 | 14 Typer subcommands (create, update, list, show, delete, diff, bind, unbind, bindings, history, test, export, import, optimize) |
| `src/openreview_cli/prompts/variables.py`           | `{key}` variable substitution engine |
| `src/openreview_cli/prompts/defaults.py`            | Default prompt loader (YAML → SQLite on first use) |
| `src/openreview_cli/prompts/defaults/`              | 5 built-in default prompts (extraction, reasoning, embedding, reranking, graph) |
| `tests/unit/test_app.py`                            | 5 tests (import, version, help, memory)    |
| `tests/unit/test_config_loader.py`                  | 6 tests (create, merge, env override)      |
| `tests/unit/test_auth.py`                           | 5 tests (create, load, perms, providers)   |
| `tests/unit/test_bilateral_comparison.py`           | 36 tests (precheck compare input validation, CLI flags, error handling) |
| `tests/unit/test_database.py`                       | 7 tests (init, cost, limits, clients)      |
| `tests/unit/test_cli_config.py`                     | 8 tests (show, get, set, validation)       |
| `tests/unit/test_cli_client.py`                     | 5 tests (add, list, delete, --force)       |
| `tests/unit/test_pdf_parser.py`                     | 11 tests (PDF parsing, headings, metadata) |
| `tests/unit/test_docx_parser.py`                    | 7 tests (DOCX parsing, tracked changes)    |
| `tests/unit/test_clause_detector.py`                | 18 tests (clause detection, hierarchy)     |
| `tests/unit/test_models.py`                         | 20 tests (Clause, Document, ParseError)    |
| `tests/unit/test_pii_*.py`                          | 45 tests (models, recognizers, placeholders, mapping, audit, engine, strip_pii_clauses) |
| `tests/unit/test_chunking_models.py`                | 4 tests (Chunk, ChunkConfig dataclasses)        |
| `tests/unit/test_chunking_tokenizer.py`             | 7 tests (token counting edge cases)             |
| `tests/unit/test_chunking_splitter.py`              | 10 tests (RCTS splitting, overlap, grouping)    |
| `tests/unit/test_chunking_stream.py`                | 6 tests (stream_chunks pipeline, formatting)    |
| `tests/unit/test_gateway_models.py`                 | 10 tests (ModelEntry, ProviderInfo)        |
| `tests/unit/test_gateway_router.py`                 | 25 tests (chat, embed, rerank, extra_params, health check) |
| `tests/unit/test_gateway_registry.py`               | 8 tests (registry load, Ollama discovery)  |
| `tests/unit/test_gateway_cost.py`                   | 5 tests (per-token pricing)                |
| `tests/unit/test_gateway_redaction.py`              | 8 tests (key redaction, RedactingFilter)   |
| `tests/unit/test_gateway_wizard.py`                 | 2 tests (interactive setup)                |
| `tests/unit/test_prompt_models.py`                  | 16 tests (model validation, 16 KB limit)   |
| `tests/unit/test_prompt_store.py`                   | 29 tests (CRUD, binding, export/import)    |
| `tests/unit/test_prompt_cli.py`                     | 24 tests (all 14 subcommands)              |
| `tests/unit/test_prompt_variables.py`               | 8 tests (substitution, unknown vars)       |
| `tests/unit/test_prompt_defaults.py`                | 5 tests (YAML loading, first-use)          |
| `tests/integration/test_prompt_lifecycle.py`        | 4 tests (create → bind → remove)           |
| `tests/integration/test_prompt_gateway.py`          | 5 tests (gateway prompt resolution)        |
| `tests/integration/test_prompt_memory.py`           | 1 test (memory budget < 110 MB)            |
| `tests/unit/test_playbook_versioning.py`            | 19 tests (YAML parsing, legacy key compat, append-only import, version-stamped report) |
| `tests/unit/test_playbook_storage.py`               | 11 tests (migration 007, schema, CRUD for playbook_meta) |
| `tests/unit/test_playbook_precedence.py`            | 9 tests (warning when both `--playbook` and `--playbook-path` provided) |
| `tests/unit/test_playbook_delete.py`                | 5 tests (soft-delete, idempotency, version preservation) |
| `tests/unit/test_playbook_history.py`               | 6 tests (version timeline, current/latest/deleted markers) |
| `tests/unit/test_playbook_set_current.py`           | 6 tests (set current version, reactivate deleted) |
| `tests/unit/test_playbook_management_storage.py`    | 47 tests (export, diff, full storage integration) |
| `tests/integration/test_playbook_commands.py`       | 15 tests (playbook import/list/show CLI, `--playbook` flag) |
| `tests/integration/test_playbook_management.py`     | 28 tests (export, diff, set-current, delete, history integration) |
| `tests/unit/test_pipeline_base.py`                  | 7 tests (Stage ABC, StageResult)           |
| `tests/unit/test_pipeline_errors.py`                | 11 tests (error hierarchy)                 |
| `tests/unit/test_pipeline_progress.py`              | 3 tests (progress events)                  |
| `tests/unit/test_pipeline_runner.py`                | 15 tests (runner, cancellation, memory)    |
| `tests/unit/test_pipeline_adapters.py`              | 28 tests (all 5 stage adapters)           |
| `tests/unit/test_pipeline_memory.py`                | 7 tests (memory budget enforcement)        |
| `tests/integration/test_pipeline_e2e.py`            | 12 tests (end-to-end pipeline)            |
| `tests/integration/test_pipeline_memory.py`         | 5 tests (pipeline memory budget)           |
| `tests/integration/test_no_pii_flag.py`             | 19 tests (`--no-pii` flag integration with review subcommands) |
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

# Chunking (clause-aware retrieval-ready splitting)
openreview chunk contract.json              # Split clauses into chunks (512 tokens, 50 overlap)
openreview chunk contract.json --format json  # JSON output with metadata
openreview chunk contract.json --summary      # One-line chunk summary

# Contract graph modeling (directed clause graph)
openreview parse contract.pdf --format json > contract.json  # Parse to JSON first
openreview graph build contract.json                           # Build clause graph
openreview graph view contract.graph.json                      # Render as ASCII tree
openreview graph metrics contract.graph.json                   # Structural metrics
openreview graph health contract.graph.json                    # Heuristic 0-100 health score
openreview graph health --weights '0.10 0.25 0.25 0.25 0.15' contract.graph.json  # Custom weights

# Retrieval (hybrid BM25 + dense search)
openreview ingest contract.pdf            # Parse, chunk, embed, and index a document
openreview retrieve "indemnification clause" contract.pdf  # Hybrid search (BM25 + dense + RRF)
openreview retrieve "liability cap" contract.pdf --method sparse  # BM25-only
openreview retrieve "governing law" contract.pdf --method dense   # Dense-only
openreview retrieve "termination" contract.pdf --rerank           # Enable cross-encoder reranking
openreview retrieve "confidentiality" contract.pdf --no-header    # Compact output (no table header)
openreview index-status contract.pdf      # Show index metadata
openreview index-clear contract.pdf       # Remove document index

# Review (PII is stripped automatically)
openreview precheck contract.pdf           # NDA review with PII stripping
openreview licensecheck contract.pdf       # SaaS license agreement review
openreview leasecheck contract.pdf         # Commercial lease agreement review
openreview privacycheck contract.pdf       # Data Processing Agreement review
openreview dealcheck contract.pdf          # Vendor/service agreement review
openreview hirecheck contract.pdf          # Employment agreement review
openreview indemnitycheck contract.pdf     # Indemnification agreement review
openreview consultcheck contract.pdf       # Consulting services agreement review
openreview workcheck contract.pdf          # Work-for-hire agreement review
openreview loicheck contract.pdf           # Letter of intent / MOU review
openreview subcheck contract.pdf           # Subcontractor agreement review
openreview settlementcheck contract.pdf    # Settlement / release agreement review
openreview assetcheck contract.pdf         # Asset transfer agreement review
openreview buycheck contract.pdf           # Asset purchase agreement review
openreview engagecheck contract.pdf        # Engagement letter review
openreview guaranteecheck contract.pdf     # Personal guarantee review
openreview loancheck contract.pdf          # Loan agreement review
openreview franchisecheck contract.pdf     # Franchise agreement review
openreview opcheck contract.pdf            # Operating agreement review
openreview partnercheck contract.pdf       # Partnership agreement review
openreview sponsorcheck contract.pdf       # Sponsorship agreement review
openreview distrocheck contract.pdf        # Distribution agreement review
openreview licensecheck review contract.pdf          # Full PAKTON pipeline for SaaS license review
openreview privacycheck review --memo-format md contract.pdf  # PrivacyCheck with memo export
openreview precheck --no-pii contract.pdf  # Skip PII stripping
openreview precheck --pii-threshold 0.7 contract.pdf  # Tune sensitivity
openreview precheck --force-reprocess contract.pdf    # Bypass cache

# Review (PAKTON 3-agent pipeline)
openreview precheck review contract.pdf                # Extract + QA pipeline
openreview precheck review contract.pdf --format json  # JSON report
openreview precheck review contract.pdf --output report.json  # Save to file
openreview precheck review --playbook-path custom.yaml contract.pdf  # Custom YAML playbook
openreview precheck review --playbook my-terms contract.pdf          # DB-stored playbook (latest version)
openreview precheck review --extraction-model fast --qa-model accurate contract.pdf  # Separate model slots
openreview precheck review --no-pii contract.pdf       # Skip PII stripping
openreview precheck review --grounding-mode strict contract.pdf  # Strict grounding (excludes ungrounded claims)
openreview precheck review --grounding-mode lenient contract.pdf # Lenient grounding (flags ungrounded)
openreview precheck review --no-grounding contract.pdf  # Skip citation grounding entirely
openreview precheck review --confidence-threshold 0.9 contract.pdf  # Raise threshold (more Amber flags)
openreview precheck review --confidence-threshold 0.3 contract.pdf  # Lower threshold (fewer Amber flags)
openreview precheck review --verbose contract.pdf      # Show per-clause progress
openreview precheck review doc1.pdf doc2.pdf doc3.pdf  # Batch review

# Memo export (structured review output)
openreview precheck review --memo-format md contract.pdf                         # Markdown memo
openreview precheck review --memo-format md --memo-format json contract.pdf      # Markdown + JSON
openreview precheck review --memo-format docx --output-dir ./memos contract.pdf  # DOCX to custom dir

# Experimental Bilateral Comparison (compare two NDAs side-by-side)
openreview precheck compare my-nda.pdf their-nda.pdf                    # Divergence report
openreview precheck compare my-nda.pdf their-nda.pdf --verbose           # Full RCBSF classification
openreview precheck compare my-nda.pdf their-nda.pdf --conservative      # Max sensitivity (threshold 0.8)
openreview precheck compare my-nda.pdf their-nda.pdf --confidence-threshold 0.9  # Custom threshold
openreview precheck compare my-nda.pdf their-nda.pdf --align-only        # Preview alignment, skip inference
openreview precheck compare my-nda.pdf their-nda.pdf --format json       # JSON output
openreview precheck compare my-nda.pdf their-nda.pdf --no-pii            # Skip PII stripping

# Game-theoretic negotiation (advisory only)
openreview negotiate contract.pdf --playbook-path playbook.yaml                          # QRE solver (default)
openreview negotiate contract.pdf --playbook-path playbook.yaml --solver nash            # Perfect-rationality Nash
openreview negotiate contract.pdf --playbook-path playbook.yaml --solver level_k         # Level-k reasoning
openreview negotiate contract.pdf --playbook-path playbook.yaml --solver qre --rationality 1.5  # Tune bounded rationality
openreview negotiate contract.pdf --playbook-path playbook.yaml --depth 3               # Level-k depth
openreview negotiate contract.pdf --playbook-path playbook.yaml --weights 0.7,0.15,0.15  # Custom payoff weights
openreview negotiate contract.pdf --playbook-path playbook.yaml --confidence-threshold 0.5  # Lower Amber threshold
openreview negotiate contract.pdf --playbook-path playbook.yaml --format json            # JSON output
openreview negotiate contract.pdf --playbook-path playbook.yaml --format memo            # Narrative memo
openreview negotiate contract.pdf --playbook-path playbook.yaml --output report.txt      # Save to file
openreview negotiate contract.pdf --playbook-path playbook.yaml --no-pii                  # Skip PII stripping
openreview negotiate contract.pdf --playbook-path playbook.yaml --verbose                 # Per-clause progress

# PII management
openreview pii list              # Documents with PII data
openreview pii delete abc123     # Delete PII data for a document
openreview pii cleanup           # Delete expired PII data

# AI Gateway (v2)
openreview gateway setup                # JSON-stdin setup (pipe JSON to stdin)
openreview gateway setup --dry-run      # Validate JSON without writing files
openreview gateway status               # Show configured slots and providers
openreview gateway status --format json # Machine-readable status
openreview gateway providers            # List supported providers
openreview gateway models openai        # List models for a provider
openreview gateway set reasoning gpt-4o # Assign model to a slot (supports short-name resolution)
openreview gateway test reasoning       # Send a test request
openreview gateway costs --today        # Show daily cost summary
openreview gateway costs --today --format json  # JSON cost report
openreview gateway refresh              # Refresh model registry
openreview models available             # Discover models reachable with current keys
openreview models available --provider openai  # Filter by provider
openreview auth add openrouter sk-or-...       # Store API key (keyring or file)
openreview auth list                           # List configured providers with key metadata
openreview auth remove openrouter              # Remove a provider's API key
openreview auth add custom sk-custom --base-url https://my-endpoint.example.com  # Custom provider
openreview migrate config                      # Migrate v1 → v2 config format
openreview migrate config --dry-run            # Preview migration without writing
openreview set reasoning gpt-4o                # Set slot with short-name resolution (alias for gateway set)

# Prompt management
openreview prompt create --name extract-clauses --content "Extract clauses..." --description "Clause extraction" --tags "extraction,default"
openreview prompt update extract-clauses --content "Improved prompt..."
openreview prompt list
openreview prompt show extract-clauses --version 1
openreview prompt diff extract-clauses --from 1 --to 2
openreview prompt delete extract-clauses --force
openreview prompt bind --slot extraction --prompt extract-clauses --version 2
openreview prompt unbind --slot extraction
openreview prompt bindings
openreview prompt history extract-clauses
openreview prompt export extract-clauses --output /tmp/prompts.yaml
openreview prompt import /tmp/prompts.yaml
openreview prompt test --prompt extract-clauses --versions 1,2 --benchmark standard
openreview prompt optimize --prompt extract-clauses --iterations 3

# Playbook management (versioned database storage)
openreview playbook import my-terms.yaml              # Import a YAML playbook into the database
openreview playbook list                              # List all playbooks with their latest version
openreview playbook show my-terms 1                   # Show a specific playbook version
openreview playbook export my-terms --output terms.yaml   # Export a playbook to YAML
openreview playbook diff my-terms 1 2                    # Structural diff between versions
openreview playbook set-current my-terms 2               # Set the effective current version
openreview playbook delete my-terms                      # Soft-delete a playbook (tombstone)
openreview playbook history my-terms                     # Show version timeline

# Review with a database-sourced playbook (version-stamped)
openreview precheck review --playbook my-terms contract.pdf  # Load latest version from DB
openreview precheck review --playbook-path custom.yaml contract.pdf  # File-based (takes precedence)

# Benchmark (automated evaluation)
openreview benchmark                              # Smoke test (CUAD, default slot)
openreview benchmark --datasets cuad,maud --slots default,fast  # Multi-dataset
openreview benchmark --all --ci --compare HEAD~1  # CI regression gate
openreview benchmark --pii-only                   # PII recall/precision only
openreview benchmark run --modes precheck,dealcheck              # Validate modes against 22-mode whitelist
openreview benchmark run --modes invalid_mode                    # Error: exit 78, lists valid modes
openreview benchmark baseline --modes precheck,licensecheck      # Accuracy baseline (mock provider, CI-safe)
openreview benchmark baseline --modes precheck --provider live   # Real provider baseline (requires configured AI gateway)
openreview benchmark baseline --modes precheck --format json --output baseline.json  # Save report to file
openreview benchmark baseline --modes all --format json --output baseline.json --save-baseline  # Official regression baseline
openreview benchmark --prompt-variant v1 --prompt-variant v2  # A/B prompt test
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
| `openreview chunk <path>`              | Split clauses into retrieval-ready chunks (512 tokens, 50 overlap) |
| `openreview chunk <path> --format json`| JSON chunk output with structural metadata  |
| `openreview chunk <path> --summary`    | One-line chunk summary (count, token range) |
| `openreview ingest <path>`             | Parse, chunk, embed, and index a document for retrieval |
| `openreview retrieve "<query>" <path>` | Hybrid search (BM25 + dense + RRF fusion)  |
| `openreview retrieve --method sparse <query> <path>`  | BM25-only search                 |
| `openreview retrieve --method dense <query> <path>`   | Dense embedding search            |
| `openreview retrieve --rerank <query> <path>`         | Enable cross-encoder reranking   |
| `openreview retrieve --no-header <query> <path>`      | Omit table header from output    |
| `openreview index-status <path>`       | Show index metadata               |
| `openreview index-clear <path>`        | Remove document index             |
| `openreview precheck <path>`           | NDA review with automatic PII stripping    |
| `openreview licensecheck <path>`       | SaaS license agreement review (LicenseCheck) |
| `openreview leasecheck <path>`         | Commercial lease agreement review (LeaseCheck) |
| `openreview privacycheck <path>`       | Data Processing Agreement review (PrivacyCheck) |
| `openreview dealcheck <path>`          | Vendor/service agreement review (DealCheck) |
| `openreview hirecheck <path>`          | Employment agreement review (HireCheck) |
| `openreview indemnitycheck <path>`     | Indemnification agreement review (IndemnityCheck) |
| `openreview consultcheck <path>`       | Consulting services agreement review (ConsultCheck) |
| `openreview workcheck <path>`          | Independent contractor/work-for-hire review (WorkCheck) |
| `openreview loicheck <path>`           | Letter of intent / MOU review (LOICheck) |
| `openreview subcheck <path>`           | Subcontractor agreement review (SubCheck) |
| `openreview settlementcheck <path>`    | Settlement / release agreement review (SettlementCheck) |
| `openreview assetcheck <path>`         | Asset transfer agreement review (AssetCheck) |
| `openreview buycheck <path>`           | Asset purchase agreement review (BuyCheck) |
| `openreview engagecheck <path>`        | Engagement letter review (EngageCheck) |
| `openreview guaranteecheck <path>`     | Personal guarantee review (GuaranteeCheck) |
| `openreview loancheck <path>`          | Loan agreement review (LoanCheck) |
| `openreview franchisecheck <path>`     | Franchise agreement review (FranchiseCheck) |
| `openreview opcheck <path>`            | Operating agreement review (OpCheck) |
| `openreview partnercheck <path>`       | Partnership agreement review (PartnerCheck) |
| `openreview sponsorcheck <path>`       | Sponsorship agreement review (SponsorCheck) |
| `openreview distrocheck <path>`        | Distribution agreement review (DistroCheck) |
| `openreview precheck --no-pii <path>`  | NDA review, skip PII (raw text in output)  |
| `openreview precheck review <paths...>`| PAKTON 3-agent review (extraction + QA + report) against a playbook |
| `openreview precheck review --playbook <id> <paths>` | Review with the latest version of a database-stored playbook (version-stamped report) |
| `openreview precheck review --playbook-path <file> <paths>` | Review with a custom YAML playbook file (takes precedence over `--playbook`) |
| `openreview precheck review --format json <paths>`     | JSON-format review report (default: text) |
| `openreview precheck review --output <file> <paths>`   | Write report to file instead of stdout    |
| `openreview precheck review --extraction-model <slot> --qa-model <slot> <paths>` | Independent model slots for extraction and QA |
| `openreview precheck review --no-pii <paths>`| Skip PII stripping in review pipeline     |
| `openreview precheck review --grounding-mode strict <paths>` | Strict grounding (exclude ungrounded claims from output) |
| `openreview precheck review --grounding-mode lenient <paths>` | Lenient grounding (flag ungrounded claims, keep in output) |
| `openreview precheck review --no-grounding <paths>` | Skip citation grounding entirely |
| `openreview precheck review --verbose <paths>` | Show per-clause progress on stderr      |
| `openreview precheck review --confidence-threshold <0.0-1.0> <paths>` | Threshold for Green/Amber/Red assignment (default 0.7) |
| `openreview precheck review --memo-format <fmt> <path>` | Export structured memo (md, json, docx). Repeat for multiple formats. |
| `openreview precheck review --output-dir <dir> <path>` | Directory for memo files (default: `review_results/`) |
| `openreview precheck compare <docA> <docB>` | [Experimental] Compare two documents clause-by-clause, detect divergences |
| `openreview precheck compare --verbose <docA> <docB>` | Show full RCBSF 5-dimension classification and rationale |
| `openreview precheck compare --conservative <docA> <docB>` | Max sensitivity, shortcut for `--confidence-threshold 0.8` |
| `openreview precheck compare --confidence-threshold <0.0-1.0> <docA> <docB>` | Custom Amber boundary for divergence confidence (default 0.7) |
| `openreview precheck compare --align-only <docA> <docB>` | Parsing + alignment only, skip all inference |
| `openreview precheck compare --format json <docA> <docB>` | Structured JSON comparison report |
| `openreview precheck compare --output <file> <docA> <docB>` | Write report to file |
| `openreview negotiate <path> --playbook-path <yaml>` | Advisory game-theoretic negotiation analysis (QRE solver) |
| `openreview negotiate <path> --playbook-path <yaml> --solver nash` | Perfect-rationality Nash equilibrium solver |
| `openreview negotiate <path> --playbook-path <yaml> --solver level_k` | Level-k bounded-reasoning solver |
| `openreview negotiate <path> --playbook-path <yaml> --solver qre --rationality 1.5` | Tune QRE bounded-rationality parameter (λ) |
| `openreview negotiate <path> --playbook-path <yaml> --depth 3` | Set level-k reasoning depth |
| `openreview negotiate <path> --playbook-path <yaml> --weights 0.7,0.15,0.15` | Custom payoff component weights (risk,financial,obligation) |
| `openreview negotiate <path> --playbook-path <yaml> --confidence-threshold 0.5` | Lower Amber-flag threshold |
| `openreview negotiate <path> --playbook-path <yaml> --format json` | JSON output |
| `openreview negotiate <path> --playbook-path <yaml> --format memo` | Narrative memo output |
| `openreview negotiate <path> --playbook-path <yaml> --output <file>` | Write output to file |
| `openreview negotiate <path> --playbook-path <yaml> --no-pii` | Skip PII stripping |
| `openreview negotiate <path> --playbook-path <yaml> --verbose` | Per-clause progress on stderr |
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
| `openreview prompt create --name <n> --content <c>` | Create version 1 of a new prompt  |
| `openreview prompt update <name> --content <c>`     | Create new version (auto-increment) |
| `openreview prompt list`               | Show all prompts with latest version       |
| `openreview prompt show <name>`        | View a specific prompt version             |
| `openreview prompt delete <name>`      | Remove a prompt and all versions           |
| `openreview prompt diff <name> --from <v1> --to <v2>` | Unified diff between versions |
| `openreview prompt bind --slot <s> --prompt <n> --version <v>` | Bind prompt version to model slot |
| `openreview prompt unbind --slot <s>`  | Remove a binding                           |
| `openreview prompt bindings`           | List all active bindings                   |
| `openreview prompt history <name>`     | Show version history with metadata         |
| `openreview prompt export <name>`      | Export prompt(s) to YAML                   |
| `openreview prompt import <path>`      | Import prompts from YAML                   |
| `openreview prompt test --prompt <n> --versions <v1,v2>` | A/B test (requires benchmark) |
| `openreview prompt optimize --prompt <n> --iterations <i>` | GRPO optimization (requires benchmark) |
| `openreview playbook import <path>`  | Import a YAML playbook into the local database (append-only versioning) |
| `openreview playbook list`           | List all playbooks with latest version and description |
| `openreview playbook show <id> <version>` | Show the full content of a specific playbook version |
| `openreview playbook export <id> --output <file>` | Export a playbook version to a YAML file |
| `openreview playbook diff <id> <v1> <v2>`        | Structural diff between two playbook versions |
| `openreview playbook set-current <id> <v>`         | Set the effective current version (re-activates if deleted) |
| `openreview playbook delete <id>`              | Soft-delete a playbook (tombstone, restorable) |
| `openreview playbook history <id>`             | Show version timeline with status markers |
| `openreview graph build <input>`          | Build a directed clause graph from a parsed contract JSON file |
| `openreview graph build <input> -o <out>` | Build with custom output path                |
| `openreview graph metrics <graph>`        | Compute structural metrics: density, depth, orphan ratio, broken cross-refs, definition coverage |
| `openreview graph health <graph>`         | Compute a 0–100 heuristic health score (default weights: density 0.15, depth 0.20, orphans 0.20, broken-refs 0.25, coverage 0.20) |
| `openreview graph health --weights '...' <graph>` | Custom weights (5 space-separated floats, auto-normalised) |
| `openreview graph view <graph>`           | Render the clause hierarchy as an indented ASCII tree |
| `openreview benchmark`                    | Run automated evaluation (CUAD/MAUD/ContractNLI) |
| `openreview benchmark --datasets cuad,maud` | Evaluate specific datasets                   |
| `openreview benchmark run --modes precheck,dealcheck` | Run benchmark for specific modes (validated against 22-mode whitelist) |
| `openreview benchmark --slots default,fast` | Compare model slots                          |
| `openreview benchmark --all --ci`          | Full CI regression gate (strict exit codes)   |
| `openreview benchmark --compare HEAD~1`    | Compare against a baseline ref               |
| `openreview benchmark --pii-only`          | PII recall/precision benchmark only           |
| `openreview benchmark baseline`            | Accuracy baseline across modes/datasets (mock provider) |
| `openreview benchmark baseline --provider live` | Real provider accuracy baseline           |
| `openreview benchmark baseline --format json --output baseline.json --save-baseline` | Save official baseline |
| `openreview benchmark --prompt-variant v1 --prompt-variant v2` | Prompt A/B test |
| `openreview benchmark --format json --output report.json` | JSON report to file |

### AI Gateway v2 (Spec 033)

The AI Gateway was redesigned in spec 033 to be fully agent-friendly, adding:

- **JSON-stdin setup** — Pipe a JSON config to `openreview gateway setup` for non-interactive configuration. Supports `--dry-run` for validation.
- **Short-name resolution** — Set slots with model short names like `gpt-4o` instead of `openai/gpt-4o`. The resolver auto-selects the best configured provider.
- **Model discovery** — `openreview models available` lists only models whose providers have API keys configured, with optional `--provider` filter.
- **Structured output** — All gateway commands support `--format json` for machine-parseable output with consistent error objects.
- **OS keyring storage** — API keys stored in the OS keyring with transparent fallback to `auth.json` (chmod 600). `openreview auth add/list/remove` commands.
- **Config migration** — v1 → v2 format migration via `openreview migrate config`. Preserves slot assignments and auth.json.
- **Cost tracking** — Historical cost queries with `--today`, `--session`, `--since` filters and JSON output.
- **Grounding slot** — Full `set grounding`, `test grounding`, and status display for the 6th model slot.
- **Custom providers** — `openreview auth add --base-url` supports self-hosted OpenAI-compatible endpoints.
- **V2 config format** — Provider-first YAML with `version: 2`, `providers`, `slots`, `fallback`, and `cost_limits` sections.

See [specs/033-ai-gateway-v2/spec.md](specs/033-ai-gateway-v2/spec.md) for the full specification.

```bash
# Quick start: setup gateway with JSON
echo '{"version":2,"providers":{"openai":{"name":"openai","env_key":"OPENAI_API_KEY","api_key_source":"file"}},"slots":{"reasoning":{"provider":"openai","model":"gpt-4o"}}}' | openreview gateway setup --dry-run

# Discover available models
openreview models available

# Set a slot with short-name resolution
openreview set reasoning gpt-4o

# Store API key
openreview auth add openai sk-...

# Query costs
openreview gateway costs --today --format json
```

## Configuration

Config lives at `config.yml` (platformdirs: `~/.config/openreview/` on Linux).
Secrets (API keys) live in `auth.json` at the same path.

| Section              | What it controls              | Example keys                       |
|----------------------|-------------------------------|------------------------------------|
| `privacy`            | PII stripping, log retention, privacy tier routing  | `tier` (maximum/balanced/performance), `strip_pii`, `log_ttl_days`|
| `gateway.models`     | LLM provider/model per task   | `reasoning.primary`, `extraction.params.temperature`, `reasoning.extra_params` |
| `gateway.fallback`   | Retry and timeout behavior    | `retries`, `timeout`, `on_failure` |
| `gateway.cost_limits`| Spending caps                 | `per_review_cents`, `daily_cents`  |
| `storage`            | Data retention                | `reviews_keep_forever`, `logs_keep_days` |

### Privacy tier routing

The `privacy.tier` setting controls how the AI Gateway routes requests, balancing
privacy guarantees against performance:

| Tier | Routing rule | Best for |
|------|--------------|----------|
| **Maximum** (default) | All operations use local providers only. Cloud calls are blocked. PII fail-closed: cloud embedding and reasoning are unavailable if the PII engine cannot strip sensitive data. | Strictest privacy — no data leaves your machine. |
| **Balanced** | Embeddings run locally (Ollama). Reasoning can use cloud providers, but PII is stripped before any cloud API call. | Privacy-focused workflows that benefit from cloud-grade reasoning on scrubbed text. |
| **Performance** | Embeddings and reasoning both use cloud providers. PII is still stripped before cloud API calls. | Maximum speed — cloud inference for everything, with automated PII redaction. |

The `TierRouter` wraps the Gateway and enforces these rules before every chat,
embedding, or rerank call. Invalid tier values in `config.yml` log a warning and
default to **Maximum**.

```bash
# Configure the tier
openreview config set privacy.tier balanced
openreview config get privacy.tier
```

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
| Benchmark        | `uv run openreview benchmark --all --ci`          |
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

### Benchmark harness (`openreview benchmark`)

Automated evaluation against standard legal contract datasets:

| Metric | What it measures |
|--------|------------------|
| Extraction F1 / precision / recall | Clause extraction quality vs CUAD/MAUD/ContractNLI ground truth |
| PII recall / precision | PII detection accuracy against labeled corpora |
| Hallucination rate | Factual accuracy of AI-generated findings |
| Latency | End-to-end processing time per contract |
| Memory | Peak RSS during evaluation |

```bash
# Quick smoke test
openreview benchmark

# Full evaluation across all datasets and model slots
openreview benchmark --all

# CI regression gate (fails on F1 drop > 2pp vs baseline)
openreview benchmark --all --ci --compare HEAD~1
```

### Product mode benchmark script

A standalone benchmark for all 22 product-mode pipelines:

```bash
uv run python scripts/benchmark_product_modes.py
```

Tests each mode against a synthetic contract, runs extraction + QA, and
reports per-mode timing, token usage, and pass/fail status. PII benchmark notes
are documented alongside the script.

#### Product mode benchmark results

Deterministic oracle run (monkeypatched gateway — tests pipeline correctness, not live model accuracy):

| Mode | Docs | Expected Cats | Matched | Recall | Time (s) | Peak Mem |
|------|------|--------------|---------|--------|----------|----------|
| indemnitycheck | 5 | 10 | 10 | 1.0 | 30.65 | 87 KB |
| consultcheck | 5 | 10 | 10 | 1.0 | 0.56 | 89 KB |
| workcheck | 5 | 10 | 10 | 1.0 | 0.56 | 101 KB |
| loicheck | 5 | 10 | 10 | 1.0 | 0.58 | 89 KB |
| subcheck | 5 | 10 | 10 | 1.0 | 0.56 | 133 KB |
| settlementcheck | 5 | 10 | 10 | 1.0 | 0.58 | 88 KB |
| licensecheck | 5 | 10 | 10 | 1.0 | 0.92 | 100 KB |
| leasecheck | 5 | 10 | 10 | 1.0 | 0.93 | 98 KB |
| privacycheck | 5 | 10 | 10 | 1.0 | 0.82 | 98 KB |
| assetcheck | 5 | 10 | 10 | 1.0 | 0.91 | 95 KB |
| buycheck | 5 | 10 | 10 | 1.0 | 0.93 | 97 KB |
| engagecheck | 5 | 10 | 10 | 1.0 | 0.87 | 99 KB |
| guaranteecheck | 5 | 10 | 10 | 1.0 | 0.89 | 96 KB |
| loancheck | 5 | 10 | 10 | 1.0 | 0.94 | 98 KB |

Note: IndemnityCheck 30.65s includes PyMuPDF module warmup; real per-doc time ~0.6s. All 14 modes use a mocked AI gateway — measures pipeline correctness, not live model accuracy. AssetCheck, BuyCheck, EngageCheck, GuaranteeCheck, and LoanCheck added in spec 029. Spec 030 added mode whitelist validation to the benchmark CLI (unknown mode → exit 78) and the `benchmark baseline` subcommand. FranchiseCheck, OpCheck, PartnerCheck, SponsorCheck, and DistroCheck added in spec 031. All 22 modes now have mock baselines in `docs/benchmarks/`; real-provider baselines tracked separately.

See [specs/010-benchmark-harness/](specs/010-benchmark-harness/) for the full specification, or run `openreview benchmark --help` for all options.

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
