# Research: Prompt Management

**Feature**: 009-prompt-management | **Date**: 2026-07-02

## R-1: SQLite Versioning Pattern

**Decision**: Append-only versioning with (name, version) composite unique key. Auto-increment version per name.

**Rationale**: Matches the spec's "append-only versioning, no lifecycle states" decision. Simple, no state machine needed. Version is immutable once created.

**Alternatives considered**:
- Lifecycle states (draft/active/deprecated) — rejected per clarification Q4
- Single-row with JSON versions array — rejected: harder to query, no per-version metadata

## R-2: Variable Substitution Syntax

**Decision**: `{key}` syntax with Python `str.format_map()` using a defaultdict that returns the original `{key}` text for unknown keys.

**Rationale**: Stdlib, no new deps. `defaultdict` gives us "warn and leave as-is" behavior for free. Per-slot variable sets are documented in the gateway slot config.

**Alternatives considered**:
- Jinja2 — rejected: new dependency, overkill for simple substitution
- Regex-based — rejected: more code, same result
- Template strings — rejected: `$key` syntax less common in prompt engineering

## R-3: Prompt-to-Gateway Integration

**Decision**: `PromptStore.resolve(slot_name)` returns the prompt content string. The gateway calls this before building the `messages` array for `litellm.completion()`. The resolved prompt is prepended as a system message.

**Rationale**: Minimal integration point. The gateway already builds messages; we just inject the prompt. No changes to litellm or provider APIs.

**Alternatives considered**:
- Prompt as a parameter to `Gateway.chat()` — rejected: changes the gateway API
- Prompt stored in config.yml — rejected: spec says SQLite primary, YAML interchange only
- Prompt as part of ModelParams — rejected: conflates model config with prompt content

## R-4: Default Prompts Shipping

**Decision**: Ship default prompts as YAML files in `src/openreview_cli/prompts/defaults/`. On first use (empty prompt store), load them into SQLite. Import cannot overwrite defaults.

**Rationale**: Follows the spec's FR-008. YAML is the interchange format. First-use loading is lazy (no startup cost). Import protection prevents accidental overwrites.

**Alternatives considered**:
- Hardcoded defaults in Python — rejected: not portable, can't be exported
- Defaults in config.yml — rejected: conflates config with content
- Always load defaults on startup — rejected: unnecessary I/O

## R-5: A/B Testing Integration Contract

**Decision**: `openreview prompt test` calls the benchmark harness (roadmap N-3) via a programmatic API. The contract: benchmark provides `run(prompt_content, dataset) → metrics`. Prompt management provides prompt versions and collects results.

**Rationale**: The benchmark harness doesn't exist yet. We define the integration contract but don't implement the harness. This allows the benchmark team to build independently.

**Alternatives considered**:
- Implement benchmark harness in this feature — rejected: out of scope, separate roadmap item (N-3)
- Skip A/B testing until benchmark exists — rejected: spec requires the contract be defined

## R-6: GRPO Optimization Approach

**Decision**: Offline CLI process. Generate candidate variants via LLM, evaluate each against benchmark, select best, save as new version with metadata. No runtime optimization.

**Rationale**: Matches spec's FR-006. GRPO is a developer workflow, not user-facing. Offline means no memory/time pressure on the CLI.

**Alternatives considered**:
- Runtime optimization — rejected: too slow, memory-intensive
- Automatic optimization on update — rejected: speculative, not requested

## R-7: Diff Implementation

**Decision**: Use Python's `difflib.unified_diff()` for content diff between two versions. Output as unified diff format via Rich.

**Rationale**: Stdlib, no new deps. Unified diff is the standard format. Rich renders it with colors.

**Alternatives considered**:
- Third-party diff library — rejected: unnecessary dependency
- Side-by-side comparison — rejected: harder to read for long prompts

## R-8: Export/Import Format

**Decision**: YAML format with structure:
```yaml
name: extract-clauses
versions:
  - version: 1
    content: "..."
    created_at: "2026-07-02T10:00:00"
    metadata: { tags: [...], description: "..." }
  - version: 2
    content: "..."
    created_at: "2026-07-02T11:00:00"
    metadata: { tags: [...], description: "..." }
```

**Rationale**: PyYAML already present. YAML is human-readable. Structure matches the data model. Import preserves version numbers per spec FR-007.

**Alternatives considered**:
- JSON — rejected: less readable for multi-line content
- SQLite dump — rejected: not portable, not human-readable

## Research Grounding

All items verified against:
- Constitution v1.2.0 (principles I-V)
- Existing codebase patterns (storage, CLI, gateway)
- Feature spec (FR-001 through FR-010)
- Product blueprint (§6.5, N-1)

No NEEDS CLARIFICATION remain.
