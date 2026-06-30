# Product Spec Extraction — Part 1

Extracted from `/home/mohamed/lab/openreview/products/openreview/` on 2026-06-28.

---

═══════════════════════════════════════════
PRODUCT SPEC PR-1: AI-Gateway.md
───────────────────────────────────────────

PURPOSE
The model routing layer that connects the contract review engine to any AI provider — cloud or local. Handles model selection, provider routing, API key management, fallback chains, and cost tracking.

USER STORIES / JOBS DEFINED
US1: Lawyer configures which AI models handle contract reviews (once, through interactive setup wizard).
US2: System routes each task (reasoning, extraction, embedding, reranking, graph) to the appropriate model.
US3: System falls back to alternate models when primary provider fails (rate limit, timeout, error).
US4: Lawyer tracks token usage and cost per review session.
US5: Lawyer can run everything locally via Ollama with no cloud APIs.
US6: Lawyer can bring their own API keys (BYOK) — no keys sent to project servers.

PRODUCT DECISIONS MADE
D1: Gateway library: LiteLLM SDK (embedded) — one function, any provider, Python-native.
D2: Provider count: 8 — OpenAI, Anthropic, Google, Ollama, OpenRouter, Cohere, HuggingFace, Custom.
D3: Model discovery: Hybrid — cached registry for cloud providers, dynamic (ping `localhost:11434/api/tags`) for Ollama.
D4: Model slots: 5 (reasoning, extraction, embedding, reranking, graph) — different tasks need different models.
D5: Embedding default: Local (Ollama) — privacy-first, contract text stays on machine, free.
D6: Reranking default: Local (Ollama) — privacy-first, free.
D7: Setup UX: Interactive wizard — same flow for all slots: pick provider → list models → pick model.
D8: Config format: YAML for routing (`config.yml`), JSON for secrets (`auth.json`).
D9: Local models are a first-class choice, not just a fallback.
D10: HuggingFace models: 8 curated (SaulLM-7B, Qwen3 8B/4B, Llama 3.1 8B, Mistral 7B, nomic-embed, bge-reranker, KL3M experimental).
D11: Refresh mechanism: Weekly auto-refresh + manual `openreview gateway refresh`.
D12: Fallback behavior: Retry (up to N times with exponential backoff) → try fallback model → raise error or skip.
D13: API keys saved in `auth.json` (chmod 600) at `~/.config/openreview/`. Env vars override `auth.json`.
D14: Contract text PII-stripped before reaching any API. Embedding and reranking run locally by default.
D15: Cost limits: per-review ($1.00) and daily ($10.00), configurable.
D16: Recommended cloud models and recommended local (Ollama) models specified per slot.

CONSTRAINTS IDENTIFIED
C1: API keys never leave the lawyer's machine. No keys sent to project servers.
C2: PII must be stripped from contract text before any API call.
C3: Embedding and reranking run locally by default for privacy.
C4: Minimal local setup must run on 8GB RAM (Qwen3 8B at 5.2GB + nomic-embed at 274MB + reranker at ~1GB = ~6.5GB total).

ASSUMPTIONS MADE
A1: Ollama can run on the target machine (8GB RAM).
A2: Lawyers have (or can obtain) API keys for cloud providers.
A3: The hosted model registry at `https://precheck.dev/models.json` will exist and be maintained.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-2: Architecture.md
───────────────────────────────────────────

PURPOSE
The shared RAG and comparison engine that powers all 22 Check products — hierarchical parsing, hybrid retrieval, contract graph, multi-document review, and hallucination control.

USER STORIES / JOBS DEFINED
US1: Lawyer sets up playbook once per client per contract type.
US2: Contract comes in (upload PDF/Word) — AI reads and compares against playbook.
US3: Lawyer sees comparison results (Green/Yellow/Red for each clause).
US4: One-click memo export.
US5: Lawyer can toggle contract graph extraction ON for complex contracts, OFF for simple ones.
US6: Lawyer reviews multi-document structures (MSA + SOW, master + amendments) with cross-document conflict detection.
US7: Lawyer uses practice-area overlays (e.g., IP overlay for asset purchases) to add industry-specific questions.
US8: Lawyer re-checks old reviews when playbook positions change.

PRODUCT DECISIONS MADE
D1: Chunking: Hierarchical (node-level / ancestor-aware / descendant-aware) — proven by PAKTON to preserve legal structure.
D2: Retrieval: Hybrid BM25 + Dense embeddings + LightRAG + Reciprocal Rank Fusion (RRF).
D3: Reranker: Cross-encoder (legal-specific if possible) — Cohere fails on legal text.
D4: Graph extraction: Optional switch (OFF by default for simple contracts, ON for complex).
D5: Text segmentation: NUPUNKT + CharBoundary.
D6: Agents: 3-agent architecture (Archivist/Researcher/Interrogator) from PAKTON, model-agnostic.
D7: Positions: 3-position framework (Preferred / Acceptable / Walkaway).
D8: Versioning: Frozen snapshots + opt-in re-check.
D9: Questions: Two layers — 3 shared questions (per client) + 10-30 product-specific questions.
D10: Multi-document: Master + subordinate hierarchy with conflict detection.
D11: Practice overlays: Base playbook + optional overlay question sets.
D12: Memo format: Standard 4 sections + optional product-specific addendums.
D13: Hallucination control: Citation Grounding (CP/CR/CT) + verification pipeline.
D14: Two-sided contracts: Separate playbooks per side.
D15: Templates: Ship pre-filled playbook templates per product.
D16: AI suggestions: From past contracts.
D17: Open source tools used: PAKTON, LegalBench-RAG, LightRAG, NUPUNKT + CharBoundary, KL3M Tokenizers.

CONSTRAINTS IDENTIFIED
C1: Must use PAKTON architecture (3-agent, hybrid retrieval, hierarchical chunking).
C2: LightRAG for graph + vector dual retrieval.
C3: NUPUNKT + CharBoundary for legal sentence/clause segmentation.
C4: KL3M Tokenizers for domain-specific tokenization.
C5: RAG over raw LLM — the Citation Grounding paper is the reference.
C6: Architecture explicitly excludes: multi-user accounts, Arabic support, clause library, analytics dashboard, web UI, fine-tuned models, long-term contract storage, CLM tool integration.

ASSUMPTIONS MADE
A1: PAKTON's hybrid approach achieves 5x better recall than the strongest baseline (citing LegalBench-RAG).
A2: Cohere's general-purpose rerankers fail on legal text.
A3: Stanford found legal AI hallucinates in 1 out of 6 queries (16.7%).
A4: The 3-position framework is the "industry standard" for how lawyers think about negotiation.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-3: CLA.md
───────────────────────────────────────────

PURPOSE
Contributor License Agreement — legal boilerplate defining the terms under which contributors grant copyright and patent licenses to the project maintainer.

USER STORIES / JOBS DEFINED
US1: Contributor submits a pull request, patch, file, or other code/content to openreview.
US2: Project maintainer can relicense contributions under the commercial license in addition to AGPL-3.0.

PRODUCT DECISIONS MADE
D1: CLA is required for all contributions.
D2: Contributors grant perpetual, worldwide, non-exclusive, royalty-free, irrevocable copyright license.
D3: Contributors grant a perpetual, worldwide, royalty-free patent license.
D4: Patent license terminates if contributor initiates patent litigation against Licensor.
D5: Licensor is not obligated to accept, merge, or use contributions.
D6: CLA signing is handled by a bot on pull request (electronic agreement).
D7: Contributors who cannot agree should open an issue instead of a PR.
D8: Contact email for CLA questions: cla@openreview.dev.

CONSTRAINTS IDENTIFIED
C1: CLA is legally required to enable dual-licensing (AGPL-3.0 + commercial).
C2: Without CLA, all contributions would be locked to AGPL-3.0 and could not be relicensed commercially.

ASSUMPTIONS MADE
N/A — Legal boilerplate, no factual assumptions.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-4: CLI-Design.md
───────────────────────────────────────────

PURPOSE
The complete CLI interface specification — every command, flag, output format, and exit code a lawyer sees when typing `openreview` in the terminal.

USER STORIES / JOBS DEFINED
US1: Lawyer reviews a contract against a client's playbook (22 mode subcommands: precheck, hirecheck, dealcheck, etc.).
US2: Lawyer manages client playbooks (create, edit, list, delete, export, import).
US3: Lawyer configures AI gateway (setup wizard, status, providers, models, set, refresh, test, costs).
US4: Lawyer manages configuration (show, get, set, edit).
US5: Lawyer backs up and restores all data.
US6: Lawyer uses shell completion for mode names, flags, providers, slots, client names, output formats.
US7: Lawyer runs in non-interactive mode for scripting.
US8: Lawyer gets help at top-level, mode-level, and review-command level.

PRODUCT DECISIONS MADE
D1: 22 mode subcommands (precheck, hirecheck, dealcheck, leasecheck, licensecheck, buycheck, partnercheck, distrocheck, franchisecheck, loancheck, guaranteecheck, indemnitycheck, consultcheck, settlementcheck, sponsorcheck, workcheck, engagecheck, opcheck, assetcheck, privacycheck, subcheck, loicheck).
D2: Every mode follows pattern: `openreview <mode> review <contract-path> [flags]`.
D3: Common flags for all modes: `--client` (required), `--output`, `--format` (markdown/json/pdf), `--questions`, `--questions-file`, `--graph`, `--role`, `--master`, `--no-pii`, `--non-interactive`, `--debug`.
D4: Mode-specific flags for hirecheck (`--state`), dealcheck (`--jurisdiction`), leasecheck (`--state`), privacycheck (`--region`), loancheck (`--secured`), franchisecheck (`--state`), licensecheck (`--type`).
D5: 10 exit codes: 0 (Success), 1 (General error), 2 (Usage error), 3 (Auth error), 4 (Cost limit), 5 (Config error), 6 (Playbook error), 7 (Provider error), 8 (Parse error), 9 (PII error), 10 (Non-interactive).
D6: Output formats: Markdown (default), JSON, PDF.
D7: Shell completion auto-generated by Typer for Bash, Zsh, Fish.
D8: Interactive commands: gateway setup, playbook create, playbook edit, playbook delete.
D9: Non-interactive commands: playbook list/export/import, gateway status/providers/models/set/refresh/test/costs, config show/get/set, backup/restore, all review commands.
D10: `--non-interactive` flag causes interactive commands to fail with exit code 10.
D11: Config commands: show, get (dot notation), set (dot notation + auto-convert types).
D12: Backup creates a zip archive of `~/.config/openreview/`; `--exclude-auth` flag available.
D13: Restore merges with existing data, handles schema migration.
D14: Review JSON output includes: review metadata, per-question results with citations, summary statistics.

CONSTRAINTS IDENTIFIED
C1: 22 modes must share a common interface pattern.
C2: Typer is the CLI framework (from TechStack.md).

ASSUMPTIONS MADE
A1: `--client` is always required for review commands.
A2: Default output directory is `./outputs/`.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-5: COMMERCIAL_LICENSE.md
───────────────────────────────────────────

PURPOSE
Describes the paid commercial license option for organizations that want to avoid AGPL-3.0's source-disclosure obligations or need commercial support.

USER STORIES / JOBS DEFINED
US1: Organization runs openreview as a network service (SaaS) and has modified it.
US2: Organization embeds openreview in a commercial product.
US3: Organization distributes a modified version under a closed-source license.
US4: Organization needs commercial support with SLAs or legal indemnification.

PRODUCT DECISIONS MADE
D1: Dual-license model: AGPL-3.0 + Commercial (paid).
D2: Commercial license is required for SaaS providers who modify openreview, embedders, and closed-source distributors.
D3: Commercial license is NOT required for solo lawyers, internal use, or professional services using openreview as a tool.
D4: Commercial license grants: full right to modify and keep modifications private, no source disclosure obligation, commercial support SLA, legal indemnification, pre-built integrations, custom playbook templates.
D5: Pricing: per-host or per-user for SaaS, per-product or per-distribution for embedded, custom for white-label.
D6: Contact email: commercial@openreview.dev.

CONSTRAINTS IDENTIFIED
C1: AGPL-3.0 Section 13 requires SaaS providers who modify the software to publish modifications.
C2: Commercial license is a separate written agreement — the document is a summary, not the binding contract.

ASSUMPTIONS MADE
N/A — Legal/commercial boilerplate.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-6: Configuration.md
───────────────────────────────────────────

PURPOSE
The complete configuration surface of openreview: what lives in `config.yml`, what lives in `auth.json`, which environment variables override what, and how everything is validated on startup.

USER STORIES / JOBS DEFINED
US1: Lawyer configures openreview via the setup wizard (normal path).
US2: Power user edits YAML by hand.
US3: CI user sets everything via environment variables.
US4: Lawyer overrides settings temporarily with CLI flags.
US5: System validates config on every command and reports clear errors.

PRODUCT DECISIONS MADE
D1: One file for settings (`config.yml`), one file for secrets (`auth.json`).
D2: CLI flags override everything.
D3: Env vars override files (both config.yml and auth.json).
D4: Sensible defaults — a lawyer who runs `gateway setup` has a working config without opening YAML.
D5: Auto-backup — every `openreview config set` auto-creates `config.yml.bak`.
D6: Schema versioning with `version` field in `config.yml`. Bumped on breaking changes.
D7: Pydantic validation on startup — exits with code 5 on invalid config.
D8: 6-level priority hierarchy: CLI flags > CLI arguments > Environment variables > config.yml > auth.json > Built-in defaults.
D9: Config migration: forward-only, version-by-version scripts, auto-backup before migration.
D10: Config editing UX layers: Interactive wizard (layer 1) → CLI commands (layer 2) → Manual YAML (layer 3) → Env var override (layer 4).
D11: auth.json permissions: chmod 600.
D12: No encryption at rest — file permissions are sufficient for a local CLI tool.
D13: PRIVACY_TIER has 3 options: maximum, balanced, performance.
D14: Gateway model slots default to Ollama local models.
D15: Config explicitly excludes: encryption at rest, web-based config UI, team-shared config, config validation web service, auto-detect providers (except Ollama).

CONSTRAINTS IDENTIFIED
C1: auth.json must have chmod 600.
C2: Env vars with `OPENREVIEW_` prefix override config.yml fields.
C3: Provider API key env vars match provider name convention (e.g., `OPENAI_API_KEY`).
C4: Config validation happens on every command.

ASSUMPTIONS MADE
A1: File permissions (600) are sufficient for secrets storage (same as SSH keys and git credentials).
A2: Config encryption at rest is "overkill for a local CLI tool."

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-7: DataStorage.md
───────────────────────────────────────────

PURPOSE
Defines where every piece of data lives on disk, what format it uses, how long it stays, and how lawyers protect it.

USER STORIES / JOBS DEFINED
US1: Lawyer's data persists across sessions on their local machine.
US2: Lawyer creates per-client playbooks that can be backed up and shared.
US3: Lawyer backs up all data to a single zip file.
US4: Lawyer restores from backup, with schema migration.
US5: System manages data lifecycle — ephemeral data cleaned on session close, persistent data managed by lawyer, operational data auto-pruned.

PRODUCT DECISIONS MADE
D1: Storage format: SQLite for structured data, JSON for simple maps (config, PII maps).
D2: Database architecture: One main DB (`openreview.db`) + one per-client playbook DB (`playbooks/<client>.db`).
D3: Session data: SQLite in `tmp/` directory, not in-memory (survives partial crashes, allows debugging).
D4: Schema migration: Version table + forward-only `.sql` migration files.
D5: Backups: Zip archive — portable, compressible, one file.
D6: auth.json permission: 600.
D7: Review retention: Keep forever (lawyer's work product).
D8: Log retention: 30 days (privacy-first, configurable).
D9: Per-client playbook DBs make backup and sharing simple.
D10: Session DB (`tmp/openreview.db`) stores chunks, vectors, graph nodes/edges — deleted on clean exit.
D11: Main DB tables: `schema_version`, `clients`, `shared_positions`, `reviews`, `review_diffs`, `cost_logs`.
D12: Per-client playbook DB tables: `questions`, `playbook_versions`.
D13: Session DB tables: `chunks`, `graph_nodes`, `graph_edges`.
D14: Cost logs in JSONL format at `logs/gateway_costs.jsonl`.
D15: Estimated persistent storage: ~25 MB/year for a typical solo lawyer.

CONSTRAINTS IDENTIFIED
C1: Configuration.md is the authoritative schema; DataStorage note defers to it for schema.
C2: All data stays on the lawyer's machine unless they explicitly configure a cloud provider.

ASSUMPTIONS MADE
A1: Typical solo lawyer has ~50 clients and ~200 reviews per year.
A2: SQLite file size estimates: ~5 KB per playbook DB, ~100 KB per review.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-8: DevelopmentSetup.md
───────────────────────────────────────────

PURPOSE
The complete development environment for openreview-cli — project structure, dependency management, code quality tools, testing, debugging, memory profiling, CI/CD, and documentation.

USER STORIES / JOBS DEFINED
US1: Developer clones and sets up the project on a low-spec machine (8GB RAM, no GPU).
US2: Developer runs linting, type checking, tests, and formatting.
US3: CI runs on every push and PR — lint, typecheck, test, memory profiling.
US4: Release is built and published to PyPI on version tag push.
US5: Developer writes documentation with MkDocs and deploys to GitHub Pages.

PRODUCT DECISIONS MADE
D1: Package manager: uv (Astral) — 10-100x faster than pip, low RAM.
D2: Linter: ruff — 10-100x faster than flake8, Rust-based.
D3: Formatter: ruff format — replaces black.
D4: Type checker: mypy (strict mode) — catches bugs before runtime.
D5: Test framework: pytest — plugin ecosystem, fixture model.
D6: HTTP mocking: pytest-httpx — block real API calls by default.
D7: Memory profiling: tracemalloc + memory_profiler.
D8: Pre-commit hooks: pre-commit.
D9: Docs: MkDocs Material.
D10: CI/CD: GitHub Actions.
D11: License: AGPL-3.0 + Commercial + CLA.
D12: Python version: 3.12.
D13: Project layout: src/ layout.
D14: Ruff configuration: line-length 100, target-version py312, specific rule selections with ignores.
D15: mypy configuration: strict mode, specific overrides for third-party packages.
D16: Pre-commit hooks: whitespace/EOF/YAML/TOML/JSON checks, ruff fix, ruff-format, mypy, local pytest-fast.
D17: Pytest configuration: testpaths = tests, markers for slow/integration/e2e/memory, deprecation warning filter.
D18: CI workflow: 5 jobs (lint, typecheck, test, memory, integration) + nightly.
D19: Release workflow: on tag v*.*.*, build + publish to PyPI.
D20: Project structure includes: src/openreview_cli/, tests/ (unit/integration/e2e/fixtures), docs/, scripts/, .github/.
D21: Source code organized into: cli/, core/, gateway/, config/, pii/, utils/ subpackages.
D22: Commit convention: Conventional Commits (feat:, fix:, docs:, test:, refactor:, chore:).
D23: Branch naming: feat/<description>, fix/<description>, docs/<description>.
D24: Community files: LICENSE (AGPL-3.0), COMMERCIAL_LICENSE.md, CLA.md, NOTICE.md, CODE_OF_CONDUCT.md, issue templates.
D25: Memory target: <100 MB peak, enforced via memory_tracker fixture in every test.
D26: Pipeline stage memory targets: Parse <10MB, Chunk+index <20MB, Embed <30MB, Compare <30MB, Write memo <10MB.
D27: Memory profiling CI job runs on every PR.

CONSTRAINTS IDENTIFIED
C1: Reference development machine: 8GB RAM, i7-5500U, no GPU, ~25GB free disk, Linux.
C2: Ollama also runs in background (~2-5 GB of model files).
C3: uv is the only package manager — no pip, poetry, or pipx.
C4: Python 3.12 required.
C5: Peak memory must stay under 100 MB (floor 110 MB).

ASSUMPTIONS MADE
A1: The developer's machine matches the reference specs.
A2: uv is available for curl-pipe-sh install.
A3: GitHub Actions is the CI provider (free for public repos).

IMPLEMENTATION STATUS
Partially built — spec states "The existing `.opencode/` skills and AGENTS.md already provide project context" and references existing development setup. The project structure described partially matches the current repo structure at `src/openreview_cli/`, `tests/`, `.github/`, etc. Some subpackages like `cli/`, `core/`, `pii/` are not yet present in the actual codebase.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-9: ErrorHandling.md
───────────────────────────────────────────

PURPOSE
Every error a lawyer could see, every recovery path the tool takes, and every fallback — designed so lawyers never stare at a frozen screen or a cryptic error.

USER STORIES / JOBS DEFINED
US1: Lawyer sees clear, plain-English error messages when something goes wrong.
US2: System automatically recovers from transient errors (retry on rate limit, timeout).
US3: System falls back to alternate models when primary provider fails.
US4: Partial results are delivered when some questions fail — review completes with visible gaps.
US5: Lawyer can re-run individual failed questions without re-parsing.
US6: System degrades gracefully when dependencies are missing (e.g., no Ollama → use cloud models).

PRODUCT DECISIONS MADE
D1: Plain English error messages — never developer-facing error text.
D2: Every error message follows 3-line template: "Error: <what happened>" + "<why it matters>" + "What to do: <action>".
D3: Rendered with Rich in a red panel.
D4: 10 error categories with dedicated exit codes: Auth(3), Provider(7), Parse(8), Config(5), Playbook(6), Cost(4), PII(9), Network(7), Storage(1), Hallucination(0/warning).
D5: 5 recovery strategies (applied in order): Retry → Fallback → Skip → Ask → Fail.
D6: Partial results beat total failure — failed questions shown in yellow during review, listed in memo.
D7: Re-run individual questions without re-parsing via `--questions` flag.
D8: Graceful degradation matrix for missing dependencies (Ollama, internet, Presidio, Docling, sqlite-vss, low memory, no GPU).
D9: Error logging to `logs/debug/` as JSON lines with redacted contract text.
D10: Debug mode (`--debug`) shows full stack traces, raw API bodies (redacted), memory usage, timing.
D11: Log retention: 30 days.
D12: Never freeze the screen — progress bars update during API calls, tool fails fast with clear message.

CONSTRAINTS IDENTIFIED
C1: Lawyers are not developers — no stack traces unless `--debug` is on.
C2: Raw contract text is never logged. PII placeholders may remain in logs; mapping file is never logged.
C3: Auto-recovery rate target: ≥90% (errors resolved by retry or fallback without user action).
C4: Screen must update every 2-3 seconds (no frozen screen).

ASSUMPTIONS MADE
A1: 90%+ auto-recovery rate is achievable.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-10: NOTICE.md
───────────────────────────────────────────

PURPOSE
License and contact summary file for the openreview project repository.

USER STORIES / JOBS DEFINED
US1: Visitor to the repository reads the license overview, trademark notice, and contact information.

PRODUCT DECISIONS MADE
D1: Project licensed under AGPL-3.0 with commercial licensing available.
D2: "openreview" and the openreview logo are trademarks.
D3: Trademark policy noted as "not yet adopted."
D4: Contact emails: hello@openreview.dev, commercial@openreview.dev, cla@openreview.dev, security@openreview.dev.

CONSTRAINTS IDENTIFIED
C1: Contributions are subject to the CLA and Code of Conduct.

ASSUMPTIONS MADE
N/A — Legal boilerplate.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-11: PerformanceOptimization.md
───────────────────────────────────────────

PURPOSE
How the Python application stays fast, responsive, and memory-efficient on low-end machines (8GB RAM, CPU-only, no GPU).

USER STORIES / JOBS DEFINED
US1: Lawyer runs contract reviews on a 5-10 year old laptop without it slowing down.
US2: Lawyer sees continuous progress during reviews — no frozen screens.
US3: System stays responsive while multiple API calls are in flight.

PRODUCT DECISIONS MADE
D1: Stream and discard — never load entire document into memory; parse page by page, clause by clause.
D2: Never block the CLI — all API calls are async via `httpx.AsyncClient`.
D3: SQLite over Python dicts for large collections (chunks, vectors, tree nodes).
D4: Lazy imports — import libraries only when needed (not at module level).
D5: Batch concurrent API calls — send questions concurrently (12 questions in ~3 seconds).
D6: Generators over lists — every sequence-producing function uses `yield`.
D7: `__slots__` on dataclasses — eliminate per-instance `__dict__`.
D8: Streaming JSON with ijson for large API responses.
D9: Pipeline architecture with 5 sequential stages (Parse → Build Tree + Chunk → Embed → Compare → Synthesize Memo), each streaming output to next.
D10: Pipeline stage memory targets: Parse <10MB, Chunk+index <20MB, Embed <30MB, Compare <30MB, Memo <10MB. Peak <~75 MB.
D11: Non-blocking CLI with Rich progress bars, spinners, and stage transition display.
D12: Concurrent requests progress indicator showing how many requests are in flight.
D13: Stage transitions display visibly changes so lawyer knows something is happening.
D14: PyMuPDF reads pages individually; python-docx iterates paragraphs lazily; Docling processes pages independently.
D15: SQLite page cache set to 16 MB for performance.

CONSTRAINTS IDENTIFIED
C1: Peak memory usage must stay under 100 MB.
C2: Target machine: 8GB RAM, CPU-only, no GPU, 5-10 year old laptop.
C3: Model inference speed and network latency are outside the application's control.

ASSUMPTIONS MADE
A1: Peak memory target ~75 MB (with approximately 50 MB steady state).
A2: Startup time with lazy imports: ~0.3s (vs ~2s without).
A3: 12 concurrent questions finish in ~3 seconds (assumes 3s API latency).
A4: 200-page PDF, 150 chunks per contract as typical workload.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-12: PlayBook.md
───────────────────────────────────────────

PURPOSE
The core system shared by all 22 Check products — where the lawyer saves their standard positions on contract terms and uses them across every contract type.

USER STORIES / JOBS DEFINED
US1: Lawyer sets up a client with 3 shared questions (governing law, dispute resolution, confidentiality) answered once and inherited by all contract types.
US2: Lawyer creates playbooks per contract type per client with Preferred/Acceptable/Walkaway positions.
US3: Lawyer starts from a template (pre-filled playbook) or from scratch.
US4: AI suggests positions based on past contracts.
US5: Lawyer uploads a contract and gets comparison results.
US6: Lawyer exports a memo in one click.
US7: Lawyer updates a playbook position and is offered to re-check old reviews.
US8: Old reviews stay frozen when playbook changes — version-stamped audit trail.

PRODUCT DECISIONS MADE
D1: Client has 3 shared positions (governing law, dispute resolution, confidentiality) that apply to ALL contracts for that client.
D2: One playbook covers ONE contract type, ONE role.
D3: Two-sided contracts get separate playbooks per side.
D4: 3-position framework: Preferred / Acceptable / Walkaway — with guidance notes and escalation rules.
D5: Position levels map to colors: Preferred→Green, Acceptable→Yellow, Walkaway→Yellow+warn, Below Walkaway→Red, Missing→Red.
D6: Playbook is versioned — snapshots at each edit.
D7: Old reviews are frozen with the playbook version they used — never automatically changed.
D8: When playbook changes, tool offers to re-check affected old reviews.
D9: Template playbooks available: "Standard NDA Playbook," "Standard Employer Playbook," "Standard SaaS Customer Playbook."
D10: AI-suggested positions from past contracts.
D11: Comparison result shows: what contract says, what playbook says, whether it matches or deviates.
D12: Comparison also includes: clause type, input type, options, required/optional flag per question.
D13: Setup time estimate: shared questions (2 min) + per-playbook (5-10 min) = 10-15 min per client.
D14: Review time estimate: 10-15 minutes (review diffs only) vs 1-2 hours without tool.
D15: Memo: 1 click vs 20-30 minutes without tool.
D16: Total per contract: ~15-20 min with tool vs ~2-3 hours without.

CONSTRAINTS IDENTIFIED
C1: One playbook per contract type, per role.
C2: The three shared questions always apply (governing law, dispute resolution, confidentiality).
C3: Not in this version: multi-user accounts, Arabic support, clause library, analytics dashboard.

ASSUMPTIONS MADE
A1: The 3-position framework (Preferred/Acceptable/Walkaway) is the "industry standard."
A2: Most clients have the same governing law, dispute resolution, and confidentiality preferences across all their contracts.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-13: PrivacyApproach.md
───────────────────────────────────────────

PURPOSE
How openreview handles data, keys, and privacy across all sub-products — what data touches the network, what stays on the lawyer's machine, how API keys are stored, how long data is kept, and what the lawyer is responsible for.

USER STORIES / JOBS DEFINED
US1: Lawyer's data stays private — embedding and reranking run locally by default.
US2: PII is automatically stripped before any data reaches a cloud API.
US3: Lawyer controls their own data — the tool does not auto-delete work product.
US4: No contract data or API keys pass through the project's infrastructure.
US5: Lawyer chooses from 3 privacy tiers (Maximum/Balanced/Performance).
US6: Lawyer gets a version-stamped audit trail for every review.

PRODUCT DECISIONS MADE
D1: Privacy by default — embedding and reranking run locally; contract text does not leave machine unless lawyer explicitly chooses cloud for those slots.
D2: PII stripped before any API call — entity-based NLP detection (not regex), 11 entity types replaced with placeholders.
D3: PII mapping saved locally at `~/.config/openreview/reviews/[id]/pii_map.json` — never sent anywhere.
D4: Lawyer owns their data — raw contract stays on disk until lawyer deletes it.
D5: BYOK — all API calls go directly from lawyer's machine to provider. No data to project servers.
D6: No storage of raw contracts on project side — no server receives/stores/processes contract text.
D7: 3 privacy tiers: Maximum (all-local, no data leaves), Balanced (local embed/rerank, cloud for reasoning/extraction/graph — PII-stripped), Performance (everything cloud — PII-stripped).
D8: API keys in `auth.json` with chmod 600 — no encryption at rest.
D9: API keys can also be set via environment variables (override auth.json).
D10: Cost logs: no contract text, no PII, no prompts/responses — just metadata for cost tracking.
D11: Debug logs: only written with `--debug` flag; contract text redacted; auto-deleted after 30 days.
D12: Version-stamped audit trail — each comparison stamped with playbook version.
D13: Compliance roadmap: PII stripping, local-first, BYOK, 600-permission file, 30-day log TTL, version-stamped audit trail for MVP. GDPR, CCPA, DPA, SOC 2 for future.
D14: Lawyer's obligations documented: verify AI output, maintain privilege, check bar rules, vet providers, manage files.

CONSTRAINTS IDENTIFIED
C1: PII stripping happens immediately after document parsing, before any chunking/embedding/API call.
C2: No encryption at rest for auth.json — file permissions relied upon.
C3: Mapping file saved locally and deleted when review is deleted.
C4: Playbook data stored locally; only relevant question text and positions sent during comparison.
C5: The only external request the tool makes is to fetch the model registry from precheck.dev (anonymous GET, no user data).

ASSUMPTIONS MADE
A1: File permissions (600) are sufficient for a local CLI tool (same as SSH keys and git credentials).
A2: NLP entity extraction (Presidio) is better than regex for detecting PII.

IMPLEMENTATION STATUS
Partially implemented for MVP — the compliance roadmap lists as MVP: PII stripping (entity-based), local-first embedding/reranking, BYOK, 600-permission secrets file, 30-day log TTL, version-stamped audit trail. Future items: GDPR right to deletion, CCPA opt-out, DPA, SOC 2.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-14: TechStack.md
───────────────────────────────────────────

PURPOSE
Every library, tool, and language decision for building openreview, with rationale and sizing estimates.

USER STORIES / JOBS DEFINED
US1: (N/A — technology reference document, not user-facing.)

PRODUCT DECISIONS MADE
D1: Language: Python 3.12.
D2: Package manager: uv (Astral).
D3: Distribution: PyPI (`uv tool install openreview-cli`).
D4: Async runtime: asyncio (built-in).
D5: CLI framework: Typer.
D6: Terminal UI: Rich.
D7: Database: SQLite (stdlib `sqlite3`).
D8: Vector search: sqlite-vss.
D9: Configuration parsing: PyYAML.
D10: Streaming JSON: ijson.
D11: HTTP client: httpx (async).
D12: AI provider SDK: LiteLLM.
D13: PDF parser: PyMuPDF (fitz).
D14: DOCX parser: python-docx.
D15: OCR engine: Docling (IBM, MIT-licensed).
D16: Local model runner: Ollama.
D17: PII detection: Presidio (Microsoft).
D18: Test framework: pytest.
D19: Linter: ruff.
D20: Type checker: mypy.
D21: Rejected: LangChain, LlamaIndex, FAISS, spaCy (for PII), sentence-transformers, Click, loguru/structlog, FastAPI/Flask.
D22: Package naming: PyPI name `openreview-cli`, CLI command `openreview`, Python import `openreview_cli`.
D23: Total runtime dependencies: 10 packages (~35 MB disk). With dev tools: ~51 MB.

CONSTRAINTS IDENTIFIED
C1: Target machine: 8GB RAM development machine.
C2: Each rejected dependency has a written reason (see "Why Not..." table).
C3: All three parsers expose a common generator: `stream_clauses(path) → Iterator[Clause]`.
C4: SQLite is the single persistent store — no server process, no separate install.
C5: Must use Ollama as local model runner (single API endpoint at `localhost:11434`).

ASSUMPTIONS MADE
A1: uv is 10-100x faster than pip.
A2: Asyncio standard library handles all concurrent API calls without extra dependencies.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-15: TestingStrategy.md
───────────────────────────────────────────

PURPOSE
The testing strategy for measuring retrieval accuracy, hallucination rate, comparison accuracy, graph extraction quality, PII stripping accuracy, and performance — with specific metrics, targets, floors, and CI integration.

USER STORIES / JOBS DEFINED
US1: (N/A — testing methodology document, not user-facing. Quality gates indirectly serve the user.)

PRODUCT DECISIONS MADE
D1: Primary benchmark: LegalBench-RAG (1,000+ legal Q&A pairs across 20+ contract types).
D2: Synthetic contracts: ~75 contracts covering edge cases across 8 categories.
D3: "Garbage In" collection: 7 types of malformed or ambiguous documents (scanned PDF with strikeouts, embedded font boxes, tracked changes DOCX, password-protected PDF, empty document, repeated clause 10,000x, non-English contract).
D4: Retrieval metrics with targets: Precision@5 ≥90%, Recall@10 ≥85%, MRR ≥0.92, NDCG@5 ≥0.88.
D5: Hallucination rate target: <5% overall (vs 16.7% Stanford baseline), with CP/CR/CT dimensions.
D6: Hallucination regression rule: If a commit increases hallucination rate by >1pp, CI fails.
D7: Comparison accuracy: Golden dataset of 500 clause-position pairs. Target classification accuracy ≥95%, false positive rate <3%, false negative rate <5%, coverage ≥90%.
D8: Graph extraction metrics: Node precision ≥90%, Node recall ≥80%, Edge precision ≥85%, Edge recall ≥70%.
D9: PII stripping metrics: Precision ≥95%, Recall ≥90%, False replacement rate <5%.
D10: Performance benchmarks: Peak memory <100 MB, cold startup <1s, warm startup <0.3s, parse 50-page PDF <3s, parse scanned 50-page <30s, API round trip <5s.
D11: CI integration: lint → types → unit → integration → retrieval benchmark → hallucination check → performance check.
D12: Real API tests run nightly only (not on every commit).
D13: Coverage thresholds: Line ≥80% (all), Branch ≥90% (core pipeline), Line ≥60% (CLI).
D14: Manual spot-checks: Pre-release, 10 real contracts, specific checklist.
D15: Golden dataset: 20 frozen contracts with hand-verified answers for 300+ questions across all 22 modes.
D16: Accuracy floors (non-negotiable, CI blocks): Retrieval P@5 ≥85%, Hallucination ≤6%, Comparison ≥90%, PII recall ≥85%, Peak memory ≤110 MB.
D17: Benchmarking schedule: Every commit (lint+types+unit+integration), Every PR (retrieval+hallucination+performance), Weekly (full), Monthly (manual), Per-release (10-contract spot-check), Quarterly (golden dataset update).

CONSTRAINTS IDENTIFIED
C1: Real API tests must run on a separate schedule (nightly) due to cost and rate limiting.
C2: Accuracy floors are looser than targets to allow iterative development.
C3: Golden dataset requires manual labeling — automated labeling risks circular validation.
C4: Benchmarks run on the reference machine (developer's laptop: 8GB RAM, i7-5500U).

ASSUMPTIONS MADE
A1: Stanford's 16.7% legal AI hallucination rate is a valid baseline.
A2: LegalBench-RAG is the primary benchmark for legal retrieval.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged.
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-16: UserJourney.md
───────────────────────────────────────────

PURPOSE
Eleven focused user journeys covering every path a lawyer walks with openreview — from first install to daily power use — told step by step with actions, screen output, emotional state, pain points, and opportunities.

USER STORIES / JOBS DEFINED
US1: First-time setup — lawyer installs, configures, creates first playbook, starts first review.
US2: Single contract review — lawyer uploads a contract, gets memo.
US3: Multi-client workflow — lawyer switches between 4 clients, 3 contract types in one morning.
US4: Two-sided review — lawyer reviews a lease from both tenant and landlord perspectives.
US5: Two-layer contracts — lawyer reviews a new SOW against an existing MSA with cross-document conflict detection.
US6: Cross-mode chains — lawyer reviews a deal across NDA, MSA, SaaS license, and DPA.
US7: Playbook evolution — lawyer updates a position and re-checks old reviews.
US8: Practice-area overlays — lawyer reviews an asset purchase with an IP overlay.
US9: Error recovery — API provider goes down, key expires, system falls back.
US10: Backup and migration — lawyer moves to a new laptop after 8 months of use.
US11: Power user patterns — lawyer scripts reviews, uses JSON output, custom question files, env vars.

PRODUCT DECISIONS MADE
(This is a UX scenarios document; it records journey flows, pain points, and improvement opportunities rather than product decisions per se. The following implicit decisions are reflected:)
D1: Persona defined: solo lawyer, terminal-comfortable, time-poor, skeptical of AI, bills $288/hour.
D2: Time savings table: PreCheck 1h45m saved, DealCheck 2h+ saved, HireCheck 1h45m saved, LeaseCheck 2h+ saved, AssetCheck 3h+ saved, etc.
D3: Each minute of friction costs the lawyer $4.80 (at $288/hour billing rate).
D4: Pain points-to-opportunities summary table for quick reference.

CONSTRAINTS IDENTIFIED
C1: Persona definition: solo lawyer using terminal (for billing and document management).
C2: Time-poor, skeptical of AI persona requires frictionless UX.

ASSUMPTIONS MADE
A1: The persona is a solo lawyer comfortable with a terminal.
A2: The lawyer bills at $288/hour.
A3: 22 modes cover the contract types a solo lawyer encounters.

IMPLEMENTATION STATUS
UNKNOWN — Not stated in this spec.

OPEN QUESTIONS IN SPEC
Q1: None explicitly flagged — however, each journey ends with "Opportunities" that are de facto suggestions for future improvements (e.g., `--quick` flag for gateway setup, auto-detect mode from contract, `--deal` flag, keychain integration, batch re-check progress). These are not flagged as unresolved decisions.
════════════════════════════════════════════
═══════════════════════════════════════════
PRODUCT SPEC PR-17: modes/AssetCheck.md
───────────────────────────────────────────

PURPOSE
Reviews asset purchase agreements for solo lawyers against their own standard template for small to mid-market business acquisitions, flagging missing provisions, unbalanced risk allocation, tax structuring traps, and missing due diligence follow-through.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set my standard asset purchase agreement template once so I don't have to remember or re-find my positions every time.
US2: As a solo lawyer, I want to upload an asset purchase agreement and see instantly which provisions match, differ from, or are missing from my standard.
US3: As a solo lawyer, I want to export a short memo to my client with what's in the agreement, matching/different/missing terms, purchase price allocation summary, due diligence checklist, and a recommended action.
___

PRODUCT DECISIONS MADE
D1: Two-sided mode — buyer-side and seller-side with separate question sets.
D2: Practice-area overlays: General business (default), Real estate heavy, Intellectual property heavy, Professional practice.
D3: Green/yellow/red comparison output: matches, differs, or missing clause.
D4: Deal size tiers: Under $1M, $1–5M, $5–10M (adjusts thresholds and standard practices).
D5: Shared questionnaire across products for common terms (governing law, dispute resolution, confidentiality, non-compete/non-solicit, indemnification, attorney's fees).
D6: Export memo includes purchase price allocation summary and due diligence checklist.
D7: Excluded from this version: stock purchase agreements, mergers, Section 338(h)(10) election analysis, full due diligence services, tax advice, international transactions, public company/SEC requirements, financing commitment review, Arabic support.
D8: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Solo lawyers only — no paralegal support, charge by the hour.
C2: Asset purchase agreements are the most complex contract most small business clients ever sign.
C3: References specific legal statutes: IRC Section 1060 (Form 8594), IRC Section 197 (non-compete amortization), WARN Act, COBRA, ERISA, CERCLA, California and Delaware bulk sales laws.
C4: Target hardware: 8 GB RAM, no GPU, 2-core CPU (from project-wide constitution). Pipeline peak memory under 110 MB.
___

ASSUMPTIONS MADE
A1: The lawyer has a "standard template" or standard positions for asset purchase agreements.
A2: The lawyer has pre-existing positions they can articulate during a one-time setup.
A3: The tool can distinguish buyer vs seller and apply the correct question set.
A4: The tool can read PDF or Word documents automatically.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-18: modes/BuyCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Stock Purchase Agreements (SPAs) against each client's standard position, flagging inherited liability risks, stale capitalization tables, missing indemnification protections, and earnout traps. Supports two modes — buyer-side and seller-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a client's SPA playbook so I don't have to search past positions each time.
US2: As a solo lawyer, I want to upload an SPA and see green/yellow/red comparison for each of seven clause areas.
US3: As a solo lawyer, I want to export a client memo with matching terms, differing terms, and an overall verdict.
___

PRODUCT DECISIONS MADE
D1: Two modes — buyer-side and seller-side with different question sets.
D2: Seven clause areas: representations and warranties, indemnification, purchase price and adjustments, closing conditions, covenants, earnout provisions, stock vs asset purchase structure.
D3: Saved client "playbook" per client.
D4: Green/yellow/red output per clause area.
D5: Export memo with three sections (matching, differing, overall verdict).
D6: Excluded: securities law compliance, 409A valuation review, antitrust (HSR) analysis, regulatory approval tracking, due diligence services, cross-deal comparison, earnout scenario modeling, Arabic support.
___

CONSTRAINTS IDENTIFIED
C1: The buyer inherits ALL liabilities (known and unknown) in a stock purchase — unlike asset purchases where buyer cherry-picks.
C2: Solo lawyers with no paralegal support.
C3: Seven critical areas must be evaluated quickly and accurately — "a single missing indemnification cap can cost the client millions."
___

ASSUMPTIONS MADE
A1: The client has established positions on SPA terms that can be saved as a playbook.
A2: The tool can read PDF or Word SPAs automatically.
A3: The lawyer can articulate standard positions during a one-time client setup.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-19: modes/ConsultCheck.md
───────────────────────────────────────────

PURPOSE
Reviews consulting agreements and independent contractor agreements for ongoing/retainer-based consulting relationships (not fixed-scope project work), flagging IRS misclassification risk, two-layer structure conflicts, indemnification, and insurance gaps. Supports both consultant-side and hirer-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to check both consultant-side and hirer-side positions against a consulting agreement.
US2: As a solo lawyer, I want to check SOWs against the master agreement for conflicts.
US3: As a solo lawyer, I want to review both master agreements and individual SOWs efficiently with two checks per SOW.
___

PRODUCT DECISIONS MADE
D1: Boundary with WorkCheck: ConsultCheck covers ongoing consulting relationships (fractional executives, advisors, ongoing services); WorkCheck covers fixed-scope project-based work (web design, app development).
D2: Boundary with DealCheck: ConsultCheck covers consulting and professional services (advice/ongoing services); DealCheck covers SaaS/technology/services MSAs where the provider delivers a product or platform.
D3: Two question sets: Set A (consultant-side) and Set B (hirer-side).
D4: Master agreement + SOW two-layer structure support with conflict detection between them.
D5: SOW-specific checks: (1) matches standard scope/price/deadlines, (2) doesn't contradict master agreement.
D6: Green/yellow/red output with SOW-specific conflict flags.
D7: Excluded: employment agreements (see HireCheck), MSAs (see DealCheck), full contract drafting, multi-state classification compliance checking, Arabic support, long-term storage of signed contracts.
D8: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: IRS misclassification risk — if the agreement sounds like employment but calls the person a contractor, the company owes back taxes and penalties.
C2: Consulting agreements involve a two-layer structure (master agreement + SOWs) that must be checked together.
C3: Indemnification is common in consulting but rare in employment — lawyers must check who pays if something goes wrong.
C4: Missing insurance requirements means the consultant is personally on the hook.
___

ASSUMPTIONS MADE
A1: The tool can remember a master agreement and check subsequent SOWs against it.
A2: Master agreements and SOWs are uploaded separately and can be linked.
A3: Lawyers have standard positions for both consultant-side and hirer-side clients.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-20: modes/DealCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Master Services Agreements (MSAs) — the umbrella agreement between two companies for ongoing service relationships — flagging liability caps, indemnification, IP ownership, termination, data security, and SOW conflicts. Supports both service provider and customer modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set each client's standard MSA positions for either provider-side or customer-side.
US2: As a solo lawyer, I want to upload an MSA and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to check SOWs against the already-reviewed MSA for conflicts.
___

PRODUCT DECISIONS MADE
D1: Two modes — service provider and customer.
D2: Five key clauses highlighted as most review-time-consuming: liability cap, indemnification, IP ownership, termination and exit, data security.
D3: MSA-specific question sets for provider and customer with distinct concerns.
D4: SOW conflict checking against already-reviewed MSA.
D5: Green/yellow/red output.
D6: Excluded: employment agreements (see HireCheck), consulting agreements (see ConsultCheck), NDAs (see PreCheck), full contract drafting, multi-state compliance checking, Arabic support, long-term storage of signed contracts.
D7: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: MSAs are the heaviest contract type solo lawyers see — longer than NDAs, more complex than employment agreements, carry bigger financial risk.
C2: MSAs introduce unique clauses not found in simpler contracts: SLAs, consequence waivers, and contract assignment rules.
C3: MSAs are paired with SOWs that must be checked for conflicts with the umbrella agreement.
___

ASSUMPTIONS MADE
A1: MSAs are always paired with SOWs that come later.
A2: The client has standard positions on MSA terms that can be captured during setup.
A3: The tool can read PDF or Word files automatically.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-21: modes/DistroCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Distribution Agreements against the lawyer's standard — flagging exclusive territory traps, Robinson-Patman Act risks, minimum purchase quota issues, and termination gaps. Supports both manufacturer-side and distributor-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to build a distribution playbook per client (manufacturer or distributor).
US2: As a solo lawyer, I want to upload a distribution agreement and see clause-by-clause comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — manufacturer-side and distributor-side with different question sets.
D2: Seven key clauses: scope of distribution rights, exclusivity and territory, minimum purchase requirements/quota, pricing and resale price maintenance, termination provisions, IP licensing, non-compete.
D3: Manual selection of client role determines which playbook applies.
D4: Saved client playbook.
D5: Green/yellow/red output.
D6: Excluded: full antitrust compliance review beyond basic flagging, FTC Franchise Rule analysis, state dealer protection law database, international distribution agreements, Arabic support.
D7: "It runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Distribution agreements carry hidden antitrust and franchise-formation risks despite looking straightforward.
C2: References Robinson-Patman Act compliance specifically.
C3: Targets solo lawyers and small law firms, no paralegal support.
___

ASSUMPTIONS MADE
A1: Distribution agreements can be read as PDF or Word.
A2: The client has established distribution standards that can be captured in a playbook.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-22: modes/EngageCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Letters of Engagement (legal engagement letters) for solo lawyers against their own standard — flagging scope creep, fee structure gaps, conflict waiver issues, and malpractice exposure. Supports lawyer-reviewing-own-letter and client-reviewing-another-firm's-letter modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to review my own engagement letter before sending it to a client against my standard positions.
US2: As a solo lawyer, I want to review another firm's engagement letter for a client switching firms.
US3: As a solo lawyer, I want the tool to check scope of services, fee structure, client identity, conflict disclosure, withdrawal rights, communication standards, and file retention against my standard.
___

PRODUCT DECISIONS MADE
D1: Two modes — lawyer (setting/sending engagement terms) and client (reviewing another lawyer's letter).
D2: Seven key clauses: scope of services, fee structure, client identity, conflict disclosure, right of withdrawal, communication standards, file retention and disengagement.
D3: Shared questions across products: governing law, dispute resolution.
D4: Green/yellow/red output.
D5: Excluded: malpractice insurance procurement, bar association compliance review, trust account compliance, conflict check services (just flagging), fee arbitration analysis, Arabic support.
D6: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Engagement letters are the lawyer's own protection — a vague engagement letter is a malpractice claim waiting to happen.
C2: Vague scope leads to scope creep and malpractice claims — precise scope description is essential.
C3: The spec is for solo lawyers reviewing their own engagement letters or those of other firms.
___

ASSUMPTIONS MADE
A1: The lawyer has a standard template or standard positions for engagement letters.
A2: The tool can read PDF or Word engagement letters.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-23: modes/FranchiseCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Franchise Agreements against the lawyer's standard template — flagging hidden fees, restrictive territory rights, supply chain traps, and FDD (Franchise Disclosure Document) gaps. Supports both franchisee-side and franchisor-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to build a franchise playbook per client (franchisee or franchisor).
US2: As a solo lawyer, I want to upload a franchise agreement and see clause-by-clause comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — franchisee-side and franchisor-side with different question sets.
D2: Ten key clauses: FDD compliance (23 mandatory items, 14-day delivery), fees and ongoing royalties, territory rights, renewal and termination, supply chain restrictions, post-termination non-compete, transfer and assignment restrictions, ongoing obligations, governing law/arbitration, fee stacking.
D3: Manual role selection determines which playbook applies.
D4: Saved client playbook.
D5: Green/yellow/red output.
D6: Excluded: FDD preparation, state franchise registration services, franchise relationship law compliance checking, multi-unit area development agreements, international franchise agreements, Arabic support.
D7: "It runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Franchise agreements are 30–50 page "take it or leave it" contracts drafted by the franchisor.
C2: 23 mandatory FDD items must be disclosed; 14-day delivery rule before signing.
C3: Targets solo lawyers and small law firms, no paralegal support.
___

ASSUMPTIONS MADE
A1: Lawyers have standard positions on franchise terms that can be captured in a playbook.
A2: The tool can read PDF or Word agreements.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-24: modes/GuaranteeCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Guarantee and Suretyship Agreements against each client's standard position — flagging personal liability traps, continuing guarantee exposure, waived defenses, and missing duration limits. Supports both creditor-side and guarantor-side modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a guarantee playbook per client (creditor-side or guarantor-side).
US2: As a solo lawyer, I want to upload a guarantee agreement and see green/yellow/red comparison per clause area.
US3: As a solo lawyer, I want to export a client memo with matching, differing, and missing clauses plus an overall verdict.
___

PRODUCT DECISIONS MADE
D1: Two modes — creditor-side and guarantor-side with different question sets.
D2: Seven key clauses: type of guarantee, surety defenses, duration and termination, waiver of defenses, subrogation rights, contribution among co-guarantors, notice requirements.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: Includes OCR for scanned PDFs.
D6: Excluded: surety bond analysis, UCC Article 3 comprehensive review, credit analysis, personal financial advice/solvency analysis, cross-guarantor comparison, automatic calculation of maximum exposure under continuing guarantees, Arabic support.
___

CONSTRAINTS IDENTIFIED
C1: "A guarantee is the most dangerous document most people sign" — personal assets (home, savings, future wages) are on the line.
C2: Guarantees are typically 5–15 pages.
C3: The guarantor receives nothing in return except the obligation to pay if the borrower defaults.
C4: A continuing guarantee can snowball without the guarantor realizing it — open-ended, no limit on amount or time.
___

ASSUMPTIONS MADE
A1: Guarantors often don't understand what type of guarantee they're signing (payment vs performance vs collection).
A2: Most guarantors don't know they may be on the hook for everything via joint and several liability.
A3: Clients have established positions on guarantee terms.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-25: modes/HireCheck.md
───────────────────────────────────────────

PURPOSE
Reviews employment agreements for solo lawyers — when a client receives a job offer or needs to send an offer to a new hire. Compares the agreement against the client's playbook and shows what's different.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set each client's standard employment positions (shared and employment-specific) during a one-time setup.
US2: As a solo lawyer, I want to upload an employment agreement and see green/yellow/red comparison per clause.
US3: As a solo lawyer, I want to export a client memo with matching terms, differing terms, and an overall verdict.
___

PRODUCT DECISIONS MADE
D1: Shared questions across products: confidentiality, IP assignment, non-solicit, governing law, dispute resolution.
D2: Employment-specific questions: role type, non-compete, severance, equity, benefits, termination notice, duty of loyalty, relocation, expenses.
D3: Two directions: client receiving an offer OR client sending an offer.
D4: Green/yellow/red output.
D5: Excluded: independent contractor and consulting agreements (see ConsultCheck), full contract drafting, multi-state compliance checking, Arabic support, long-term storage of signed contracts.
D6: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Employment agreements typically have 10–15 clauses that must be reviewed.
C2: The lawyer must find past positions on non-compete scope, severance, and equity terms each time without the tool.
C3: Targets solo lawyers and small firms.
___

ASSUMPTIONS MADE
A1: Clients have standard positions that can be saved and reused.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-26: modes/IndemnityCheck.md
───────────────────────────────────────────

PURPOSE
Reviews standalone Indemnification Agreements and indemnification provisions within other contracts — flagging one-sided obligations, defense cost traps, and survival period gaps. Supports both indemnitor (paying) and indemnitee (protected) sides.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to build an indemnification playbook per client (indemnitor or indemnitee).
US2: As a solo lawyer, I want to upload a contract and see clause-by-clause comparison per clause area.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — indemnitor (the party paying) and indemnitee (the party protected).
D2: Seven key clauses: "indemnify, defend, and hold harmless" (three separate obligations), scope of covered claims ("arising out of" broad vs "caused by" narrow), notice requirements, control of defense, caps/baskets/deductibles, survival period, subrogation and contribution rights.
D3: Checks whether the governing state has anti-indemnity statutes (construction, oil and gas states).
D4: Saved client playbook.
D5: Green/yellow/red output.
D6: Excluded: insurance coverage analysis, anti-indemnity statute database by state, full contract drafting beyond indemnification clauses, Arabic support.
D7: "It runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: "Indemnify, defend, and hold harmless" are three separate legal obligations often conflated into one sentence.
C2: The word "defend" forces the party to pay the other side's legal fees before anyone is found at fault.
C3: Some states have anti-indemnity statutes, particularly in construction and oil and gas.
C4: Indemnification is the most misunderstood clause in contract law.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on indemnification terms.
A2: The tool can read PDF or Word.
A3: Lawyers know which state's law applies and whether it has anti-indemnity statutes.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-27: modes/LeaseCheck.md
───────────────────────────────────────────

PURPOSE
Reviews commercial lease agreements — whether the client is renting space (tenant) or leasing property (landlord) — flagging lease type traps, CAM charge exposure, personal guarantee risks, maintenance/repair obligations, and use clause restrictions.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a client's commercial lease standard positions (tenant or landlord) during setup.
US2: As a solo lawyer, I want to upload a lease (or amendment or LOI) and see clause-by-clause comparison.
US3: As a solo lawyer, I want to know the real total monthly cost (base rent plus estimated CAM, taxes, insurance).
US4: As a solo lawyer with a retail or restaurant client, I want to check for retail/restaurant-specific add-ons and traps.
___

PRODUCT DECISIONS MADE
D1: Two modes — tenant and landlord with separate question sets.
D2: Seven key clauses: lease type (gross, triple-net, modified gross), operating expenses/CAM, personal guarantee, maintenance and repairs, use clause, assignment and subletting, default and remedies.
D3: Retail and restaurant add-ons: exclusivity, hours of operation, percentage rent, outdoor operations, liquor license, HVAC/kitchen maintenance, drive-through rights.
D4: Support for full lease, lease amendment, and letter of intent uploads.
D5: Automated calculation of true monthly cost (base + pass-throughs).
D6: Shared questions across products: governing law, dispute resolution, force majeure, confidentiality.
D7: Green/yellow/red output.
D8: Excluded: residential leases, purchase and sale agreements (see BuyCheck), full contract drafting, multi-state tenant rights compliance, CAM audit service (just flagging whether audit rights exist), sublease review, Arabic support.
D9: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Commercial leases are the most expensive contract most small businesses ever sign — a five-year lease at $5,000/month is a $300,000 commitment before extras.
C2: Most businesses sign a lease once every 5–10 years and don't know what's standard or negotiable.
C3: CAM charges can push real rent 30–50% above base rent.
C4: Personal guarantee means business owner's personal assets are on the line.
___

ASSUMPTIONS MADE
A1: The property location can auto-detect governing law.
A2: Lawyers have standard positions on lease terms.
A3: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-28: modes/LicenseCheck.md
───────────────────────────────────────────

PURPOSE
Reviews SaaS subscription agreements and software license agreements — whether the client is buying software (customer) or selling software (vendor) — flagging auto-renewal traps, data lock-in risks, audit rights, uncapped price increases, and beta feature gaps.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set standard SaaS positions per client (customer or vendor).
US2: As a solo lawyer, I want to upload a SaaS agreement and see green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings.
___

PRODUCT DECISIONS MADE
D1: Two modes — customer (buying software) and vendor (selling software) with separate question sets.
D2: SaaS-specific traps highlighted: auto-renewal, data lock-in, audit rights, usage restrictions, price increases with no cap, beta features (no warranty/liability), support levels.
D3: Shared questions across products: confidentiality, IP ownership, governing law, dispute resolution, data security, force majeure, liability cap, indemnification.
D4: Green/yellow/red output.
D5: Excluded: MSAs (see DealCheck), employment agreements (see HireCheck), consulting agreements (see ConsultCheck), NDAs (see PreCheck), full contract drafting, per-user pricing calculations, Arabic support.
D6: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: SaaS agreements have unique traps a general contract reviewer would miss: auto-renewal, data lock-in, audit penalties, uncapped price increases, beta features with no warranty.
C2: Auto-renewal silently continues unless cancelled 30–90 days before the end.
C3: Audit rights can result in back fees plus penalties if usage exceeds limits.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on SaaS terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-29: modes/LoanCheck.md
───────────────────────────────────────────

PURPOSE
Reviews loan agreements and promissory notes against the lawyer's standard — flagging usury traps, acceleration risks, security interest gaps, and financial covenant dangers. Supports both lender-side and borrower-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set standard loan agreement positions per client (lender or borrower).
US2: As a solo lawyer, I want to upload a loan agreement and see per-clause comparison.
US3: As a solo lawyer, I want to export a memo with findings and usury notes for the client to discuss with a tax professional.
___

PRODUCT DECISIONS MADE
D1: Two modes — lender-side and borrower-side with separate question sets.
D2: Seven key clauses: interest rate and usury compliance, payment terms (interest-only, amortizing, balloon), default provisions/cure periods, acceleration clause, security interests (UCC Article 9), financial covenants, prepayment and penalty provisions.
D3: Shared questions: governing law, dispute resolution.
D4: Usury notes included in export memo.
D5: Green/yellow/red output.
D6: Excluded: usury law database (just flagging), SBA loan compliance, securities law analysis, tax advice, loan brokerage/matching services, Arabic support.
D7: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Usury laws set maximum allowable interest rates — exceeding them can void the entire loan.
C2: Balloon payments are a major trap — borrower faces a large lump sum with no guaranteed refinancing.
C3: Breach of a financial covenant is an event of default even if payments are current.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on loan terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-30: modes/LOICheck.md
───────────────────────────────────────────

PURPOSE
Reviews Letters of Intent (LOIs) for business transactions — flagging binding vs non-binding ambiguity, missing exclusivity terms, and inadequate due diligence timelines before the deal locks in. Supports both buyer (offeror) and seller (offeree) modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a client's LOI playbook (buyer or seller).
US2: As a solo lawyer, I want to upload an LOI and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — buyer (offeror) and seller (offeree) with different question sets.
D2: Seven key clauses: binding vs non-binding provisions, exclusivity/no-shop, confidentiality, due diligence timelines, break-up fees/termination, transaction structure (asset vs stock), purchase price allocation.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: Excluded: definitive agreement drafting, due diligence management/data room setup, state securities law compliance review, tax advice on deal structure, Arabic support, long-term storage, multi-user accounts, AI training.
___

CONSTRAINTS IDENTIFIED
C1: LOIs look like informal documents but create real legal obligations.
C2: The binding vs non-binding distinction is where most mistakes happen — some clauses are binding (confidentiality, exclusivity, governing law), others are not (price, deal structure).
___

ASSUMPTIONS MADE
A1: Lawyers have established positions on LOI terms that can be saved.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-31: modes/OpCheck.md
───────────────────────────────────────────

PURPOSE
Reviews LLC Operating Agreements against the client's standard position — flagging missing buy-sell provisions, capital account traps, fiduciary duty gaps, and tax election misalignment. Supports both member-side and manager-side.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set an operating agreement playbook (member-side or manager-side).
US2: As a solo lawyer, I want to upload an operating agreement and see green/yellow/red comparison per clause area.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — member-side and manager-side with different question sets.
D2: Seven key clauses: management structure (member-managed vs manager-managed), capital accounts/contribution obligations, profit/loss allocation and distributions, buy-sell provisions, fiduciary duties, transfer restrictions, dissolution and continuation.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: OCR for scanned PDFs.
D6: Excluded: state-specific LLC statute database, tax election advice (pass-through vs entity-level), Articles of Organization drafting, multi-member vs single-member comparative analysis, cross-LLC comparison, automatic tax distribution calculation, Arabic support.
___

CONSTRAINTS IDENTIFIED
C1: Most operating agreements are downloaded from the internet and miss critical provisions.
C2: A missing buy-sell provision can leave a client's family stuck with an illiquid interest in a business.
C3: Operating agreements are typically 15–40 pages with cross-references.
C4: Default in most states is member-managed, which may not match the client's intent.
___

ASSUMPTIONS MADE
A1: References IRC Section 704(b) (profit/loss allocation) are familiar to the lawyer.
A2: References IRC Section 754 (inside basis adjustment) are familiar.
A3: Clients have established standard positions on operating agreement terms.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-32: modes/PartnerCheck.md
───────────────────────────────────────────

PURPOSE
Reviews partnership agreements against the lawyer's own standard for a well-drafted partnership — flagging missing clauses, dangerous default rules, and tax traps. Handles three partnership types: General Partnership, Limited Partnership, and Limited Liability Partnership.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set my standard template for partnership agreements (not per-client history, but my own framework).
US2: As a solo lawyer, I want to upload a partnership agreement and see per-clause comparison against my standard.
US3: As a solo lawyer, I want partnership-type-specific checks (GP, LP, LLP) with extra questions for each.
US4: As a solo lawyer, I want to select review context: pre-signing, amendment, or new partner admission.
___

PRODUCT DECISIONS MADE
D1: Three partnership type variants: General Partnership, Limited Partnership, Limited Liability Partnership, each with specific extras.
D2: Three review contexts: pre-signing review, amendment review, new partner admission.
D3: Core questions apply to all types; GP-specific (joint and several liability, mutual agency, apparent authority), LP-specific (limited partner safe harbor, GP control, key person, investor protections, anti-Holzman language, special tax allocations, transfer of interests), LLP-specific (professional regulatory compliance, insurance, locked capital, partner retirement, client continuity, succession).
D4: Green/yellow/red output with type-specific examples.
D5: Excluded: LLC operating agreements (see OpCheck), corporate bylaws/shareholder agreements, full contract drafting, international partnership agreements (non-US law), tax return preparation/tax advice/IRC analysis, partnership dissolution services, Arabic support.
D6: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Partnership agreements are governance documents between people who trust each other — not arm's-length buyer/seller deals.
C2: General partners are jointly and severally liable for everything.
C3: In Limited Partnerships, exercising management rights can cost Limited Partners their liability shield.
C4: A 50/50 partnership with no deadlock mechanism is paralyzed on every disagreement.
___

ASSUMPTIONS MADE
A1: The lawyer has a standard "best-practice framework" for partnership agreements (not per-client history).
A2: The spec assumes familiarity with Section 754 election, Section 179 deduction allocation, Section 704(b) compliant capital account maintenance, and "anti-Holzman language."
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-33: modes/PreCheck.md
───────────────────────────────────────────

PURPOSE
Reviews incoming Non-Disclosure Agreements (NDAs) and instantly shows what's different from what each client normally accepts. The simplest product mode — 6 setup questions, green/yellow/red comparison, one-click memo.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a client's NDA playbook with 6 standard positions so I don't have to search "what did this client accept last time."
US2: As a solo lawyer, I want to upload an NDA and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Six client setup questions: one-way or mutual, confidentiality duration, definition of confidential information, exclusions (public info, independently developed, known), governing law, remedy for breach.
D2: Saved client playbook.
D3: Green/yellow/red output.
D4: Export memo with three sections (matching, differing, overall verdict).
D5: Excluded: other contract types (MSA, employment, lease), Arabic support, long-term storage, multi-user accounts, AI training.
D6: "It runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Solo lawyers waste time hunting for "what did this client accept last time" for each NDA.
C2: Lawyers charge by the hour and have no paralegal support.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on 6 NDA dimensions that can be captured.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-34: modes/PrivacyCheck.md
───────────────────────────────────────────

PURPOSE
Reviews Data Processing Agreements (DPAs) — the privacy add-on attached to MSAs and SaaS agreements whenever personal data is involved — flagging controller/processor role confusion, cross-border transfer gaps, sub-processor notice issues, and breach notification timeline problems. Checks for conflicts between the DPA and the main agreement.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set standard data processing positions per client (controller or processor).
US2: As a solo lawyer, I want to upload a DPA and see clause-by-clause comparison.
US3: As a solo lawyer, I want the DPA checked against the main agreement (MSA or SaaS) for conflicts.
___

PRODUCT DECISIONS MADE
D1: Two modes — controller (data owner) and processor (data handler) with separate question sets.
D2: Combined review with the main agreement (MSA or SaaS) for conflicts between the two documents.
D3: Shared questions across products: IP ownership, governing law, dispute resolution, force majeure, liability cap, indemnification.
D4: Specific DPA checks: cross-border transfers (SCCs, UK Addendum, DPF), sub-processors (general auth vs specific approval, notice period), breach notification (hours), data return timeline, data subject rights assistance, audit rights, security measures.
D5: Green/yellow/red output with conflict flags.
D6: Excluded: SaaS agreements (see LicenseCheck), MSAs (see DealCheck), NDAs (see PreCheck), full contract drafting, multi-regulatory compliance checking, Arabic support.
D7: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: DPAs are always an add-on to another agreement — never standalone. The lawyer must read two documents together and check for conflicts.
C2: Most DPA clauses are required by law (GDPR Article 28), not by negotiation.
C3: Cross-border data transfers need specific legal mechanisms: Standard Contractual Clauses, UK Addendum, or Data Privacy Framework.
C4: Missing breach notification timeline can mean fines.
C5: Missing data security annex makes the DPA incomplete (GDPR Article 32).
___

ASSUMPTIONS MADE
A1: The main agreement (MSA or SaaS) may already be in the system for conflict checking.
A2: Clients have standard positions on data processing terms.
A3: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-35: modes/SettlementCheck.md
───────────────────────────────────────────

PURPOSE
Reviews settlement and release agreements against the lawyer's own standard — flagging dangerous release language, hidden tax consequences, government reporting obligations (Medicare/Medicaid), and practice-area-specific traps (employment, personal injury, commercial). Supports plaintiff and defendant roles.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set my standard settlement template (best-practice framework) for settlement agreements.
US2: As a solo lawyer, I want to upload a settlement agreement and see per-clause green/yellow/red comparison.
US3: As a solo lawyer, I want practice-area-specific checks (employment, personal injury, or commercial) with extra rules for each.
US4: As a solo lawyer, I want to select role (plaintiff or defendant), practice area, and context (pre-litigation, litigation, post-judgment).
___

PRODUCT DECISIONS MADE
D1: Two roles — plaintiff (receiving payment) and defendant (paying and seeking finality), each with core and context-specific question sets.
D2: Three practice areas: employment, personal injury, commercial — each with specific extras.
D3: Three contexts: pre-litigation settlement, litigation settlement, post-judgment settlement.
D4: Nine key clauses: release of claims, tax allocation, Medicare/Medicaid compliance, confidentiality/non-disparagement, non-admission of liability, waiver of unknown claims, indemnification/hold harmless, payment terms/timing, ongoing obligations.
D5: Green/yellow/red output with role- and practice-area-specific examples.
D6: Export memo includes tax notes on how proceeds are likely to be taxed.
D7: Excluded: corporate bylaws/shareholder agreements, class action settlement review, tax advice (just flagging), full contract drafting, bankruptcy settlement review, international settlements, Arabic support.
D8: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: Settlement agreements are "the most dangerous type of contract on a per-clause basis" — they permanently extinguish rights, often including rights the client doesn't know they have.
C2: Cites specific statutes: IRC Section 104(a)(2) (physical injury tax-free), IRC Section 409A (deferred compensation), OWBPA (21-day consideration, 7-day revocation for ADEA claims), California Civil Code Section 1542 (unknown claims waiver), Medicare/Medicaid SCHIP Extension Act Section 111 ($1,000/day non-compliance penalty), Speak Out Act (2022), Silenced No More Act, IRC Section 130 (structured settlement assignments).
C3: Wrong tax characterization can trigger IRS audit and tax deficiency.
C4: Medicare non-compliance penalty: $1,000 per day per claim.
___

ASSUMPTIONS MADE
A1: The lawyer has a standard template for settlement agreements.
A2: The lawyer has practice areas they typically handle (employment, personal injury, or commercial).
A3: The lawyer can select role, practice area, and context for each review.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-36: modes/SponsorCheck.md
───────────────────────────────────────────

PURPOSE
Reviews sponsorship agreements — flagging vague deliverables, missing brand usage rights, tax deductibility traps, and termination gaps before the money starts flowing. Supports both sponsor (paying) and sponsee (receiving) modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a sponsorship playbook per client (sponsor or sponsee).
US2: As a solo lawyer, I want to upload a sponsorship agreement and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — sponsor (paying for exposure) and sponsee (receiving sponsorship) with different question sets.
D2: Seven key clauses: scope and deliverables, brand usage/IP licensing, exclusivity provisions, payment terms/timing, termination and refund provisions, indemnification/insurance, content approval rights.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: Excluded: tax advice on UBIT (Unrelated Business Income Tax), nonprofit compliance review, FTC disclosure analysis, ASC 606 revenue recognition analysis, Arabic support, long-term storage, multi-user accounts, AI training.
___

CONSTRAINTS IDENTIFIED
C1: Sponsorship agreements sit at the intersection of marketing, IP, tax, and contract law.
C2: Vague deliverables are a key risk — "reasonable promotional support" is too vague to enforce.
C3: Exclusivity provisions can be too broad ("all industries") with significant consequences.
___

ASSUMPTIONS MADE
A1: Clients have established positions on sponsorship terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-37: modes/SubCheck.md
───────────────────────────────────────────

PURPOSE
Reviews subcontractor agreements — flagging flow-down clause traps, pay-when-paid risks, one-sided indemnification, and insurance gaps. Supports both General Contractor (GC) and subcontractor modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set a subcontractor playbook per client (GC or subcontractor).
US2: As a solo lawyer, I want to upload a subcontract and see clause-by-clause green/yellow/red comparison.
US3: As a solo lawyer, I want to export a client memo with findings and recommendations.
___

PRODUCT DECISIONS MADE
D1: Two modes — general contractor and subcontractor with different question sets.
D2: Seven key clauses: scope of work/change orders, payment terms (pay-when-paid vs pay-if-paid, retainage), flow-down clause (inherits prime contract obligations), indemnification/hold harmless, insurance requirements (workers' comp, general liability, umbrella, additional insured), dispute resolution, termination provisions.
D3: Saved client playbook.
D4: Green/yellow/red output.
D5: Excluded: construction law compliance review, prevailing wage analysis, mechanic's lien filing guidance, OSHA compliance checks, contractor licensing verification, Arabic support, long-term storage, multi-user accounts, AI training.
___

CONSTRAINTS IDENTIFIED
C1: Subcontractor agreements are "the most dangerous documents in construction" — typically 30–50 pages of dense construction language.
C2: A single flow-down clause can inherit the entire prime contract obligations in one sentence.
C3: Indemnification using "arising out of" language covers even when the subcontractor did nothing wrong.
___

ASSUMPTIONS MADE
A1: Clients have established positions on subcontract terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════

═══════════════════════════════════════════
PRODUCT SPEC PR-38: modes/WorkCheck.md
───────────────────────────────────────────

PURPOSE
Reviews independent contractor work agreements for project-based work (not ongoing/retainer-based; see ConsultCheck) — flagging misclassification risk, intellectual property gaps, vague scope, and payment traps. Supports both client (hiring) and contractor (being hired) modes.
___

USER STORIES / JOBS DEFINED
US1: As a solo lawyer, I want to set standard work agreement positions per client (client-side or contractor-side).
US2: As a solo lawyer, I want to upload a work agreement and see green/yellow/red comparison.
US3: As a solo lawyer, I want to export a memo with misclassification risk notes besides the standard findings.
___

PRODUCT DECISIONS MADE
D1: Boundary with ConsultCheck: WorkCheck covers project-based work with defined deliverables (web design, app development, content creation); ConsultCheck covers ongoing/retainer-based consulting relationships.
D2: Two modes — client-side (hiring the contractor) and contractor-side (being hired) with separate question sets.
D3: Seven key clauses: independent contractor status (IRS 20-Factor Test reference), scope of work/deliverables, IP assignment or work-for-hire, payment terms (deposit, milestones, late penalties), termination for cause and convenience, confidentiality, non-solicitation and non-compete.
D4: Shared questions across products: governing law, dispute resolution, confidentiality.
D5: Misclassification risk notes included in export memo.
D6: Green/yellow/red output.
D7: Excluded: misclassification legal advice (just flagging risk indicators), IRS 20-Factor Test analysis, state-specific worker classification guidance, tax filing/1099 preparation, full contract drafting, Arabic support.
D8: "Runs on your computer as a simple program."
___

CONSTRAINTS IDENTIFIED
C1: "A signed independent contractor agreement does NOT shield you if the actual working relationship shows employer control."
C2: Independent contractor agreements are the most misused contracts in small business.
C3: Silence on IP ownership means the contractor owns everything they create.
___

ASSUMPTIONS MADE
A1: Clients have standard positions on work agreement terms.
A2: The tool can read PDF or Word.
___

IMPLEMENTATION STATUS
UNKNOWN
___

OPEN QUESTIONS IN SPEC
N/A
════════════════════════════════════════════
