# Feature Specification: Build AI Gateway Package

**Feature Branch**: `005-ai-gateway`

**Created**: 2026-07-01

**Status**: Draft

**Input**: User description: "Build AI Gateway package — the model routing layer that connects the contract review engine to any AI provider (cloud or local). Covers provider models, routing engine, cost store, setup wizard, registry, YAML importer, and key redaction. Every review command depends on this."
## Clarifications

### Session 2026-07-01
- Q: How should `session_id` be passed to the gateway methods? → A: Option A - Pass `session_id` explicitly as an optional kwarg to `chat()`, `embed()`, and `rerank()`.
- Q: Should the hosted registry use a placeholder or a definitive URL? → A: Keep the remote refresh and use a GitHub raw file URL for the registry.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Route a Chat Request to Any Provider (Priority: P1)

A developer building a review command calls `gateway.chat(slot="reasoning", messages=[...])` and gets back a response from whichever model the user configured for that slot — OpenAI, Anthropic, Google, Ollama, or any supported provider. The developer never imports provider SDKs directly. The gateway handles authentication, request formatting, retry, and fallback transparently.

**Why this priority**: This is the gateway's core purpose. Without routing, no review command can call any AI model. Every downstream feature depends on this working.

**Independent Test**: Can be tested by configuring a single model slot and making one chat call. Delivers the ability to call any AI provider through a uniform interface.

**Acceptance Scenarios**:

1. **Given** a configuration with `reasoning` slot assigned to `openai/gpt-4o`, **When** the engine calls `gateway.chat(slot="reasoning", messages=[...])`, **Then** the gateway sends the request to OpenAI and returns the model's response as a string.
2. **Given** a configuration with `reasoning` slot assigned to `ollama/qwen3:8b`, **When** the engine calls `gateway.chat(slot="reasoning", messages=[...])`, **Then** the gateway sends the request to the local Ollama server and returns the response.
3. **Given** the primary model for a slot is unreachable, **When** a chat request is made, **Then** the gateway retries up to the configured number of times, then falls back to the configured fallback model.
4. **Given** both primary and fallback models are unreachable, **When** a chat request is made, **Then** the gateway raises a clear, user-friendly error.

---

### User Story 2 - Generate Embeddings for Semantic Search (Priority: P1)

A developer building the retrieval pipeline calls `gateway.embed(slot="embedding", texts=["clause text..."])` and gets back a list of vector embeddings. Embedding runs locally by default (Ollama) so contract text never leaves the machine. Cloud embedding is available if the user configures it.

**Why this priority**: The retrieval pipeline (chunking → embedding → search) is required before any review mode can work. Embedding is called once per chunk — hundreds of times per contract.

**Independent Test**: Can be tested by embedding a short text list and verifying the returned vectors have the expected dimensions.

**Acceptance Scenarios**:

1. **Given** the `embedding` slot is assigned to `ollama/nomic-embed-text`, **When** the engine calls `gateway.embed(slot="embedding", texts=["contract text"])`, **Then** the gateway returns a list of float vectors with 768 dimensions.
2. **Given** the `embedding` slot is assigned to `openai/text-embedding-3-large`, **When** the engine calls `gateway.embed(...)`, **Then** the gateway returns vectors with the configured dimensions.
3. **Given** the local Ollama server is not running, **When** embedding is called, **Then** the gateway raises a clear error explaining that Ollama is required for local embedding.

---

### User Story 3 - Rerank Retrieved Chunks (Priority: P2)

A developer building the retrieval pipeline calls `gateway.rerank(slot="reranking", query="liability cap", documents=["chunk1...", "chunk2..."], top_n=5)` and gets back the documents re-scored and sorted by relevance. Reranking runs locally by default.

**Why this priority**: Reranking improves retrieval precision but is not strictly required for a minimal retrieval pipeline. It can be deferred while chat and embedding ship first.

**Independent Test**: Can be tested by reranking a small set of text chunks against a query and verifying the returned order and scores.

**Acceptance Scenarios**:

1. **Given** the `reranking` slot is assigned to a local reranker model, **When** the engine calls `gateway.rerank(...)`, **Then** the gateway returns a list of scored results sorted by relevance.
2. **Given** no reranking model is configured, **When** reranking is called, **Then** the gateway raises a clear error or returns documents in original order with a warning.

---

### User Story 4 - Interactive Gateway Setup (Priority: P2)

A user runs `openreview gateway setup` for the first time. An interactive wizard walks them through configuring each of the 5 model slots: for each slot it lists available providers, lets the user pick one, lists that provider's models, lets the user pick a model, and prompts for an API key if needed. The configuration is saved to `config.yml` and keys to `auth.json`.

**Why this priority**: Users need a way to configure the gateway before any review command works. However, configuration can also be done by hand-editing `config.yml`, so the wizard is not a hard blocker for development.

**Independent Test**: Can be tested by running the wizard, making selections, and verifying the resulting config.yml and auth.json files are correct.

**Acceptance Scenarios**:

1. **Given** no existing configuration, **When** the user runs `openreview gateway setup`, **Then** the wizard prompts for each of the 5 slots, shows provider choices and model choices, and saves a valid configuration.
2. **Given** the user selects Ollama for all slots, **When** setup completes, **Then** no API keys are requested and the configuration works without any network access.
3. **Given** the user enters an API key, **When** setup completes, **Then** the key is saved to `auth.json` with mode 600 and is validated before saving.

---

### User Story 5 - Track Cost per Review Session (Priority: P3)

After a review completes, the user can see how many tokens were consumed and what the estimated cost was. Costs are logged per session to a local SQLite store. The user can view costs with `openreview gateway costs --today`.

**Why this priority**: Cost tracking is valuable for cost-conscious users but not required for the gateway to function. It can be added after the core routing works.

**Independent Test**: Can be tested by running a few gateway calls, then querying the cost store for token counts and cost estimates.

**Acceptance Scenarios**:

1. **Given** a completed review session, **When** the user calls `gateway.get_cost(session_id)`, **Then** the gateway returns token counts and estimated cost broken down by slot.
2. **Given** cost limits are configured, **When** a review would exceed the per-review cost limit, **Then** the gateway warns the user before proceeding.

---

### User Story 6 - Manage Model Registry (Priority: P3)

The gateway ships with a cached `models.json` listing available models per provider. The user can refresh it with `openreview gateway refresh`. For Ollama, models are discovered dynamically by querying the local server. The user can list available models with `openreview gateway models <provider>`.

**Why this priority**: A cached registry is needed for the setup wizard but can be a simple static file initially. Dynamic refresh and Ollama discovery are enhancements.

**Independent Test**: Can be tested by loading the registry, listing models for a provider, and verifying the output matches the registry contents.

**Acceptance Scenarios**:

1. **Given** the cached registry exists, **When** the user runs `openreview gateway models openai`, **Then** the gateway lists OpenAI's available models with slot compatibility and recommendations.
2. **Given** Ollama is running locally, **When** the user runs `openreview gateway models ollama`, **Then** the gateway queries the Ollama API and lists installed models alongside recommended models.
3. **Given** the cached registry is older than 7 days, **When** the gateway starts, **Then** it attempts a background refresh (silently, without blocking the user).

---

### Edge Cases

- What happens when a configured model is removed from a provider's API? → The gateway reports a clear "model not found" error and suggests alternatives from the registry.
- What happens when the user's API key is invalid or expired? → The gateway detects the authentication error and reports it distinctly from network errors, suggesting `openreview gateway setup` to reconfigure.
- What happens when Ollama is configured but not running? → The gateway reports "Ollama not reachable at localhost:11434" and suggests starting Ollama.
- What happens when config.yml is malformed or missing required fields? → The gateway raises a validation error at load time listing which fields are missing or invalid.
- What happens when `auth.json` has incorrect permissions? → The gateway warns that the file is world-readable and offers to fix permissions.
- What happens when a slot is not configured? → The gateway raises a clear error naming the unconfigured slot and suggesting `openreview gateway setup`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a uniform `Gateway` interface with `chat()`, `embed()`, and `rerank()` methods that route requests to the configured provider for each model slot. These methods MUST accept an explicit optional `session_id` keyword argument to associate the API call with a specific review session for cost tracking.
- **FR-002**: System MUST support 5 model slots: `reasoning`, `extraction`, `embedding`, `reranking`, and `graph`. The `reasoning`, `extraction`, and `graph` slots are independently configurable with a primary model and an optional fallback model. The `embedding` and `reranking` slots are primary-only — embedding runs locally by default (no network call to fail), and reranking is an optional precision step; there is no fallback model to switch to.
- **FR-003**: System MUST support 8 providers: OpenAI, Anthropic, Google, Ollama, OpenRouter, Cohere, HuggingFace, and Custom (any OpenAI-compatible endpoint).
- **FR-004**: System MUST load API keys from `auth.json` (with mode 600) or environment variables. Environment variables override `auth.json` values.
- **FR-005**: System MUST implement retry logic (configurable retries, delay, timeout) and fallback chains (primary → fallback → error) for all API calls.
- **FR-006**: System MUST never log, print, or expose API keys in any output. Keys in debug logs MUST be redacted to show only the last 4 characters.
- **FR-007**: System MUST provide a `health_check()` method that tests reachability for all configured providers.
- **FR-008**: System MUST ship a cached model registry (`models.json`) listing available models per provider with slot compatibility metadata.
- **FR-009**: System MUST support dynamic model discovery for Ollama by querying `http://localhost:11434/api/tags`.
- **FR-010**: System MUST provide an interactive setup wizard (`openreview gateway setup`) that walks through provider and model selection for each slot.
- **FR-011**: System MUST log token usage and estimated cost per API call to a local SQLite cost store.
- **FR-012**: System MUST support provider-specific pass-through parameters via an `extra_params` field on model configuration, per product-blueprint revision R-4.
- **FR-013**: System MUST support an all-local configuration where no network calls are made (all slots configured to Ollama).
- **FR-014**: System MUST validate configuration at load time and report missing or invalid fields before any API call is attempted.
- **FR-015**: System MUST provide CLI subcommands: `gateway setup`, `gateway status`, `gateway providers`, `gateway models <provider>`, `gateway set <slot> <model>`, `gateway refresh`, `gateway test <slot>`, `gateway costs`.

### Key Entities

- **ModelSlot**: Represents one of the 5 task-specific model assignments (reasoning, extraction, embedding, reranking, graph). Has a primary model, optional fallback model, and slot-specific parameters.
- **Provider**: Represents an AI service (OpenAI, Anthropic, Ollama, etc.). Has a name, authentication method, and a set of available models.
- **ModelEntry**: A specific model offered by a provider. Has a model identifier, compatible slots, context window size, recommended flag, and optional metadata (RAM requirements for local models, embedding dimensions).
- **CostRecord**: A log entry capturing token usage (prompt tokens, completion tokens), estimated cost, provider, model, slot, session_id, and timestamp.
- **GatewayConfig**: The loaded configuration from `config.yml` including all slot assignments, fallback settings, cost limits, and privacy settings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can send a chat request through the gateway and receive a response within the provider's typical latency plus no more than 50ms gateway overhead.
- **SC-002**: The gateway supports switching between any two configured providers for the same slot without code changes — only configuration changes.
- **SC-003**: When a primary model fails, fallback engages within 2 seconds (excluding retry delays) and the caller receives a response without needing to handle provider-specific errors.
- **SC-004**: All 5 model slots can be configured to use local models only, with zero outbound network calls during a review session.
- **SC-005**: The setup wizard can configure all 5 slots in under 3 minutes for a user who knows which providers they want to use.
- **SC-006**: API keys are never present in any log output, error message, or debug trace — only the last 4 characters are shown when referencing a key.
- **SC-007**: Cost tracking records token usage for every API call, and `gateway costs` produces a per-session and per-day summary. Accuracy is best-effort — LiteLLM's built-in pricing data may lag provider price changes by up to 72 hours.
- **SC-008**: The gateway package stays within the 100 MB peak memory budget (excluding loaded NLP and inference models) per the constitution.

## Assumptions

- LiteLLM SDK is the routing library. It is already specified in PR-1 and approved. It will be added as a runtime dependency via `uv add litellm` when implementation begins.
- Ollama is available at `http://localhost:11434` when local models are configured. The gateway does not manage the Ollama installation or lifecycle.
- The `config.yml` and `auth.json` paths follow the existing configuration infrastructure in `src/openreview_cli/config/`.
- Cost estimation uses LiteLLM's built-in token counting and pricing data. Exact cost accuracy is best-effort since provider pricing changes frequently.
- The model registry (`models.json`) is a static file shipped with the package. Remote refresh is a fetch from a GitHub raw URL (e.g., `https://raw.githubusercontent.com/mohamed-benoughidene/openreview-cli/main/models.json`).
- The gateway does not manage model downloads for Ollama. The user pulls models via `ollama pull` or the existing `openreview gateway install-models` command delegates to `ollama pull`.
- The PII stripping pipeline runs BEFORE the gateway is called. The gateway receives already-stripped text. The gateway itself does not perform PII detection or stripping.
- Provider-specific pass-through parameters (`extra_params`) are forwarded as-is to LiteLLM. The gateway does not validate provider-specific fields.
