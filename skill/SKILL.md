---
name: openreview-cli
version: 0.10
description: Use when a user wants to review, compare, search, or analyze legal/contract documents (PDF/DOCX) locally — produce review memos, compare two versions, search indexed clauses, run negotiation analysis, manage LLM gateway slots/playbooks, or audit/delete stored PII mappings. This is the local `openreview` CLI, NOT the openreview.net academic platform.
---

# openreview-cli

## Purpose

Maps user intent to the correct `openreview` CLI command for local document-review work. Covers: CLI bootstrap (install/verify/readiness), review-memo production, bilateral comparison, retrieval over indexed chunks, negotiation analysis, gateway/playbook/PII management, privacy-tier configuration, and export of saved reports. It is a routing layer for an agent — not CLI documentation, not a tutorial, not the openreview.net academic platform.

## Before Using OpenReview

Bootstrap the CLI before any contract-review work. Do not assume OpenReview is installed, configured, or ready — verify each stage. The package is `openreview-cli` on PyPI (NOT the unrelated `openreview` / `openreview-py` academic-platform packages).

### 1. Determine Whether OpenReview Applies

Check `## When to Use` / `## When NOT to Use` first. If the request is outside the verified contract-review surface (filesystem ops, legal advice, benchmarks, config/graph/prompt/client/TUI operator tasks), decline — do not install or invoke the CLI.

### 2. Check Whether OpenReview Is Available

Run `openreview --version`. Success (prints `openreview <version>`) → CLI is installed and callable → proceed to readiness. "command not found" / no such executable → CLI is absent → install.

### 3. Install If Necessary

Only when the availability check failed:

```
pip install openreview-cli
```

- Requires Python ≥ 3.12.
- Installs the `openreview` console command (entry point `openreview_cli.app:app`).
- A successful install exit code is NOT the end of bootstrap — verify next.

### 4. Verify Installation

After install, confirm the CLI is usable:

```
openreview --version
openreview --help
```

Both must succeed. `--help` must list at least the expected subcommands (parse, chunk, ingest, retrieve, negotiate, export, product modes, gateway, playbook, pii, config). Additional operator-only groups also appear in `--help` (precheck, index-status, index-clear, client, graph, benchmark, prompt) — that is expected and they are out of routing scope (see When NOT to Use). If verification fails, report the error verbatim; do not retry blindly (Rule 10). Installation failure is an environment/package problem, not a workflow problem.

### 5. Determine Setup and Readiness Requirements

Installation and configuration are **separate states**. A freshly installed CLI is NOT ready to review:

- **Check config:** `openreview gateway status` — shows each of the 6 slots (reasoning, extraction, graph, grounding, embedding, reranking) with status.
- **`configured`** → provider assigned and ready: API key present for cloud providers; keyless for local ollama. Ready for that slot.
- **`missing_api_key`** → a *cloud* slot has a provider but no credentials → must configure before cost-bearing work. Local/keyless providers (ollama) never show this — if they did, it would be a false alarm.
- **`not_configured`** → no provider assigned to the slot yet (no config/primary) — the default for a fresh install. Configure it before a workflow that consumes that slot.
- **Ollama is local and keyless** — if the user wants fully local/on-device processing, `gateway set <slot> ollama/<model>` (list local models with `gateway models ollama`) needs no API key, only a running local Ollama server.
- **Cloud providers require API keys** — stored in `~/.config/openreview/auth.json` (chmod 600). The agent does not collect or enter keys itself; `gateway setup` is interactive and a human runs it in their own terminal. Agent-driven alternatives: `gateway set <slot> <model>` (model assignment) and `gateway provider add <name> --base-url <url> [--env-key VAR] [--cred k=v]` (custom provider). **`--cred k=v` places the key in shell history/process args — prefer the user running it in their own terminal or setting the key via its environment variable rather than passing the secret on the command line.**

### 6. Verify Readiness Before the Workflow

Before a cost-bearing workflow (`precheck review`, product modes, `precheck compare`):

1. `openreview gateway status` — needed slots `configured` (or keyless local ollama).
2. `openreview gateway test <slot>` — provider reachable (network check; may fail if local Ollama isn't running).
3. Only then run the review workflow.

If a slot is `missing_api_key` or `gateway test` fails: report what is missing and what information/setup is needed — never run the review blindly into a gateway error. `negotiate` does NOT require the gateway (pure local NumPy).

### 7. Privacy Tier (task-relevant configuration)

- Check the active tier: `openreview config get privacy.tier`.
- Set it: `openreview config set privacy.tier maximum|balanced|performance`.
- `maximum` — all LLM + embedding inference runs local-only (Ollama); no data is transmitted externally.
- `balanced` — PII stripped locally; LLM reasoning may use cloud; embeddings local.
- `performance` — PII stripped locally; LLM + embeddings may use cloud.
- The tier is persistent (stored in `~/.config/openreview/config.yml`) and enforced per-operation by the gateway. This is a **processing-policy** control, distinct from PII stripping (see Privacy Routing below).

## When to Use

Activate when the user request matches any of:

- **(A) Review a local document** — user hands a PDF/DOCX and asks for review, analysis, risks, or a memo.
- **(B) Query saved local artifacts** — user asks about previously-produced memos, clauses, PII mappings, or metrics on disk.
- **(C) Vague but document-review-oriented** request with no file path yet ("summarize my contract", "what are the risks here").

Recognizable entities: PDF/DOCX documents, clauses, review memos, playbooks/categories, gateway/LLM slots, PII mappings, retrieval indices.

## When NOT to Use

- **Filesystem management only** — rename/move/delete/organize files with no review logic.
- **Trivial file inspection** — page count, word count, file size.
- **General contract-law/knowledge questions with no document** — no review task exists.
- **Benchmarks / accuracy checks** — `benchmark run`, `benchmark baseline` are developer/operator-only.
- **Low-level operator tasks** — `config show/get/set`, `graph *`, `prompt *`, `client *`, TUI. Do not route user requests to these.
- **`parse` / `chunk` as a *review substitute*** — never use them as the answer to "review this." They are OPTIONAL building blocks (see Optional Capabilities): legitimate as a terminal deliverable only when the user explicitly asks for clause-level output (`parse`) or chunk output (`chunk` for indexing). Never as a mandated pipeline step, never as a review.
- **Legal interpretation** — the agent relays and structures CLI output; a human interprets.
- **PII handling** — PII stripping is automatic and fail-closed for `precheck review` and `precheck compare`. Never bypass, never second-guess. Exception: `negotiate` does NOT strip PII (Capability 5).

## Available Capabilities

### 1. Review & Produce Memo
End-to-end: parse → PII-strip → extract → QA → memo.

Use when: user wants analysis/risks/memo on one or more documents.

CLI: `openreview precheck review <paths...>` — or a product-mode command when the user names a document type. 22 product modes exist: `licensecheck` (SaaS license), `leasecheck` (commercial lease), `privacycheck` (DPA), `dealcheck` (vendor/service), `hirecheck` (employment), `indemnitycheck` (indemnification), `consultcheck` (consulting), `workcheck` (independent contractor), `loicheck` (LOI/MOU), `subcheck` (subcontractor), `settlementcheck` / `settlementcheck_v2` (settlement/release), `assetcheck` (asset transfer), `buycheck` (asset purchase/acquisition), `engagecheck` (engagement letter), `guaranteecheck` (personal guarantee), `loancheck` (loan/promissory note), `franchisecheck` (franchise/FDD), `opcheck` (operating agreement), `partnercheck` (partnership), `sponsorcheck` (sponsorship), `distrocheck` (distribution/reseller). For the authoritative list, run `openreview --help`.

Required: one or more PDF/DOCX paths.

Key constraint: memo written to `review_results/` by default.

### 2. Bilateral Comparison
Clause-by-clause comparison of two documents.

Use when: user explicitly wants to compare two versions/documents.

CLI: `openreview precheck compare <doc_a> <doc_b>`

Required: two PDF/DOCX paths.

Key constraint: EXPERIMENTAL (≤64% F1) — disclose this to the user.

### 3. Retrieval & Index Management
Search indexed clause chunks; manage the local index.

Use when: user wants to search already-indexed documents or manage the index.

CLI: `openreview ingest <file.ndax>` → `openreview retrieve "<query>" [file]`; ops: `openreview index-status <file>`, `openreview index-clear [file|--all]`. Destructive (`index-clear`) requires explicit user intent — see Rule 10.

Required: for `ingest`, a JSON file containing a list of chunk dicts (`.ndax` is a user-applied extension; any JSON list works). For `retrieve`, a query string; `file` falls back to last indexed document.

Key constraint: no CLI command produces `.ndax`. To build one: `openreview chunk <doc> --format json` (stdout) → save to file → `ingest` (`chunk` is OPTIONAL — see Optional Capabilities). `precheck review` does NOT require chunking or indexing. **`ingest`/`retrieve` default to `hybrid`, which needs the `embedding` slot configured; without it the CLI silently falls back to BM25/sparse and prints a fallback notice. Surface that notice to the user, or use `--method sparse` deliberately to avoid the silent quality drop. `--rerank` is opt-in and routes to the configured `reranking` slot (e.g. `ollama/qwen3-reranker-0.6b`, `cohere/rerank-english-v3.0`, `voyage/rerank-2.5`); it needs that slot configured and reachable — check `gateway status` (slot `configured`) then `gateway test reranking` before relying on it.**

### 4. Query Saved Artifacts
List previously-produced review outputs.

Use when: user asks "show my past reviews".

CLI: none — read the default output dir `review_results/` from disk. Use `export` to re-format.

Key constraint: saved memos are outputs, not compare inputs. If the user asks to compare a document against a previously reviewed one, the original document (or the user) is needed — a saved memo is not a valid `precheck compare` input. Locate the original file or ask.

**When you produced an output yourself with `--output <file>` or `--output-dir <dir>`, remember that path for the session — saved artifacts may live outside `review_results/`. Re-read the path you used, not just the default dir.**

### 5. Negotiation Analysis
Game-theoretic QRE/Nash/Level-k assessment. Pure NumPy, no LLM.

Use when: user asks about negotiation dynamics/leverage.

CLI: `openreview negotiate <doc_path>` (`--solver qre|nash|level_k`, `--format table|json|memo`).

Required: one PDF/DOCX path.

Key constraint: `negotiate` does NOT strip PII — it parses the document directly (no `PiiEngine`; there is no `--no-pii` flag on it). Never promise privacy for negotiation analysis; if redaction matters, use `precheck review` instead.

### 6. Gateway & Provider Management
Configure LLM provider slots, check costs/connectivity, refresh model registry.

Use when: user wants to set up/inspect LLM providers or costs.

CLI: `openreview gateway setup` (interactive TTY wizard — a human runs this in their own terminal; the agent cannot drive it headless) | `status` | `providers` | `models <provider>` | `set <slot> <model>` | `refresh` | `test <slot>` | `costs [--today]`; custom provider (non-interactive): `openreview gateway provider add <name> --base-url <url> [--env-key VAR] [--cred k=v]...`.

Key constraint: 6 slots — reasoning, extraction, graph, grounding, embedding, reranking. Agent-driven slot/provider config uses the non-interactive `gateway set <slot> <model>` and `gateway provider add`; only `gateway setup` is interactive. **`gateway setup` covers all 6 slots, including `grounding`.**

## Model Slot Selection Guide

Advisory only — this section helps the agent *recommend* models. Actual configuration stays with `gateway set`/`gateway provider add` (see Capability 6). Every requirement is traced to a downstream consumer; do not infer model needs from a slot name.

### How to Help a User Choose Models

1. **Map the user's ask to the actually-consumed slots** (matrix below). Not every slot is consumed by every workflow.
2. **Reject incompatible candidates first** (hard requirements), then compare the rest.
3. **Apply the user's priority** (quality / cost / latency / local / language) per slot — one universal ranking does not exist. **If no priority is stated, ask which matters most (quality, cost, latency, or local/private) — the recommendation changes with the answer.**
4. **Recommend and explain**: model + slot + why it fits + the trade-off + why alternatives were not preferred.

### Quick Cross-Slot Matrix

| Slot | What it does | Model must be able to | Top selection criteria | User priorities that matter |
| --- | --- | --- | --- | --- |
| extraction | Per-clause position analysis (core review) | Generate text + emit parseable JSON | 1. structured-output reliability 2. legal extraction precision 3. citation fidelity | quality, cost/latency, local |
| embedding | Dense retrieval vector search | Produce fixed-size dense embeddings | 1. retrieval relevance 2. stable dimension 3. latency/cost | quality, cost, local |
| reranking | Opt-in rerank flag; uses the configured `reranking` slot | Score query-chunk pairs | 1. Precision@K improvement 2. latency 3. cost | quality, local; usually skip (disabled by default) |
| grounding | Verify citations post-review | Generate text + emit parseable verdicts | 1. entailment discrimination 2. structured-output reliability 3. consistency | quality, cost, local |
| reasoning | Declared chat slot; **no current consumer** | Generate text (if exercised) | n/a (reserved surface) | n/a |
| graph | Declared chat slot; graph subsystem is LLM-free | Generate text (if exercised) | n/a (reserved surface) | n/a |

### extraction

- **What this slot does:** The extraction agent reads each clause, matches it to a playbook category, and returns a structured position (Preferred/Acceptable/Walkaway/Uncertain) with confidence and a citation. It is the per-clause analysis stage of `precheck review` and product modes. "Walkaway" means the position the party should refuse.
- **What kind of model belongs here:** a chat/text-generation model.
- **The model must:** (a) generate text; (b) have a provider declaring `reasoning` capability; (c) reliably emit parseable JSON (`position`, `confidence`, `citation`) — malformed output degrades to uncertain/0.0.
- **Prioritize:** 1. structured-output reliability; 2. legal extraction precision; 3. citation fidelity.
- **User requirements that change the choice:** quality → strongest reliable structured-output model (low temperature); cost/latency → a smaller model is often fine (per-clause tasks are small); local/private → must be local (Ollama).
- **A strong choice looks like:** a deterministic, low-temperature chat model with strong instruction-following and reliable JSON. Does not need a huge context window.
- **Avoid choosing primarily by:** general reasoning benchmark rank — verbose/unparseable output is a poor fit regardless of reasoning score.
- **Candidate evaluation rule:** reject non-chat / non-JSON-reliable models; then compare on structured-output reliability, then legal precision; adjust by the user's priority.

### embedding

- **What this slot does:** embeds query and clause text into vectors for cosine-similarity dense retrieval (`retrieve --method dense|hybrid` only).
- **What kind of model belongs here:** a dedicated embedding model.
- **The model must:** (a) produce dense embeddings; (b) have a provider declaring `embedding` capability; (c) return a fixed-size vector. Changing the model after indexing breaks dimension consistency — re-index.
- **Prioritize:** 1. retrieval relevance on legal text; 2. stable, documented dimension; 3. latency/cost.
- **User requirements that change the choice:** quality → stronger/higher-dimension embedding; cost/speed → smaller/faster embedding; local/private → local embeddings are required under `balanced` and `maximum`.
- **A strong choice looks like:** a dedicated embedding model with good semantic search on domain text.
- **Avoid choosing primarily by:** chat reasoning ability — an embedding model does not generate text.
- **Candidate evaluation rule:** reject non-embedding models; compare on retrieval relevance and dimension stability; adjust by priority.

### reranking

- **What this slot does:** `--rerank` (opt-in) routes to the configured `reranking` slot — the gateway resolves the provider/model from this slot's config. The reranker is disabled by default (degrades legal retrieval). When the stored validation record shows degradation (`degradation_pp <= 0`), the CLI prints a warning suggesting `--force-rerank`; the reranker still runs (advisory, not a hard auto-disable).
- **What kind of model belongs here:** a reranker/cross-encoder.
- **The model must:** (a) score query-document pairs; (b) have a provider declaring `rerank` capability.
- **Prioritize:** 1. Precision@K improvement on legal text; 2. latency; 3. cost.
- **User requirements that change the choice:** quality → a reranker that actually improves Precision@5; cost/speed → skip reranking (the default); local/private → local reranker if reranking is wanted under `maximum` (e.g. `ollama/qwen3-reranker-0.6b`).
- **A strong choice looks like:** a cross-encoder fine-tuned for legal/contract retrieval that beats the BM25 baseline. If no such evidence, the disabled default is correct.
- **Avoid choosing primarily by:** popularity — a reranker that degrades legal retrieval is actively harmful. If a validation warning appears but the user still wants reranking, `--force-rerank` suppresses it.
- **Candidate evaluation rule:** reject models without a `rerank` capability; compare on Precision@K improvement, then latency/cost; adjust by the user's priority.

### grounding

- **What this slot does:** post-pipeline citation grounding — verifies each assessment claim is actually supported by its cited clause.
- **What kind of model belongs here:** a chat/text-generation model.
- **The model must:** (a) generate text; (b) have a provider declaring `reasoning` capability; (c) emit parseable per-claim verdicts (grounded/ungrounded/uncertain + provenance).
- **Prioritize:** 1. entailment/support discrimination; 2. structured-output reliability; 3. consistency (low temperature).
- **User requirements that change the choice:** quality → strong textual-entailment judgment; cost → a smaller model may be acceptable (batched claims); local/private → must be local under `maximum`.
- **A strong choice looks like:** a deterministic chat model good at entailment/verification without hallucinating support.
- **Avoid choosing primarily by:** creative/generative ability — grounding is verification, not generation.
- **Candidate evaluation rule:** reject non-chat / non-verdict-reliable models; compare on entailment accuracy; adjust by priority.

### reasoning and graph (reserved surfaces)

- **What these slots do:** `reasoning` and `graph` are declared chat slots (`_SLOT_METHOD_MAP` maps both to `chat`) and configurable via `gateway set` / testable via `gateway test`, but **no current workflow consumes them**. The `graph` subsystem is pure structural analysis (no LLM); `--cluster-clauses` uses a hardcoded local legal-bert, not the `graph` or `embedding` slot. The `reasoning` slot is not called by the review pipeline (extraction/QA use the `extraction` slot).
- **Guidance:** if a user asks about these slots, say they are configurable reserved surfaces without an active consumer today — do not claim a workflow depends on them. If the user's actual goal is analysis/review, redirect to the `extraction` slot guidance.

### How to Compare a User's Candidate Models

1. **Identify each candidate's actual capabilities.** Do not assume from a name; if unknown, ask or verify.
2. **Reject against each slot's hard requirements.** Compatible ≠ good — it means it passes the bar.
3. **Compare the compatible set using slot-specific criteria** (never one universal ranking).
4. **Apply the user's priority** — cost matters more for per-clause extraction than for a single-shot high-stakes analysis; locality matters most for embedding under `maximum`/`balanced`.
5. **Recommend with reasoning.** State the slot, why the model fits, the trade-off, and why alternatives were not preferred. Avoid "Model X for reasoning" without explanation.

Distinguish: **compatible** (passes hard requirements) vs **better fit** (higher on selection criteria) vs **trade-off** (preferable only under a specific priority) vs **unsuitable** (fails a hard requirement). Never conflate "good AI model" with "right model for this OpenReview slot."

### 7. Playbook Management
Import, list, show, diff, activate, delete review playbooks.

Use when: user wants to use a custom playbook or inspect available ones.

CLI: `openreview playbook import <yaml> | list | show <id> <version> | export | diff | set-current <id> <version> | delete | undelete | history`.

Key constraint: 24 bundled playbooks. For `precheck review`: `--playbook <id>` selects a DB playbook, `--playbook-path <yaml>` supplies a custom file. For product modes: `--playbook` takes a YAML path only (no DB id).

### 8. PII Governance
Audit/delete stored PII mappings at rest.

Use when: user asks "what PII data do you have" / "delete my data".

CLI: `openreview pii list [--format json] | pii delete <document_hash> | pii cleanup [--dry-run]`.

Key constraint: PII stripping on review (`precheck review`, `precheck compare`) is automatic and fail-closed — these commands only manage stored mappings. `negotiate` does NOT strip PII (Capability 5). Destructive (`pii delete`, `pii cleanup`) requires explicit user intent — see Rule 10.

### 9. Export Saved Reports
Re-format saved ReviewReport JSONs to readable memos.

Use when: user wants to export or convert previously-saved reviews.

CLI: `openreview export --batch-dir <dir> [--format md|json|docx] [--output-dir review_results]`.

Required: `--batch-dir` pointing at a directory of saved review JSONs. If the user names one report, identify it (ask or locate) before export — export is batch-oriented but user language is often singular.

### 10. Privacy Tier
Control whether LLM/embedding processing runs local-only or may use cloud providers.

Use when: user requires on-device/local-only processing, wants to avoid cloud where supported, or expresses a privacy/offline/cost constraint.

CLI: `openreview config get privacy.tier` | `openreview config set privacy.tier maximum|balanced|performance`.

Key constraint: persistent processing-policy setting (stored in config.yml). `maximum` = all-local (LLM + embeddings, Ollama only); `balanced` (default) = local PII strip + cloud LLM, local embeddings; `performance` = local PII strip + cloud LLM + cloud embeddings. **Distinct from PII stripping** — PII is always stripped before any cloud call (fail-closed) unless `--no-pii` (Rule 7). The tier controls *where inference runs*, not *whether PII is stripped*. Local processing does NOT mean nothing is stored — PII mappings, cost logs, review reports, and the retrieval index are stored locally; audit/delete stored mappings via Capability 8. Config commands beyond `privacy.tier` are operator-only and NOT routed (When NOT to Use).

## Optional Capabilities (enable on explicit request)

### Parse (standalone)
Extract the clause stream of one document to stdout.

Use when: the user explicitly asks to "extract the clauses" without a full review.

CLI: `openreview parse <path> --format json` (`--format text|json`, `--summary`).

Required: one PDF/DOCX path.

Key constraint: a building block — never the answer to "review this"; never a mandated step of `precheck review`.

### Chunk (standalone)
Break a document into retrieval-ready chunks (stdout).

Use when: the user asks to chunk a document, usually to build a search index.

CLI: `openreview chunk <path> --format json` (stdout only).

Required: one PDF/DOCX path.

Key constraint: no CLI command writes `.ndax`. Save the chunk stdout to a file, then `ingest` it. A building block — `precheck review` does NOT require chunking; use `ingest`→`retrieve` only when real retrieval is needed.

## Command Selection Rules

1. **Highest-level command wins.** Pick the single command that delivers the user's goal (`precheck review`, `precheck compare`, `negotiate`, or `parse`/`chunk` for explicit clause/chunk output). Decompose only via flags (`--playbook`, `--playbook-path`, `--no-pii`, `--grounding-mode`, `--no-grounding`, `--extraction-model`, `--qa-model`, `--confidence-threshold`, `--dual-path`). Chain only when composition is unavoidable (retrieval requires `ingest` before `retrieve`). **Compound requests spanning multiple workflows** (e.g. "review, compare, then tell me what to negotiate"): each workflow is self-contained — `precheck compare` re-runs the full review of both documents internally, so a separate `precheck review` of the same documents is redundant (double cost). Identify each distinct deliverable, run each once, present results per deliverable; if the user's priority between deliverables is unclear, ask — do not silently drop a sub-request.

2. **Intent → capability.**
   - "What does this say" / narrow factual question about an **already-indexed** doc → `retrieve "<q>"`.
   - "What are the risks / issues / analyze this" → `precheck review <paths>`.
   - "Compare these two" / "what changed" / "version diff" → `precheck compare <a> <b>`. Two documents with an ambiguous verb ("check/review these two") → ask: compare vs review-both.
   - "Negotiation dynamics / leverage" → `negotiate <doc>`.
   - "Extract the clauses (JSON, no review)" → `parse <path> --format json`.
   - "Chunk this document for indexing" → `chunk <path> --format json` → save → `ingest`.
   - "Show past reviews" → read `review_results/`; "export / convert to docx" → `export --batch-dir`.

3. **Output format.** `--format json` / `--memo-format json` when the agent will parse or compute over results. `--memo-format md` (or default text) when the user wants a directly readable artifact. Match the deliverable the user asked for. **`--format json` prints the report to stdout (or to a file with `--output <file>`); `--memo-format json` writes memo JSON files to `review_results/` (or `--output-dir`). `export --batch-dir` accepts BOTH shapes — report JSON (from `--format json --output`) and memo JSON (from `--memo-format json`). Only a run that wrote no JSON file at all leaves nothing to export.**

4. **Playbook selection for review.** Prefer DB playbook (`--playbook <id>`) for `precheck review` unless the user supplies a YAML file (`--playbook-path`). For product modes, `--playbook` is a YAML path only. Prefer the named product mode (`hirecheck`, `leasecheck`, …) over `precheck review` when the user names the document type. If a DB playbook id is named, verify it exists (`playbook list`) before passing it; never guess an id.

5. **Search vs. review.** Route through `ingest`→`retrieve` only when the doc is already indexed or the query is narrowly factual. Otherwise use `precheck review` end-to-end for structured per-clause analysis.

6. **Grounding is post-pipeline.** `--grounding-mode strict|lenient` / `--no-grounding` on `precheck review` run *after* extraction + QA LLM calls as an optional validation pass. Do not describe grounding as a pre-filter.

7. **`--no-pii` — explicit opt-out only.** Present on `precheck review`, `precheck compare`, product modes, and legacy `precheck`. It disables PII stripping, so **raw unredacted text is sent to the LLM**. Use it only when the user explicitly opts out; never use it to satisfy a locality/privacy requirement (that is what the privacy tier is for). It is mutually exclusive with `--pii-threshold` on legacy `precheck`. **After the compare-PII fix (v0.10), `--no-pii` on `precheck compare` genuinely skips stripping** — raw text goes to extraction/QA/comparison.

8. **`--allow-partial-pii` — last resort only.** May be surfaced on `precheck review`, `precheck compare`, or product modes, but only after informing the user that raw unredacted text will be sent to the LLM.

9. **Legacy `openreview precheck -d <doc>` exists** (PII strip + memo.txt only, no extraction/QA; its `--format` flag is dead). Always prefer `precheck review` unless the user explicitly wants a quick no-AI memo.

10. **Never guess missing inputs.** If the target document/entity cannot be identified, stop and ask. If the request is outside openreview-cli's document-review domain, decline cleanly. If the request is internally contradictory ("compare two docs but analyze only one"), stop and ask. If the CLI returns no results, report that honestly — do not retry blindly. If a command can only run interactively (e.g. `gateway setup`), do not invoke it headless — tell the user to run it in their own terminal, or use the non-interactive equivalent (`gateway set`, `gateway provider add`). Destructive or consequential ops (`pii delete`, `pii cleanup`, `index-clear`) run only on explicit user request — never as a helpful add-on; prefer `pii cleanup --dry-run` first. Cost/network ops (`precheck review`, `precheck compare`, `gateway refresh`, `gateway test`) surface their cost/network effect before running.

11. **Pre-flight is the CLI's job.** Do not pre-check file existence, PDF/DOCX validity, or PII risk before invoking — `precheck review` and product modes validate these and fail closed on PII errors before any cost-bearing LLM call. The agent decides intent and flags; the CLI owns input safety. **Exception:** the bootstrap/readiness checks in `## Before Using OpenReview` (CLI availability, `gateway status`, `gateway test`) run *before* the first cost-bearing workflow — those are environment checks, not document checks.

12. **Privacy routing.** If the user expresses a privacy/locality/cloud constraint (local-only, on-device, avoid cloud), check `config get privacy.tier` before choosing the workflow and surface `config set privacy.tier maximum` when the requirement is "everything stays local". PII stripping is automatic and separate — `--no-pii` disables stripping (Rule 7), never use it to satisfy a locality requirement. Ambiguous privacy requests: report the trade-off (tier vs cost vs accuracy) and let the user choose — do not guess. **Exception:** `negotiate` does not strip PII and has no `--no-pii` flag (Capability 5).

## Examples / Operational Guidance

> Operational layer for the openreview-cli skill: how to move from user intent → workflow → command(s) → interpretation → next action. Complements the Command Selection Rules above. Examples show verified commands only, in the pip-installed `openreview ...` form.

## 1. Operational Workflow Principles

1. **Start from the user's goal, not the command.** Each *single* request maps to exactly one primary workflow: review, compare, search, negotiate, manage (gateway/playbook/PII), or export. Select the workflow first, then the command. A compound request spanning multiple workflows decomposes into one workflow per deliverable (Rule 1).
2. **`precheck review` is the default for document analysis.** It is the only command that performs end-to-end parse → PII-strip → extract → QA → memo. Prefer it over any pipeline decomposition.
3. **Cost and state awareness.** `precheck review`, `precheck compare`, and product modes call LLM providers and incur cost; `gateway refresh`/`gateway test` hit the network. `ingest`→`retrieve` requires a pre-built index. `export` requires saved review JSONs. Check state before chaining; surface cost before running.
4. **Let the CLI own input safety.** Do not pre-check file existence, PDF/DOCX validity, or PII risk. The CLI validates these and fails closed on PII errors before any cost-bearing call (Rule 11).
5. **Reuse existing state when it matches the goal.** Saved memos (in `review_results/` or any `--output`/`--output-dir` path you used), a built index, an imported playbook — reuse instead of re-running.
6. **Report results honestly; ask rather than guess.** Missing document, missing index, missing query, or missing report → ask or report, never invent (Rule 10).

## 2. Intent-to-Workflow Guidance

| If the user… | Workflow | Command |
| --- | --- | --- |
| hands a PDF/DOCX and wants analysis/risks/memo | Review | `precheck review <paths>` (or product mode for a named document type) |
| names a document type (employment/lease/license…) | Product-mode review | `hirecheck`, `leasecheck`, `licensecheck`, … |
| asks how two documents differ / "what changed" | Compare | `precheck compare <a> <b>` |
| asks a factual question about an already-indexed document | Retrieve | `retrieve "<query>" [file]` |
| wants to make a document searchable | Build index | `chunk <path> --format json` → save → `ingest <file.ndax>` |
| asks about negotiation dynamics / leverage | Negotiate | `negotiate <doc>` |
| asks what past reviews exist | Query saved artifacts | read `review_results/` |
| wants a saved review in another format | Export | `export --batch-dir <dir> --format md\|json\|docx` |
| asks about LLM providers / costs / connectivity | Gateway | `gateway status`, `gateway set`, `gateway costs`, `gateway test` |
| requires local-only / on-device processing | Privacy tier | `config get privacy.tier`, `config set privacy.tier maximum` |
| wants to use or inspect a playbook | Playbook | `playbook list`, `playbook import`, `precheck review --playbook <id>` |
| asks what PII is stored / to delete it | PII governance | `pii list`, `pii delete <hash>`, `pii cleanup` |
| asks for clause-level output (no review) | Parse | `parse <path> --format json` |
| asks for chunks (to index) | Chunk | `chunk <path> --format json` |

## 3. Representative Examples

Each example: **intent → workflow selection → commands → prerequisites → result interpretation → next action**.

### E-1. Review a single document

- **Intent:** "Check this contract for risky clauses." User supplies `contract.pdf`.
- **Workflow:** Review (the default for a single doc + analysis intent).
- **Command:** `precheck review contract.pdf --memo-format md`
- **Prerequisites:** PDF/DOCX exists (CLI validates); gateway configured (else the CLI reports a gateway error — check `gateway status`).
- **Result meaning:** Terminal summary shows per-clause position (Preferred/Acceptable/Walkaway/Uncertain), confidence scores, and Amber flags. The memo is written to `review_results/precheck-contract-<timestamp>.md`. Amber flags mean "review recommended," not a failure.
- **Next action:** Read the memo, summarize the Amber/high-risk clauses for the user, and report `openreview gateway costs --today` if cost was a concern. Offer follow-ups: compare against another version (E-3), search a specific clause (E-4), or export to docx (E-6).

### E-2. Product-mode review (named document type)

- **Intent:** "Review this employment agreement." User supplies `offer.pdf`.
- **Workflow:** Product-mode review — a named document type selects the appropriate bundled playbook automatically.
- **Command:** `openreview hirecheck offer.pdf --memo-format md`
- **Prerequisites:** PDF/DOCX exists; gateway configured.
- **Result meaning:** Same structure as `precheck review` but scored against the employment-specific playbook categories.
- **Next action:** Same as E-1. Prefer the product mode over `precheck review` whenever the user names the document type (Rule 4).

### E-3. Compare two versions

- **Intent:** "How do the termination clauses differ between draft and final?" User supplies `draft.pdf` and `final.pdf`.
- **Workflow:** Compare — explicitly "differ/compare/versions" → `precheck compare`.
- **Command:** `openreview precheck compare draft.pdf final.pdf --version-label-a draft --version-label-b final`
- **Prerequisites:** Both documents exist; gateway configured; **EXPERIMENTAL (≤64% F1) — disclose to the user before running.**
- **Result meaning:** Paired per-clause assessments with divergence classification (three-color status). The experimental caveat means divergences should be treated as candidates, not authoritative.
- **Next action:** Report the divergent clauses and their colors. For a disputed clause, suggest a focused review of that clause's document section, or run `precheck review` on one document for a deeper single-doc assessment.

### E-4. Search an already-indexed document

- **Intent:** "What does the confidentiality section say?" — user confirms this document was indexed before.
- **Workflow:** Retrieve (narrow factual question over an existing index).
- **Command:** `openreview retrieve "confidentiality obligations" --top-k 3 --format json`
- **Reranking note:** if a reranker validation warning appears and the user still wants reranking, re-run with `--force-rerank`.
- **Prerequisites:** An index exists for the document (`ingest` was run previously; confirm with `index-status <file.ndax>`). If no index exists, do **not** run `retrieve` — fall back to `precheck review` (Rule 5) or build the index (E-5).
- **Result meaning:** Ranked chunks with `chunk_id`, `text`, and `score`; higher score = better match. Chunk text is the retrieval evidence.
- **Next action:** Quote the matched chunk(s) as the answer, with the clause heading if present. If the user wants a deeper per-clause analysis, offer `precheck review`.

### E-5. Build a search index (chunk → ingest → retrieve)

- **Intent:** "I want to be able to search my contracts." User supplies `contract.pdf` (no index yet).
- **Workflow:** Index build — the only chained workflow (Rule 1).
- **Commands:**
  ```
  openreview chunk contract.pdf --format json > contract.ndax
  openreview ingest contract.ndax
  ```
  then confirm with `openreview index-status contract.ndax` → `Status: indexed`.
- **Prerequisites:** PDF/DOCX exists. `chunk` writes to **stdout only** — the `> contract.ndax` redirect is required; no command writes `.ndax` files (Capability 3 key constraint).
- **Result meaning:** `ingest` prints "Indexed N chunks" and creates the SQLite index; `index-status` shows `Status: indexed`, chunk count, and method. After this, `retrieve` works.
- **Next action:** Run `retrieve "<query>"` against the new index (E-4). If the user only wanted a one-off search, this workflow is heavier than `precheck review` — prefer review unless repeated search is the goal.

### E-6. Re-format a saved review

- **Intent:** "Export my last review as a Word document."
- **Workflow:** Export — operates on saved review JSONs, does not re-run the review.
- **Command:** `openreview export --batch-dir review_results --format docx`
- **Prerequisites:** Saved ReviewReport JSONs exist in `review_results/` (from a prior `precheck review --memo-format json`). If the user names one specific report, identify it (ask or locate) before exporting — export is batch-oriented (Capability 9).
- **Result meaning:** "Exported N memo(s)" — formatted files written to `--output-dir` (default `review_results/`).
- **Next action:** Point the user at the output file(s). If the user wants a report that was never generated, do not export — run the review first (E-1).

### E-7. Negotiation analysis

- **Intent:** "What's the negotiation leverage here?" User supplies `agreement.pdf`.
- **Workflow:** Negotiate — local NumPy, no LLM, no gateway needed. **Does NOT strip PII** (parses the document directly) — do not promise privacy.
- **Command:** `openreview negotiate agreement.pdf --format memo`
- **Prerequisites:** PDF/DOCX exists only.
- **Result meaning:** Per-clause strategies, predicted outcomes, suggested counteroffers, and a disclaimer that it is EXPERIMENTAL/advisory only.
- **Next action:** Relay the suggested counteroffers and assumptions; remind the user it is advisory, not legal advice. No follow-up command is required — the goal is satisfied.

### E-8. Custom playbook for review

- **Intent:** "Use my company's custom playbook for this review." User supplies `custom_playbook.yaml` and `contract.pdf`.
- **Workflow:** Playbook-backed review.
- **Command:** `openreview precheck review contract.pdf --playbook-path custom_playbook.yaml`
- **Prerequisites:** YAML playbook file exists (for DB playbooks, verify the id exists with `playbook list` before passing `--playbook <id>` — never guess an id, Rule 4).
- **Result meaning:** Review scored against the custom playbook's categories instead of the default. For product modes, `--playbook` takes a YAML path only.
- **Next action:** Same as E-1; the custom playbook was the user's stated requirement.

### E-9. Inspect stored PII (read-only audit)

- **Intent:** "What PII data do you have stored about my documents?"
- **Workflow:** PII governance, read-only.
- **Command:** `openreview pii list --format json`
- **Prerequisites:** None.
- **Result meaning:** Documents with stored PII mappings, entity counts, creation/expiry dates, and mapping locations.
- **Next action:** Report the listing. If the user asks to delete, that is a destructive op — confirm intent explicitly and prefer `pii cleanup --dry-run` first (Rule 10). Never run `pii delete` or `pii cleanup` as a helpful add-on.

### E-10. Check gateway/cost state before a review

- **Intent:** "Is the review tool set up?" / "What did my reviews cost?"
- **Workflow:** Gateway status/costs/readiness.
- **Command:** `openreview gateway status` or `openreview gateway costs --today`; before a cost-bearing review, pair with `openreview gateway test <slot>`.
- **Prerequisites:** None.
- **Result meaning:** `gateway status` shows slot → provider assignments for the 6 slots (reasoning, extraction, graph, grounding, embedding, reranking). A slot status of `configured` means provider assigned and ready — API key present for cloud providers, keyless for local ollama. `not_configured` means no provider assigned yet. `missing_api_key` means a *cloud* slot's credentials are absent — reviews using that slot will fail until configured. `gateway test <slot>` confirms the provider is reachable (may fail if local Ollama isn't running).
- **Next action:** If a slot is `missing_api_key` or unconfigured, use the non-interactive `gateway set <slot> <model>` or `gateway provider add <name> --base-url <url>` (never `gateway setup` headless — it is interactive-only). For fully local processing, `gateway set <slot> ollama/<model>` needs no API key (only a running local Ollama server) — see Before Using OpenReview §5–6. Then re-check `gateway status` before running the review (E-1).

## 4. Choosing Between Similar Operations

| Situation | Choose | Why not the alternative |
| --- | --- | --- |
| "What are the risks?" (one doc) | `precheck review` | `precheck compare` needs two docs; `retrieve` answers factual, not analytical, questions |
| "How do these differ?" (two docs) | `precheck compare` | `precheck review` on each doc does not align clauses pairwise |
| "Check these two contracts." (ambiguous verb) | **Ask** (compare vs review-both) | Both are plausible; Rule 2 says ask |
| Factual question, doc indexed | `retrieve` | `precheck review` is costlier and overkill for a narrow lookup |
| Factual question, doc NOT indexed | `precheck review` | `retrieve` will fail; do not silently chain ingest first (E-5) unless the user wants indexing |
| "Summarize/analyze" (no doc yet) | Ask for the document, then `precheck review` | Do not guess a document path (Rule 10) |
| "Export the report" (singular) | Ask which / locate, then `export --batch-dir <dir>` | Export is batch-only; blindly exporting the whole dir may not match intent |
| "Delete my PII" | Confirm intent; `pii cleanup --dry-run` first | `pii delete`/`cleanup` are destructive; explicit intent required (Rule 10) |
| "Use playbook X" | Verify id (`playbook list`), then `--playbook <id>` | Guessing an id fails at runtime (Rule 4) |
| "Extract the clauses" | `parse <path> --format json` | `precheck review` also extracts but adds the full review pipeline |
| "What's the negotiation leverage?" | `negotiate <doc>` | `precheck review` does not model game-theoretic strategy |

## 5. Prerequisites and State Awareness

| Operation | Prerequisite state | How to verify | If missing |
| --- | --- | --- | --- |
| `precheck review` / product modes / `precheck compare` | PDF/DOCX file; configured gateway | CLI validates file; `gateway status` | CLI errors on file; gateway errors on slots — report, don't guess |
| `retrieve` | Existing index for the document | `index-status <file.ndax>` | Do not run `retrieve`; use `precheck review` or offer to build the index |
| `ingest` | A saved `.ndax` file (JSON list of chunk dicts) | `ls <file>.ndax` | Build it: `chunk <path> --format json > file.ndax` |
| `export` | Saved ReviewReport JSONs in `--batch-dir` | `ls <dir>/*.json` | Run `precheck review --memo-format json` first |
| `precheck review --playbook <id>` | Playbook exists in DB | `playbook list` | Ask for a valid id or `--playbook-path <yaml>` |
| `pii delete <hash>` | Valid document hash (min 8 chars) | `pii list` | Ask for the target; never guess |
| `gateway set <slot> <model>` | Valid slot name + model | `gateway status`, `gateway models <provider>` | Check available slots/models first |
| Cost-bearing review (precheck/product/compare) | CLI installed; gateway slot `configured` (or keyless local ollama); provider reachable | `openreview --version`; `gateway status` (look for `missing_api_key`); `gateway test <slot>` | Report what's missing (install / config / credentials / local server) — see Before Using OpenReview |

## 6. Result Interpretation and Next Actions

- **Review output:** position counts + Amber flags + confidence. Amber = review recommended, not failure. Next: summarize high-risk clauses; offer compare/search/export; report cost if relevant.
- **Compare output:** per-clause paired assessments with divergence classification. EXPERIMENTAL ≤64% F1 — treat divergences as candidates. Next: highlight divergent clauses; offer focused single-doc review for disputed sections.
- **Retrieve output:** ranked chunks with `score`. Higher score = better match. Next: answer from the top chunk(s); offer full review if the user wants analysis, not just the passage.
- **Export output:** "Exported N memo(s)" with file paths. Next: point to files; if N=0, report "no JSON report files found" — the prerequisite was missing.
- **Negotiate output:** strategies, predicted outcomes, suggested counteroffers, advisory disclaimer. Next: relay; goal satisfied, no chaining.
- **Gateway status:** slot→provider table. Any unconfigured slot → use `gateway set`/`gateway provider add` (non-interactive) before cost-bearing work.
- **PII list:** documents with stored mappings. Next: relay; destructive follow-ups require explicit confirmation.
- **Empty/no-results output from any command:** report honestly. Do not retry blindly, do not invent results (Rule 10).

## 7. Common Mistakes and Recovery Rules

| Condition | Likely cause | Correct agent action |
| --- | --- | --- |
| `retrieve` errors "no index" / empty results | Document never ingested | Do not retry; check `index-status`; explain ingest-first or use `precheck review` |
| User asks to "compare" but supplies one document | Compare requires two docs | Ask for the second document (CLI itself errors "Both doc_a and doc_b are required") |
| `export` reports no files | No saved review JSONs | Run the review first, or point `--batch-dir` at the dir that has them |
| `precheck review --playbook <id>` fails | Id doesn't exist | Run `playbook list`; ask for a valid id or a `--playbook-path` YAML |
| Gateway errors on a review | Slot unconfigured / wrong model / missing key (cloud slots) | Check `gateway status` (`missing_api_key` → configure credentials; keyless local ollama never shows it); fix via `gateway set`/`gateway provider add`; verify with `gateway test <slot>` |
| `openreview` not found / command not available | CLI not installed | Check `openreview --version`; if absent, `pip install openreview-cli`, then re-verify — see Before Using OpenReview |
| User requires local-only / on-device processing | Privacy tier may allow cloud | Check `config get privacy.tier`; if not `maximum`, surface `config set privacy.tier maximum` (all-local, Ollama-only). Do NOT equate with `--no-pii` (that disables stripping, not cloud) |
| User says "review the changes" | Delta language → compare intent | Route to `precheck compare` (or ask if the "changes" reference is ambiguous) |
| User says "check these two contracts" | Ambiguous: compare vs review-both | **Ask** — do not default to compare |
| User says "export the report" (singular) | Singular vs batch mismatch | Identify/locate the report first, then export |
| User requests `pii delete`/`index-clear` mid-task | Helpful-sounding destructive op | Require explicit user request; prefer `pii cleanup --dry-run`; never run as add-on |
| User asks to "search" a doc never indexed | Assumes prepared state | Explain ingest-first or fall back to `precheck review` |
| User names a benchmark/graph/config/prompt/client/TUI command | Out of scope | Decline cleanly (When NOT to Use) |
| Raw PDF handed to `ingest` | Wrong input type | Explain `.ndax` pipeline (chunk → save → ingest); ingest takes JSON, not PDF |
| CLI error after a correct command | Code/runtime issue | Report the error verbatim; do not mask or retry blindly (Rule 10) |
