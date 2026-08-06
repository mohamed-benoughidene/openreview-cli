![openreview-cli](assets/ChatGPT%20Image%20Aug%203,%202026,%2007_05_28%20PM.png)
# openreview-cli

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](https://github.com/mohamed-benoughidene/openreview-cli) [![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/LICENSE) [![status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)](https://github.com/mohamed-benoughidene/openreview-cli)

Privacy-first contract review automation CLI. Local-first, multi-agent AI that strips PII before any cloud call. Parse, review, and negotiate contracts through an AI Gateway spanning 17 providers all from the command line.

## What is openreview-cli?

openreview-cli is a local-first, privacy-first contract review automation tool that runs entirely from the command line. It parses contract documents, strips personally identifiable information before any cloud call, reviews clauses through a multi-agent pipeline, and emits a structured memo. It runs fully locally by default, with cloud providers and privacy tiers available as explicit opt-in.

## Why it matters

- **PII stripped locally before cloud:** the pipeline is fail-closed if page-level detection fails, the review halts rather than leak.
- **Local-first by default:** Ollama (`qwen3` reasoning, `nomic-embed-text` embeddings) out of the box; cloud providers are opt-in per slot.
- **Multi-agent review pipeline:** extraction → QA verification → citation grounding, not one monolithic prompt.
- **21 contract-type modes** with bundled 3-position playbooks (Preferred / Acceptable / Walkaway).
- **Dual human/agent interface:** Typer CLI + Textual TUI for humans; Python API + JSON output for agents.
- **Spec-driven development:** 33 specs, all tracked in `specs/`.

## Quickstart

Install from PyPI (Python ≥ 3.12):

```bash
pip install openreview-cli

# One-time: configure the AI Gateway (local Ollama by default)
openreview gateway setup

# Review a contract
openreview precheck review contract.pdf
```

### From source (contributors)

```bash
git clone https://github.com/mohamed-benoughidene/openreview-cli.git
cd openreview-cli && git submodule update --init && uv sync

# One-time: configure the AI Gateway (local Ollama by default)
uv run openreview gateway setup

# Review a contract
uv run openreview precheck review contract.pdf

# Memo written to review_results/ (Markdown, JSON, or DOCX)
```

## Measured results

| Area | Value |
|---|---|
| Version | 0.1.1 (pre-alpha) |
| Tests | 2,725 collected (10 markers) |
| Gateway | 17 providers, 27 models |
| Contract modes | 21 |
| Startup | 0.68 s median, ~43 MB RSS |
| Review accuracy | 90.9% F1 (12 NDA clauses, claude-sonnet-4.6 via OpenRouter) |
| CUAD clause identification | 100% sentence boundary recall (462 contracts, 4,034 queries) |
| PII detection | 52.8% recall on 50 seeded contracts (spaCy `en_core_web_lg`) |

Full methodology + raw numbers + measured-vs-unmeasured: [BENCHMARKS.md](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/BENCHMARKS.md).

### What was measured

- **Review accuracy**: 90.9% F1 on 12 labeled NDA clauses (Claude Sonnet 4.6 via OpenRouter)
- **Clause detection**: 100% sentence boundary recall on CUAD v1 (462 real commercial contracts, 4,034 queries)
- **PII detection**: 52.8% recall on 50 seeded contracts (spaCy en_core_web_lg)
- **Startup**: 0.68 s median, ~43 MB RSS
- **Honest gaps documented**: what is NOT measured (e.g. retrieval on raw PDFs, end-to-end pipeline accuracy) is called out explicitly in [BENCHMARKS.md](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/BENCHMARKS.md)

## How it works

An async pipeline splits a contract into clauses, strips PII behind a fail-closed gate, and runs each clause through keyword match (no LLM), an extraction agent, a QA verification agent, and a citation-grounding discriminator before emitting a memo. The AI Gateway abstracts 17 providers through litellm with fallback, cost tracking, privacy tier routing, and API-key redaction. State lives in a single SQLite database, with per-document retrieval indexes alongside. → [ARCHITECTURE.md](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/ARCHITECTURE.md)

### Architecture at a glance

- **Pipeline**: parse → PII strip (fail-closed) → clause split → per-clause multi-agent review (keyword match, extraction agent, QA verification, citation grounding) → structured memo
- **AI Gateway**: one litellm abstraction (chat / embed / rerank) across 17 providers, 27 bundled models, local Ollama by default
- **Storage**: single SQLite DB (reviews, cost logs, PII cache, playbooks, benchmarks) + per-document FTS5 retrieval indexes with RRF fusion
- **Privacy**: three tiers (Maximum / Balanced / Performance); nothing leaves the machine unless you opt in

Full architecture: [ARCHITECTURE.md](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/ARCHITECTURE.md)

## Features by capability

### Document processing

PyMuPDF page-by-page streaming parser (never loads the full PDF) plus python-docx for DOCX. Clause detection via 7 regex patterns + nupunkt sentence segmentation. Metadata extraction, corrupt/empty/password detection, non-English and tofu (broken glyph) detection. Streaming keeps memory bounded regardless of document length.

### Privacy & PII

Presidio PII engine with spaCy `en_core_web_lg` plus 4 custom regex recognizers (AMOUNT, TAX_ID, ID_DOCUMENT, REG_NUMBER). **Fail-closed by default:** if page-level detection fails, the pipeline halts before any cloud call raises `PartialProcessingError`; opt out with `--allow-partial-pii`. Entities are replaced with `[PARTY_A]`-style placeholders; the reversible mapping is encrypted with Fernet (AES-128-CBC + HMAC, key via HKDF-SHA256) and stored chmod 600. Privacy tiers (Maximum / Balanced / Performance) control what leaves the machine.

### AI Gateway

A single litellm abstraction: `chat → completion`, `embed → embedding`, `rerank → rerank`. 17 providers (openai, anthropic, google, openrouter, cohere, huggingface, deepseek, qwen, minimax, voyage, moonshot, mistral, zai, bedrock, azure, vertex, ollama). 27 bundled models with default config pointing at local Ollama (`qwen3:8b`, `qwen3:4b`, `nomic-embed-text`). Per-slot fallback (2 retries, 60 s timeout), cost tracking to SQLite `cost_logs` (cents via `litellm.completion_cost`, non-fatal on error), configurable per-review/per-day limits (100¢/1,000¢ defaults, warn-only). API-key pattern redaction on all log output. Streaming with 15 s connect / 45 s idle timeouts.

### Multi-agent review

Per-clause pipeline: keyword category match (no LLM) → extraction agent (LLM, outputs position + confidence + citation) → QA verification agent (LLM, agree/disagree/uncertain verdict, amber flag) → citation grounding discriminator (LLM, claim-vs-source verification, strict/lenient modes). 24 bundled playbooks across 21 modes. 3-position model: Preferred / Acceptable / Walkaway. 3-color confidence output: Green / Amber / Red with configurable threshold.

### Analysis tools

- **Game-theoretic negotiation** (`openreview negotiate`): pure local NumPy Nash (support enumeration), QRE (logit fixed-point), Level-k (k ≤ 3) solvers. No LLM calls.
- **Bilateral comparison** (`precheck compare`): experimental RCBSF 5-dimension divergence detection, 3-tier heading alignment, ≤64% F1 ceiling (documented).
- **Contract graph** (`openreview graph`): directed clause graph, 0–100 health score from 5 structural metrics, optional legal-bert + HDBSCAN clustering, ASCII tree view, graph diff.

### Storage & retrieval

Single SQLite database (20 tables: reviews, cost_logs, PII cache, playbooks, benchmarks, graph data, recovery state). Per-document retrieval indexes in separate SQLite files with FTS5 (BM25 unicode61, prefix 2–3) + dense embeddings (brute-force cosine scan, no vector DB honest limitation) + RRF fusion (k=60). Reranker present but disabled by default (degrades legal text); opt-in with `--rerank`.

## Contract-type modes

| Mode | What it reviews |
|---|---|
| precheck | Non-Disclosure Agreement (NDA) |
| licensecheck | SaaS/software license agreement |
| leasecheck | Commercial lease agreement |
| privacycheck | Data Processing Agreement (DPA) |
| dealcheck | Vendor/service agreement |
| hirecheck | Employment agreement |
| indemnitycheck | Indemnification agreement |
| consultcheck | Consulting services agreement |
| workcheck | Independent contractor/work-for-hire agreement |
| loicheck | Letter of intent or MOU |
| subcheck | Subcontractor agreement |
| settlementcheck | Settlement/release agreement |
| assetcheck | Asset transfer/assignment agreement |
| buycheck | Asset purchase/business acquisition agreement |
| engagecheck | Professional services engagement letter |
| guaranteecheck | Personal guarantee/suretyship agreement |
| loancheck | Loan agreement/promissory note |
| franchisecheck | Franchise agreement or franchise disclosure document |
| opcheck | Operating Agreement (LLC governance document) |
| partnercheck | General or limited partnership agreement |
| sponsorcheck | Sponsorship agreement |
| distrocheck | Distribution or reseller agreement |

Each mode has a bundled 3-position playbook and mode-specific prompt vocabulary.

## Privacy tiers

| Tier | PII processing | Reasoning | Embedding | Description |
|---|---|---|---|---|
| Maximum | All local (fail-closed) | Local (Ollama) | Local | Nothing leaves the machine |
| Balanced (default) | All local (fail-closed) | Cloud (OpenRouter, OpenAI…) | Local | PII stripped, reasoning in cloud |
| Performance | All local (fail-closed) | Cloud | Cloud | PII stripped, all inference in cloud |

Configure with `openreview config set privacy.tier maximum|balanced|performance` or env var `OPENREVIEW_PRIVACY_TIER`.

## Essential commands

```
parse          → inspect clauses in a PDF/DOCX
precheck review → run full review (parse → PII strip → extract → QA → memo)
gateway setup  → configure AI providers (one-time)
gateway test   → verify each slot can connect
negotiate      → run game-theoretic negotiation analysis
export         → batch-export saved review reports
```

Run `openreview --help` for all 77 subcommands. No args launches the Textual TUI.

## FAQ

**Does openreview-cli send contract text to the cloud?**

No not by default. PII is stripped locally by Presidio before any cloud call. The pipeline is fail-closed: if a page-level detection fails, the review halts immediately (use `--allow-partial-pii` to opt out). Cloud providers are opt-in per slot.

**Can it run fully offline?**

Yes. The default gateway configuration points at local Ollama models (`qwen3:8b` reasoning, `qwen3:4b` extraction, `nomic-embed-text` embeddings). Set the privacy tier to Maximum to guarantee nothing leaves the machine.

**How accurate is it?**

Measured against public benchmarks: 90.9% F1 on contract clause review (12 labeled NDA clauses through Claude Sonnet 4.6), 100% sentence boundary recall on CUAD v1 (462 real commercial contracts), 52.8% PII recall on 50 seeded contracts. All numbers, methodology, and unmeasured gaps in [BENCHMARKS.md](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/BENCHMARKS.md).

**What can AI agents do with it?**

Every module is independently importable as a Python library (`from openreview_cli.parsing.stream import parse_document`, `from openreview_cli.review.extraction import extract_clause`). The CLI supports `--format json` and `--output` for structured output. The benchmark runner (`BenchmarkRunner`) and pipeline (`run_review`) are Python-callable with typed return values.

**What file formats are supported?**

PDF (PyMuPDF, page-by-page streaming, password-protected, corrupt/empty detection) and DOCX (python-docx, track-changes, images, flat documents).

**Is openreview-cli free?**

Open source under AGPL-3.0 ([LICENSE](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/LICENSE)). A commercial license option is available ([COMMERCIAL_LICENSE.md](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/COMMERCIAL_LICENSE.md)).

## Tech stack / Licenses / Status

Python 3.12 · Typer CLI · Textual TUI · Presidio (PII) · litellm (gateway) · PyMuPDF / python-docx (parsing) · SQLite + FTS5 (storage, BM25) · numpy / scikit-learn (embeddings, solvers) · torch / transformers (CPU-only) · nupunkt · pydantic · cryptography · rich · jinja2 · httpx · pyyaml. Dev: pytest, mypy (strict), ruff.

AGPL-3.0-only, with a commercial license option (see [LICENSE](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/LICENSE) and [COMMERCIAL_LICENSE.md](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/COMMERCIAL_LICENSE.md)).

Pre-alpha. Measured performance, accuracy, and methodology in [BENCHMARKS.md](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/BENCHMARKS.md).

[Architecture](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/ARCHITECTURE.md) · [Benchmarks](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/BENCHMARKS.md) · [Issues](https://github.com/mohamed-benoughidene/openreview-cli/issues) · [Discussions](https://github.com/mohamed-benoughidene/openreview-cli/discussions)
