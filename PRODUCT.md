# Product

<!-- impeccable:product-schema 1 -->

## Platform

<!-- impeccable-override: platform=cli (local terminal application: Typer CLI + Textual TUI; non-web/non-mobile target) -->
cli

## Users

Primary users are legal professionals, contract analysts, operations leads, and businesses performing first-pass review, comparison, and analysis on agreements (e.g. NDAs, MSAs, DPAs, vendor leases, employment contracts). Secondary users include automated pipelines and AI agents invoking the tool programmatically via structured JSON.

## Product Purpose

OpenReview brings privacy-preserving, local-first contract analysis and review automation to the terminal. It parses contracts, strips personally identifiable information (PII) before any cloud inference, evaluates clauses against customizable institutional playbooks (Preferred / Acceptable / Walkaway), compares bilateral counterparty drafts, and computes game-theoretic negotiation posture without vendor-hosted lock-in.

Success means delivering an accurate, descriptive review memo in seconds with zero data leakage and full auditability, operating entirely offline when local models are configured.

## Positioning

Unlike cloud-hosted SaaS legal tech platforms that require uploading raw agreements to third-party servers, OpenReview runs locally with a fail-closed PII stripping pipeline, strict hardware budgets (<100MB streaming peak), encrypted local PII mapping, and direct BYO provider routing (or local SLMs via Ollama) with no intermediary servers.

## Operating Context

- **Environment**: Local command-line interface (Typer CLI) and full-screen terminal interface (Textual TUI) running on standard developer/analyst workstations (minimum baseline: 8 GB RAM, 2 CPU cores, no dedicated GPU).
- **Documents**: PDF (PyMuPDF streaming) and DOCX agreements parsed paragraph/page-by-page.
- **Workflow**: Document ingestion → PII redaction (Presidio + Fernet encryption) → clause-level assessment against playbook standards → citation grounding / verification → multi-format report export (Markdown, JSON, DOCX).
- **Automation**: CI/CD and scripted workflows via `--format json` and standard POSIX exit codes.

## Capabilities and Constraints

### Capabilities
- **5-Stage Pipeline**: Parse → Strip PII → Chunk → Multi-Agent Extract/QA → Structured Memo.
- **24 Bundled Playbooks**: Pre-configured domain playbooks covering 23 contract modes (NDAs, Leases, DPAs, SaaS licenses, Employment, etc.).
- **Privacy Tiers**: Configurable routing modes (Maximum: all-local; Balanced: local embeddings + cloud reasoning with stripped PII; Performance: cloud reasoning with stripped PII).
- **Bilateral Comparison (Experimental)**: RCBSF divergence detection across counterparty drafts with heading alignment (experimental; documented accuracy ceiling $\le$64% F1).
- **Negotiation Modeling (Experimental)**: Local game-theoretic equilibrium solver (Nash, QRE, Level-k) with payoff matrices from playbook positions.
- **Contract Graph**: Clause dependency, cross-reference mapping, and structural health scoring.
- **AI Gateway**: Unified multi-provider abstraction supporting 17+ backends and local Ollama SLMs across 6 task-specific model slots.

### Constraints
- **Privacy Guarantee**: Fail-closed PII redaction before any external API dispatch; no raw contract text in logs.
- **Local-First / No Daemon**: Zero web servers, background daemons, or telemetry.
- **Hardware & Memory**: Peak streaming memory target <100MB (hard ceiling 110MB, with spaCy model load exempt).
- **Dependency Minimalist**: Pure Python 3.12 managed exclusively with `uv`; AGPL-3.0 and commercial dual-licensing compatibility.

## Brand Commitments

- **Product Names**: Package `openreview-cli`, CLI binary `openreview`, Python import `openreview_cli`.
- **Identity Distinctiveness**: Distinct from academic peer-review platforms (unrelated to openreview.net).
- **Tone & Ethics**: Objective, analytical, and descriptive; never dispenses legal advice or prescriptive guarantees.

## Evidence on Hand

- **Test Suite**: ~296 test files covering unit, integration, memory profiling, and TUI flows.
- **ContractNLI Real-World NDA Benchmark**: 95-NDA structural coverage at 97.84% (1,359 / 1,389 spans across 977 tests, all 5 standard PreCheck categories) via `scripts/benchmark_contractnli.py`. Live LLM extraction + QA verification on 15 real ContractNLI NDA clauses across 5 NDAs via Claude Sonnet 4.6 (OpenRouter): 0 uncertain, 1 preferred, 14 acceptable, QA agreement 6.67%, amber rate 93.33%, steady-state latency ~7.8 s/clause (frozen clause set; model recorded in the artifact).
- **CUAD Commercial Benchmark**: Parsed 462 commercial contracts (4,042 labeled clause spans) via NUPunkt; clause identification is not yet measured with a meaningful, reproducible metric (`BENCHMARKS.md`).
- **PII Corpus Accuracy**: Evaluated on 50 seeded contracts with 94.35% overall recall (100% on regex-based financial/tax/id identifiers, 62% on synthetic person names).
- **Review Accuracy Signal**: 90.9% F1 / 100% QA catch rate measured against the 12-clause NDA corpus fixture (`nda-corpus-v1.json`) via Claude Sonnet 4.6.
- **Knowledge Graph**: Complete structural AST graph in `graphify-out/` (7,967 nodes, 445 communities, zero import cycles).

## Product Principles

1. **Privacy-First**: No un-redacted contract data ever crosses machine boundaries.
2. **Local-First Autonomy**: Always functional offline with local SLMs; no mandatory cloud dependencies.
3. **Descriptive, Never Prescriptive**: Highlight discrepancies, risks, and amber ambiguities without pretending to replace human legal judgment.
4. **Lean & Deterministic**: Strict memory and resource containment; stream rather than hoard.
5. **Inspectable & Auditable**: Every redaction, classification, and transformation provides an encrypted or inspectable trail.

## Accessibility & Inclusion

- Fully accessible keyboard navigation within the Textual TUI.
- High-contrast terminal output with standard three-color coding (Green / Amber / Red) paired with explicit textual labels for non-color terminals.
