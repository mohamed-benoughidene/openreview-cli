![openreview-cli](assets/ChatGPT%20Image%20Aug%203,%202026,%2007_05_28%20PM.png)

# openreview-cli

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://github.com/mohamed-benoughidene/openreview-cli) [![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](https://github.com/mohamed-benoughidene/openreview-cli/blob/main/LICENSE) [![status: alpha](https://img.shields.io/badge/status-alpha-orange)](https://github.com/mohamed-benoughidene/openreview-cli)

Privacy-first contract review automation CLI. Local-first, multi-agent AI that strips PII before any cloud call. Parse, review, and negotiate contracts through an AI Gateway spanning 17 providers, all from the command line.

## What it is

openreview-cli runs entirely from the command line. It parses a contract, strips personally identifiable information before anything leaves your machine, reviews each clause through a multi-agent pipeline, and writes a structured memo. Every model slot ships pointed at local Ollama, so a default run makes no cloud calls. Set `privacy.tier` to `maximum` to hard-enforce local-only.

## Status: alpha

The core pipeline works and is tested (3,499 tests). Two numbers matter most if you're deciding whether to trust it with real documents right now.

- Review accuracy: 90.9% F1 on 12 labeled NDA clauses (Claude Sonnet 4.6 via OpenRouter)
- PII detection: 94.4% recall on 50 seeded contracts (spaCy `en_core_web_lg`)

That second number is measured on an artificially generated test set, so treat it as a synthetic-data baseline rather than a promise about real contracts. The pipeline is fail-closed, meaning it halts rather than proceed if page-level detection fails outright, but fail-closed is not the same as perfect recall. Read the full methodology and the honest list of what's not yet measured before using this on anything sensitive: [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

## Quickstart

```bash
pip install openreview-cli

# One-time: configure the AI Gateway (local Ollama by default)
openreview gateway setup

# Review a contract
openreview precheck review contract.pdf

# No args launches the Textual TUI
openreview
```

<details>
<summary>From source (contributors)</summary>

```bash
git clone https://github.com/mohamed-benoughidene/openreview-cli.git
cd openreview-cli && git submodule update --init && uv sync

uv run openreview gateway setup
uv run openreview precheck review contract.pdf
uv run openreview
```

Memo written to `review_results/` as Markdown, JSON, or DOCX.

</details>

## Why local-first

- **Fail-closed by design.** If page-level PII detection fails, the review halts instead of proceeding partially stripped.
- **Local by default.** Every model slot defaults to Ollama (`qwen3` reasoning, `nomic-embed-text` embeddings). Swap any slot to a different local or cloud model.
- **Three privacy tiers** control exactly what, if anything, leaves the machine.

| Tier | PII | Reasoning | Embedding |
|---|---|---|---|
| Maximum | Local | Local | Local |
| Balanced (default) | Local | Cloud | Local |
| Performance | Local | Cloud | Cloud |

Set with `openreview config set privacy.tier maximum|balanced|performance`.

## What it does

- **Multi-agent review**: keyword match → extraction agent → QA verification → citation-grounding discriminator, per clause
- **23 named product modes** covering NDAs, leases, DPAs, licensing, employment, M&A, and more, plus the base `precheck` NDA review, each with a bundled 3-position playbook (Preferred / Acceptable / Walkaway)
- **Negotiation analysis**: local game-theoretic solvers (Nash, QRE, Level-k), no LLM calls
- **Contract graph**: clause relationships, a 0–100 structural health score, diffing
- **Dual interface**: Typer CLI and a Textual terminal UI, both running the same pipeline
- **Agent-ready**: JSON output, an importable Python API, and a routing skill for AI agents ([skill/SKILL.md](skill/SKILL.md))

Run `openreview --help` for the full command list.

<details>
<summary>All contract-type modes</summary>

`precheck` is the base NDA mode, not counted among the 23 named product modes below it.

| Mode | What it reviews |
|---|---|
| precheck | Non-Disclosure Agreement (NDA), base mode |
| licensecheck | SaaS/software license agreement |
| leasecheck | Commercial lease agreement |
| privacycheck | Data Processing Agreement (DPA) |
| privacycheck_v2 | Data Processing Agreement (v2) |
| dealcheck | Vendor/service agreement |
| hirecheck | Employment agreement |
| indemnitycheck | Indemnification agreement |
| consultcheck | Consulting services agreement |
| workcheck | Independent contractor/work-for-hire agreement |
| loicheck | Letter of intent or MOU |
| subcheck | Subcontractor agreement |
| settlementcheck | Settlement/release agreement |
| settlementcheck_v2 | Complex settlement/release agreement (v2) |
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

</details>

## Where to go next

| Doc | For |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the pipeline, AI Gateway, and storage actually work |
| [docs/BENCHMARKS.md](docs/BENCHMARKS.md) | Every accuracy and privacy number, methodology, and what's not yet measured |
| [skill/SKILL.md](skill/SKILL.md) | Intent-to-command routing for AI agents |

<details>
<summary>FAQ</summary>

**Does it send contract text to the cloud?**
Not by default. PII is stripped locally before any cloud call, and the pipeline halts rather than proceed on a failed detection (`--allow-partial-pii` to opt out). Cloud providers are opt-in per slot.

**Can it run fully offline?**
Yes, with the default local Ollama configuration. Set the privacy tier to Maximum to guarantee nothing leaves the machine.

**What file formats are supported?**
PDF (PyMuPDF, page-by-page streaming, password-protected and corrupt/empty detection) and DOCX (python-docx, track-changes, images, flat documents).

**What can AI agents do with it?**
Every module is independently importable (`from openreview_cli.parsing.stream import parse_document`, `from openreview_cli.review.extraction import extract_clause`). The CLI supports `--format json` and `--output`. For intent-to-command routing rather than raw library calls, use [skill/SKILL.md](skill/SKILL.md).

</details>

## Contributing

Issues and discussions are open. Contributing code requires agreeing to the [CLA](CLA.md). Dev setup is in the "from source" section above.

## License

AGPL-3.0-only ([LICENSE](LICENSE)), with a commercial license available ([COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)) for anyone who can't use AGPL.

<sub>Python 3.12 · Typer · Textual · Presidio · litellm · PyMuPDF / python-docx · SQLite + FTS5 · numpy / scikit-learn · torch (CPU-only) · pydantic</sub>
