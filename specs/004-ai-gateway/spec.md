# Feature Specification: AI Gateway

**Feature Branch**: `feat/004-ai-gateway`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "Phase 4 — AI Gateway: model routing layer connecting the review engine to AI providers (cloud and local), with 5 task-specific slots, fallback chains, cost tracking, interactive setup, and BYOK key management"

## Clarifications

### Session 2026-06-25

- Q: What identifies a review session for cost aggregation? → A: UUID auto-generated per `openreview review` invocation (no user input needed).
- Q: What YAML schema does `gateway import` accept? → A: Slot-keyed format — top-level keys are slot names (`reasoning:`, `extraction:`, `embedding:`, `reranking:`, `graph:`), each mapping to `provider`, `model`, optional fallback and parameters.
- Q: Can YAML import files contain inline API keys? → A: No. YAML references env var names only (`api_key_env: OPENAI_API_KEY`). Keys resolved from environment or auth file at runtime. Zero leakage risk.
- Q: How long are cost records retained? → A: Indefinitely. No auto-prune. Users can filter via `gateway costs --days N` or clear via `gateway costs --clear`.
- Q: What should the wizard show when Ollama has no models or API validation is slow? → A: Three explicit states: (1) Ollama not running → actionable message with `ollama serve`, (2) Ollama running but no models → actionable message with `ollama pull`, (3) API validation timeout → spinner, configurable timeout (default 10s), retry/skip.
- Q: How does the gateway handle provider API versioning and breaking changes? → A: API version compatibility is managed by LiteLLM. The gateway relies on LiteLLM for provider-specific API support; version updates may be needed to support new provider APIs.
- Q: What happens if the config file is partially written during save? → A: Atomic writes: write to temp file, fsync, then rename. Old file preserved until rename succeeds.
- Q: What counts as a "minimal test request" for API key validation? → A: Call `GET /v1/models` (or provider equivalent). Zero cost, works for OpenAI, OpenRouter, Anthropic, Custom. Fallback to 1-token chat completion if the provider doesn't support a list endpoint.
- Q: What should the gateway log and where? → A: Three-tier logging: console shows INFO (API calls, cost, fallback activations); debug file (`~/.openreview/gateway.log`) captures DEBUG details (per-call timing, tokens, model); response bodies never logged unless `--debug-unsafe` is used.
- Q: Should the spec use "slot" or "model slot" consistently? → A: Use "slot" everywhere. Shorter, matches CLI output, used 90% of the time already.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Route Requests Through Task-Specific Slots (Priority: P1)

The review engine needs to call AI models for five distinct tasks — reasoning (compare contract vs playbook), extraction (pull clause values), embedding (vectorize text chunks), reranking (re-score retrieved chunks — optional, disabled by default), and graph extraction (structured JSON output). Each task gets its own slot so the user can assign the best model for each job. The engine calls a single routing function with a slot name and the gateway handles provider selection, authentication, and response formatting. The engine code never imports provider-specific libraries.

**Why this priority**: This is the foundation. Without a working routing layer, no review can run. Every downstream phase (chunking, comparison, memo generation) depends on being able to call a model through a slot.

**Independent Test**: Can be fully tested by configuring a slot with a known provider, sending a request through the routing function, and verifying the response is returned correctly. Repeat for each of the five slots.

**Acceptance Scenarios**:

1. **Given** the reasoning slot is configured with a provider and model, **When** the engine sends a chat completion request through the routing function for the reasoning slot, **Then** the request reaches the configured provider and the response text is returned to the engine.
2. **Given** the embedding slot is configured with a local model, **When** the engine sends a list of text chunks for embedding, **Then** a list of vectors (one per chunk) is returned.
3. **Given** the reranking slot is configured with a local model, **When** the engine sends a query and a list of documents for reranking, **Then** the documents are returned sorted by relevance with scores.
4. **Given** all five slots are configured, **When** the engine sends requests through each slot, **Then** each request is routed to the correct provider/model for that slot, and no slot receives a request meant for another.
5. **Given** a slot has model parameters configured (temperature, max_tokens), **When** a request is sent through that slot, **Then** the parameters are applied to the request.

---

### User Story 2 - Interactive First-Time Setup (Priority: P1)

A user running the tool for the first time has no models configured. They run the setup command and an interactive wizard walks them through each of the five slots. For each slot, the wizard lists available providers, the user picks one, the wizard lists that provider's models, the user picks one, and the assignment is saved. For cloud providers, the wizard collects and validates the API key with masked input and a copy-to-clipboard action. For local providers (Ollama), no key is needed. When a provider is selected, the wizard offers to apply the same provider to compatible remaining slots (e.g., "Apply OpenAI to the extraction and graph slots too? (Y/n)"). The user may skip any slot.

A visible progress indicator shows "Step X of 4" at all times (reranking is optional — the step is skipped unless the user opts in). The user can navigate back to previous slots without losing entered values, and can cancel at any step with a warning that progress will be saved for configured slots so far. At the end, a summary is shown and the user confirms.

The wizard is not the only path. Users can also configure slots via command-line flags (`--<slot> <provider/model>`) or by importing a YAML config file. These paths are described in User Story 6.

**Why this priority**: Without setup, no review can run. The setup wizard is the user's first experience with the tool — it must be clear, fast, and produce a working configuration. A user who completes setup can immediately run a review.

**Independent Test**: Can be fully tested by running the setup command on a clean configuration (no existing config or auth files), walking through all five slots with simulated input, and verifying the resulting config and auth files are valid and complete. Can also be tested with non-interactive flags and with a config file import.

**Acceptance Scenarios**:

1. **Given** no configuration exists, **When** the user runs the setup command, **Then** the wizard starts with a welcome message explaining the purpose and that API keys stay on the user's machine.
2. **Given** the wizard is at the API key prompt for a cloud provider, **When** the user enters a key with masked input, **Then** a "copy to clipboard" action is available adjacent to the field, and the wizard immediately validates the key with a minimal test request before advancing to the next step.
3. **Given** the wizard is at a slot prompt, **When** the user selects Ollama (local), **Then** the wizard lists installed Ollama models (discovered dynamically) and does NOT prompt for an API key.
4. **Given** the wizard is at the embedding or reranking slot, **When** the user selects a cloud provider, **Then** a notice is shown: "This slot processes full contract text. Selecting a cloud provider means contract data leaves your machine."
5. **Given** the wizard has completed all five slots, **When** the summary is shown, **Then** each slot's assigned model and fallback (if any) is displayed, along with estimated cost per review.
6. **Given** the user confirms the summary, **When** the wizard saves, **Then** model routing is written to the config file and API keys are written to the auth file with restricted permissions.
7. **Given** the wizard is at any step, **When** the user selects "Back", **Then** the previous slot's selections are restored and editable.
8. **Given** the wizard is at any step, **When** the user selects "Cancel", **Then** a warning shows "Configured slots so far will be saved. Cancel anyway? (y/N)" and, if confirmed, exits with a message showing what was configured.
9. **Given** the wizard has set a provider on the reasoning slot, **When** moving to the extraction slot, **Then** the wizard asks "Apply this provider to extraction and graph too? (Y/n)". If yes, those slots are pre-filled.
10. **Given** the wizard is at any slot prompt, **When** the user selects "Skip this slot", **Then** the slot is marked as unconfigured and the wizard moves on.
11. **Given** the user runs setup with flags (e.g., `--reasoning openai/gpt-4o --embedding ollama/nomic-embed-text`), **When** the command completes, **Then** the specified slots are configured and the wizard is not shown.
12. **Given** the user provides both flags and runs the wizard, **When** both are present, **Then** the flags take precedence (CLI convention) and the wizard skips configured slots.

---

### User Story 3 - Automatic Fallback and Retry on Failure (Priority: P2)

AI providers can fail — rate limits, timeouts, temporary outages, invalid responses. When a request through a slot fails, the gateway retries the primary model (with exponential backoff, up to a configurable number of attempts). If retries are exhausted and a fallback model is configured for that slot, the gateway tries the fallback. If the fallback also fails, the behaviour depends on the configured on-failure mode: error (raise and halt), skip (omit the result and continue), or warn (emit a warning and continue with partial results). The user sees which model served each response in the review output.

**Why this priority**: Resilience is critical for a tool that may process large contracts over many API calls. A single provider outage should not halt an entire review if a fallback is available. This is the second most important capability after basic routing.

**Independent Test**: Can be fully tested by configuring a slot with a primary and fallback model, simulating a primary failure (e.g., mock a timeout), and verifying the gateway retries, then falls back, and returns a successful response from the fallback model.

**Acceptance Scenarios**:

1. **Given** a slot's primary model returns a rate-limit error, **When** the gateway catches the error, **Then** it waits (exponential backoff starting at the configured retry delay) and retries the primary model, up to the configured retry count.
2. **Given** retries are exhausted on the primary model and a fallback is configured, **When** the gateway attempts the fallback, **Then** the fallback model serves the request and the response includes an indicator that the fallback was used.
3. **Given** both primary and fallback fail, and on-failure is set to "error", **When** the failure occurs, **Then** the gateway raises an error with the slot name and failure reason, and the review halts.
4. **Given** both primary and fallback fail, and on-failure is set to "skip", **When** the failure occurs, **Then** the gateway logs the failure and the review continues without the result from that slot.
5. **Given** both primary and fallback fail, and on-failure is set to "warn", **When** the failure occurs, **Then** the gateway emits a user-visible warning and the review continues with partial results.
6. **Given** no fallback is configured for a slot, **When** the primary model fails after all retries, **Then** the on-failure behaviour applies directly (no fallback attempt).

---

### User Story 4 - Track Costs and Enforce Limits (Priority: P2)

Each API call consumes tokens and incurs cost. The gateway tracks token usage (input tokens, output tokens) and estimated cost per call, aggregating by review session. The user can view costs for the current day or for a specific review. Configurable limits (per-review and daily) prevent runaway spending. When a limit is reached, the gateway stops making calls and informs the user with options (wait until tomorrow, switch to local models, or raise the limit).

**Why this priority**: Cost visibility prevents surprise bills. A lawyer reviewing many contracts could accumulate significant API costs without realising it. Limits are a safety net. This is important but secondary to routing and fallback — the tool works without cost tracking, just without visibility.

**Independent Test**: Can be fully tested by making several API calls through the gateway, verifying token counts and cost estimates are recorded, and confirming that when a cost limit is reached, subsequent calls are blocked with the appropriate message.

**Acceptance Scenarios**:

1. **Given** a review session is active, **When** an API call completes, **Then** the token counts (input, output) and estimated cost for that call are recorded against the session.
2. **Given** the user runs the cost command, **When** it executes, **Then** it shows total tokens and estimated cost for the current day, and optionally for a specific review ID.
3. **Given** the per-review cost limit is configured and a call would exceed it, **When** the gateway checks the limit before the call, **Then** the call is blocked and the user sees a message with the current cost, the limit, and options to proceed.
4. **Given** the daily cost limit is configured and has been reached, **When** a new API call is attempted, **Then** the call is blocked and the user sees a message indicating the daily limit has been reached.
5. **Given** cost tracking is active, **When** the review completes, **Then** the final cost summary is included in the review output.

---

### User Story 5 - Manage Gateway Configuration via CLI (Priority: P3)

After initial setup, the user needs to check status, change models, test connectivity, list providers and models, refresh the model registry, and install local models — all without re-running the full setup wizard. Each operation is a subcommand under the gateway command group.

**Why this priority**: These are maintenance and diagnostic commands. They are needed for day-to-day use but do not block the core workflow (setup → review). They can be added incrementally.

**Independent Test**: Can be fully tested by running each subcommand against a known configuration and verifying the output matches expectations.

**Acceptance Scenarios**:

1. **Given** a configuration exists, **When** the user runs the status command, **Then** each slot's assigned model, provider reachability, and last-known health status are displayed.
2. **Given** the user runs the providers command, **When** it executes, **Then** all supported providers are listed with their authentication method and current status (configured/not configured).
3. **Given** the user runs the models command for a specific provider, **When** it executes, **Then** the available models for that provider are listed with slot compatibility.
4. **Given** the user runs the set command with a slot and model identifier, **When** it executes, **Then** the config is updated to assign that model to the slot, and the change is confirmed.
5. **Given** the user runs the test command for a slot, **When** it executes, **Then** a small test request is sent through the slot and the result (success/failure, latency) is displayed.
6. **Given** the user runs the refresh command, **When** it executes, **Then** the cloud model registry is fetched from the remote source and the local cache is updated. If the fetch fails, the existing cache is retained.
7. **Given** the user runs the install-models command with a list of Ollama model names, **When** it executes, **Then** each model is pulled via Ollama and progress is shown.

---

### User Story 6 - Import Configuration from YAML File (Priority: P2)

A user who manages multiple machines or a team wants to share model configuration via a single file. They write a config file once and run `openreview gateway import <file>` to apply all five slot assignments at once. No interactive prompts needed. Power users can also skip the wizard entirely and configure slots via command-line flags (`--<slot> <provider/model>`).

**Why this priority**: P2 because it's a convenience for power users and teams, not a blocker. A single-machine user can use the wizard or flags. Teams benefit from shareable dotfiles. This story also covers the non-interactive flags path, which is essential for CI, scripting, and automated provisioning.

**Independent Test**: Write a valid YAML config file with all five slots, run the import command, and verify the config matches. Repeat with invalid files and verify all errors are reported. Also test with flags and verify no wizard appears.

**Acceptance Scenarios**:

1. **Given** a valid YAML config file with all five slots defined, **When** the user runs `openreview gateway import <file>`, **Then** all five slots are assigned and a summary is displayed.
2. **Given** a YAML config file with a missing required field, **When** the import command runs, **Then** all missing fields are reported in a single error message, and no config changes are applied.
3. **Given** a YAML config file with an unrecognized provider, **When** the import runs, **Then** the error lists all valid providers, and no config changes are applied.
4. **Given** existing configuration, **When** the user imports a new config file, **Then** a confirmation prompt is shown before overwriting.
5. **Given** the user runs `openreview gateway set --reasoning openai/gpt-4o --embedding ollama/nomic-embed-text`, **When** the command completes, **Then** those two slots are configured and all other slots remain unchanged.
6. **Given** the user sets environment variables for API keys (e.g., `OPENAI_API_KEY`), **When** the gateway calls a provider, **Then** the env-var key is used instead of the one in the auth file.

---

### Edge Cases

- What happens when no model is configured for a slot and a review attempts to use it? The gateway raises a clear error naming the slot and instructing the user to run setup.
- What happens when an API key is invalid or expired? The gateway detects the authentication error during setup validation and at runtime, displaying a message that names the provider and suggesting checking the key.
- What happens when Ollama is not running and a local slot is used? The gateway detects the connection failure and reports that Ollama is not reachable, with instructions to start it.
- What happens when a provider returns a response in an unexpected format? The gateway validates the response structure and raises a parse error with the slot name, without crashing.
- What happens when the user is fully offline and all slots are cloud-based? The gateway reports that no reachable provider is configured and suggests switching to local models or connecting to the internet.
- What happens when the same model is assigned to multiple slots? This is allowed — the gateway routes each slot independently even if they share a model.
- What happens when a cost limit is exactly equal to the current spend? The next call is blocked (limit is a ceiling, not a threshold).
- What happens when the model registry cache is corrupted or empty? The gateway falls back to a built-in minimal registry that ships with the application.
- What happens when no configuration flags are passed and no existing config exists? The system falls back to the interactive wizard. If non-interactive mode is forced (e.g., `--no-interactive`), it errors.
- What happens when a slot was skipped during setup? The gateway raises a clear error naming the slot and instructing the user to run `openreview gateway set <slot> <provider/model>`.
- What happens when API key validation fails during setup? The wizard shows the specific error ("Invalid key: authentication failed for provider X"), allows retry, skip the slot, or cancel.
- What happens when conflicting config is provided (e.g., both a flag and a wizard answer)? Flags take precedence (CLI convention).
- What happens during an import when a config file has multiple errors? All errors are reported at once (not just the first), and no config is applied until all are fixed.
- What happens when Ollama is running but has no models installed? The wizard shows "No models found. Run `ollama pull <model>` to install one, then retry or skip this slot."
- What happens when API key validation times out during setup? The wizard shows a spinner, aborts after the configured timeout (default 10s), and offers retry or skip the slot.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a routing layer that accepts a slot name and a request, and dispatches the request to the provider/model configured for that slot.
- **FR-002**: The system MUST support four required slots (reasoning, extraction, embedding, graph) and one optional slot (reranking, disabled by default).
- **FR-003**: The system MUST support at least these providers: OpenAI, Anthropic, Google, Ollama, OpenRouter, Cohere, HuggingFace, and Custom (OpenAI-compatible endpoint).
- **FR-004**: The system MUST route chat completion requests (for reasoning, extraction, graph slots), embedding requests (for embedding slot), and MAY route reranking requests (for reranking slot) through the appropriate provider API.
- **FR-005**: The system MUST store API keys in a dedicated auth file with restricted file permissions (mode 600), and MUST support equivalent environment variables that override the file.
- **FR-006**: The system MUST NEVER send API keys, raw contract text, or PII to any server operated by the tool. All API calls go directly from the user's machine to the user's chosen provider.
- **FR-007**: The system MUST support a fallback model for each slot. When the primary model fails after all retries, the fallback model is attempted.
- **FR-008**: The system MUST support configurable retry behaviour: number of retries, delay between retries (exponential backoff), request timeout, and on-failure mode (error, skip, warn).
- **FR-009**: The system MUST track token usage (input tokens, output tokens) and estimated cost per API call, aggregated per review session.
- **FR-010**: The system MUST enforce configurable cost limits: per-review and daily. When a limit is reached, further API calls are blocked.
- **FR-011**: The system MUST provide an interactive setup command that walks the user through configuring each slot: provider selection, model selection, and API key entry (for cloud providers).
- **FR-012**: The system MUST discover local models dynamically by querying the local model server, and MUST discover cloud provider models from a cached registry that can be refreshed.
- **FR-013**: The system MUST provide CLI subcommands for: status, providers, models, set, test, refresh, costs, and install-models.
- **FR-014**: The system MUST support a fully local configuration where every slot uses Ollama and no API keys or network calls are required.
- **FR-015**: The system MUST validate API keys during setup by calling the provider's models list endpoint (`GET /v1/models` or equivalent). If the provider does not support a list endpoint, fall back to a 1-token chat completion on the cheapest available model.
- **FR-016**: The system MUST indicate in review output which model served each response, including when a fallback was used.
- **FR-017**: The system MUST NOT import provider-specific libraries in engine code. All provider interaction MUST go through the routing layer.
- **FR-018**: The system MUST retain the cached model registry when a refresh fetch fails (network error, timeout).
- **FR-019**: The system MUST include a built-in minimal model registry as a fallback when the cached registry is missing or corrupted.
- **FR-020**: The system MUST support configuring all slots via command-line flags (`--<slot> <provider/model>`), without requiring the interactive wizard.
- **FR-021**: The system MUST support environment variables for API keys (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) that override the auth file's stored keys.
- **FR-022**: The system MUST allow users to skip any slot during interactive setup. Skipped slots are marked as unconfigured; the gateway raises a clear error if a review attempts to use one.
- **FR-023**: The system MUST support importing model configuration from a YAML file via the `gateway import` subcommand.
- **FR-024**: The system MUST validate the entire imported config file before applying any changes, reporting all errors at once.
- **FR-025**: The system MUST prompt for confirmation before overwriting existing configuration during import.
- **FR-026**: The system MUST provide visible step progress ("Step X of 4"; reranking is optional — the step is skipped unless the user opts in), back navigation, and cancel-with-save during the interactive wizard.
- **FR-027**: The system MUST offer to apply the selected provider to compatible remaining chat slots (reasoning, extraction, graph) when a provider is chosen for one of them during setup.
- **FR-028**: The system MUST validate API keys immediately on entry in the wizard (not at end), and show a copy-to-clipboard action adjacent to masked input fields.
- **FR-029**: The system MUST write configuration files atomically: write to a temporary file in the same directory, call `fsync`, then rename to the target path. This prevents partial/corrupt configs on crash.

### Key Entities

- **Model Slot**: A named task category (reasoning, extraction, embedding, graph — required; reranking — optional, disabled by default) with a primary model assignment, optional fallback model, and optional parameters (temperature, max_tokens, dimensions, etc.).
- **Provider**: An AI service endpoint (cloud or local) with an authentication method (API key, none for Ollama, API key + base URL for Custom) and a set of available models.
- **Model Registry**: A cached catalogue of providers and their available models, including slot compatibility, context window, and RAM requirements (for local models). Refreshed periodically from a remote source.
- **Cost Record**: A per-call record of input tokens, output tokens, estimated cost (USD), slot used, model used, and review session ID. Aggregated for cost reporting and limit enforcement.
- **Auth Store**: A local file containing provider-to-API-key mappings, created with restricted permissions. Overridable by environment variables.
- **Config File (YAML)**: A portable YAML file describing all five slot assignments, optionally with API key environment variable references. Importable via `gateway import`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with no prior configuration can complete the interactive setup for all five slots in under 5 minutes.
- **SC-002**: A review that uses cloud providers completes with correct responses routed through the configured slots, and switching providers requires only a configuration change — no code changes.
- **SC-003**: When a primary provider is unavailable, the gateway automatically falls back to the configured fallback model within 30 seconds (including retry delays), and the review continues without user intervention.
- **SC-004**: Cost tracking accurately reports token usage within 1% of the provider's own usage reporting.
- **SC-005**: A fully local configuration (all slots using local models) processes a 50-page contract review with zero network calls to external providers.
- **SC-006**: When a cost limit is reached, no further API calls are made — the limit is enforced before the call, not after.
- **SC-007**: The gateway routing layer adds less than 50 ms of overhead per request compared to a direct provider call (excluding network latency).
- **SC-008**: 100% of API keys stored in the auth file are redacted in all log output and CLI display (except during masked entry in setup).
- **SC-009**: A user can configure all five slots from the command line using flags or environment variables, without any interactive prompts, in under 30 seconds.
- **SC-010**: The wizard displays a visible progress indicator at all times, supports back navigation and cancel-with-save, and the majority of first-time users complete setup in under 3 minutes.
- **SC-011**: A user can configure all five slots by running `openreview gateway import config.yaml` in under 10 seconds with no interactive prompts.
- **SC-012**: API keys are masked on entry with a copy-to-clipboard action, and validation occurs immediately (before advancing to the next step).

## Assumptions

- The user has Python 3.12+ and the openreview-cli package installed.
- For local slots (Ollama), the user has Ollama installed and running on the default port (localhost:11434).
- The user has sufficient RAM for local models (the minimal setup requires ~6.5 GB for all three local models).
- The cloud model registry is hosted at a known URL and is reachable when the user has internet access.
- PII stripping (Phase 3) has already processed contract text before it reaches the gateway. The gateway does not perform its own PII detection.
- The review engine (Phase 5+) will call the gateway through its routing interface. This spec defines the gateway layer only, not the engine's prompts or review logic.
- LiteLLM is used as the provider abstraction layer (approved in the constitution, not on the forbidden list).
- Pydantic is used for configuration validation and gateway routing (explicitly permitted in the constitution).
- Cost estimates are based on provider-published pricing tables. Actual costs may vary slightly due to pricing changes; the estimates are guidance, not billing.
- The Custom provider accepts any OpenAI-compatible endpoint (base URL + API key). The user is responsible for ensuring their custom endpoint is compatible.
- Response caching (same clause producing the same result) is explicitly out of scope for this phase.
- Multi-user API key management is out of scope.
- Automatic model selection based on contract complexity is out of scope.
- Provider API version compatibility is managed by LiteLLM. The gateway relies on LiteLLM for provider-specific API support; LiteLLM version updates may be needed to support new provider APIs or breaking changes.
