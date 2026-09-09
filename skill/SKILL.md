---
name: openreview-cli
version: 0.2.0
description: Use when a user wants to review, compare, search, or analyze legal/contract documents (PDF/DOCX) locally — produce review memos, compare two versions, search indexed clauses, run negotiation analysis, manage LLM gateway slots/playbooks, or audit/delete stored PII mappings. This is the local `openreview` CLI, NOT the openreview.net academic platform.
---

# openreview-cli

## Versioning

The skill's frontmatter `version` field tracks the CLI's `__version__` (`src/openreview_cli/__init__.py`) and `pyproject.toml` `version` field. They are kept in lockstep: bumping any one is a P3+ (or release-time) edit that must update the others. If the user asks "what version is the skill for?" the answer is the same as `openreview --version`. If they disagree, the CLI is the source of truth and the skill is stale.

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

CLI: `openreview precheck review <paths...>` — or a product-mode command when the user names a document type. 23 product modes exist: `licensecheck` (SaaS license), `leasecheck` (commercial lease), `privacycheck` (DPA), `privacycheck_v2` (DPA v2), `dealcheck` (vendor/service), `hirecheck` (employment), `indemnitycheck` (indemnification), `consultcheck` (consulting), `workcheck` (independent contractor), `loicheck` (LOI/MOU), `subcheck` (subcontractor), `settlementcheck` / `settlementcheck_v2` (settlement/release), `assetcheck` (asset transfer), `buycheck` (asset purchase/acquisition), `engagecheck` (engagement letter), `guaranteecheck` (personal guarantee), `loancheck` (loan/promissory note), `franchisecheck` (franchise/FDD), `opcheck` (operating agreement), `partnercheck` (partnership), `sponsorcheck` (sponsorship), `distrocheck` (distribution/reseller). For the authoritative list, run `openreview --help`.

Required: one or more PDF/DOCX paths.

Key constraint: memo written to `review_results/` by default.

#### PII cache behavior on re-runs

PII caching differs by command path. The agent must distinguish them:

- **Legacy `precheck -d` (uses `ReviewCommand` at `review/base.py:65-87`):** the PII cache is consulted on re-run. If a cached `PiiResult` exists for the document hash, the strip is short-circuited; **no new `pii_audit_trail` row is written**. Use `precheck -d <doc> --force-reprocess` to bypass the cache and force a fresh strip + new audit row.

- **Modern `precheck review` / product modes (use the pipeline at `review/runner.py:267-270` with `ParseStage` → `StripStage` → `ReviewStage`):** the `StripStage` (`pipeline/adapters/strip.py:51-100`) **always** calls `strip_pii_clauses` and **always** calls `_persist_pii` → `persist_pii_result` → `write_audit_trail_row` (`pii/persist.py:127-133`). There is **no** cache check in the StripStage path. Every modern re-run re-strips the document and writes a new `pii_audit_trail` row. The PII cache only short-circuits the legacy `ReviewCommand` path.

**A new `session_id` is written to `cost_logs` on every run** (both legacy and modern), so `gateway costs --today` shows additive cost regardless of the path.

**There is no `--force-reprocess` flag on the modern `precheck review` command.** For modern, the only ways to skip the strip are: (a) `--no-pii` (with Rule 13 confirmation if tier ≠ maximum), which disables the strip stage entirely. (b) `--allow-partial-pii`, which lets individual pages fail without aborting the pipeline (the failed pages leak raw text to the LLM; see Privacy Tier vs PII Stripping). To force a fresh re-strip on the modern path, the existing audit row is `INSERT OR REPLACE`d, so the re-run naturally produces a new row; there is no flag to control this.

#### PDF parse failure modes

Two pre-LLM failure modes surface before the LLM call. The user-facing message and exit code differ between the standalone `parse` command and the modern `precheck review` / product-mode path:

- **Password-protected PDF** (`pdf_parser.py:62-107`): `ParseError(category="password_protected")`. Standalone `parse` exits 8 with the message "This contract is password-protected." on stderr. `precheck review` and product modes exit 1 with "No documents processed." on stderr — the parse error is caught by the pipeline runner (`review/runner.py:289-293`) and the empty-reports list triggers the "No documents processed" exit (`app.py:167-169`). The original "password-protected" message is logged to `openreview.log` but does not surface on the terminal in the modern path. The user must remove the password (e.g. `qpdf --decrypt`) and rerun.
- **Scanned-image PDF** (`pdf_parser.py:113-146`): `ParseError(category="no_text")`. Same dual-path behavior: standalone `parse` exits 8 with "This PDF contains no extractable text." on stderr; `precheck review` and product modes exit 1 with "No documents processed." on stderr. The user must re-export with an embedded text layer (e.g. `ocrmypdf input.pdf output.pdf`, or export from the original authoring tool as "searchable PDF").

#### Product-mode `--mode-threshold` flag

`precheck review` and product-mode commands accept a repeatable `--mode-threshold MODE=VALUE` flag (`app.py:3111-3116`) that overrides the default confidence threshold for a specific mode. The flag is repeatable: pass `--mode-threshold extraction=0.65 --mode-threshold reasoning=0.8` to set per-stage thresholds. Values must be in `[0.0, 1.0]`. The flag is useful for noisy domains (legal/medical) where the default 0.7 is too tight, or for high-volume triage where the default is too loose. This is distinct from the global `--confidence-threshold` (which applies to all stages). Source: `app.py:3111-3116`.

#### Global `--debug` and `--no-tui` flags

- `--debug` (global Typer option at `app.py:309-313`): enable verbose debug logging. This sets the root logger to DEBUG, writes stack traces on exceptions, and may slow the CLI significantly. The agent should not enable `--debug` by default — only on explicit user request when troubleshooting an unexpected failure.
- `--no-tui` (parsed at `app.py:33-35` via `"--no-tui" in sys.argv`): suppress the Textual TUI and force the plain-text CLI. Use this when running in a non-interactive shell, when output is being captured/piped, or when the TUI's input loop is incompatible with the calling environment. The agent should default to `--no-tui` for any non-interactive invocation.

### 2. Bilateral Comparison
Clause-by-clause comparison of two documents.

Use when: user explicitly wants to compare two versions/documents.

CLI: `openreview precheck compare <doc_a> <doc_b>`

Required: two PDF/DOCX paths.

Key constraint: EXPERIMENTAL (≤64% F1) — disclose this to the user.

#### `--show-redlines` flag (DOCX-only)

The `--show-redlines` flag renders a per-clause redline block (insertions / deletions) for each matched clause pair. It is **DOCX-only** — the redline is derived from the `w:ins` / `w:del` markup that DOCX carries as tracked changes. PDF inputs do not have tracked-changes markup; passing a PDF (or any non-DOCX) for either side silently skips the redline block with no warning (`app.py:1922-1926` `continue`).

- Use `--show-redlines` only when at least one of `doc_a` / `doc_b` is a DOCX with tracked changes.
- Comparing two PDFs with `--show-redlines` produces zero redline output and exits 0 — this is the expected behavior, not a bug.
- If the user expects redlines but the input is a PDF, route them to convert the source to DOCX (or use the underlying compare report without redlines).

#### `--format` flag (text|json only)

`precheck compare --format` accepts only two values: `text` (terminal, default) and `json`. The flag is enum-validated at `app.py:1782-1787` (`if format not in ("text", "json"): ... Error: --format must be 'text' or 'json', got '<value>'` then `typer.Exit(code=1)`). Anything else (e.g. `--format md`, `--format yaml`) fails with exit 1 and the error message above. There is no `--format docx` or `--format memo` on `precheck compare`; for memo-style output use `export` (Capability 7) on a saved compare JSON. Source: `app.py:1730` (declaration), `app.py:1782-1787` (validation).

### 3. Retrieval & Index Management
Search indexed clause chunks; manage the local index.

Use when: user wants to search already-indexed documents or manage the index.

CLI: `openreview ingest <file.ndax>` → `openreview retrieve "<query>" [file]`; ops: `openreview index-status <file>`, `openreview index-clear [file|--all]`. Destructive (`index-clear`) requires explicit user intent — see Rule 10.

Required: for `ingest`, a JSON file containing a list of chunk dicts (`.ndax` is a user-applied extension; any JSON list works). For `retrieve`, a query string; `file` falls back to last indexed document.

Key constraint: no CLI command produces `.ndax`. To build one: `openreview chunk <doc> --format json` (stdout) → save to file → `ingest` (`chunk` is OPTIONAL — see Optional Capabilities). `precheck review` does NOT require chunking or indexing. **`ingest`/`retrieve` default to `hybrid`, which needs the `embedding` slot configured; without it the CLI silently falls back to BM25/sparse and prints a fallback notice. Surface that notice to the user, or use `--method sparse` deliberately to avoid the silent quality drop. `--rerank` is opt-in and routes to the configured `reranking` slot (e.g. `ollama/qwen3-reranker-0.6b`, `cohere/rerank-english-v3.0`, `voyage/rerank-2.5`); it needs that slot configured and reachable — check `gateway status` (slot `configured`) then `gateway test reranking` before relying on it.**

#### `retrieve` and `ingest` flags

These flags are part of the index-and-retrieve surface and are commonly needed but were not formally documented:

- `retrieve --method <sparse|dense|hybrid>` (default `hybrid`): chooses the retrieval method. `hybrid` requires the `embedding` slot; without it the CLI falls back to BM25/sparse with a notice (see above). `dense` requires the `embedding` slot configured and reachable — verify with `gateway test embedding` before relying on it. `sparse` is BM25-only and needs no embedding model. Source: `app.py:2064-2066`.
- `retrieve --top-k <int>`: number of top chunks to return. The default is implementation-defined; raise it for broader context, lower it for tight scoping. Source: `app.py:2067`.
- `retrieve --rerank-depth <int>`: number of chunks to re-rank before truncating to `--top-k`. Requires the `reranking` slot configured. Larger values improve quality at the cost of latency. Source: `app.py:2071`.
- `retrieve --no-header`: suppress the column header in text-format output (useful when piping into other tools). Source: `app.py:2078`.
- `retrieve --db-dir <path>`: override the default DB directory. By default, the CLI uses `platformdirs.user_data_dir("openreview") / "openreview.db"` (Linux/macOS: `~/.local/share/openreview/openreview.db`); `--db-dir` lets the user point at a different index for isolation, testing, or multi-tenant setups. Source: `app.py:2078` (declaration; same parameter name used for `ingest`, `retrieve`, and other index commands).
- `ingest --model <id>`: override the embedding model used to vectorize chunks at ingest time. Defaults to the configured `embedding` slot. If the model used at ingest differs from the one configured at retrieve time, dense retrieval will be incoherent; surface this to the user. Source: `app.py:1961`.
- `ingest --db-dir <path>`: same semantics as `retrieve --db-dir` (above). The `--db-dir` passed at `ingest` must match the one passed at `retrieve` for results to be visible. Source: `app.py:1962`.

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

#### `negotiate` flags

These flags are commonly needed but were not formally documented:

- `negotiate --playbook-path <yaml>`: use a custom YAML playbook for clause extraction (same playbook format as `precheck review --playbook-path`). Use this when the bundled negotiation playbook does not match the document type. Source: `app.py:2807`.
- `negotiate --rationality <float>`: bounds the rationality coefficient in QRE/Level-k solvers (range 0.0–∞; values near 0 = uniform randomization, large = best-response). The default is solver-specific. Source: `app.py:2815`.
- `negotiate --depth <int>`: recursion depth for Level-k (`--solver level_k`). Higher depth models deeper strategic reasoning at exponential cost. Source: `app.py:2820`.
- `negotiate --weights <a,b,c>`: comma-separated weights for the negotiation objective (e.g. `payoff,risk,acceptance`). The order and meaning depend on the playbook; check the playbook YAML or `negotiate --help` for the current schema. Source: `app.py:2825`.

### 6. Gateway & Provider Management
Configure LLM provider slots, check costs/connectivity, refresh model registry.

Use when: user wants to set up/inspect LLM providers or costs.

CLI: `openreview gateway setup` (interactive TTY wizard — a human runs this in their own terminal; the agent cannot drive it headless) | `status` | `providers` | `models <provider>` | `set <slot> <model>` | `refresh` | `test <slot>` | `costs [--today]`; custom provider (non-interactive): `openreview gateway provider add <name> --base-url <url> [--env-key VAR] [--cred k=v]...`.

Key constraint: 6 slots — reasoning, extraction, graph, grounding, embedding, reranking. Agent-driven slot/provider config uses the non-interactive `gateway set <slot> <model>` and `gateway provider add`; only `gateway setup` is interactive. **`gateway setup` covers all 6 slots, including `grounding`.**

#### Stale-model diagnostic (C-α)

If `gateway test <slot>` returns a 4xx or "model not found" but the user is sure the model id is correct, the upstream model registry has likely been renamed or deprecated. The diagnostic chain:

1. `openreview gateway refresh` — re-fetch `models.json` from the registry URL.
2. `openreview gateway models <provider>` — list current valid ids for the provider.
3. `openreview gateway set <slot> <new-model>` — e.g. `openreview gateway set extraction openrouter/anthropic/claude-sonnet-4.5`.
4. `openreview gateway test <slot>` — verify the new model id is reachable.

The registry (`models.json` at `app.py:230-253`) is a flat list with no deprecation map; there is no automatic "your model was renamed to X" warning. `gateway refresh` + `gateway models` is the only way to discover the new id. This diagnostic path is the same for any provider (OpenRouter, Ollama, custom); for Ollama, "not found" usually means the model is not pulled locally (use `ollama pull`, not `gateway refresh`).

**End-to-end evidence (P2 S-P2-F):** a mock OpenAI-compatible server returning HTTP 404 with `{"error":{"message":"The model `stale-model-v1` does not exist or you do not have access to it.","type":"invalid_request_error","param":"model","code":"model_not_found"}}` for the stale model id, and HTTP 200 with a valid chat completion for the new model id, triggers: (1) `Error: model not found for mock-stale: litellm.NotFoundError: OpenAIException - The model \`stale-model-v1\` does not exist or you do not have access to it.` on the stale id, and (2) `Response: OK` (exit 0) after `gateway set <slot> <new-model>` switches to the valid id. The `model not found for <provider>:` prefix is the CLI's `ModelNotFoundError` class (`gateway/errors.py:39-46`); the router triggers it at `router.py:488` on status 404. See `draft/raports/phase7-p2-execution-report.md` S-P2-F for the full walkthrough.

#### `gateway` query flags

These flags are commonly needed for agent automation but were not formally documented:

- `gateway providers --json`: emit the configured providers as JSON (one provider per object) instead of the human-readable table. Use this when scripting against the providers list. Source: `app.py:1383`.
- `gateway models <provider> --json`: emit the registry models for `<provider>` as JSON. Without `--json`, the output is a numbered list. Source: `app.py:1431`.
- `gateway costs --session <session_id>`: show the cost log for a specific review session (filtered to that `session_id`). Without `--session`, the default is "today" (or use `--today` explicitly). Use the `session_id` returned in a review's JSON output (`reports[].session_id`) to drill into a single review. Source: `app.py:1561-1573`.

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

#### `playbook export` and `playbook diff` flags

These flags are commonly needed but were not formally documented:

- `playbook export <id> <version> --output <file>`: write a single playbook's YAML to `--output`. Source: `app.py:766-773`.
- `playbook export --all --output <file>`: dump every active playbook to a single YAML file (for backup or migration). Source: `app.py:766-773`.
- `playbook export --version <v>`: export a specific historical version (defaults to the active version when omitted). Source: `app.py:766-773`.
- `playbook export --force`: overwrite an existing `--output` file without prompting. Without `--force`, the CLI refuses to overwrite and prints a clear error. Source: `app.py:766-773`. Note: `playbook export` writes via `out_path.write_text(...)` **without** a `try/except` (`app.py:808, 868`); on a permission error the user sees a raw Python traceback. This is the same write-failure class documented in Common Mistakes.
- `playbook diff <id> <v1> <v2> --json`: emit a machine-readable JSON diff between two versions of a playbook. Without `--json`, the diff is human-readable text. Source: `app.py:877`.

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

#### `export` flags

These flags are commonly needed for templated exports but were not formally documented:

- `export --template <name>`: use a named memo template (e.g. `default`, `concise`, `legal-brief`). Templates are resolved from `~/.local/share/openreview/templates/` (Linux/macOS) or the platform equivalent; an unknown template name exits 1 with an error. Source: `app.py:3004-3010`.
- `export --mode <mode>`: choose an export mode (`memo`, `summary`, `redline`, etc.). The available modes depend on the report shape; an unknown mode exits 1. Source: `app.py:3004-3010`.

### 10. Privacy Tier
Control whether LLM/embedding processing runs local-only or may use cloud providers.

Use when: user requires on-device/local-only processing, wants to avoid cloud where supported, or expresses a privacy/offline/cost constraint.

CLI: `openreview config get privacy.tier` | `openreview config set privacy.tier maximum|balanced|performance`.

Key constraint: persistent processing-policy setting (stored in config.yml). `maximum` = all-local (LLM + embeddings, Ollama only); `balanced` (default) = local PII strip + cloud LLM, local embeddings; `performance` = local PII strip + cloud LLM + cloud embeddings. **Distinct from PII stripping** — PII is always stripped before any cloud call (fail-closed) unless `--no-pii` (Rule 7). The tier controls *where inference runs*, not *whether PII is stripped*. Local processing does NOT mean nothing is stored — PII mappings, cost logs, review reports, and the retrieval index are stored locally; audit/delete stored mappings via Capability 8. Config commands beyond `privacy.tier` are operator-only and NOT routed (When NOT to Use).

#### Privacy Tier vs PII Stripping (do not conflate)

The privacy tier and PII stripping are **two independent axes**. Conflating them is the root cause of the P0 CRITICAL anti-pattern (Rule 13) and the live S-5 reproduction (Phase 7 P0 evidence). The two axes:

- **Privacy tier** (this Capability): controls **where inference runs** — local Ollama vs cloud provider. Three tiers: `maximum` (all-local), `balanced` (default when `privacy.tier` is absent in config.yml; local PII strip + cloud LLM + local embeddings), `performance` (local PII strip + cloud LLM + cloud embeddings). The tier is set via `config set privacy.tier <tier>` and is a persistent config value (`src/openreview_cli/gateway/tier_config.py:13-15`).
- **PII stripping**: controls **whether the LLM sees raw or redacted text**. Stripping is **automatic and fail-closed** under all tiers (`src/openreview_cli/pii/engine.py: run unless no_pii=True`, called from `review/runner.py:268-269`). The LLM never sees unredacted text unless `--no-pii` is passed (or `--allow-partial-pii` is passed and partial processing fails — see below).

**`--no-pii` is a PII-skip path, not a tier override.** `--no-pii` disables the PII strip stage entirely. It does **not** change the privacy tier; under `balanced` / `performance` it sends **raw unredacted contract text to a cloud LLM**. This is the exfiltration path. The two acceptable resolutions are documented in Rule 13: (a) set the tier to `maximum` (keep `--no-pii`, all inference local) and re-run; or (b) remove `--no-pii` (PII stripping is automatic, fail-closed) and re-run. **There is no resolution that keeps `--no-pii` + a non-`maximum` tier; that combination is the anti-pattern.**

**`--allow-partial-pii` is a different PII-skip path.** It allows the strip stage to fail for individual pages (`PartialProcessingError` is raised in `pii/engine.py:191-197` when individual pages fail PII detection; the catch-and-re-raise site is `pipeline/adapters/strip.py:91-98`, which re-raises as `CriticalStageError`) rather than aborting the whole pipeline. The failed pages' raw text is then sent to the LLM. Under a non-`maximum` tier, this is also an exfiltration path for the failed pages and falls under Rule 13's anti-pattern check.

**Embeddings locality:** the embedding slot is local-only under both `maximum` and `balanced` (`tier_config.py:46-47`); it may use a cloud provider only under `performance`. The LLM slot is local-only under `maximum`; may use a cloud provider under `balanced` or `performance`. The reranking slot follows the LLM slot. Reasoning and graph slots follow the LLM slot.

**Recovery interaction:** the recovery subsystem's `provider_fallback` strategy respects the product tier (`recovery/models.py:50-60`): a `maximum` user is never moved to a cloud fallback; a `balanced` or `performance` user may be. The product → recovery tier mapping is: `product.maximum → recovery.strict`, `product.balanced → recovery.standard`, `product.performance → recovery.none`. See the Recovery Subsystem subsection for details.

**PII-unavailable is terminal.** If PII stripping fails for the whole document (engine not initialized, all pages fail under `--allow-partial-pii` without the flag), the pipeline raises `PIIUnavailableError` (`pii/engine.py`) which the router catches and refuses to send to a cloud provider even under `performance` (`router.py:331-337`, the per-process `_pii_available` flag). The agent must surface this as a hard error, not fall back to a cloud slot.

**Cross-references:** Rule 13 (CRITICAL anti-pattern) is the enforcement gate for this section. The Cost-Limit Behavior (P1.a) and Recovery Subsystem (P1.b) subsections document the gateway-side and recovery-side interactions. The `--no-pii` flag is on `precheck review`, `precheck compare`, product modes, and legacy `precheck`; it is **not** on `negotiate` (Capability 5), which has no PII strip and no `--no-pii` flag.

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

`chunk --summary` is a useful flag that produces a one-line summary per chunk (length, leading sentence, first entity tag) instead of the full chunk text. Use `--summary` when you want a quick overview of how the document is structured without dumping every chunk body to the terminal. The default (no `--summary`) is full chunk text. Source: `app.py:1657`.

Required: one PDF/DOCX path.

Key constraint: no CLI command writes `.ndax`. Save the chunk stdout to a file, then `ingest` it. A building block — `precheck review` does NOT require chunking; use `ingest`→`retrieve` only when real retrieval is needed.

## Command Selection Rules

1. **Highest-level command wins.** Pick the single command that delivers the user's goal (`precheck review`, `precheck compare`, `negotiate`, or `parse`/`chunk` for explicit clause/chunk output). Decompose only via flags (`--playbook`, `--playbook-path`, `--no-pii`, `--grounding-mode`, `--no-grounding`, `--extraction-model`, `--qa-model`, `--confidence-threshold`). Chain only when composition is unavoidable (retrieval requires `ingest` before `retrieve`). **Compound requests spanning multiple workflows** (e.g. "review, compare, then tell me what to negotiate"): each workflow is self-contained — `precheck compare` re-runs the full review of both documents internally, so a separate `precheck review` of the same documents is redundant (double cost). Identify each distinct deliverable, run each once, present results per deliverable; if the user's priority between deliverables is unclear, ask — do not silently drop a sub-request.

2. **Intent → capability.**
   - "What does this say" / narrow factual question about an **already-indexed** doc → `retrieve "<q>"`.
   - "What are the risks / issues / analyze this" → `precheck review <paths>`.
   - "Compare these two" / "what changed" / "version diff" → `precheck compare <a> <b>`. Two documents with an ambiguous verb ("check/review these two") → ask: compare vs review-both.
   - "Negotiation dynamics / leverage" → `negotiate <doc>`.
   - "Extract the clauses (JSON, no review)" → `parse <path> --format json`.
   - "Chunk this document for indexing" → `chunk <path> --format json` → save → `ingest`.
   - "Show past reviews" → read `review_results/`; "export / convert to docx" → `export --batch-dir`.
    - **When the user names a document type with no registered product mode** (e.g. "construction contract", "supply agreement", "joint venture", "trademark license", "shareholder agreement", "merger agreement"): (a) run `openreview --help` to enumerate the 23 registered product modes (licensecheck, leasecheck, privacycheck, privacycheck_v2, dealcheck, hirecheck, indemnitycheck, consultcheck, workcheck, loicheck, subcheck, settlementcheck, settlementcheck_v2, assetcheck, buycheck, engagecheck, guaranteecheck, loancheck, franchisecheck, opcheck, partnercheck, sponsorcheck, distrocheck); (b) recognize the gap — no `constructioncheck` / `supplycheck` / `jvcheck` / etc. exists; (c) fall back to `openreview precheck review <pdf> --playbook-path <yaml>` (or `--playbook <id>`) with a custom playbook for the document type; (d) **NEVER invent a product-mode command** — the agent must not synthesize `openreview constructioncheck <pdf>` or any other unregistered mode. The 23 modes are the closed set; for anything else, route to `precheck review` with a custom playbook.

3. **Output format.** `--format json` / `--memo-format json` when the agent will parse or compute over results. `--memo-format md` (or default text) when the user wants a directly readable artifact. Match the deliverable the user asked for. **`--format json` prints the report to stdout (or to a file with `--output <file>`); `--memo-format json` writes memo JSON files to `review_results/` (or `--output-dir`). `export --batch-dir` accepts BOTH shapes — report JSON (from `--format json --output`) and memo JSON (from `--memo-format json`). Only a run that wrote no JSON file at all leaves nothing to export.**

4. **Playbook selection for review.** Prefer DB playbook (`--playbook <id>`) for `precheck review` unless the user supplies a YAML file (`--playbook-path`). For product modes, `--playbook` is a YAML path only. Prefer the named product mode (`hirecheck`, `leasecheck`, …) over `precheck review` when the user names the document type. If a DB playbook id is named, verify it exists (`playbook list`) before passing it; never guess an id.

5. **Search vs. review.** Route through `ingest`→`retrieve` only when the doc is already indexed or the query is narrowly factual. Otherwise use `precheck review` end-to-end for structured per-clause analysis.

6. **Grounding is post-pipeline.** `--grounding-mode strict|lenient` / `--no-grounding` on `precheck review` run *after* extraction + QA LLM calls as an optional validation pass. Do not describe grounding as a pre-filter.

7. **`--no-pii` — explicit opt-out only.** Present on `precheck review`, `precheck compare`, product modes, and legacy `precheck`. It disables PII stripping, so **raw unredacted text is sent to the LLM**. Use it only when the user explicitly opts out; never use it to satisfy a locality/privacy requirement (that is what the privacy tier is for). It is mutually exclusive with `--pii-threshold` on legacy `precheck`. **After the compare-PII fix (v0.10), `--no-pii` on `precheck compare` genuinely skips stripping** — raw text goes to extraction/QA/comparison.

8. **`--allow-partial-pii` — last resort only.** May be surfaced on `precheck review`, `precheck compare`, or product modes, but only after informing the user that raw unredacted text will be sent to the LLM.

9. **Legacy `openreview precheck -d <doc>` exists** (PII strip + memo.txt only, no extraction/QA; its `--format` flag is dead). Always prefer `precheck review` unless the user explicitly wants a quick no-AI memo. The legacy path is the **only** command with a `--force-reprocess` flag: `precheck -d <doc> --force-reprocess` re-runs the PII strip and writes a new `pii_audit_trail` row. The modern `precheck review` has **no** `--force-reprocess` flag; the PII cache hit is not bypassable from the modern command (see Capability 1's PII-cache subsection for the four remediation paths on the modern command).

10. **Never guess missing inputs.** If the target document/entity cannot be identified, stop and ask. If the request is outside openreview-cli's document-review domain, decline cleanly. If the request is internally contradictory ("compare two docs but analyze only one"), stop and ask. If the CLI returns no results, report that honestly — do not retry blindly. If a command can only run interactively (e.g. `gateway setup`), do not invoke it headless — tell the user to run it in their own terminal, or use the non-interactive equivalent (`gateway set`, `gateway provider add`). Destructive or consequential ops (`pii delete`, `pii cleanup`, `index-clear`) run only on explicit user request — never as a helpful add-on; prefer `pii cleanup --dry-run` first. Cost/network ops (`precheck review`, `precheck compare`, `gateway refresh`, `gateway test`) surface their cost/network effect before running.

11. **Pre-flight is the CLI's job.** Do not pre-check file existence, PDF/DOCX validity, or PII risk before invoking — `precheck review` and product modes validate these and fail closed on PII errors before any cost-bearing LLM call. The agent decides intent and flags; the CLI owns input safety. **Exception:** the bootstrap/readiness checks in `## Before Using OpenReview` (CLI availability, `gateway status`, `gateway test`) run *before* the first cost-bearing workflow — those are environment checks, not document checks.

12. **Privacy routing.** If the user expresses a privacy/locality/cloud constraint (local-only, on-device, avoid cloud), check `config get privacy.tier` before choosing the workflow and surface `config set privacy.tier maximum` when the requirement is "everything stays local". PII stripping is automatic and separate — `--no-pii` disables stripping (Rule 7), never use it to satisfy a locality requirement. Ambiguous privacy requests: report the trade-off (tier vs cost vs accuracy) and let the user choose — do not guess. **Exception:** `negotiate` does not strip PII and has no `--no-pii` flag (Capability 5).

13. **CRITICAL anti-pattern: `--no-pii` on a non-`maximum` privacy tier exfiltrates raw contract text to the cloud.** Before any workflow that includes `--no-pii`, run `config get privacy.tier`. If the tier is `balanced` or `performance` (or any non-`maximum` cloud tier), the destination is a **cloud** provider; `--no-pii` disables the local PII strip, so the raw unredacted text is sent to that cloud provider. **Do not run.** Surface the warning, **name the destination provider** explicitly (e.g. "this would send raw contract text to `openrouter/anthropic/claude-sonnet-4.6`"), and require explicit user confirmation before proceeding. The two acceptable resolutions are: (a) `config set privacy.tier maximum` (keep `--no-pii`, all inference local) and re-run; or (b) remove `--no-pii` and re-run (PII stripping is automatic, fail-closed, see Capability 10 and the Privacy Tier vs PII Stripping subsection). **Exemption:** `negotiate` (Capability 5) has no `--no-pii` flag and is exempt. **Back-references:** this rule is the enforcement gate for Capability 10's "Privacy Tier vs PII Stripping" subsection; recovery (Recovery Subsystem) cannot save a request that has already exfiltrated raw text.

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

### All-Uncertain or All-Amber outcomes (C-β.1 vs C-β.2)

When every clause in a review reports the same low-confidence position, the agent's interpretation depends on **why** the position is low. Two distinct failure modes share the surface "no Green / no Red" but require different agent responses:

- **All-Uncertain (C-β.1)** — every clause has `Position.UNCERTAIN` (`extraction.py:94, 134`). Cause: the LLM output was unparseable (malformed JSON, schema-violating) or no playbook matched. The model did not actually produce a usable assessment. **Agent response:** report the position distribution verbatim, **refuse** to call the document "high-risk" or "low-risk" (the assessment is not a real assessment). Recommend retrying with a stronger extraction model, a different provider, or a matching playbook. Do not synthesize a risk verdict from the unparseable output.

- **All-Amber (C-β.2)** — every clause is parseable but has confidence below `--confidence-threshold` (default 0.7; `app.py:1254-1265`). Cause: the model returned real output but with low confidence on every clause. The assessment is real, but the model is uncertain. **Agent response:** report the parseable-but-low-confidence outcome, **distinguish from C-β.1** (this is not a parse failure; it is a confidence failure). Treat the review with skepticism — the clauses are real but the verdicts are not strongly grounded. Recommend either a stronger extraction model (one with higher confidence on this document type) or a tighter playbook. Do not pretend the low-confidence verdicts are high-confidence.

**Distinguishing the two:** check whether the extraction LLM output is parseable and matches the `Position` schema. If parsing failed → C-β.1. If parsing succeeded but every clause has confidence < threshold → C-β.2. Both share the surface symptom (no Green / no Red), but only C-β.1 is an "unusable output" failure mode; C-β.2 is a "usable but low-confidence" failure mode.

**End-to-end evidence (P2 S-P2-H1 and S-P2-H2):** both failure modes were exercised against mock OpenAI-compatible servers. C-β.1: a mock returning malformed JSON in the `content` field of every chat completion triggers `_parse_response`'s `json.JSONDecodeError` fallback (`extraction.py:171-172`), producing `position=uncertain, confidence=0.0` for the LLM-evaluated clause (verified in `cb1_final.json`: `summary.uncertain_count=5, position=uncertain, amber_reasons=['low_confidence', 'qa_uncertain']`). C-β.2: a mock returning parseable JSON with `confidence: 0.3` (below 0.7 threshold) and `verdict: "agree"` for every chat completion produces `position=acceptable, confidence=0.3, color=amber, amber_reasons=['low_confidence']` for the LLM-evaluated clause (verified in `cb2_final.json`). The distinction is real: C-β.1 → `position=uncertain, confidence=0.0`; C-β.2 → `position=acceptable, confidence=0.3` (parseable, just low). See `draft/raports/phase7-p2-execution-report.md` S-P2-H1 and S-P2-H2.

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
| Review exits with code 6 / "Cost limit exceeded" | Daily or per-review cost limit reached | Do NOT retry. Report the message verbatim, suggest `config set gateway.cost_limits.daily_cents <new>` (or `per_review_cents`), or wait for the daily reset (UTC midnight — the CLI's "local midnight" wording is misleading; see Cost-Limit Behavior (P1.a)) |
| `gateway test <slot>` fails — "model not found" / "not found" | Ollama model configured but not pulled | The configured model id is not present locally. Remediation: `ollama pull <model>` (or `ollama pull <tag>`); then re-run `gateway test <slot>`. Source: `gateway/router.py:440-497` raises `ModelNotFoundError` (from `gateway/errors.py:39-46`, message `model not found for <provider>: <orig>`) when the underlying litellm call returns 404 or contains "not found" / "model_not_found". For Ollama, litellm typically prefixes the message with "try pulling it first" — that text is from litellm, not the CLI's error class. The model-not-found message is the canonical signal; do not confuse it with a tier or key issue. **End-to-end evidence (P2 S-P2-I):** a mock Ollama server returning the exact `{"error":"model \"<name>\" not found, try pulling it first"}` JSON with HTTP 404 on `/v1/api/chat` triggers `Error: model not found for ollama: litellm.APIConnectionError: OllamaException - {"error": "model \"qwen3:8b\" not found, try pulling it first"}` (see `draft/raports/phase7-p2-execution-report.md` S-P2-I). The CLI's `ModelNotFoundError` prefix is produced by `router.py:488` (`if status == 404 or any(i in msg for i in model_indicators):`). For real environments without a mock: a live Ollama server with the model absent produces the same error. Without any Ollama running, the CLI fails earlier with `connection refused` (see C-γ below). |
| `gateway test <slot>` fails — connection refused / cannot connect to Ollama | Ollama server not running on the configured host/port | Start the Ollama daemon (`ollama serve`, or launch the desktop service) and re-run `gateway test <slot>`. Source: `app.py:1524-1556`. Distinguish from model-not-pulled (above) by the error text: connection refused / cannot connect → server-down; "not found, try pulling" → model-not-pulled. For cloud slots, a connection error usually means a 401/403 (key bad) or a 4xx with a deprecated model id (use `gateway refresh`; see C-α below). |
| `precheck compare --show-redlines` produces no redline output for one party | One side is non-DOCX (PDF or other) | `--show-redlines` works on tracked-changes DOCX only. If `doc_b` is a PDF (or any non-DOCX), the redline block is silently skipped with no warning (Source: `app.py:1922-1926` `continue`). Verify with `docx_parser.detect_tracked_changes` that the input is DOCX with `w:ins` / `w:del` markup; if not, route the user to convert or use a different comparison. Comparing two PDFs produces zero redline output with exit 0 — that is the expected behavior, not a bug. |
| User requests `index-clear --all` | No confirmation prompt (asymmetric to `playbook delete --all`) | `index-clear --all` does NOT prompt before clearing every index database. It is destructive and silent; require explicit user confirmation before running, and prefer `index-clear <db_name>` for single-target clearing. Source: `app.py:2321-2341` (no `Confirm.ask` before the loop). This is asymmetric to `playbook delete --all`, which IS gated by a prompt. (`pii delete` / `pii cleanup` already require explicit request per the destructive-op row above.) |
| `playbook delete --all` (interactive) or `--all --force` | Soft-delete lifecycle | `--all` prompts for confirmation (interactive only); `--all --force` skips the prompt. The deletion is **soft** (recoverable via `playbook undelete <id> <v>`) and the CLI says "cannot be undone" — that wording is misleading; soft-delete is reversible. A single `playbook delete <id> <v>` (no `--all`) is unprompted. Source: `app.py:981-1019`. |
| `playbook list` does not show a playbook the user expected | Soft-deleted playbook is hidden by default | `playbook list` hides soft-deleted entries. Use `playbook list --include-deleted` to see them. Source: `app.py:607-612`. |
| `playbook set-current <id> <v>` re-activates a soft-deleted playbook | Silent tombstone clearance | `set-current` on a soft-deleted playbook silently clears `deleted_at` (re-activates it). There is no warning. The playbook reappears in default `playbook list` output. Source: `app.py:955-979`; `playbooks.py:217-220`. If the user did not intend to re-activate, run `playbook undelete <id> <v>` is NOT the recovery path; the playbook is already active. Verify with `playbook show <id> <v>` before issuing `set-current` on a soft-deleted id. |
| Stale configured model after upstream rename / deprecation | Models registry is a flat list; renames require explicit user action | If a configured model id was renamed upstream, `gateway test <slot>` returns a 4xx or "model not found" without telling the user the model was deprecated. Diagnostic: `gateway refresh` to re-fetch `models.json`, then `gateway status` to see the new ids, then `gateway set <slot> <new-model>` (e.g. `gateway set extraction openrouter/anthropic/claude-sonnet-4.5`) and re-verify with `gateway test <slot>`. The registry has no deprecation map; this is the only diagnostic path. Source: `app.py:230-253, 1513-1521`. |
| Re-running a review | PII cache behavior differs by command path (legacy vs modern) | The legacy `precheck -d` path (`review/base.py:65-87`) consults a PII cache; a re-run short-circuits the strip and does **not** write a new `pii_audit_trail` row. The modern `precheck review` and product modes (`review/runner.py:267-270` → `pipeline/adapters/strip.py:51-100`) **do not** consult a cache; every re-run re-strips the document and writes a new `pii_audit_trail` row (`pii/persist.py:127-133`). In both paths, `cost_logs` accumulates a new `session_id` row, so `gateway costs --today` shows additive cost. The modern `precheck review` has **no** `--force-reprocess` flag; the legacy `precheck -d <doc> --force-reprocess` flag DOES bypass the legacy cache and force a fresh audit row. To force a fresh re-strip on the modern path, the existing audit row is `INSERT OR REPLACE`d, so the re-run naturally produces a new row; there is no flag. Source: `review/runner.py:118-125`; `review/base.py:65-87`; `pipeline/adapters/strip.py:51-100`; `pii/persist.py:127-133`; `storage/costs.py:23`. |
| `--output` write failure (chmod 0o500 / read-only / disk-full) — modern commands | `_write_output_file` catches `OSError` | The modern `--output` path (`app.py:146-152`) catches `OSError` and returns a clean `Error: cannot write output file...` (exit 1). The user must fix the filesystem issue (chmod, mount, free space) and retry. This covers `precheck review --output`, `precheck compare --output`, `parse --output`, `retrieve --output`, etc. **Note:** the clean-error guarantee fires **only when `_write_output_file` is reached**. Earlier failures (parse error → "No documents processed." exit 1; SQLite init failure → raw `OperationalError` traceback exit 1) surface different messages. Source for `_write_output_file`: `app.py:146-152`. |
| `--output-dir` write failure (memo export) | Inner `except Exception` catches → `logger.exception` prints raw traceback to stderr, exit 0 | The `--output-dir` path (memo export) routes through `_export_memo_reports` (`app.py:182`) → `MemoExporter.export` (`review/memo/exporter.py:81-94`) → `MemoExporter._write_memo` (`review/memo/exporter.py:188`) which calls `path.write_text(...)` **without** a `try/except`. The inner `except Exception:` at `review/memo/exporter.py:91-92` catches the `PermissionError` and calls `logger.exception("Failed to export %s format", fmt.value)` — this writes the full Python traceback to stderr (via the `[ERROR]` formatter at `app.py:193`). The outer `except Exception` at `app.py:134-135` (which would emit the clean "Warning: Memo export failed: {e}" message) is unreachable in this path because the inner exporter catch runs first. The user sees a raw Python traceback on stderr, the review **exits 0**, the text report is still printed to stdout/--output, and no memo file is written. The traceback is the signal; it is NOT a clean error message. Tell the user the export failed (the traceback shows the file path and `PermissionError: [Errno 13]`) and to check the directory permissions. |
| `--output` write failure on `playbook export <id>` or `playbook export --all` | Un-`try`'d `out_path.write_text` | `playbook export` (`app.py:808, 868`) calls `out_path.write_text(...)` **without** a `try/except`, leaking a raw Python traceback to the user (no clean error message). Same filesystem root cause as the modern path above. Tell the user the traceback is from the write-failure on the output path; fix the filesystem issue and retry. `playbook import` has no `--output` flag and is NOT affected. |
| Disk full mid-review | No pre-check; surfaces as `OperationalError` or `OSError(ENOSPC)` | The CLI does not pre-check free space. A full disk produces a SQLite `OperationalError("database or disk is full")` on the next `INSERT` (cost log) or an `OSError(ENOSPC)` on the output write path. The review exits non-zero with a partial state in the cost log. PII persistence failures on the modern `StripStage` path (`pii/persist.py:111-133`) are caught and logged as a warning but do NOT cause the review to exit non-zero — the strip itself succeeded, but no new `pii_cache`/`pii_audit_trail` row is written. Tell the user the disk is full; free space; rerun if the partial state is acceptable (cost will be additive). Source: `storage/costs.py:23`; `pii/persist.py:114-117, 165-186`; `pipeline/adapters/strip.py:145-146`; `app.py:146-152`. |
| User names a document type with no registered product mode (e.g. "construction contract", "supply agreement", "joint venture", "trademark license", "shareholder agreement", "merger agreement") | The 23 product modes registered at `app.py:3131-3248` do not cover every contract type | (1) Run `openreview --help` to enumerate the registered product modes (licensecheck, leasecheck, privacycheck, privacycheck_v2, dealcheck, hirecheck, indemnitycheck, consultcheck, workcheck, loicheck, subcheck, settlementcheck, settlementcheck_v2, assetcheck, buycheck, engagecheck, guaranteecheck, loancheck, franchisecheck, opcheck, partnercheck, sponsorcheck, distrocheck). (2) Recognize the gap — no `constructioncheck` / `supplycheck` / `jvcheck` / etc. exists. (3) Fall back to `openreview precheck review <pdf> --playbook-path <yaml>` (or `--playbook <id>`) with a custom playbook for the document type. (4) **NEVER invent a product-mode command** — the agent must not synthesize `openreview constructioncheck <pdf>`. Source: `_PRODUCT_MODES` at `app.py:3131-3248`.
| Two reviews started in parallel hit the same DB | SQLite write contention (mitigated by WAL; the second writer may still error after a 5s wait) | The CLI's database layer uses `PRAGMA journal_mode=WAL` (`storage/database.py:13`), which allows one writer + many readers concurrently — the classic `OperationalError: database is locked` from default-rollback journal mode is much rarer. However, two writers can still contend briefly: the second `sqlite3.connect(...)` call (default timeout 5s) will wait, and if the first writer hasn't released by then, it raises `OperationalError: database is locked`. The second review exits non-zero with no memo, and the cost log row from the failed write may also be missing. **Do not** run two reviews in parallel against the same DB; serialize them. If parallel runs are unavoidable, point each at its own `--db-dir` (Capability 3 flags) so they use separate DB files. Source: `storage/database.py:13` (WAL pragma); `storage/costs.py:21, 39, 47, 56`; `config/paths.py:16-19` (`platformdirs.user_data_dir`). |
| `precheck review` on a DOCX with no detectable clauses (clause detector returns 0) | DOCX body is prose-only OR has no paragraphs at all | The clause detector at `parsing/stream.py` may return 0 clauses for a DOCX whose body has no paragraphs (truly empty DOCX) or for some unusual prose shapes. **The modern `precheck review` / product-mode path TOLERATES this**: it runs the pipeline, the report lists "0 clauses", the CLI prints "No clauses to assess." (exit 0) — there is no error and no "No documents processed." message. The agent should expect exit 0 in this case and report "0 clauses detected; no review produced" to the user. This is **different** from password-protected / scanned PDF / empty-file cases, which raise `ParseError` and produce "No documents processed." (exit 1) via `app.py:167-169`. **End-to-end evidence (P3 B2):** `uv run openreview precheck review /tmp/truly_empty.docx --no-grounding --no-tui` against a DOCX with 0 paragraphs produces `Document: truly_empty.docx (1 pages, 0 clauses)` → "No clauses to assess." (exit 0). Source: `parsing/stream.py`; `review/report.py:72`. |
| `precheck review` on an empty file (0 bytes) | `ParseError(category="empty")` with action "Provide a non-empty document file." | An empty file triggers `ParseError` at `parsing/stream.py:42-45` with `category="empty"`, the message "The file appears to be empty or unreadable.", and the action "Provide a non-empty document file.". The modern `precheck review` / product-mode path catches this and exits 1 with "No documents processed." on stderr (`app.py:167-169`); the original empty-file message and action are logged to `openreview.log` but do not surface on the terminal. Standalone `parse` exits 8 with the message on stderr. The user must supply a non-empty file. This is the same dual-path behavior as password-protected and scanned-image PDFs. **End-to-end evidence (P3 B3):** `uv run openreview precheck review /tmp/empty.pdf --no-grounding --no-tui` produces `ParseError category="empty"` → "The file appears to be empty or unreadable." (logged) → "No documents processed." on stderr (exit 1). Source: `parsing/stream.py:42-45`; `app.py:167-169`. |
| User expects company names like "Beta LLC", "Acme Inc.", "Stark Industries" to be redacted as PII | The PII engine does NOT recognize company / organization names as personal data | Company / organization names are **not** PII under the current engine. The PII recognizers in `pii/recognizers.py` cover `AMOUNT`, `TAX_ID`, `ID_DOCUMENT`, `REG_NUMBER`, `PHONE_NUMBER`, `ACCT` — there is no `ORGANIZATION` or `COMPANY_NAME` recognizer. This is intentional: company names are not personal data under GDPR / CCPA scope, and stripping them would destroy the document's meaning. The agent must NOT promise company-name redaction. If the user needs entity-level redaction (e.g. competitor names for an NDA), use `--no-pii` is the wrong path; redact externally before ingest. Source: `pii/recognizers.py`; `pii/engine.py:74`. |

The following subsections document the actual current behavior of the cost-limit (Phase 6 B3) and recovery subsystems, and the precise relationship between privacy tier and PII stripping. They are derived from `src/openreview_cli/gateway/router.py:397` (cost-limit check), `src/openreview_cli/recovery/coordinator.py` (recovery orchestrator), and `src/openreview_cli/gateway/tier_config.py:13-15` (tier enum). Use them as the authoritative reference when the user asks about limit breaches, provider failures, or tier vs stripping.

### Cost-Limit Behavior (Phase 6 B3)

The CLI enforces two cost limits via `config set gateway.cost_limits.<key>`, both checked by `Router._check_cost_limits` (`src/openreview_cli/gateway/router.py:397-438`) **before any LLM call**:

- **Daily limit** (`gateway.cost_limits.daily_cents`, default 1000): cumulative spend for the calendar day as recorded by the cost-log table. **The reset is at UTC midnight.** The source uses `WHERE date(created_at) = date('now')` (`src/openreview_cli/storage/costs.py:41`), and SQLite's `date('now')` returns UTC. The user-facing error message at `router.py:420` says "Reset at UTC midnight" (as of P3-C2); previously it said "Reset at local midnight" which was a misleading drift between the message and the SQL. The reset time depends on the user's timezone; a user at UTC-5 will see the limit reset 5 hours before their local midnight.
- **Per-review (session) limit** (`gateway.cost_limits.per_review_cents`, default 100): cumulative spend for a single `precheck review` / `precheck compare` / product-mode invocation. Resets per `session_id` (`router.py:425` keys it on `session_id`, not on per-CLI-invocation; a single CLI process running two `precheck review` invocations shares the budget, but two CLI processes do not). **The per-review check only fires when the CLI passes a `session_id` to the router** (`router.py:423`: `if session_id and per_review_cents is not None:`). If a CLI path omits `session_id`, the per-review limit is silently not enforced for that call.

When a limit is breached, the router raises `cost_limit_error` (`src/openreview_cli/errors.py:10-12`), which `sys.exit(6)`s the process with the message `Cost limit exceeded: <context> (limit=<key> cents=<current>/<max>). Reset at UTC midnight.` (P3-C2: was "local midnight" before 2026-08-30) followed by `exit=6` on stderr. There is no JSON envelope, no exception trace, and no recovery hook — this is a hard pre-call exit, **not** a recoverable error.

**Differences from an ordinary provider failure:**

- Cost-limit is checked **before** any LLM call (the strip stage may run, but the LLM call never does). The cost check is in the gateway, so it fires before the LLM call.
- Cost-limit does **not** flow through the recovery subsystem (the recovery coordinator only sees LLM-side failures, not the cost-limit pre-check).
- A retry of the same command at the same limit hits the same limit immediately. **Do not** retry the same command. **Do not** loop recovery. **Do not** silently fall back to a cheaper model — the user is at their budget, not their model.
- `--no-pii` does not bypass the cost-limit: even with raw text, the cost check runs first and exits 6 before the LLM call. The exfiltration path requires the LLM call to complete, which it won't under a cost-limit exit.

**Agent action when exit 6 is observed:**

1. Report the cost-limit message verbatim to the user — do not paraphrase, do not translate "exit 6" into "rate limit" or "quota" (the user may be tracking against a specific key).
2. **Do not** retry the same command. **Do not** invoke the recovery subsystem for cost-limit.
3. Offer the user two remediations: (a) raise the limit (`config set gateway.cost_limits.daily_cents <new_cents>` or `gateway.cost_limits.per_review_cents <new_cents>`), or (b) wait for the daily reset at UTC midnight (not "local midnight" as the in-CLI message says).
4. Suggest `gateway costs --today` to show the current spend; the user may want to inspect before deciding.
5. If the user is on a tight budget, surface a brief table of slot-level cost options (e.g. "the `extraction` slot costs X cents/clause; switching to the `balanced` model would drop that to Y") rather than letting them guess.

### Recovery Subsystem

The recovery subsystem (`src/openreview_cli/recovery/coordinator.py`) is invoked **after** the LLM call (or the gateway) returns a failure. It does not run for pre-call exits like cost-limit (P1.a) or for parse errors like PDF password (Capability 1). Recovery only sees LLM-side failures and gateway-side failures that survive the cost-limit pre-check.

**The four strategies** (named in `coordinator.py:31-35` and selected in `coordinator.py:50-60`):

- `auto_retry` — exponential backoff retry of the same call. Default 4 attempts, base interval 1.0s (`recovery/models.py:23-25`).
- `provider_fallback` — switch the slot to a different configured provider/model. Respects the privacy tier (see below).
- `stage_isolation` — re-run only the failed stage (extraction, QA, etc.) with the existing outputs from the other stages. Produces a partial result if the re-run fails again.
- `graceful_degradation` — produce a partial result with the stages that succeeded. Memory-budget threshold at 80% of `RAG_CHUNK_RATIO` ceiling (`recovery/strategies/graceful.py:42`).

**Dispatch logic — gateway-failure path vs stage-failure path** (the `transient` category is split because the two detection sites dispatch differently):

- **Gateway-failure path** (`coordinator.py:220-239`, `handle_gateway_failure`): a `transient` gateway error (e.g. 5xx, connection reset) goes **straight to `provider_fallback`**; auto-retry is skipped (the gateway already retried). Permanent errors (4xx, auth) skip recovery and surface the error.
- **Stage-failure path** (`coordinator.py:142-176`, `handle_stage_failure`): a `transient` stage error chains `auto_retry` → `stage_isolation`. Permanent errors chain `stage_isolation` → `graceful_degradation`. Schema/parse errors skip recovery.

**Privacy-tier interaction (SC-04):** `provider_fallback` consults `RecoveryContext.user_privacy_tier` (`recovery/models.py:50-60`). If the tier is `strict` (the recovery-internal strict tier, mapped from product `maximum`) and the fallback provider is a cloud provider, the strategy is skipped (the recovery respects the tier — it will not move a `maximum` user off local). The product → recovery tier mapping (`recovery/models.py:55-60`) is: `product.maximum → recovery.strict`, `product.balanced → recovery.standard`, `product.performance → recovery.none`.

**Cost-limit interaction:** cost-limit failures bypass recovery entirely (they happen in the gateway pre-check, not in the LLM call). See the Cost-Limit Behavior (P1.a) subsection above.

**PII-before-egress gate (R3-1, R3-2):** in addition to the recovery-time tier check, the router has a per-process `_pii_available` flag (`router.py:331-337`). If PII stripping fails (engine not initialized, no PII available), the router refuses to call a cloud provider even under `performance`. This is a runtime protection that recovery does not provide: recovery can swap providers, but it cannot re-enable PII stripping mid-pipeline. The agent must surface a PII-unavailable failure to the user, not fall back to a cloud slot.

**Strategy detail:**

- `auto_retry` — exponential backoff. Default `max_retries=4`, `base_interval_s=1.0`, capped at 30s. After max retries, escalates to `provider_fallback`.
- `provider_fallback` — picks the next configured provider for the slot, respecting the tier. If the slot has only one configured provider, the strategy aborts and escalates to `stage_isolation`.
- `stage_isolation` — re-runs only the failed stage with the same inputs; other stages' outputs are preserved. The `RecoveryOutcome` enum values from `recovery/models.py` are returned (e.g. `RESOLVED` on success, `DEGRADED` on partial, `EXHAUSTED` if the re-run fails again and there are no more strategies).
- `graceful_degradation` — produces a `RecoveryReport` with whatever stages succeeded. Memory budget: abort when `current_memory ≥ memory_budget_bytes` (default 100 MB; `memory_threshold_pct` defaults to 100, see `coordinator.py:88-89`). The agent's job is to surface the partial result honestly, not fill in missing stages.

**Persistence — read this carefully:** the recovery state table and coordinator methods exist, but the user-facing pipeline at `review/runner.py:248-251` constructs the coordinator *without* `db_path`, so no row is ever saved in a real review run. The persistence path is test-only. If the user asks "where is my recovery report stored?", the answer is: there is no row; the `RecoveryReport` is returned in memory to the calling code and not persisted. Do not promise the user a row that does not exist.

**Agent action when reading a `RecoveryReport`:**

1. `resolved` — all strategies succeeded; continue as if no failure occurred.
2. `degraded` — some strategy succeeded with reduced output; surface the notice ("the QA stage was re-run in isolation; the final assessment may be less confident") and continue.
3. `unrecoverable` — all strategies exhausted; **stop** and surface the user-guided error verbatim. Do not retry the same command.
4. `partial_results` — `graceful_degradation` produced a partial output; **stop** the workflow and offer to save the partial result (`--memo-format json --output <path>`) for the user to inspect.

**When to stop and surface a user-guided error (the four user-intervention triggers):**

1. The recovery coordinator returns `unrecoverable` after exhausting all strategies.
2. The slot has no configured fallback provider (and the primary is down).
3. The privacy tier blocks the only available fallback (e.g. `maximum` + the only Ollama model is not pulled).
4. The recovery surfaces a PII-unavailable error (do not silently fall back to a cloud slot under `performance`).

**No blind retry:** recovery itself exhausts strategies; the agent must not loop with the same command. If recovery returns `unrecoverable`, the agent stops and asks the user.
