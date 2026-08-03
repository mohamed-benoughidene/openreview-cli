# Architecture

openreview-cli is a local-first, privacy-first contract review automation tool: an async stage pipeline, an AI Gateway abstraction over 17 providers, SQLite storage, per-document retrieval indexes, and a spec-driven development process that has produced 33 specs. This document describes how the pieces fit, with honest limitations where the implementation is simpler than the ambition.

## Dual interface

The tool serves two audiences through the same codebase:

- **Human CLI/TUI:** `openreview precheck review contract.pdf` (Typer CLI) or no-args → Textual TUI with 13 screens. Rich formatting, progress bars, interactive prompts.
- **Agent/programmatic API:** every module is independently importable (`from openreview_cli.parsing.stream import parse_document`, `from openreview_cli.review.extraction import extract_clause`, etc.). CLI supports `--format json` / `--memo-format json --output <path>` for structured output. The benchmark runner (`BenchmarkRunner`) and pipeline runner (`run_review`) are Python-callable. Non-zero exit codes signal failures for automation.

- [Dual interface](#dual-interface)
- [Pipeline](#pipeline)
- [Model routing](#model-routing)
- [Data flow and SQLite's two roles](#data-flow-and-sqlites-two-roles)
- [AI Gateway](#ai-gateway)
- [Retrieval and chunking](#retrieval-and-chunking)
- [Negotiation, comparison, graph](#negotiation-comparison-graph)
- [Spec-driven development](#spec-driven-development)
- [Honest limitations](#honest-limitations)

## Pipeline

```mermaid
flowchart LR
    F[PDF / DOCX] --> P[ParseStage]
    P --> S{StripStage<br/>fail-closed gate}
    S -- page detection failure --> HALT["halt before any API call<br/>(--allow-partial-pii opts out)"]
    S --> R[ReviewStage]
    R --> C["per-clause: keyword match (no LLM)"]
    C --> E["extraction agent (LLM)<br/>position + confidence + citation"]
    E --> Q["QA agent (LLM)<br/>agree / disagree / uncertain"]
    Q --> G["citation grounding (LLM discriminator)<br/>strict / lenient"]
    G --> M[structured memo + report]
    D[(SQLite app DB)] -.-> R
    D -.-> G
    I[(per-doc index DB)] -.-> R
```

The pipeline is an async sequential framework (`pipeline/base.py`: `Stage` ABC + runner). Stages:

1. **ParseStage** (critical): PyMuPDF page-by-page streaming iterator the full PDF is never loaded into memory (the public `parse_document()` materializes the clause list; the streaming path does not). DOCX via python-docx. Clause detection is heuristic: 7 regex header patterns plus nupunkt sentence segmentation (lazy, one-time ~3 s model load per process). Metadata extraction covers author/title/company, corrupt/empty/password detection (`OPENREVIEW_PDF_PASSWORD`), and non-English + tofu (broken glyph) detection.
2. **StripStage**: Presidio PII engine with spaCy `en_core_web_lg` plus 4 custom regex recognizers (AMOUNT, TAX_ID, ID_DOCUMENT, REG_NUMBER). **Fail-closed by default**: any page-detection failure raises `PartialProcessingError`; the pipeline converts it to `CriticalStageError` and halts before any external API call. `--allow-partial-pii` opts out. A 50-char overlap buffer catches boundary-crossing PII. Entities become `[PARTY_A]`-style placeholders; the reversible mapping is encrypted with Fernet (AES-128-CBC + HMAC), key derived via HKDF-SHA256(document_hash + salt), written chmod 600 to `{data_dir}/reviews/{id}/pii_map.enc`. An audit JSON is written per review.
3. **ReviewStage**: multi-agent review means separate LLM calls per clause, not agent classes keyword category match (no LLM) → extraction agent (LLM, JSON: position, confidence, citation) → QA agent (LLM, verdict agree/disagree/uncertain, amber flag). Playbook selection precedence: DB id > file path > bundled (24 YAMLs: `precheck-nda-v1`, `saas-license-v1`, `hirecheck-v1`, …). Findings use a 3-position model: Preferred / Acceptable / Walkaway.
4. **Citation grounding** (post-pipeline): an LLM discriminator verifies each claim against the source (strict/lenient modes). A failure here never kills the review.

The runner emits per-stage progress events and tracks per-stage memory via tracemalloc against a quota. A recovery coordinator selects among 5 strategies by error category: `auto_retry` (exponential backoff), `provider_fallback`, `graceful_degradation`, `stage_isolation`, `user_guided_recovery`; recovery state persists to the `recovery_state` table.

## Model routing

All model calls go through the AI Gateway (litellm): `chat → completion`, `embed → embedding`, `rerank → rerank`. Six slots route per task:

| Slot | Default (local, fully offline) | Cloud examples | Why |
|---|---|---|---|
| reasoning | `qwen3:8b` (Ollama) | `gpt-4o`, `claude-sonnet-latest`, `gemini-2.0-flash`, `deepseek-chat` | highest-capability local model; hard reasoning stays local by default |
| extraction | `qwen3:4b` (Ollama) | `gpt-4o-mini`, `claude-haiku-latest` | smaller/faster, enough for structured JSON extraction |
| embedding | `nomic-embed-text` (Ollama) | `text-embedding-3-small`, `text-embedding-004` | primary-only: no embedding fallback (fallback model would change vector space) |
| reranking | `qwen3-reranker-0.6b` (Ollama) | provider rerank APIs | primary-only; disabled by default (see limitations) |
| grounding | `qwen3:8b` (Ollama) | | claim-vs-source verification |
| graph | `qwen3:8b` (Ollama) | | clause-graph health scoring and clustering |

Privacy tier routing (`maximum` / `balanced` / `performance`) gates which providers a slot may use; `maximum` blocks cloud entirely. Fallback: 2 retries, 60 s timeout, a fallback model per slot except embedding/reranking, which are primary-only by design.

## Data flow and SQLite's two roles

SQLite serves two distinct roles:

1. **App database** a single `openreview.db` in the platformdirs data dir. 12 migrations (001–013, no 012), 20 tables: `clients`, `reviews`, `review_reports`, `review_diffs`, `cost_logs`, `pii_cache`, `pii_audit_trail`, `prompt_versions`, `prompt_bindings`, `playbook_versions`, `playbook_meta`, `benchmark_runs`/`results`/`baselines`, contract graph (`graph_nodes`/`edges`/`meta`), `recovery_state`, `schema_version`.
2. **Per-document retrieval indexes** separate SQLite files at `{data_dir}/indexes/{doc_hash}.db`, isolating vector/FTS data per contract.

Pipeline flow: parse → strip → review writes the review + report + cost rows to the app DB; retrieval reads from the per-doc index DB; the encrypted PII map and audit JSON live next to the review in `{data_dir}/reviews/{id}/`.

## AI Gateway

- **Single abstraction**: litellm for chat, embedding, and rerank calls one surface over 17 providers, 27 bundled models in `models.json` (openai, anthropic, google, ollama with auto-discovery via localhost:11434, openrouter, cohere, huggingface, deepseek, qwen, minimax, voyage, moonshot, mistral, zai; bedrock/azure/vertex supported via multi-field credentials, spec 034).
- **Fallback & streaming**: 2 retries default, 60 s timeout, fallback model per slot; streaming chat with 15 s connect / 45 s idle timeouts.
- **Cost tracking**: tokens from responses → `litellm.completion_cost` → cents → SQLite `cost_logs` (non-fatal on error); configurable per-review/per-day limits (100¢ / 1,000¢, warn-only defaults).
- **Privacy**: tier routing per slot; a redaction filter strips API-key patterns from **all** logs.
- **Credentials**: multi-field provider credentials (spec 034) CLI-managed (`openreview gateway set`, `provider add`), stored in `auth.json` (chmod 600).

## Retrieval and chunking

- **Chunking**: custom RCTS recursive char split on `["\n\n", ". "]` with word-split fallback and merge of undersized chunks; regex tokenizer (explicitly an approximation, not model-aware); defaults 512 tokens / 50 overlap; clause-boundary aware; groups short clauses; flattens tables.
- **Retrieval**: hybrid BM25 + dense + RRF. BM25 via SQLite FTS5 (unicode61, prefix 2–3); dense via gateway embeddings (default `nomic-embed-text`) with a **brute-force cosine scan no vector DB, no ANN**; RRF fusion (k=60). A reranker exists but is disabled by default (it degrades legal text; opt-in `--rerank`, auto-disables after 3 consecutive degradations). Degrades gracefully to BM25-only when the gateway is unavailable.

## Negotiation, comparison, graph

- **Negotiation** (`openreview negotiate`): pure local NumPy game theory Nash (support enumeration), QRE (logit fixed-point), Level-k (k ≤ 3). **No LLM calls** in this path; assessments are built from playbook heading-match and default positions a simplified local path, not the full review pipeline.
- **Bilateral comparison** (`precheck compare`): experimental. RCBSF 5-dimension divergence taxonomy (category/location/evidence/issue/suggestion), 3-tier heading alignment, LLM comparison agent. Documented accuracy ceiling ≤ 64% F1.
- **Contract graph** (`openreview graph`): directed clause graph (`parent_child`, `cross_ref`, `def_ref` edges); 0–100 health score from 5 structural metrics (density, depth, orphan ratio, broken refs, definition coverage); ASCII tree view; graph diff; optional `legal-bert` + HDBSCAN clustering (`--cluster-clauses`, first-time model download).

## Spec-driven development

Development is driven by spec-kit: requirements land as specs in `specs/`, get plans, then implementation. 33 spec directories (001–034; 023 absent), including:

| Spec | Area |
|---|---|
| 001 | Config + storage |
| 002 | Document parsing |
| 003/004 | PII |
| 005 | AI Gateway |
| 007 | Chunking strategy |
| 010 | Benchmark harness |
| 011 | Single-party review 3-agent pipeline |
| 012 | Citation grounding |
| 016 | Hierarchical retrieval (BM25 + dense + RRF) |
| 018 | 5-stage async pipeline |
| 020 | Privacy tier routing |
| 025 | Contract graph |
| 026 | Game-theoretic negotiation |
| 032 | Interactive TUI |
| 033 | AI Gateway v2 (fail-safe privacy routing, full provider registry, capability validation, streaming) |
| 034 | Multi-field provider credentials |

Deferred work is tracked in `specs/DEFERRED.md` check it before touching any module with open deferrals.

## Honest limitations

- **Dense retrieval is a brute-force cosine scan** over the per-doc index no vector DB, no ANN. Fine for single contracts; document the ceiling.
- **Regex tokenizer** approximates tokens; chunk sizes are estimates, not model-precise counts.
- **Benchmark harness**: CUAD/MAUD/ContractNLI paths use a mock pipeline by default (real LLM integration deferred); PII benchmarks use the real engine. Hallucination detection is a ROUGE-L lexical-overlap placeholder (EXPERIMENTAL default).
- **`prompt test` (A/B) and `prompt optimize` are roadmap stubs** the prompt storage, versioning, bindings, and YAML import/export are real; the A/B and optimization commands are not shipped features.
- **Negotiation uses a simplified local path** (heading-match + defaults), not the full review pipeline no LLM, no clause grounding.
- **Bilateral comparison has a documented accuracy ceiling ≤ 64% F1** and is experimental.
- **Audit-table gap**: the `pii_audit_trail` SQL table and `pii_cache` exist, but the pipeline currently writes the audit trail to a JSON file only verified source gap.
- **TUI discipline**: the Textual TUI must never import litellm at module level (lazy gateway via PEP 562 + domain wrappers) keeps TUI startup fast; treat that boundary as load-bearing.
- **Cost/accuracy numbers**: see [BENCHMARKS.md](BENCHMARKS.md) for what was measured this session and what was not.

Back to [README.md](README.md) (overview) · [BENCHMARKS.md](BENCHMARKS.md) (measured numbers).
