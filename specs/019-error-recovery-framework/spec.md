# Error Recovery Framework

**Feature ID**: 019-error-recovery-framework
**Status**: Draft Specification
**Created**: 2026-07-05

---

## 1. Executive Summary

The multi-stage review pipeline (parse → strip → chunk → retrieve → generate) and the AI Gateway that powers it run on consumer hardware with constrained resources — 8 GB RAM, slow or absent GPUs, intermittent connectivity, and no guaranteed provider availability. Today, when any stage or provider call fails, the entire operation terminates with a generic error message. The user has no visibility into what failed, whether the system tried alternatives, or what to do next.

This specification defines an **error recovery framework** that wraps pipeline execution and provider calls with five automated recovery strategies: re-attempt transient operations with backoff, fall back to alternate AI providers when the primary is unavailable, reduce output scope under memory pressure, isolate stage failures so one broken stage does not kill unrelated work, and present a clear user-facing decision when automation cannot recover. The framework targets automatic resolution of at least 90% of pipeline failures without user intervention, while guaranteeing that the remaining 10% produce an actionable message — never a silent fallback or a generic crash.

The framework sits on top of the existing pipeline runner (spec-018) and the AI Gateway (spec-005). It does not re-implement either. Instead, it adds a recovery layer that intercepts failures at the pipeline stage boundary and at the gateway provider-call boundary, applies the appropriate strategy, and reports outcomes to the user through the same progress-reporting mechanism the pipeline already uses.

**What this delivers:**

- Five concrete recovery strategies, each with a clear trigger and lifecycle
- A recovery coordinator that selects and applies strategies when failures occur
- Integration with the pipeline runner so stage failures are intercepted, not propagated as crashes
- Integration with the AI Gateway so provider-call failures trigger fallback or degradation
- User-visible recovery status in the pipeline progress output: the user sees retry attempts, fallback switches, and degradation decisions in real time
- A guarantee that no pipeline failure results in a silent fallback — if the framework cannot recover, it tells the user exactly what went wrong and what configuration change would fix it

---

## 2. User Scenarios

### Scenario 1 — An AI provider is temporarily unreachable, and the system retries transparently (Priority: P1)

A user runs `openreview precheck review nda.pdf`. The extraction agent calls the AI Gateway, which routes to the user's primary provider (OpenAI). The provider returns a 503 (service temporarily unavailable). The recovery framework automatically retries the call twice with exponential backoff (1 s, then 4 s wall-clock delay). On the third attempt, the provider responds successfully. The user sees:

```
[3/5] Generating assessment...
  ◼ Retrying provider call (attempt 2/5)…
  ◼ Retrying provider call (attempt 3/5)…
```

The review completes normally. The user is never prompted to intervene.

**Why this priority**: Transient provider failures are the most common pipeline failure mode. Auto-retry eliminates the most frequent user-facing crash with zero user effort.

**Independent Test**: A test that injects two consecutive HTTP 503 responses before a success, then asserts the pipeline completes with the retry count reported in progress output.

**Acceptance Scenarios**:

1. **Given** the primary AI provider returns a transient error (503, 429, timeout), **When** the Gateway makes a call, **Then** the framework retries up to 4 times with exponential backoff (1 s, 4 s, 9 s, 16 s) before surfacing a permanent failure.
2. **Given** the provider recovers within the retry window, **When** a retry succeeds, **Then** the pipeline continues normally with no user intervention.
3. **Given** all retries are exhausted, **When** the final attempt also fails, **Then** the framework escalates to the provider-fallback strategy.

---

### Scenario 2 — The primary provider is permanently down, and the system falls back to an alternate provider (Priority: P1)

A user has configured two AI providers: OpenAI (primary) and Ollama (local fallback). OpenAI is experiencing an outage (all calls return 500). After exhausting retries, the recovery framework selects Ollama as the fallback provider and re-routes the generation call. The user sees:

```
[3/5] Generating assessment...
  ◼ Retrying provider call (attempt 5/5)… failed.
  ◼ Falling back to "ollama/llama3.1"…
```

The review completes using the local model, which may produce slightly different results but still functional output. No data leaves the machine.

**Why this priority**: Provider outages happen. Without fallback, every outage becomes a blocked user. With fallback, the user stays productive.

**Independent Test**: A test that configures two providers, permanently fails the primary, and asserts the call routes to the fallback with a fallback notification in the output.

**Acceptance Scenarios**:

1. **Given** the primary AI provider is permanently unavailable, **When** auto-retry is exhausted, **Then** the framework routes the call to the next configured provider in the user's provider list.
2. **Given** no alternate provider is configured, **When** the primary fails after retries, **Then** the framework produces a user-facing error explaining that no fallback exists and suggesting the user configure one.
3. **Given** the fallback provider also fails, **When** all providers are exhausted, **Then** the framework escalates to the user-guided-recovery strategy (clear error with configuration guidance).

---

### Scenario 3 — A pipeline stage runs out of memory, and the system degrades gracefully (Priority: P2)

A user reviews a 500-page contract on an 8 GB machine. The chunking stage allocates memory for the full clause tree and approaches the 100 MB processing budget. The recovery framework detects the memory pressure (via a before-stage allocation check) and invokes graceful degradation: the chunking stage uses smaller batch sizes, and the generation stage uses a lower-cost model. The user sees:

```
[3/5] Chunking…
  ◼ Memory pressure detected — reducing chunk batch size.
[4/5] Retrieving…
  OK
[5/5] Generating assessment…
  ◼ Memory pressure detected — switching to lightweight model.
```

The review completes with a warning banner: "Completed with memory degradation. Results may have reduced coverage on 2 of 48 clauses."

**Why this priority**: The memory budget is a hard constitutional constraint. Without graceful degradation, a memory spike kills the entire pipeline. Degradation preserves partial results.

**Independent Test**: A test that sets an artificially low memory threshold, runs a pipeline that would exceed it, and asserts that degradation triggers and the pipeline completes with a degradation warning.

**Acceptance Scenarios**:

1. **Given** a pipeline stage approaches the configured memory threshold, **When** the stage is about to allocate, **Then** the framework triggers graceful degradation (reduced batch size, lower-cost model, or simplified processing).
2. **Given** degradation is active, **When** the stage completes within budget, **Then** the pipeline continues to the next stage and a degradation notice is included in the final output.
3. **Given** degradation is insufficient to keep memory within budget, **When** the stage still exceeds the limit, **Then** the framework stops the pipeline and reports a memory-related error with the stage name and memory consumed.

---

### Scenario 4 — One pipeline stage fails but the rest of the pipeline can still produce partial results (Priority: P2)

A user runs a review on a mixed-format document (PDF with scanned pages). The OCR stage fails on three pages, but the remaining pages parse correctly. The recovery framework marks the OCR stage as partially failed, excludes the three unparseable pages from the pipeline, and continues with the rest. The user sees:

```
[2/5] Parsing…
  ◼ 3 pages could not be OCR-processed — excluded from analysis.
[3/5] Generating assessment…
  OK
```

The final report includes a note: "3 of 50 pages skipped due to OCR failure. Results based on 47 pages."

**Why this priority**: Stage isolation lets the pipeline produce partial results instead of nothing. This is especially important for the multi-party comparison use case where one party's document is problematic but the other is fine.

**Independent Test**: A test that injects a failure into one pipeline stage and asserts that subsequent stages continue with available data, producing a partial-output report.

**Acceptance Scenarios**:

1. **Given** a non-critical pipeline stage fails, **When** the framework detects the failure, **Then** the failing stage's error is captured and reported, and the pipeline continues with the data available from previous stages.
2. **Given** a critical pipeline stage fails (e.g., parsing, which all later stages depend on), **When** the framework detects the failure, **Then** the pipeline stops and reports a clear error identifying the failed stage and the reason.
3. **Given** a stage fails partially (some data processed, some not), **When** the framework detects partial failure, **Then** the pipeline continues with partial data and reports the gap in the final output.

---

### Scenario 5 — Auto-recovery is impossible, and the user receives a clear, actionable error (Priority: P3)

A user has configured only a local model slot (Ollama) and is offline. The Gateway cannot reach Ollama because the Ollama service is not running. The recovery framework exhausts auto-retry and falls back to the user-guided-recovery strategy, producing:

```
Error: The AI provider "ollama/llama3.1" is unreachable, and no fallback provider is configured.
Possible actions:
  A. Start Ollama: openreview gateway start ollama
  B. Configure a cloud provider: openreview gateway setup
  C. Exit and try later.
```

**Why this priority**: The resolved open questions on the product blueprint establish that silent cloud fallback is forbidden. The user must always be in control of where their data goes.

**Independent Test**: A test that configures a single unreachable provider and asserts the error message matches the expected pattern (actionable options, no silent fallback).

**Acceptance Scenarios**:

1. **Given** all recovery strategies are exhausted, **When** no provider can be reached, **Then** the framework produces a user-facing error with specific suggested actions.
2. **Given** only a local provider is configured and it is unreachable, **When** auto-recovery is exhausted, **Then** the framework does NOT silently fall back to a cloud provider — it reports the error with local-repair options.
3. **Given** only cloud providers are configured and all are unreachable, **When** auto-recovery is exhausted, **Then** the framework reports the error with connectivity-check options.

---

### Edge Cases

- **What happens when recovery itself fails?** — If auto-retry triggers an exception in its own mechanism (e.g., timer bug, state corruption), the framework treats this as an unrecoverable error and surfaces the original failure to the user with a note that recovery also failed.
- **How does the system handle concurrent failures across stages?** — Failures are handled at stage boundaries in sequence. If Stage 1 requires recovery and delays Stage 2, Stage 2's timeout is adjusted accordingly via a configurable grace period.
- **What if the user has no providers configured at all?** — The framework produces a clear error the first time a Gateway call is attempted, directing the user to the setup wizard.
- **How are recovery decisions logged without exposing PII?** — Recovery events are logged with error codes and strategy names only. No contract text, PII, or provider-specific prompts appear in logs.
- **What if the fallback provider costs more?** — The framework uses the exact cost tracking already in the AI Gateway. A fallback notification includes the estimated cost difference so the user is informed.

---

## 3. Dependencies & Related Specifications

The recovery framework builds on and integrates with the following existing capabilities (all described in natural language, per the product blueprint's architecture):

| Dependency | Description | Relationship |
|---|---|---|
| AI Gateway (spec-005) | Routes model calls to configured providers, tracks cost, handles LiteLLM integration | Recovery wraps every provider call; fallback and retry operate at the Gateway routing level |
| 5-Stage Async Pipeline (spec-018) | Stage-based pipeline runner with shared context, progress reporting, and completion callbacks | Recovery intercepts failures at stage boundaries and at the stage-to-Gateway call boundary |
| Single-Party Review (spec-011) | 3-agent extraction→QA→report pipeline that runs on the pipeline runner | Recovery runs inside the review pipeline, catching failures during extraction, QA, and report generation |
| Memory Budget Constraint (constitutional principle) | Peak processing memory under 100 MB on 8 GB target machines | Graceful-degradation strategy monitors memory pressure and adjusts processing before hitting the limit |

The recovery framework does not re-implement any of these. It is a thin cross-cutting layer that plugs into existing hook points.

---

## 4. Functional Requirements

Each requirement below cites its source in the product blueprint using natural-language descriptions. Blueprint-internal codes are not used in this document.

### FR-01 — Auto-Retry with Backoff

The system **must** automatically retry failed AI Gateway provider calls when the failure is classified as transient (network timeout, HTTP 429/503, connection reset). Retries **must** follow exponential backoff with configurable base interval and maximum attempts. (Reference: the product blueprint defines auto-retry with backoff as one of five recovery strategies for the error recovery capability, driven by the risk that provider calls may fail due to transient network conditions or service unavailability.)

### FR-02 — Provider Fallback

When auto-retry on the primary provider is exhausted, the system **must** attempt the next configured provider in the user's provider list. If all configured providers are exhausted, the system **must** escalate to user-guided recovery (FR-05). (Reference: the product blueprint identifies graceful degradation when the AI Gateway or LiteLLM provider fails as a requirement, and the resolved open question on the Gateway's role establishes that silent cloud fallback is forbidden.)

### FR-03 — Graceful Degradation Under Resource Pressure

When the system detects that a pipeline stage is approaching the configured memory budget, the system **must** apply degradation measures — reducing batch sizes, switching to a lighter model, or simplifying processing — to keep the stage within budget. If degradation is insufficient, the system **must** stop the stage and report the memory constraint rather than crash. (Reference: the product blueprint's architecture section describes memory budget constraints on the 8 GB target machine and requires sequential model loading and eager unload mitigation; the risk assessment identifies out-of-memory as a concrete threat.)

### FR-04 — Stage Error Isolation

When a non-critical pipeline stage fails, the system **must** capture the error, record which stages completed and which failed, and continue pipeline execution with the data available from successful stages. A critical stage failure (parsing, which all later stages depend on) **must** stop the pipeline and report the error. (Reference: the product blueprint's multi-party gap requires the system to surface comparison uncertainty rather than crash, which implies per-stage failure isolation; the 5-stage pipeline architecture establishes stage boundaries as natural recovery points.)

### FR-05 — User-Guided Recovery

When all automated recovery strategies are exhausted, the system **must** produce a user-facing error message that includes:
- The specific failure and the stage or provider where it occurred
- The recovery strategies that were attempted and their outcomes
- Concrete, actionable suggestions for the user (start a local service, configure a provider, check connectivity)
- Never a silent fallback to a different provider unless the user explicitly configured it

(Reference: the product blueprint's resolved open questions establish that the system must detect missing local configuration and stop with a clear user-facing error, with no silent fallback to cloud providers.)

### FR-06 — Recovery Visibility

The system **must** report recovery actions through the same progress-reporting mechanism the pipeline already uses. The user **must** see:
- Retry attempts (attempt number and provider name)
- Fallback switches (which provider is now being used)
- Degradation decisions (what was degraded and why)
- Final recovery outcome (resolved, degraded, or unrecoverable)

(Reference: the product blueprint defines a target of at least 90% auto-recovery, which requires the user to observe and verify recovery outcomes.)

### FR-07 — User Data Preservation During Recovery

Recovery actions **must not** lose or corrupt user data that was successfully processed before the failure. Results from completed pipeline stages **must** be retained when a later stage fails, so that re-running the pipeline can skip already-completed stages. (Reference: the product blueprint's risk assessment identifies out-of-memory breach as a threat, and the architecture requires that the pipeline fire completion callbacks between stages so large objects can be released — establishing data preservation as a design invariant.)

### FR-08 — Configurable Recovery Thresholds

The user **must** be able to configure the following recovery parameters:
- Maximum retry attempts per provider call (default: 4)
- Base retry interval in seconds (default: 1)
- Whether to enable or disable specific recovery strategies (e.g., disable graceful degradation)
- Memory threshold that triggers degradation (percentage of budget, default: 80%)

(Reference: the product blueprint's error recovery capability describes five strategies with configurable behavior, and the resolved open question on hardware choice means recovery behavior must adapt to the user's machine.)

---

## 5. Non-Goals / Out of Scope

The following are explicitly out of scope for this specification:

- **Automatic cloud-provisioning of compute resources** — The framework does not spin up cloud instances, start services, or install software to resolve failures. It works with what the user has configured.
- **Retry of user-initiated document-parsing failures** — If the input document is corrupt, password-protected, or otherwise invalid, the framework reports the parsing error but does not retry; the user must provide a valid document.
- **Full-dual-path or multi-provider parallel execution** — The framework does not call multiple providers simultaneously and compare results. Fallback is sequential: one provider at a time, in user-specified order.
- **Persistent recovery state across CLI invocations** — Recovery state lives only for the duration of a single CLI command. If the user restarts the tool, recovery starts fresh. No recovery state is persisted to disk.
- **Recovery from logic errors or hallucinated outputs** — The framework handles operational failures (network, memory, provider errors), not semantic correctness failures (wrong answers). The QA agent in the review pipeline handles verification of output quality.
- **Automatic recovery reconfiguration** — The framework does not modify the user's provider list or config to fix an outage. It reports the issue and recommends configuration changes. The user makes the change manually or via the setup wizard.

---

## 6. Success Criteria

Each criterion is measurable, technology-agnostic, and verifiable without implementation knowledge. References to the product blueprint are in natural language.

### SC-01 — High Auto-Recovery Rate

At least 90% of all pipeline failures during standard operation must be resolved automatically without user intervention. (Reference: the product blueprint defines a target of at least 90% auto-recovery for the error recovery capability.)

*Verification*: Automated tests inject 100 representative failure scenarios (a mix of transient provider errors, memory-pressure triggers, and non-critical stage failures) and count how many complete without user-facing error prompts. Pass rate ≥ 90%.

### SC-02 — Transient Failure Tolerance

Transient network or provider failures (503, 429, timeout) must recover within 30 seconds of the initial failure without any user action. (Reference: the product blueprint identifies auto-retry for the AI Gateway/LiteLLM dependency as a recovery strategy, and the architecture requires result delivery within reasonable timeframes.)

*Verification*: A test injects a 10-second provider outage followed by a successful response. The pipeline must complete within 30 seconds of the initial failure and produce correct output.

### SC-03 — Memory Pressure Handling

When a pipeline stage would exceed the configured memory budget, the system must either complete the stage via degradation or produce a clear error message that identifies the stage, budget consumed, and suggested mitigation. User data from prior stages must be intact. (Reference: the product blueprint's architecture section specifies the memory budget for the 8 GB target machine and requires out-of-memory mitigation.)

*Verification*: A test sets an artificially low memory threshold (e.g., 10 MB) and runs a stage that would allocate 20 MB. The test asserts that either (a) the stage completes with degradation and a warning, or (b) the pipeline stops with a clear memory-related error and prior-stage data is accessible.

### SC-04 — No Silent Cloud Fallback

When only a local provider is configured and it is unreachable, the system must surface an actionable error message. It must not silently fall back to a cloud provider. (Reference: the product blueprint's resolved open questions establish that the system does not force cloud fallback and must stop with a clear user-facing error when no local option is configured.)

*Verification*: A test configures only a local provider (Ollama), makes it unreachable, and asserts that the error message (a) does not include any cloud-provider call, (b) includes specific action options (start Ollama, configure a cloud provider), and (c) does not use the word "retrying" after strategy exhaustion.

### SC-05 — Recovery Visibility

All recovery actions (retries, fallbacks, degradations) must be visible in the pipeline progress output. The user must be able to see what recovery strategy was applied, to which stage or provider, and what the outcome was. (Reference: the product blueprint's auto-recovery target of at least 90% necessarily implies that recovery outcomes are observable so the user can verify the system's automatic decisions.)

*Verification*: A test instruments the progress-output stream and asserts that every injected failure produces at least one recovery-related progress line (retry count, fallback notification, or degradation notice).

### SC-06 — Stage Failure Isolation

A non-critical stage failure must not crash the pipeline. The pipeline must produce output for whatever work completed successfully, and the failure must be documented in the final report. (Reference: the product blueprint's multi-party gap requires the system to surface comparison uncertainty rather than crash, which extends to all non-critical stage failures.)

*Verification*: A test injects a failure in a non-critical stage (e.g., generation fails on one clause) and asserts that the pipeline completes, the report includes results from completed work, and a failure notice appears in the report.

### SC-07 — Actionable Final Error Messages

When auto-recovery is exhausted, the final error message must include at least two specific, actionable suggestions. "Try again later" alone is insufficient. (Reference: the product blueprint's resolved open question on Gateway failure handling requires the system to stop with a clear user-facing error, not a generic crash.)

*Verification*: A test exhausts all recovery strategies and asserts the error message contains at least two of the following patterns: "Start", "Configure", "Check", "Install", or a direct CLI command that would resolve the issue.

---

## 7. Assumptions

- The pipeline runner (spec-018) provides a hook or callback mechanism at stage boundaries that the recovery framework can attach to. If no such mechanism exists, the framework defines its own wrapper that decorates stage execution.
- The AI Gateway (spec-005) exposes provider-call results with enough metadata to classify failures as transient vs. permanent (HTTP status code, error type, provider name). If it does not, the recovery framework adds a thin classification layer.
- The user's provider list is ordered by preference, and fallback follows that order. The system does not reorder providers.
- Memory pressure is monitored at stage boundaries, not continuously. This reduces overhead and matches the pipeline's stage-based execution model. Continuous monitoring is a future enhancement if stage-boundary checks miss intra-stage spikes.
- The target machine has at least Python 3.12 and the openreview package installed. Recovery strategies do not need to handle missing runtime dependencies — if a dependency is missing, that is a pre-flight validation failure, not a runtime recovery case.
- Users have at least one AI provider configured. The "no providers configured" case is handled by the gateway setup wizard before the pipeline runs, not by the recovery framework.

---

## 8. Key Entities

### RecoveryStrategy

Represents one of the five recovery approaches (auto-retry, provider fallback, graceful degradation, stage isolation, user-guided recovery). Each strategy has a trigger condition, a lifecycle (initiate → execute → succeed or exhaust), and an outcome (resolved, escalated, or exhausted).

### RecoveryContext

A per-pipeline-invocation object that tracks which strategies have been attempted, which providers are remaining in the fallback list, the current memory-pressure level, and the set of completed vs. failed stages. Passed between recovery strategy evaluations so decisions are cumulative.

### RecoveryReport

An output structure attached to the pipeline's final result. Contains a list of all recovery events that occurred during execution, their outcomes, and the final resolution status. The pipeline progress display uses this for real-time output; the final user report includes a summary.

### ErrorClassification

The logic that categorizes a provider or stage failure as transient, permanent, resource-related, or unknown. Used by the recovery coordinator to select which strategy to apply. Classification is based on error type, HTTP status code, and provider metadata.

---

## 9. Quality Checklist

See `checklists/requirements.md` for the spec quality validation checklist.
