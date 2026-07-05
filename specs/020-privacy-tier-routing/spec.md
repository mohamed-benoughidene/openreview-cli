# Privacy Tier Routing

**Feature ID**: 020-privacy-tier-routing
**Status**: Draft Specification
**Created**: 2026-07-05

---

## 1. Executive Summary

The AI Gateway (spec-005) routes model calls to whichever provider the user has configured — local (Ollama), cloud (OpenAI, Anthropic, etc.), or both. Today, every call goes to the same provider regardless of the sensitivity of the data being processed. A user reviewing a standard NDA and a user reviewing a trade-secret license get the same routing behavior: whatever the config says.

This specification defines a **privacy tier routing** system that lets users choose how their data travels based on the privacy requirements of each operation. Three tiers:

- **Maximum** — all inference runs locally via Ollama. No data ever leaves the machine. Zero external API calls.
- **Balanced** — embeddings and retrieval run locally. Only the LLM reasoning call goes to a cloud provider, and only after PII has been stripped from the contract text. The cloud never sees raw personal data.
- **Performance** — all inference runs on cloud providers for speed. PII is stripped from contract text before it leaves the machine, just as in Balanced.

The router sits between the Gateway and the calling code (review pipeline, extraction agent, etc.). It inspects the configured privacy tier before every Gateway call and enforces the rules: Maximum tier blocks cloud providers, Balanced and Performance tiers ensure PII stripping is complete before allowing cloud egress. If the PII stripping engine is unavailable and the current operation requires a cloud call, the router blocks the call with a clear error — it never silently falls back to raw-text cloud inference.

The privacy tier is read from `config.yml` at the `privacy.tier` key so the user sets it once per environment. Changing the tier takes effect on the next operation. The current tier is visible in all pipeline output so the user always knows what protection level is active.

**What this delivers:**

- Three well-defined privacy tiers, each with a clear data-flow contract
- Enforcement at the Gateway call boundary — no cloud provider is reachable on Maximum tier, and no raw (unstripped) text reaches a cloud provider on any tier
- PII-stripping-before-egress guarantee for Balanced and Performance tiers
- Graceful block when PII stripping fails and a cloud call is pending — never an accidental data leak
- Tier visibility in all pipeline progress output and final reports
- Configuration via `config.yml` `privacy.tier` — no CLI flags needed for normal use

---

## 2. User Scenarios

### Scenario 1 — Maximum tier: all processing stays local (Priority: P1)

A lawyer reviews a contract containing trade secrets, employee personal data, and financial information. They set `privacy.tier: maximum` in their config. Every model call — embeddings, LLM reasoning, classification — routes to the local Ollama instance. The review completes with no network activity beyond the local machine.

The user sees:

```
Privacy tier: MAXIMUM — all inference local
[1/5] Parsing…  OK
[2/5] Stripping PII…  OK (PII kept local)
[3/5] Generating assessment…
  ◼ Using model "ollama/llama3.1" (local)
```

The final report includes a banner: "Processed under Maximum privacy tier. No data was sent to external services."

**Why this priority**: Maximum tier is the core privacy guarantee. Without it, users handling sensitive documents have no way to enforce local-only processing.

**Independent Test**: A test that sets `privacy.tier: maximum`, configures both a local and a cloud provider, runs a review on a synthetic document, and asserts that zero HTTP requests are made to any URL outside `localhost` or `127.0.0.1`.

**Acceptance Scenarios**:

1. **Given** `privacy.tier: maximum`, **When** any Gateway model call is made, **Then** the router selects only local providers (Ollama) and blocks any cloud provider call with a clear error.
2. **Given** `privacy.tier: maximum` and only cloud providers configured, **When** a Gateway call is attempted, **Then** the router produces an error: "Maximum privacy tier requires a local provider (Ollama). No local provider configured."
3. **Given** `privacy.tier: maximum`, **When** the review completes, **Then** the final output includes a privacy-tier banner confirming local-only processing.

---

### Scenario 2 — Balanced tier: local embeddings, cloud LLM with PII stripped (Priority: P1)

A contract analyst runs a review on a batch of standard NDAs. They set `privacy.tier: balanced`. The embedding and retrieval stages run locally (faster, no network latency for vector operations). When the extraction agent calls a cloud LLM for reasoning, the PII engine strips all detected personal data from the contract text before the text is sent to the cloud provider. The cloud LLM receives only anonymized text with placeholders.

The user sees:

```
Privacy tier: BALANCED — local embeddings, cloud LLM (PII stripped)
[1/5] Parsing…  OK
[2/5] Stripping PII…  24 entities replaced with placeholders
[3/5] Generating assessment…
  ◼ Using model "gpt-4o" (cloud) — PII stripped before call
```

The final report includes: "Processed under Balanced privacy tier. Embeddings processed locally. Cloud LLM received PII-stripped text (24 entities redacted)."

**Why this priority**: Balanced is the default tier for most use cases. It optimizes for the common case where embeddings benefit from local speed and cloud LLMs provide higher reasoning quality, without exposing raw personal data.

**Independent Test**: A test that sets `privacy.tier: balanced`, configures cloud LLM + local embeddings, runs a review on a document with seeded PII, and asserts that (a) embedding calls route to local provider, (b) the cloud LLM call receives PII-stripped text (verified via a mock that captures the prompt), and (c) the cloud LLM call does NOT contain raw PII values.

**Acceptance Scenarios**:

1. **Given** `privacy.tier: balanced`, **When** an embedding call is made, **Then** the router selects a local embedding provider or runs embeddings locally.
2. **Given** `privacy.tier: balanced`, **When** an LLM generation call is made to a cloud provider, **Then** PII is stripped from the input text before the call is dispatched.
3. **Given** `privacy.tier: balanced` and no local embedding provider is available, **When** an embedding call is needed, **Then** the router produces an actionable error suggesting installation of a local embedding model.

---

### Scenario 3 — Performance tier: full cloud inference with PII stripped (Priority: P1)

A team processes a large batch of standard contracts under a tight deadline. They set `privacy.tier: performance`. All model calls — embeddings, LLM reasoning, classification — route to cloud providers for maximum throughput. Before any contract text leaves the machine, the PII engine strips detected personal data. The cloud receives only anonymized text.

The user sees:

```
Privacy tier: PERFORMANCE — cloud inference (PII stripped before egress)
[1/5] Parsing…  OK
[2/5] Stripping PII…  24 entities replaced with placeholders
[3/5] Generating assessment…
  ◼ Using model "gpt-4o" (cloud) — PII stripped before call
[4/5] Embedding…
  ◼ Using model "text-embedding-3-small" (cloud) — PII stripped before call
```

The final report includes: "Processed under Performance privacy tier. All inference used cloud providers. PII was stripped before all external calls (24 entities redacted)."

**Why this priority**: Performance tier is the speed option for non-sensitive documents. It must include the PII-stripping guarantee so users never have to choose between speed and privacy.

**Independent Test**: A test that sets `privacy.tier: performance`, configures cloud providers for both embeddings and LLM, runs a review on a document with seeded PII, and asserts that (a) every model call routes to a cloud provider, (b) every call receives PII-stripped input, and (c) no PII values appear in the captured prompts.

**Acceptance Scenarios**:

1. **Given** `privacy.tier: performance`, **When** any model call is made, **Then** the router selects cloud providers for all model types (embeddings, LLM, classification).
2. **Given** `privacy.tier: performance`, **When** a model call is dispatched, **Then** PII is always stripped from input text before the call.
3. **Given** `privacy.tier: performance` and no cloud provider is configured, **When** a model call is needed, **Then** the router produces an error suggesting configuration of a cloud provider or switching to a different tier.

---

### Scenario 4 — PII stripping engine fails, cloud calls blocked (Priority: P2)

A user runs a review on a document under Balanced tier. The PII stripping engine encounters an error (model file missing, out of memory, corrupted cache). The router detects the PII engine failure, blocks the pending cloud LLM call, and produces an error. No raw (unstripped) text reaches the cloud.

The user sees:

```
Privacy tier: BALANCED
[2/5] Stripping PII…  FAILED — PII engine unavailable
Error: PII stripping failed before a cloud call. Cloud inference blocked to prevent data exposure.
Actions:
  A. Switch to Maximum tier to continue with local inference only: openreview config set privacy.tier maximum
  B. Fix the PII engine issue: verify spaCy model is installed
  C. Use --no-pii only if you have confirmed the document contains no personal data
```

**Why this priority**: This is the safety guarantee. A PII engine failure must never default to "send the raw text anyway." The router must fail closed, not open.

**Independent Test**: A test that causes the PII engine to fail (unavailable model, corrupt mapping), then attempts a cloud provider call on Balanced tier, and asserts that the call is blocked with an error message that does not contain any document text and includes at least two actionable suggestions.

**Acceptance Scenarios**:

1. **Given** the PII stripping engine is unavailable, **When** a cloud provider call is attempted on Balanced or Performance tier, **Then** the router blocks the call and produces an error — no raw text is sent.
2. **Given** the PII stripping engine is unavailable and the current tier is Maximum, **When** a local provider call is attempted, **Then** the call proceeds normally (local inference does not require PII stripping).
3. **Given** a PII stripping failure blocks a cloud call, **When** the user switches to Maximum tier, **Then** the review can proceed with local inference (PII stripping is not a precondition for local calls).

---

### Scenario 5 — Tier change takes effect on next operation only (Priority: P3)

A user has been working under Performance tier. They realize the current document contains sensitive personal data and want to switch to Maximum tier. They update `config.yml` `privacy.tier: maximum` while a review is running. The current operation continues under the old tier. The next operation (new review, re-run, or different subcommand) picks up the new setting.

The user sees on the next run:

```
Privacy tier: MAXIMUM (changed from PERFORMANCE since last operation)
```

**Why this priority**: Runtime tier switching within a single operation adds complexity with little benefit — the user can restart the operation. Keeping per-operation stability avoids race conditions and simplifies the implementation.

**Independent Test**: A test that changes the config file while a review is in progress (within a test-scoped temp config), then asserts the current operation completes under the original tier and a subsequent operation uses the new tier.

**Acceptance Scenarios**:

1. **Given** the user changes `privacy.tier` in config.yml, **When** a review is already running, **Then** the running review continues with the tier that was active when it started.
2. **Given** the user changes `privacy.tier` in config.yml, **When** the next CLI command is invoked, **Then** the new tier is active for that command.
3. **Given** the tier has changed since the last operation, **When** the next operation starts, **Then** the output includes a notice about the tier change.

---

### Edge Cases

- **No local provider on Maximum tier** — If the user sets Maximum tier but has not installed or configured Ollama, every model call fails with a clear error directing them to install Ollama or change the tier. The router does not silently fall back to a cloud provider.
- **No PII engine on Balanced/Performance tier** — Same as Scenario 4: the router blocks cloud calls and suggests either fixing the PII engine or switching to Maximum tier.
- **PII stripping is partial** — If the PII engine completes but warns that some entities may have been missed (confidence below threshold), the router records the warning in the call metadata but allows the cloud call to proceed. The user sees a notice: "PII stripping completed with low confidence on 3 entities — review results for potential personal data."
- **Tier config key is missing** — If `privacy.tier` is not present in `config.yml`, the router defaults to Maximum (safest default). A warning is shown on the first operation: "privacy.tier not configured. Defaulting to Maximum."
- **Invalid tier value** — If `privacy.tier` is set to an unrecognized value, the router treats it as a configuration error and defaults to Maximum with a warning explaining valid values.
- **Provider type ambiguity** — The router must determine whether each configured provider is local or cloud. Providers running on localhost (127.0.0.1, localhost, Unix socket) are classified as local. All others are classified as cloud. This classification is documented in config specification.

---

## 3. Dependencies & Related Specifications

The privacy tier router builds on and integrates with the following existing capabilities (all described in natural language, per the product blueprint's architecture):

| Dependency | Description | Relationship |
|---|---|---|
| AI Gateway (spec-005) | Routes model calls to configured providers, tracks cost, manages provider registry and slots | Tier router wraps every Gateway call; it intercepts before the Gateway resolves the provider and enforces tier rules |
| PII Stripping Engine (spec-003/004) | Detects and replaces personal data with placeholders, maintains encrypted mapping, audit trail | Tier router calls PII stripping before cloud egress on Balanced and Performance tiers; depends on engine availability and completion |
| Configuration Loader (foundation) | Loads config.yml from standard paths, supports get/set commands | Tier router reads `privacy.tier` from the config at startup; does not write config |
| Model Registry (spec-005) | Maintains list of known providers and models, classifies capabilities | Tier router uses registry to determine whether each provider is local or cloud-based |
| Single-Party Review (spec-011) | 3-agent extraction→QA→report pipeline | Tier router operates transparently below the review pipeline — the pipeline calls the Gateway as usual, the router enforces tier rules |

The privacy tier router does not re-implement any of these. It is a thin enforcement layer between the calling code and the Gateway.

---

## 4. Functional Requirements

Each requirement below cites its source using plain-English descriptions. Blueprint-internal codes are not used in this document.

### FR-01 — Three Privacy Tiers with Defined Behavior

The system **must** support exactly three privacy tiers: Maximum, Balanced, and Performance. Each tier **must** have the following well-defined behavior (reference: the product blueprint's privacy tier routing capability defines three tiers with specific data-flow characteristics — Maximum local-only, Balanced local-embeddings-plus-cloud-LLM, Performance full-cloud):

| Tier | Embeddings | LLM Reason | PII Required Before Cloud | Default? |
|---|---|---|---|---|
| Maximum | Local only | Local only | No (no cloud calls) | Yes |
| Balanced | Local only | Cloud allowed | Yes | No |
| Performance | Cloud allowed | Cloud allowed | Yes | No |

### FR-02 — Tier Enforcement at Gateway Call Boundary

Every Gateway model call **must** pass through the tier router before provider selection. The router **must** compare the resolved provider's location (local or cloud) against the current tier's rules. If the call would violate tier rules, the router **must** block the call with an error message that identifies the violation and the current tier. (Reference: the product blueprint requires that the privacy tier router enforce rules before any provider call is dispatched, preventing data from leaving the machine against the user's privacy preference.)

### FR-03 — PII Stripping Verification Before Cloud Egress

On Balanced and Performance tiers, before any model call routes to a cloud provider, the system **must** verify that PII has been stripped from the input text. The router **verifies** stripping completion (it does not perform stripping itself — the upstream review pipeline performs PII stripping before the router is invoked). The router checks a per-operation cache or flag indicating stripping was done. If the cache indicates PII has not been stripped, or if `PiiEngine.is_available()` returns `False`, the call **must** be blocked. The router must never trigger PII stripping on its own; it only gates the call based on evidence that stripping already completed. If PII stripping is unavailable or the evidence is missing, the call **must** be blocked with a clear error. (Reference: the product blueprint requires PII stripping before external API calls as a core privacy principle, and the privacy tier routing capability inherits this requirement.)

### FR-04 — Block Cloud Calls When PII Unavailable

When the PII stripping engine is unavailable (model file missing, engine error, or disabled by `--no-pii` flag) and the current tier requires PII before cloud calls (Balanced or Performance), the router **must** block the cloud call and produce an actionable error. The router **must not** silently fall back to sending unstripped text to the cloud. (Reference: the product blueprint's privacy principle requires that the system fail closed — no data leaves the machine without PII stripping — and the resolved open questions confirm that silent cloud fallback is forbidden.)

### FR-05 — Tier Configuration in config.yml

The system **must** read the privacy tier from `config.yml` at the `privacy.tier` key. Valid values are `maximum`, `balanced`, and `performance`. If the key is absent, the system **must** default to `maximum`. If the key has an unrecognized value, the system **must** default to `maximum` with a configuration warning. The tier **must** be readable via `openreview config get privacy.tier`. (Reference: the product blueprint states the user configures privacy tier per environment, and the configuration system already supports YAML-based settings.)

### FR-06 — Tier-Aware Provider Selection

The router **must** be able to determine whether each configured provider is local (runs on localhost or Unix socket, typically Ollama) or cloud (connects to a remote API, such as OpenAI or Anthropic). This classification **must** drive provider filtering on Maximum tier (only local providers allowed) and may be based on the provider's base URL or a provider-type attribute in the registry. (Reference: the product blueprint's Maximum tier requires that no data leaves the machine, which requires knowing which providers are local.)

### FR-07 — No Silent Tier Downgrade

The system **must never** change the privacy tier automatically. If the current tier prevents a call from completing (e.g., Maximum tier with no local provider configured), the system **must** produce an error with suggested actions — it **must not** downgrade to Balanced or Performance to make the call succeed. (Reference: the product blueprint's resolved open questions establish that user control over data flow is absolute — the system must never silently route data in a way the user did not authorize.)

### FR-08 — Tier Visibility in Output

Every operation that makes model calls **must** display the current privacy tier near the top of the progress output. The final report **must** include the privacy tier used and a summary of what it meant (e.g., "All inference local" for Maximum, "Cloud LLM received PII-stripped text" for Balanced). (Reference: the product blueprint's user-experience requirement for transparency — the user must always know what privacy protections are active.)

### FR-09 — Tier Stability Within a Single Operation

The privacy tier **must** be captured at the start of each CLI operation (when `config.yml` is loaded) and remain fixed for the duration of that operation. Changes to `config.yml` `privacy.tier` made while an operation is running **must not** affect the running operation. (Reference: the product blueprint's risk assessment identifies that runtime tier switching could cause partial-operation data flow inconsistencies; per-operation stability avoids this.)

---

## 5. Non-Goals / Out of Scope

The following are explicitly out of scope for this specification:

- **Automatic tier recommendation** — The system does not analyze the document and suggest a tier. The user chooses the tier explicitly.
- **Per-clause or per-page tier selection** — The tier applies to the entire operation. Finer-grained tier selection is a future enhancement.
- **Runtime tier switching** — The tier cannot change mid-operation (FR-09). The user must wait for the next operation or cancel the current one.
- **Per-provider PII stripping exemptions** — All cloud providers receive PII-stripped text on Balanced and Performance tiers. No provider can be exempted.
- **Tier inheritance from parent configs** — The tier is read from the active config.yml only. No cascading or profile-based tier resolution.
- **Data classification or sensitivity detection** — The system does not attempt to classify document sensitivity. Tier choice is the user's responsibility.
- **Bypass mode for the privacy tier router** — There is no CLI flag to disable tier enforcement. The user changes the tier in config to change behavior.
- **Tier-specific performance benchmarks** — Success criteria define correctness, not speed. Performance characteristics of each tier are measured separately by the benchmark harness (spec-010).
- **Accuracy benchmarking per tier** — The accuracy of model inference under each tier is not defined or measured in this specification. The trust threshold required before lawyers adopt a tier is a product question deferred to user research. (Resolved from CL-04.)
- **Per-operation tier change notification** — The "changed from X since last operation" message (Scenario 5, P3) is dropped from the MVP. The system always displays the current tier at the start of every operation. Detecting and displaying a diff between consecutive operations is deferred until explicitly requested. (Resolved from CL-05.)

---

## 6. Success Criteria

Each criterion is measurable, technology-agnostic, and verifiable without implementation knowledge. References are in natural language.

### SC-01 — Maximum Tier Has Zero External Network Calls

When `privacy.tier: maximum`, the system must not make any HTTP requests to non-localhost addresses during processing. Every model call must resolve to a local provider.

*Verification*: A test sets Maximum tier, configures both a local and a cloud provider, runs the review pipeline on a test document, and asserts that every intercepted HTTP request targets `localhost` or `127.0.0.1`. Any request to an external IP or hostname is a failure.

### SC-02 — Balanced Tier Routes Correctly by Model Type

When `privacy.tier: balanced`, embedding and retrieval model calls must route to local providers. LLM generation calls must be allowed to route to cloud providers, but only after PII stripping has been verified.

*Verification*: A test runs a review on a document with seeded PII and captures the provider used for each model call. Embedding calls must resolve to a local provider. LLM calls must resolve to a cloud provider (if configured). The LLM call input must not contain raw PII values (verified via mock capture).

### SC-03 — PII Stripping Failure Blocks Cloud Calls

When the PII stripping engine is unavailable or fails, and the current tier requires PII before cloud egress (Balanced or Performance), the system must block the cloud provider call and produce an actionable error. No unstripped text may reach a cloud provider.

*Verification*: A test disables or breaks the PII engine, then attempts a cloud model call under Balanced tier. The test asserts that (a) no HTTP request is made to the cloud provider's URL, (b) the error message includes the phrase "PII" and at least two actionable suggestions, and (c) no document text appears in the error message.

### SC-04 — Tier Selection Affects Provider Routing

Changing `privacy.tier` in config.yml must produce corresponding changes in which providers are selected for model calls. Maximum tier must select only local providers. Performance tier must select only cloud providers (if available). Balanced must select local for embeddings and cloud (or local fallback) for LLM.

*Verification*: A test iterates over all three tier values, runs a review that exercises both embedding and LLM calls, and asserts that the set of providers used matches the tier's rules for each iteration.

### SC-05 — Current Tier Visible in Output

Every CLI operation that involves model calls must display the current privacy tier and a brief description of what it means in the progress output. The final report must include a privacy tier summary.

*Verification*: A test captures the progress output and final report for an operation on each tier. Each captured output must contain the tier name and a meaningful description (e.g., "local only", "PII stripped before cloud calls").

### SC-06 — Tier Change Takes Effect on Next Operation

A change to `privacy.tier` in config.yml must not affect a running operation. The new tier must take effect on the next CLI invocation.

*Verification*: A test starts a long-running operation (or a mock that simulates one), changes the tier in the config file mid-operation, and asserts that the in-progress operation completes under the original tier. A subsequent operation uses the new tier.

### SC-07 — Missing or Invalid Tier Defaults to Maximum

If `privacy.tier` is absent from config.yml, or if it is set to an unrecognized value, the system must default to Maximum tier. A warning must be shown on the first operation using the default.

*Verification*: A test removes or corrupts the `privacy.tier` key, runs any model-call operation, and asserts that the router operates as Maximum tier (local-only providers selected) and that a warning message about the missing or invalid config appears.

---

## 7. Assumptions

- The AI Gateway (spec-005) exposes a hook or wrapping point that the tier router can intercept before provider resolution. If the Gateway does not provide this, the router wraps the Gateway's call method.
- The PII Stripping Engine (spec-003/004) exposes a synchronous check — "is the engine available and ready?" — that the router can call before deciding whether to allow a cloud call. If no such check exists, the router attempts a lightweight detection run on a known-safe input and uses the result as a readiness signal.
- Local providers can be identified by their base URL matching localhost patterns (`127.0.0.1`, `localhost`, `[::1]`, Unix socket paths). The Model Registry may already store this information; if not, the router classifies based on URL inspection.
- Embedding model calls and LLM generation calls are distinguishable in the Gateway's call interface (via model name, model type, or call parameter). If they are not, the router treats all model calls the same (all local on Maximum, all cloud on Performance, mixed on Balanced with LLM preferred for cloud).
- The user's `config.yml` is loaded before any model calls are made, and the tier value is available at that point. The configuration loader (foundation) already reloads config on every CLI invocation.
- PII stripping is idempotent for the same document and configuration. If the pipeline strips PII once, the stripped text can be cached per operation and reused for multiple cloud calls without re-stripping. This is a performance optimization, not a correctness requirement.
- Users of the Maximum tier have Ollama (or another local inference engine) installed and configured. The router does not install or start local services — it only enforces routing rules.
- **Model type detection** — The Gateway exposes separate methods for different model types (e.g., `chat()` for LLM calls, `embed()` for embedding calls). The tier router wraps each method individually to determine call type. If the Gateway does not expose typed methods, the router accepts a `model_type` parameter on its own `call()` interface. (Resolved from CL-03.)
- **Gateway routing overhead on Maximum tier** — The tier router always delegates to the Gateway's provider resolution and dispatch, even on Maximum tier (where only local providers are eligible). Direct bypass is not implemented unless measured overhead justifies it. (Resolved from CL-02.)
- **8GB hardware and local model availability** — The tier router does not detect or account for hardware constraints (RAM, GPU). If Ollama is installed but a requested model is too large for the machine, Ollama returns an OOM error which the Gateway propagates as a normal provider error. The router does not pre-emptively disable Maximum tier on low-RAM hardware. (Resolved from CL-01.)

---

## 8. Key Entities

### PrivacyTier

An enumeration with three values: `maximum`, `balanced`, `performance`. Each value has associated rules: which provider types (local, cloud) are allowed for which model types (embedding, LLM, classification), and whether PII stripping is required before dispatch.

### TierRouter

The central enforcement point. Wraps the AI Gateway's provider resolution and call dispatch. Before each call:
1. Reads the current tier (captured at operation start).
2. Determines the model type (embedding, LLM, classification) from the call parameters.
3. Inspects the configured providers and filters them by tier rules.
4. If the filtered provider list is empty, produces an error with actionable suggestions.
5. If the call will go to a cloud provider, verifies PII stripping completed for the input text.
6. If PII stripping is unavailable or failed, blocks the call with a privacy-protection error.
7. Passes the filtered provider list to the Gateway for normal provider selection and dispatch.

### TierConfig

A configuration object loaded from `config.yml` at startup. Contains:
- `tier`: the privacy tier value (defaults to `maximum` if absent or invalid).
- A list of valid tier values for validation.
- A factory method `from_config(config)` that reads `privacy.tier` and returns a TierConfig with the appropriate defaults.

### ProviderLocationClassifier

Determines whether a configured provider is local or cloud-based. Uses the provider's base URL: matches against `localhost`, `127.0.0.1`, `[::1]`, and Unix socket patterns. If the registry already stores a `local` flag, that takes precedence.

### PrivacyTierReport

A structure attached to the operation's result containing:
- The tier used for the operation.
- The number of cloud calls made (if any).
- The number of PII entities stripped before cloud calls (if applicable).
- Any tier-related warnings or errors.

---

## 9. Quality Checklist

See `checklists/requirements.md` for the spec quality validation checklist.

---

## 10. Clarifications

This section records the outcome of the clarification phase for this specification (Stage 2: `speckit.clarify`). Each entry identifies an ambiguity found during the scan, the options considered, and the resolution applied to the spec.

### CL-01: 8GB Hardware and Maximum Tier Degradation

**Ambiguity**: The specification assumes Ollama is available for Maximum tier but does not address what happens on 8 GB RAM machines where local SLMs cannot run.

**Options**:
1. Add hardware detection — Router pre-checks available RAM and blocks Maximum tier on 8 GB machines with an explanatory error.
2. Let Ollama handle resource exhaustion naturally — If a model is too large for the available RAM, Ollama returns an OOM error; the Gateway propagates it as a provider error.

**Resolution**: Option 2. The router follows YAGNI and does not add hardware detection. Ollama's own error handling covers this case. If no suitable model is configured, the existing "Maximum tier requires a local provider" error triggers. Updated §7 Assumptions.

### CL-02: Gateway Bypass for Maximum Tier

**Ambiguity**: Whether Maximum-tier calls should route through the AI Gateway (cost tracking, registry lookup, provider resolution) or call Ollama directly to avoid overhead.

**Options**:
1. Always route through Gateway — Single code path, consistent behavior, simpler testing.
2. Bypass Gateway for Maximum tier — Slightly less overhead, introduces a second code path.

**Resolution**: Option 1. The Gateway overhead is negligible for a CLI tool. A bypass path adds complexity and testing surface with no measurable benefit. Updated §7 Assumptions.

### CL-03: Model Type Detection Mechanism

**Ambiguity**: The router needs to distinguish embedding calls from LLM generation calls for Balanced-tier routing. The mechanism for this distinction is not specified.

**Options**:
1. Wrap individual Gateway methods (`chat()`, `embed()`) — Call type is known from the wrapper that was invoked.
2. Single `call()` with `model_type` parameter — Requires changing the Gateway interface.
3. Infer from provider registry metadata — Fragile, indirect, hard to test.

**Resolution**: Option 1. The router wraps individual Gateway methods, giving it direct knowledge of call type without changing Gateway internals. Updated §7 Assumptions.

### CL-04: Accuracy Threshold

**Ambiguity**: The product blueprint notes that the accuracy threshold lawyers need before trusting a tier has not been quantified.

**Options**:
1. Define placeholder accuracy metrics in this specification.
2. Defer entirely to user research and a future product specification.

**Resolution**: Option 2. Accuracy quantification is a product question, not an implementation concern. This specification defers it. Updated §5 Non-Goals.

### CL-05: Tier Change Notification Mechanism

**Ambiguity**: The spec requires a "changed from X since last operation" notification (Scenario 5, P3) but does not specify the detection mechanism.

**Options**:
1. State file — Persist last-used tier to disk for comparison on next operation.
2. Simple display without diff — Always show the current tier name and description. Drop the change-diff from MVP.
3. Config-file timestamp comparison — Compare config mtime against operation start.

**Resolution**: Option 2 for MVP. The "changed since last operation" notice is P3 and adds file I/O complexity disproportionate to its value. The system always displays the current tier prominently. The change-diff notification is deferred until explicitly requested. Updated §5 Non-Goals.
