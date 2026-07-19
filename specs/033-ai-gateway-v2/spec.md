# Feature Specification: AI Gateway v2 — Fail-Safe Privacy Routing, Complete Provider Registry, Capability Validation, and Streaming

**Feature Branch**: `feat/ai-gateway-v2`

**Created**: 2026-07-17

**Status**: Draft

**Input**: User description: "Feature: AI Gateway v2 — Fail-Safe Privacy Routing, Complete Provider Registry, Capability Validation, and Streaming"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fail-safe privacy classification (Priority: P1)

A user runs a review under the Maximum privacy tier, where every model slot is configured to a local provider (e.g. an Ollama-prefixed model). Even if the gateway hits an internal error while resolving the provider's routing config, the call must not be silently reclassified as a cloud call and falsely blocked. The gateway must either resolve the correct local classification or surface the error explicitly. Cloud-call telemetry must reflect the real dispatch destination.

**Why this priority**: A false-positive block prevents a legitimate local-only call from completing, and inflated cloud-call telemetry corrupts the privacy audit trail. This is the confidentiality-relevant core fix.

**Independent Test**: Configure a slot with a local Ollama model, force an internal error in provider-config resolution, and verify the call is never silently coerced into a "cloud" classification that blocks it; telemetry shows zero cloud calls.

**Acceptance Scenarios**:

1. **Given** a slot configured with a local Ollama model, **When** `_get_provider_cfg()` encounters an internal error while resolving it, **Then** the error is either resolved to the correct local classification or explicitly surfaced — never silently coerced into a `"cloud"` result that blocks a call which should have succeeded.
2. **Given** a local provider with a resolvable base URL, **When** classification runs, **Then** the URL-hostname local-detection path is live (not dead code) and correctly returns `"local"`.

---

### User Story 2 - Complete provider registry (Priority: P1)

A user wants to route calls to Deepseek, Qwen (cloud), and MiniMax — three of the four intended target providers — plus OpenRouter, with no gateway code changes. Each provider ships a pre-configured registry entry: environment-variable credential mapping, default headers where required, base URL, and capability metadata (embedding / reasoning / context window / tool-call support). A user must also be able to register an arbitrary OpenAI-compatible provider (name, base URL, credential env var, capability flags) purely through configuration.

**Why this priority**: Three of the four target providers are currently unreachable, and the gateway serves six LLM-calling components (Extraction Agent, QA Agent, Comparison Agent, Citation Grounding Discriminator, Reranker, and Embedding Engine). Without this, the tool cannot fulfil its core routing purpose.

**Independent Test**: Configure a slot to use a Deepseek model; verify the gateway resolves a complete registry entry requiring only an API key. Separately, add a custom provider via configuration and verify a slot referencing it routes through the same code path as pre-listed providers.

**Acceptance Scenarios**:

1. **Given** a slot configured to use a Deepseek model, **When** the gateway resolves it, **Then** it finds a complete registry entry requiring only an API key from the user.
2. **Given** a user adds a custom provider via configuration, **When** a slot references it, **Then** the gateway routes to it using the same code path as a pre-listed provider.
3. **Given** a fresh install with no prior config, **When** the TUI is opened for the first time, **Then** it successfully lists the same providers the CLI's `gateway providers` command lists, with no manual file setup required.

---

### User Story 3 - Pre-dispatch capability validation (Priority: P1)

An agent declares what it needs from a model (e.g. embedding support, a minimum context window, tool-call support). Before any request reaches a provider, the gateway validates the selected model's registry-declared capabilities against those requirements. A misconfigured pairing is rejected with a typed capability-mismatch error naming the specific mismatch, before any network call.

**Why this priority**: Today a model lacking required capabilities is silently assigned to any slot and only fails opaquely at request time. Failing fast, before the network, saves user time and produces actionable errors.

**Independent Test**: Configure the Embedding Engine with a chat-only model; attempt a call; verify a typed capability-mismatch error is raised before any network request is made.

**Acceptance Scenarios**:

1. **Given** the Embedding Engine is configured with a chat-only model, **When** a call is attempted, **Then** a typed capability-mismatch error is raised before any network request is made.

---

### User Story 4 - Typed error classification (Priority: P2)

When a provider call fails, the gateway classifies the error by real type — authentication failure, rate limiting, model-not-found, connection failure, capability mismatch — and correctly identifies which provider produced the error instead of hardcoding a default (e.g. "Ollama not reachable"). A 429 from any provider becomes a distinct rate-limit error, not a generic "all providers failed".

**Why this priority**: Opaque, mis-attributed errors make the tool impossible to debug for end users and operators.

**Independent Test**: Inject a 429 response from a named provider and verify it is raised as a distinct rate-limit error naming that provider. Inject a connection failure from a cloud provider and verify the message names that provider.

**Acceptance Scenarios**:

1. **Given** a 429 response from any provider, **When** the error is classified, **Then** it is raised as a distinct rate-limit error, not a generic all-providers-failed error.
2. **Given** a connection failure from a cloud provider, **When** the error is reported, **Then** the message names that provider, not a hardcoded default.

---

### User Story 5 - Provider message-format correction (Priority: P2)

Certain pre-listed providers reject specific message-format quirks. For example, Anthropic rejects empty message content parts with a hard 400. The gateway must detect and correct these automatically for pre-listed providers before sending the request, so no format-rejection error occurs.

**Why this priority**: Silently failing calls due to provider-specific format quirks are user-visible defects with no actionable cause from the user's perspective.

**Independent Test**: Build a message history containing an empty content part routed to Anthropic; verify the empty part is removed before sending and no format-rejection error occurs.

**Acceptance Scenarios**:

1. **Given** a message history containing an empty content part routed to Anthropic, **When** the request is prepared, **Then** the empty part is removed before sending and no format-rejection error occurs.

---

### User Story 6 - Streaming with dual timeouts (Priority: P2)

The CLI and TUI need live, incremental output rather than blocking on a full response. The gateway must support streaming responses with two independent timeouts — one for initial response headers, one for inter-chunk liveness — and emit incremental output events consumable by the CLI/TUI layer. If a provider stalls mid-stream, the call aborts with a clear timeout error instead of hanging indefinitely.

**Why this priority**: The constitution already mandates async, concurrent API calls and live CLI progress; streaming is a prerequisite for that user experience.

**Independent Test**: Run a full request/response cycle in streaming mode against a provider that is artificially delayed or dropped mid-stream; verify incremental output arrives and the call aborts with a clear timeout error without hanging.

**Acceptance Scenarios**:

1. **Given** a provider stops sending data mid-stream, **When** the chunk timeout elapses, **Then** the call is aborted with a clear timeout error and no indefinite hang occurs.

---

### User Story 7 - Agent-drivable, non-interactive gateway configuration (Priority: P2)

An AI agent wants to query the available providers and models, register a new custom provider, and configure model slots non-interactively. The CLI must support a machine-readable output mode for listing commands (`gateway providers` and `gateway models`), a non-interactive subcommand to add custom providers, and a complete non-interactive workflow to configure and test the gateway end to end without blocking on human-interactive wizard inputs.

**Why this priority**: Without machine-readable outputs and non-interactive setup subcommands, the gateway setup cannot be automated or driven reliably by an external AI agent.

**Independent Test**: Run `gateway providers --json` and `gateway models --json` and verify the output parses as valid JSON. Run the non-interactive provider add command and verify the provider registry is updated and that the provider can be set and tested successfully without any interactive prompt.

**Acceptance Scenarios**:

1. **Given** `gateway providers --json` is run, **When** the output is parsed, **Then** it is valid structured data containing the same provider set the human-facing table shows.
2. **Given** an agent runs the non-interactive add-provider command with valid arguments, **When** the command completes, **Then** the provider is available to `gateway set` without any interactive prompt having occurred.
3. **Given** no interactive terminal is available, **When** gateway setup is performed using only non-interactive commands, **Then** the gateway is fully configured and passes `gateway test` for every configured slot.

---

### Edge Cases

- What happens when an internal error occurs while building provider config for a genuinely local provider? (Must not be coerced to "cloud".)
- How does the gateway handle a custom provider whose declared capabilities do not match the calling agent's requirements?
- How does streaming behave when the initial headers never arrive within the 15-second header timeout?
- What happens when cost-limit enforcement itself raises an exception during a call? (Must not be silently discarded.)
- What happens when a provider returns a 401 (auth) vs a 404 (model-not-found) vs a 429 (rate-limit)? Each must be distinctly classified.
- What happens when a version upgrade adds a new pre-listed provider but the user's existing config-directory registry copy predates it? (Must merge the new provider in without touching user customizations.)
- What happens when two custom provider names derive to the same credential environment variable? (Must reject with an explicit error, never silently overwrite.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-1**: `classify_provider()` MUST correctly classify a genuinely local provider (e.g. an Ollama-prefixed model) as `"local"` even if an upstream exception occurs while building its input — an exception building the provider config MUST raise or be handled explicitly, not silently default to values that force a `"cloud"` classification. The `api_base` field MUST be populated from the real provider config (currently hardcoded to `""`) so the existing URL-hostname detection path is live.
- **FR-2**: The provider registry MUST include pre-configured entries for Deepseek, Qwen (cloud), and MiniMax, each with an environment-variable credential mapping, default headers where required, base URL, and capability metadata (embedding / reasoning / context window / tool-call support).
- **FR-3**: Users MUST be able to register a custom OpenAI-compatible provider outside the pre-listed set by supplying a name, base URL, and capability flags through configuration (stored in the user config directory, resolved per the platform's config-dir convention), without editing gateway code. The credential environment variable is derived automatically from the provider name (uppercased, non-alphanumeric characters replaced by underscores). If a user-supplied provider name derives to an environment variable that collides with an existing provider's (pre-listed or custom), the registration MUST be rejected with an explicit naming-collision error rather than silently overwriting the existing entry. (Exact config key, path, and derivation rule: `contracts/registry.md`.)
- **FR-4**: Before dispatching any request, the gateway MUST validate that the selected model's registry-declared capabilities satisfy the calling agent's requirements (capability type, minimum context window, tool-call support where applicable). This applies to all six LLM-calling components: Extraction Agent, QA Agent, Comparison Agent, Citation Grounding Discriminator, Reranker, and Embedding Engine.
- **FR-5**: The gateway MUST classify errors into distinct types — at minimum authentication failure, rate limiting, model-not-found, connection failure, and capability mismatch — and MUST correctly identify which provider produced the error rather than defaulting to a hardcoded one.
- **FR-6**: Exceptions inside cost-limit enforcement checks MUST NOT be silently discarded. They must be surfaced at a visible log level and must not allow limit enforcement to fail silently.
- **FR-7**: For each pre-listed provider with a known message-format requirement (at minimum: Anthropic rejecting empty content parts), the gateway MUST apply the correction automatically before sending the request.
- **FR-8**: The gateway MUST support streaming responses with two independent timeouts — a 15-second header (first-byte) timeout and a 45-second inter-chunk idle timeout — and MUST emit incremental output events consumable by the CLI/TUI layer.
- **FR-9**: The CLI and TUI MUST resolve the provider registry from a single shared source of truth. On first run, if the user-config-directory copy does not exist, it MUST be seeded from the packaged default automatically. On every subsequent run, any pre-listed provider present in the packaged default but absent from the user's copy MUST be merged in automatically, without overwriting user-added custom providers or any user modifications to existing pre-listed entries. All registry reads (CLI commands, TUI domain layer, custom-provider additions from FR-3) MUST go through one shared resolution function, not two independent path constants. (Resolution algorithm: `contracts/registry.md`.)
- **FR-10**: The provider-listing and model-listing commands MUST support a machine-readable output mode returning the same data currently rendered as a human table, so an agent can consume it reliably without parsing formatted text.
- **FR-11**: Registering a custom provider and setting its credentials MUST be possible through a direct, non-interactive command, independent of the interactive setup wizard. (Exact command syntax: `contracts/cli-gateway.md`.)
- **FR-12**: The interactive `gateway setup` wizard MAY remain interactive for human use, but MUST NOT be the only path to complete gateway configuration — full setup (adding providers, setting credentials, assigning models to slots, testing them) MUST be achievable entirely through non-interactive commands (`gateway provider add`, `gateway set`, `gateway test`) end to end.

### Key Entities *(include if feature involves data)*

- **Provider Registry Entry**: a provider definition (name, base URL, credential env var, default headers, capability metadata: embedding / reasoning / context window / tool-call support). Pre-listed entries live in the bundled default registry (inside the installed package, overwritten on upgrade); user-added entries live in the user config directory. Both share the same field shape. The credential env var for user-added entries is derived deterministically from the provider name.
- **Model Capability Declaration**: the registry-declared capabilities of a model (capability type, context window size, tool-call support), used for pre-dispatch validation.
- **Agent Capability Requirement**: what a calling agent needs from a model (capability type, minimum context window, tool-call support).
- **Error Classification**: a typed result (auth, rate-limit, not-found, connection, capability-mismatch) plus the identity of the failing provider.
- **Streaming Output Event**: an incremental chunk emitted to the CLI/TUI layer, constrained by header and inter-chunk timeouts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-1**: A confidentiality-relevant internal error can no longer result in a request being sent to a cloud provider, or in a legitimate local call being falsely blocked.
- **SC-2**: All four target providers (OpenRouter, Deepseek, Qwen, MiniMax) plus any user-added custom provider are addressable with no gateway code changes required by the user.
- **SC-3**: A misconfigured agent/model pairing is rejected before any network call, with an error naming the specific mismatch.
- **SC-4**: Rate limits, auth failures, and connection failures are distinguishable from each other in both logs and user-facing messages.
- **SC-5**: Streaming works correctly under test: the first content chunk arrives within the 15-second header timeout; each subsequent chunk arrives within the 45-second idle timeout of the previous one; across 20 consecutive automated runs against a mocked slow/dropping provider, zero indefinite hangs occur; at least 95% of successful runs render one or more intermediate chunks before the final chunk.
- **SC-6**: Cloud-call telemetry accurately reflects the real dispatch destination for every routed call.
- **SC-7**: On a fresh install, the CLI's `gateway providers` and the TUI's provider list return the identical provider set, with zero manual file setup by the user. After a version upgrade that adds a new pre-listed provider, existing users' installs reflect that new provider without needing to delete or manually recreate their config.
- **SC-8**: A gateway can be fully configured — providers added, credentials set, models assigned to slots, all slots tested — using only non-interactive commands, with zero interactive prompts triggered, verified in an environment with no interactive terminal available.

## Assumptions

- The privacy tier enforcement model (`llm_local_only`, `pii_required_before_cloud`) already correctly implements Principle I and is not changed by this spec; FR-1 only corrects a classification bug.
- Provider SDKs (where used) are lazy-loaded at call time, never preloaded at startup, to respect the <100 MB peak memory budget and <1s cold start (Principle III).
- Streaming is implemented using `httpx`'s existing streaming support; no new SSE/chunk-parsing dependency is introduced unless `httpx` proves insufficient, in which case the addition is justified in the implementation plan and subject to the forbidden-dependency list (Principle IV).
- The custom-provider path is a plain data/config extension stored in the user config directory, sharing the same field shape as the bundled default registry. It is not a plugin interface or factory (Principle V). The bundled default registry lives inside the installed package and is overwritten on every upgrade; it is not a user-owned config file.
- No new reactive retries (e.g. exponential backoff) are required by this spec; current linear retry behavior is retained.
- No agent in this tool currently makes tool/function calls, so Mistral tool-call ID sanitization is out of scope.
- The Retrieval Engine (no model calls) is unchanged by this spec. The Comparison Agent (`bilateral/comparison.py`) calls the gateway unconditionally on every bilateral comparison; it is one of the six LLM-calling consumers scoped by FR-4 but its routing logic is unchanged by this spec. (Corrects the earlier assumption that it was rule-based only.)

## Clarifications

### Session 2026-07-17

Implementation-specific decisions captured during clarification (concrete timeout values, storage paths, credential-env-var derivation, CLI command syntax, the six capability-scoped consumers, and the shared-registry resolution algorithm) are recorded in the feature's contract artifacts — `contracts/cli-gateway.md` and `contracts/registry.md` — rather than inline here, to keep this specification technology-agnostic and stakeholder-readable. The spec above references those contracts at the relevant FRs.

Summary of resolved points (detail in contracts):
- Streaming timeouts and SC-5 success floor → `contracts/cli-gateway.md` (streaming section).
- Custom-provider storage location and registry resolution algorithm → `contracts/registry.md`.
- Six FR-4-scoped consumers (Extraction, QA, Comparison, Citation Grounding Discriminator, Reranker, Embedding Engine) and their module locations → `contracts/registry.md` (Capability Validation section).
- Credential env-var derivation and naming-collision rule → `contracts/registry.md` (Custom Provider section).
- Non-interactive CLI command syntax (`--json`, `provider add`) → `contracts/cli-gateway.md`.
