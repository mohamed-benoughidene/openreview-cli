# Feature Specification: Prompt Management

**Feature Branch**: `feat/009-prompt-management`

**Created**: 2026-07-02

**Status**: Draft

**Input**: User description: "Prompt management specification. Versioned prompt storage (SQLite table or YAML in config). Prompt A/B testing harness (benchmark integration). GRPO optimization workflow (offline, not runtime). Prompt-to-model binding (which prompt version with which model version). Motivated by the documented HIGH-priority gap that no prompt engineering/optimization strategy exists (accuracy floors at ~29% for structured tasks without it), the CHANCERY finding that prompt removal causes a 46-percentage-point accuracy drop, and the GRAPH-GRPO-LEX finding that GRPO optimization improves F1 from 0.66 to 0.80."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Versioned Prompt Storage (Priority: P1)

A developer working on the review pipeline needs to create, store, and version prompts used by the AI models. They open the CLI and run `openreview prompt create --name extract-clauses --content "Extract all clauses from the contract..."`. Later, they need to improve the prompt and create version 2 without losing the original. They run `openreview prompt update extract-clauses --content "..."` which auto-increments the version. They can list all prompts, view specific versions, and see which version is currently active for each model slot.

**Why this priority**: Versioned storage is the foundation — without it, prompt-to-model binding, A/B testing, and GRPO optimization have nothing to operate on. The prompt becomes a first-class artifact, not a hardcoded string.

**Independent Test**: Can be tested by creating a prompt via CLI, verifying it appears in `openreview prompt list`, updating it, and confirming both versions exist in `openreview prompt show --name extract-clauses`.

**Acceptance Scenarios**:

1. **Given** no prompts exist, **When** a developer runs `openreview prompt create --name extract-clauses --content "Extract fields from contract"`, **Then** the prompt is stored, appears in `openreview prompt list`, and has version `1`
2. **Given** prompt `extract-clauses` version 1 exists, **When** the developer runs `openreview prompt update extract-clauses --content "Revised content"`, **Then** version 2 is created, version 1 remains accessible via `openreview prompt show extract-clauses --version 1`, and the output of both versions differs only in content and version number
3. **Given** 10 prompts exist, **When** the developer runs `openreview prompt list`, **Then** all 10 are listed with their names, latest version numbers, and creation dates

---

### User Story 2 - Prompt-to-Model Binding (Priority: P1)

A developer configures which prompt version each model slot in the gateway should use. They bind the `extract-clauses` prompt version 2 to the `extraction` model slot. When a review pipeline runs, the gateway loads prompt version 2 from the store and sends it to the model configured in the `extraction` slot. If the binding is removed, the pipeline falls back to a sensible default (latest version).

**Why this priority**: Prompt-to-model binding is how prompts become operational. Without it, prompts sit in storage but don't affect the actual pipeline. This is the bridge between management and execution.

**Independent Test**: Can be tested by binding a prompt to a model slot, running a review or extraction, and verifying the bound prompt's content appears in the API call (verifiable via mock or debug output). The fallback behavior can be tested by removing the binding and confirming the default prompt is used.

**Acceptance Scenarios**:

1. **Given** prompt `extract-clauses` version 2 exists, **When** a developer runs `openreview prompt bind --slot extraction --prompt extract-clauses --version 2`, **Then** the binding is stored and `openreview prompt bindings` shows `extraction → extract-clauses:v2`
2. **Given** a binding `extraction → extract-clauses:v2` exists, **When** the review pipeline runs, **Then** the gateway sends `extract-clauses` version 2 content to the model configured in the `extraction` slot
3. **Given** no binding exists for the `extraction` slot, **When** the pipeline runs, **Then** the pipeline uses the latest version of the default prompt for that slot (a built-in prompt shipped with the product)
4. **Given** a binding for slot `extraction` exists, **When** the developer runs `openreview prompt unbind --slot extraction`, **Then** the binding is removed and subsequent pipeline runs use the default

---

### User Story 3 - Prompt A/B Testing via Benchmark (Priority: P2)

A developer has two versions of the `extract-clauses` prompt (v1 and v2) and wants to know which one extracts contract fields more accurately. They run `openreview prompt test --prompt extract-clauses --versions 1,2 --benchmark standard`. The tool runs both prompt versions through the benchmark dataset (CUAD, MAUD, or a subset) and produces a side-by-side comparison of metrics — extraction F1, precision, recall. The developer can see which version wins and by how much.

**Why this priority**: The CHANCERY governance-reasoning study shows that prompt design alone swings accuracy by 46 percentage points. Without A/B testing, choosing between prompt versions is guesswork. The benchmark harness provides the dataset infrastructure; this feature connects prompts to that infrastructure.

**Independent Test**: Can be tested by creating two prompt versions, running the A/B test command against a small seeded dataset, and verifying the output shows per-prompt metrics and a comparison summary.

**Acceptance Scenarios**:

1. **Given** prompt `extract-clauses` has versions 1 and 2, **When** the developer runs `openreview prompt test --prompt extract-clauses --versions 1,2 --benchmark standard`, **Then** the output shows per-version metrics (F1, precision, recall) and a comparison (which metric each version wins)
2. **Given** a benchmark run completes, **When** the developer runs `openreview prompt history extract-clauses`, **Then** the test results appear in the prompt's version history
3. **Given** the developer specifies only one version (e.g., `--versions 1`), **When** the test runs, **Then** only that version is evaluated (useful for establishing baseline metrics for a new prompt)
4. **Given** no benchmark dataset is configured, **When** the developer runs the test command, **Then** an informative error is shown explaining how to configure a benchmark dataset

---

### User Story 4 - GRPO Optimization Workflow (Priority: P3)

A developer has a prompt that works but wants to systematically improve it. They run `openreview prompt optimize --prompt extract-clauses --benchmark standard --iterations 5`. The tool runs GRPO-guided optimization offline — it generates candidate prompt variants, evaluates each against the benchmark, and selects the best performer. The optimized version is saved as a new prompt version (e.g., version 3) with metadata linking it to the optimization run. The developer can review the diff between the original and optimized prompt before deploying.

**Why this priority**: The GRAPH-GRPO-LEX study shows GRPO optimization improves F1 from 0.66 to 0.80 (a ~14-point gain). This is the most advanced capability — it requires the benchmark harness, the storage system (US1), and optimization logic. It is the lowest priority because it is an offline developer workflow, not a user-facing feature.

**Independent Test**: Can be tested by running the optimize command on a simple prompt against a small seeded benchmark, verifying a new version is created, and confirming the new version has associated metadata about the optimization run (source version, iteration count).

**Acceptance Scenarios**:

1. **Given** prompt `extract-clauses` version 1 exists with a benchmark dataset configured, **When** the developer runs `openreview prompt optimize --prompt extract-clauses --iterations 3`, **Then** a new version is created with metadata recording the source version, number of iterations, and per-iteration metrics
2. **Given** an optimization run completes, **When** the developer runs `openreview prompt diff extract-clauses --from 1 --to 2`, **Then** the output shows the content changes between the source and optimized prompt
3. **Given** the developer runs optimization with no benchmark dataset configured, **Then** an informative error is shown
4. **Given** the developer runs optimization with `--iterations 0`, **Then** a validation error is shown (at least 1 iteration required)

---

### Edge Cases

- What happens when a prompt with the same name and version already exists? — Version increments are automatic; a create with the same name creates version 1 only if no versions exist. An update always creates a new version number (append-only).
- What happens when a binding references a prompt version that is later deleted or the prompt is removed entirely? — The binding remains but the pipeline falls back to the default prompt for that slot, logging a warning.
- What happens when the benchmark set is too small for reliable A/B test results? — The test command warns if fewer than 10 benchmark examples are available.
- What happens during a long GRPO optimization run (hours)? — The CLI shows live progress per iteration and supports `Ctrl+C` to abort, preserving results from completed iterations.
- What happens if the GRPO process produces a prompt that has the same content as the source? — The optimization reports "no improvement found" and does not create a new version.
- What happens to prompt data when the user runs `openreview config reset`? — Prompts and bindings are preserved (they are application data, not configuration).
- What happens when a prompt version's content exceeds 16 KB? — The create/update command rejects it with a validation error message specifying the 16 KB limit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a SQLite-backed prompt store with versioned entries. Each prompt entry SHALL have: unique name (string), version (integer, auto-incremented per name), content (text, max 16 KB), created_at (timestamp), and optional metadata (tags, description). The combination of (name, version) SHALL be unique. Content exceeding 16 KB SHALL be rejected with a validation error.
- **FR-002**: The system MUST provide CLI subcommands under `openreview prompt` for: `create` (create version 1 of a new prompt), `update` (create new version of existing prompt), `list` (show all prompts with latest version, with basic pagination for >25 entries), `show` (view specific prompt version), `delete` (remove a prompt and all its versions), and `diff` (show content changes between two versions).
- **FR-003**: The system MUST provide CLI subcommands under `openreview prompt` for: `bind` (associate a prompt version with a model slot), `unbind` (remove a binding), and `bindings` (list all active bindings). Bindings SHALL be persisted in SQLite and loaded at pipeline startup.
- **FR-004**: The system MUST integrate with the AI Gateway so that when a review pipeline runs, the gateway loads the prompt version specified by the active binding for each model slot. If no binding exists for a slot, the gateway MUST use the latest version of the built-in default prompt for that slot.
- **FR-005**: The system MUST provide a `openreview prompt test` subcommand that runs one or more prompt versions through a benchmark dataset and reports per-version metrics (F1, precision, recall) and a comparison. The benchmark harness is an integration dependency (the model-params / benchmark-harness capability already shipped); this feature defines the integration contract.
- **FR-006**: The system MUST provide a `openreview prompt optimize` subcommand that runs GRPO-guided prompt optimization as an offline CLI process. The command SHALL: generate candidate prompt variants across N iterations, evaluate each against the benchmark dataset, select the best performer, and save it as a new version with optimization metadata (source version, iteration count, per-iteration metrics).
- **FR-007**: The system MUST support exporting and importing prompts as YAML files for portability and version control. Export format SHALL include the prompt name, all versions, and their metadata. Import SHALL create new entries, preserving version numbers.
- **FR-008**: The system MUST ship a set of default prompts for the built-in model slots (extraction, QA, comparison) as part of the package. These defaults SHALL be loaded into the prompt store on first use and SHALL not be overwritable by import (users create their own versions on top).
- **FR-009**: The system MUST provide a `openreview prompt history` subcommand that shows the version history for a prompt, including A/B test results and GRPO optimization metadata attached to each version.
- **FR-010**: The system MUST support `{key}` variable substitution in prompt content, resolved at pipeline runtime from a per-slot predefined variable set. Each model slot SHALL expose a documented set of injectable variables (e.g., `{document_type}`, `{clause_count}`, `{playbook_position}`). If a prompt contains an unrecognized variable name, the system MUST log a warning and leave the variable text as-is.

### Key Entities

- **Prompt**: A versioned artifact containing instruction text sent to an AI model. Key attributes: name (unique identifier), version (integer, auto-incremented), content (text, max 16 KB, may contain `{key}` template variables), created_at (timestamp), metadata (optional tags/description), test_results (array of A/B test outcomes linked to this version), optimization_meta (GRPO run metadata, if version was created by optimization).
- **PromptBinding**: An association between a gateway model slot (e.g., `extraction`) and a specific (prompt_name, version) pair. The binding determines which prompt is loaded when the pipeline calls a model slot.
- **PromptStore**: The SQLite-backed repository that manages prompt CRUD, versioning, and querying. Exposes a `resolve(slot_name)` method that returns the appropriate prompt content for a given model slot at pipeline runtime.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can complete the full lifecycle for a prompt — create, update (creating a new version), list, show specific version, diff between versions, and delete — entirely via the CLI without errors, in under 30 seconds total command time.
- **SC-002**: A developer can bind a prompt version to a model slot, run a pipeline invocation, and verify the bound prompt content is used by inspecting debug output or a mock provider — the binding takes effect within one CLI invocation.
- **SC-003**: A developer can run `openreview prompt test --versions 1,2` and receive a side-by-side comparison table with F1, precision, and recall for each version — the command completes in under 5 minutes for a 100-example benchmark subset on the reference hardware (8 GB RAM, 2-core CPU).
- **SC-004**: A developer can run `openreview prompt optimize --iterations 5` and receive a new prompt version with improved or equal benchmark metrics compared to the source — the command completes and reports results within 60 minutes on the reference hardware.
- **SC-005**: Exporting all prompts to YAML and re-importing them into a fresh SQLite database produces an identical prompt store (same names, versions, content, metadata) — verifiable via checksum comparison.
- **SC-006**: Peak memory usage for any prompt command (create, list, bind, test, optimize) does not exceed the project's 100 MB processing budget — verifiable via tracemalloc in CI.
- **SC-007**: No new external runtime dependencies are added for core prompt storage, versioning, and binding functionality — SQLite (stdlib) and PyYAML (already present) are sufficient.

## Assumptions

- SQLite is the primary store for prompts and bindings. YAML serves as an interchange format for export/import only.
- Prompt versions are immutable once created (append-only versioning, no lifecycle states). An `update` creates a new version; it does not modify an existing one. Delete removes all versions of a prompt.
- The expected data scale is medium: up to 50 prompts, with up to 20 versions each. Basic pagination is sufficient for list commands.
- The benchmark harness already exists and exposes a programmatic API that this feature can call. The prompt management spec defines the integration contract but does not implement the benchmark harness itself.
- GRPO optimization is a developer-only workflow, not exposed to end users of the product. It runs offline, may take significant time, and requires the benchmark dataset.
- Default prompts for built-in model slots are shipped with the package as YAML files in `src/openreview_cli/gateway/prompts/defaults/` and loaded on first use if the prompt store is empty.
- The gateway's `ModelParams` already supports extra provider-specific parameters (via the `extra_params` field — see spec 006); prompt content is passed as part of the `messages` array, not as a separate parameter.
- Each model slot defines a set of injectable variables (`{document_type}`, `{clause_count}`, `{playbook_position}`, etc.) that the gateway resolves at pipeline runtime.
- Prompt storage does not need encryption at rest — prompts are instruction text, not sensitive data. They are stored in the project's SQLite database alongside other application data.
- The `openreview prompt` subcommand tree lives under the existing Typer app in `src/openreview_cli/app.py`, following the established CLI structure.

## Clarifications

### Session 2026-07-02

- Q: Should prompt content support variable substitution at pipeline runtime? → A: Simple `{key}` substitution with per-slot predefined variable set.
- Q: What is the expected data scale — how many prompts and versions per prompt? → A: Medium scale — up to 50 prompts, up to 20 versions each (basic pagination needed).
- Q: Should prompt storage be primarily SQLite-based or YAML file-based? → A: SQLite primary store, YAML for import/export.
- Q: Should prompts have lifecycle states (draft/active/deprecated) beyond append-only versioning? → A: Append-only versioning, no lifecycle states.
- Q: Should there be a maximum content length for stored prompts? → A: 16 KB maximum content length.
