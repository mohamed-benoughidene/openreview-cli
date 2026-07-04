# 5-Stage Async Pipeline Framework

**Feature ID**: 018-5-stage-async-pipeline
**Status**: Draft Specification
**Created**: 2026-07-04
**Blueprint References**: [C-25], [PR-11], §6.1, §6.2, §6.6, §6.8, [C-08], [C-12], [C-19], [N-4a], [C-32], [C-10], [C-11], [R-3], [R-7], [Q-3], [Q-7], [Q-9]

---

## 1. Executive Summary

The existing review, bilateral, and benchmark flows each contain a hand-wired synchronous loop that chains document processing stages — parse, strip, chunk, retrieve, generate — as a linear Python function with no abstraction between stages. This spec defines a **reusable async pipeline runner** that decouples stage logic from orchestration, making it possible for any CLI flow to adopt a uniform, memory-budget-aware execution model. (C-25 — 5-stage async pipeline architecture; §6.6 — memory budget and eager unload)

**What this delivers:**

- A generic pipeline runner that accepts a list of stages and executes them in sequence, passing a shared context between stages
- Each stage is an isolated unit with a well-defined input/output contract, making stages independently testable and swappable
- Async execution so that IO-bound stages (network calls to AI providers, document loading) can run concurrently where the stage contract permits
- Memory-budget awareness: the pipeline runner fires completion callbacks between stages so that each stage can release large objects before the next stage allocates
- Error isolation: a stage failure is captured and reported without crashing the whole pipeline, unless the stage is marked as critical
- Progress reporting so the user sees which stage is running and how it is progressing
- Integration surface so that existing `run_review()`, `ReviewCommand`, and benchmark runners can adopt the framework incrementally without rewriting their stage logic

The framework is not a new background runtime — it runs synchronously from the CLI's perspective (user types a command, waits for output, gets it). The "async" refers to internal concurrency: IO-bound work inside each stage (API calls, file reads) uses asyncio so that the CLI can show live progress and interleave multiple playbook questions without blocking.

---

## 1.5 Dependencies & Related Capabilities

The pipeline orchestrates execution across six existing capabilities (listed with their current TRL):

| Dependency | ID | Description | TRL | Status |
|---|---|---|---|---|
| Stream Clauses (Parse stage) | [C-08] | Page-by-page PDF/DOCX streaming, clause-boundary detection, hierarchy builder | TRL 7+ | Shipped in parsing/ |
| AI Gateway (Generate stage) | [C-12] | Model routing, cost tracking, provider pass-through, LiteLLM integration | TRL 7+ | Shipped in gateway/ |
| Hierarchical Retrieval (Retrieve stage) | [C-19] | BM25 + Dense + RRF hybrid retrieval via SQLite FTS5 and Ollama embeddings | TRL 5 | Spec 016 (in progress) |
| RCTS Chunking (Chunk stage) | [C-32] | Recursive clause-tree chunking with hierarchy metadata, parent-chunk references | TRL 7+ | Shipped (spec 007) |
| PII Stripping (Strip stage) | [C-10]/[C-11] | Presidio-based PII detection, placeholder generation, encrypted mapping | TRL 7+ | Shipped in pii/ |
| PII→Chunk Bridge (Strip→Chunk seam) | [N-4a] | Structural bridge between PII-stripped clauses and the chunking pipeline | TRL 4 | Defined |

Each stage adapter wraps the corresponding capability interface. The pipeline runner does not re-implement any of these — it orchestrates them. (§6.2 — retrieval/chunking stage composition, §6.8 — provider pass-through for AI Gateway)

---

## 2. User Scenarios & Testing

### Scenario 1 — A review command runs its 5 stages through the pipeline framework (Priority: P1)

A user runs `openreview precheck contract.pdf`. Behind the scenes, the existing hand-wired loop in `run_review()` is replaced with the pipeline framework. The user sees no difference in the output format, but the internal architecture is now stage-based. The framework reports progress to stderr: `[1/5] Parsing...`, `[2/5] Stripping PII...`, etc.

**Why this priority**: This is the primary motivation for the framework — making the existing review flow adoptable to the new architecture. Without this scenario, the framework has no consumer.

**Independent Test**: Create a pipeline with the five review stages (Parse, Strip PII, Chunk, Retrieve, Generate) wired to mock stage implementations. Assert that the pipeline runner calls each stage's `run()` method exactly once, in the correct order, with the shared context accumulating the expected keys after each stage.

**Acceptance Scenarios:**

1. **Given** a pipeline configured with five stage objects (Parse → Strip → Chunk → Retrieve → Generate), **When** the pipeline runner executes all stages, **Then** each stage's `run()` is invoked in order, the shared context dict contains the output of every preceding stage, and the runner returns a result from the final stage.

2. **Given** a stage that raises a non-fatal error, **When** the pipeline runner encounters the error, **Then** the stage's error is captured in the stage result, the shared context carries an `errors` list, and subsequent stages still execute.

3. **Given** a stage marked as `critical=True`, **When** that stage raises an error, **Then** the pipeline halts immediately and the error is propagated to the caller without executing remaining stages.

---

### Scenario 2 — A developer creates a custom pipeline with different stage ordering (Priority: P2)

A benchmark developer wants to run only the Parse and Chunk stages without Strip or Generate. They compose a pipeline from those two stages, pass it to the runner, and receive the chunk output directly.

**Why this priority**: Pipeline composition is a key selling point for adoption across different flows. It is not the initial use case — the initial use case is replacing the existing synchronous loop — but it must be supported from day one to avoid a rewrite later.

**Independent Test**: Instantiate a pipeline with only `[ParseStage, ChunkStage]`, run it on a test document, and verify that the returned context contains parse results and chunk results but no strip or generate keys.

**Acceptance Scenarios:**

1. **Given** a pipeline with two stages `[ParseStage, ChunkStage]`, **When** the runner executes them, **Then** only those two stages run and the shared context has keys only for those two stages.

2. **Given** a stage `SkipStage` that implements `should_skip()` returning `True` under a config condition, **When** the pipeline runs, **Then** `SkipStage.run()` is never called and the context is unmodified for that stage's key.

---

### Scenario 3 — Pipeline respects memory budget between stages (Priority: P2)

A user runs the pipeline on a large contract (200+ pages). Between stages, the pipeline runner calls a cleanup callback that releases stage-owned references. Memory pressure stays under 100 MB for the non-NLP portion of processing.

**Why this priority**: The constitutional memory budget is a release-blocker constraint. Without stage-level memory management, a long pipeline on a large document will accumulate context data across all five stages and exceed the budget.

**Independent Test**: Implement a stage that returns a large object (e.g., a 50 MB string). Run the pipeline with that stage followed by a monitor stage that prints the size of the shared context before and after cleanup. Assert that cleanup removes the large object from the context (or that its reference count drops to the pipeline runner only).

**Acceptance Scenarios:**

1. **Given** a stage that returns a large data object, **When** the pipeline runner completes processing for that stage, **Then** the runner invokes the stage's `cleanup()` method, releasing stage-local memory.

2. **Given** the cleanup callback registered on a stage, **When** the pipeline transitions to the next stage, **Then** the peak memory of the process does not exceed the configured budget (measurable via `tracemalloc` in CI).

---

### Edge Cases

- **Empty pipeline**: When the stage list is empty, the runner returns an empty context immediately with no error.
- **Stage with no output**: A stage may return `None`. The runner treats this as a successful no-op stage and proceeds.
- **Concurrent stage limit**: If a stage is IO-bound, the runner may run multiple instances concurrently. The concurrency limit is configurable per pipeline, not per stage.
- **User interrupt (Ctrl+C)**: The runner captures `KeyboardInterrupt`, cancels in-flight async work gracefully, and returns the partial context with a `cancelled=True` flag. (§6.1 — CLI-first responsiveness, cancellation on interrupt)
- **Zero-byte input**: A stage that receives empty input (no clauses, no chunks) completes successfully with an empty result set.

---

## 3. Requirements

### Functional Requirements

- **FR-001**: The pipeline runner MUST accept an ordered list of stage objects and execute them sequentially, passing a shared mutable context between stages. (C-25, §6.2 — stage orchestration pattern)
- **FR-002**: Each stage MUST implement an interface with a `run(context) → dict` method that receives the shared context and returns stage-specific results to merge into the context. (C-25 — stage abstraction contract)
- **FR-003**: The pipeline runner MUST support async stage execution — each stage's `run()` MAY be a coroutine, and the runner MUST await it. (C-25, §6.8 — async IO for provider calls)
- **FR-004**: The pipeline runner MUST support an optional per-stage `cleanup()` callback that is invoked after the stage's result is merged into the context, before the next stage starts. (§6.6, R-3 — memory budget, eager unload between stages)
- **FR-005**: The pipeline runner MUST report progress — at minimum, the current stage index, total stage count, and stage name — via a callback or a Python generator yielding progress events. (C-25 — user-facing progress signaling)
- **FR-006**: Stage errors MUST be captured per-stage: the runner stores the exception in the stage result and continues to the next stage UNLESS the stage is marked as `critical=True`, in which case the pipeline halts immediately. (C-25 — error isolation, stage fault tolerance)
- **FR-007**: The pipeline runner MUST support optional concurrency within a single stage: an IO-bound stage may process items in parallel (e.g., multiple API calls for different playbook questions) using asyncio primitives. (§6.8 — provider pass-through enables concurrent API calls)
- **FR-008**: Each stage MUST be independently instantiable and testable without the pipeline runner — i.e., `stage.run({"document_path": "test.pdf"})` must work in isolation in a unit test. (C-25 — stage independence, testability)
- **FR-009**: The pipeline context MUST be a plain dict (or a dataclass with dict-like access) to minimise coupling. The runner MUST NOT enforce a schema on the context contents. (C-25 — minimal coupling, no schema enforcement)
- **FR-010**: The pipeline runner MUST support an optional `max_memory_mb` parameter and emit a warning when a stage's allocated memory exceeds that threshold (measured using `tracemalloc` or `psutil.Process().memory_info().rss`). (R-3, §6.6 — memory budget enforcement, zero-allocation traversal between stages)
- **FR-011**: The pipeline runner MUST support a `cancellation_token` mechanism (an `asyncio.Event` or callback) so that the CLI can interrupt a long-running pipeline on `KeyboardInterrupt`. (C-25 — CLI interrupt handling; §6.1 — SLM-first responsiveness)
- **FR-012**: The pipeline MUST produce a `PipelineReport` containing: list of stage results (stage name, duration in seconds, error if any, output keys), total wall-clock time, and cancellation status. (C-25 — pipeline execution reporting)

### Key Entities

- **Pipeline**: The orchestrator that accepts a list of stages, a context initialiser, and optional configuration (memory limit, concurrency limit, cancellation token). Exposes `run()` that returns a `PipelineReport`.
- **Stage**: A unit of pipeline work. Implements `run(context) → dict` and optionally `cleanup()`. Has a `name` string, a `critical` boolean flag, and an optional `max_concurrency` for internal parallel work.
- **PipelineContext**: The shared mutable dict that flows through stages. Stages read prior outputs from it and write their outputs into it. The runner does not inspect or validate its contents.
- **StageResult**: A record of a single stage execution: stage name, duration, optional error, list of keys written to context, and whether the stage was skipped.
- **PipelineReport**: The final output of a pipeline run: list of `StageResult` entries, total duration, cancellation flag, and peak memory measured during the run.

---

## 4. Success Criteria

### Measurable Outcomes

- **SC-001**: The existing `run_review()` function in `review/__init__.py` can be rewritten to use the pipeline framework with zero changes to its output format and zero regressions in the test suite. (§6.1 — CLI-first design, no user-facing behavior change)
- **SC-002**: A 5-stage pipeline (Parse → Strip → Chunk → Retrieve → Generate) runs end-to-end on a 50-page PDF document in under 30 seconds when each stage uses a fast local implementation (no network IO). (§9, R-7 — SLM performance target on consumer hardware; C-08, C-32, C-10/C-11 — stage deps)
- **SC-003**: Peak memory for the pipeline runner (excluding the PII NLP model) stays under 15 MB above the baseline of the heaviest single stage, measured by `tracemalloc` on a 200-page document. This keeps total non-NLP processing well under the 100 MB constitutional budget. (Constitution memory budget: 100 MB processing floor, 110 MB test ceiling; §6.6, R-3 — eager unload between stages)
- **SC-004**: A stage failure in a non-critical stage produces a `StageResult` with the error attached, and subsequent stages execute. The user sees a warning per failed stage but receives the partial output. (C-25 — error isolation, partial output on non-fatal failure)
- **SC-005**: The pipeline framework is adopted by at least one existing consumer (`run_review()` or `ReviewCommand.run()`) within the same feature branch where the framework lands. The switchover is measured: zero test regressions in the consumer's test suite. (C-25 — adoption by existing consumers; §6.1 — incremental switchover preserves behavior)
- **SC-006**: A custom pipeline of two stages (Parse, Chunk) can be composed and executed in under 10 lines of user code — import, instantiate stages, instantiate pipeline, call `run()`. (C-25 — pipeline composition; C-08, C-32 — stage deps for Parse and Chunk)

---

## 5. Adoption Strategy (Incremental)

The framework ships in the same feature branch as at least one consumer rewrite. The recommended first consumer is the single-party review pipeline (`run_review()`), because it is:

1. The most mature and tested pipeline
2. Already organised as stages in the code (parse → strip → extract → QA → report), though the stages are not abstracted
3. The pipeline that other consumers (bilateral, benchmark) were modelled on
4. The consumer with the richest test suite, making regression detection reliable

The switchover follows this sequence:

1. Land the pipeline framework as a new private module (`src/openreview_cli/pipeline/`) with tests
2. Do **not** change any consumer yet — the framework and its tests are standalone
3. In the same PR stack, rewrite `run_review()` to use the pipeline framework
4. Run the full review test suite — all existing acceptance tests must pass with zero changes
5. If the bilateral or benchmark consumers benefit from the same pattern, they can adopt in a follow-up PR

---

## 6. Assumptions

- The existing stage logic (parse via `stream.parse_document`, strip via `pii.engine.strip_and_persist`, chunk via the chunking module, retrieve via the retrieval module, generate via the AI Gateway router) does not need to change — the pipeline framework wraps each as a stage adapter. (C-25, §6.2 — stage orchestration wraps existing capabilities; C-08, C-10/C-11, C-32, C-19, C-12 — stage deps)
- The PII NLP model memory exemption (constitution Principle III) continues to apply: the ~500 MB spaCy model is loaded once per session and excluded from the pipeline's memory budget tracking. (§6.6 — memory budget, NLP model exemption; R-3 — memory budget breach risk)
- The pipeline runs in-process and single-threaded from the perspective of the GIL, with async IO concurrency only. There is no multiprocessing or subprocess forking. (C-25 — in-process orchestration; §6.6 — no multiprocessing overhead)
- The user-facing CLI behaviour does not change: the user types a command, sees progress, receives output. The "async" is an internal implementation detail. (§6.1 — SLM-first, CLI-only; no user-facing behavior change)
- The pipeline framework is not a replacement for the entire application architecture — it is an orchestrator for a specific linear workflow. Background tasks, event loops that outlive a single command, and cross-command state are out of scope. (C-25 — scope boundary: linear CLI workflow only)
- No new third-party dependencies are required for the pipeline framework itself — the stdlib provides `asyncio`, `dataclasses`, `time`, `abc`, and `tracemalloc`. (§6.8 — existing LiteLLM dependency for provider calls; no additional deps for orchestration)
