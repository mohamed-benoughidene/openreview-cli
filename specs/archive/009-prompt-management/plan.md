# Implementation Plan: Prompt Management

**Branch**: `feat/009-prompt-management` | **Date**: 2026-07-02 | **Spec**: [spec.md](../specs/009-prompt-management/spec.md)

**Input**: Feature specification from `/specs/009-prompt-management/spec.md`

## Summary

Versioned prompt storage with SQLite-backed CRUD, prompt-to-model binding via the AI Gateway, A/B testing harness integration with the benchmark infrastructure (roadmap N-3), and GRPO optimization workflow. Prompts become first-class artifacts — versioned, testable, and optimizable — addressing the 46pp accuracy swing from prompt design documented in research [P-5].

**TDD Approach**: Tests written before implementation. Each task starts with a failing test, then minimal code to pass, then refactor.

## Technical Context

**Language/Version**: Python 3.12 (pinned in `.python-version` and `pyproject.toml`)

**Primary Dependencies**: SQLite (stdlib), PyYAML (already present), Typer (CLI), Pydantic (validation), Rich (terminal output), litellm (gateway integration)

**Storage**: SQLite with migration system (next: `004_prompts.sql`). WAL mode, foreign keys enabled.

**Testing**: pytest with `unit/` and `integration/` split. TDD approach: tests written before implementation. Memory budget enforced via `memory_tracker` fixture (<110 MB peak).

**Target Platform**: Local CLI on Linux/macOS/Windows. Reference hardware: 8 GB RAM, 2-core CPU, no GPU.

**Project Type**: CLI tool (`openreview` command, `openreview-cli` PyPI package)

**Performance Goals**: <30s total CLI command time for prompt lifecycle operations. <5 minutes for A/B test on 100-example benchmark subset. <60 minutes for GRPO optimization with 5 iterations.

**Constraints**: <100 MB peak memory (constitutional). No new runtime dependencies for core functionality. SQLite + PyYAML sufficient. 16 KB max prompt content.

**Scale/Scope**: Medium — up to 50 prompts, up to 20 versions each. Basic pagination for list commands.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Privacy First | **PASS** | Prompts are instruction text, not sensitive data. No PII in prompts. No network calls for prompt storage. |
| II. Local-First, CLI-Only | **PASS** | All prompt operations are local CLI commands. No server, no daemon. |
| III. Hardware-Bounded | **PASS** | SQLite storage is lightweight. Prompt content is text (<16 KB). No memory concerns. |
| IV. Dependency Minimalism | **PASS** | No new dependencies. SQLite (stdlib) + PyYAML (already present) are sufficient. |
| V. Spec-Driven, YAGNI | **PASS** | Spec exists. No speculative abstractions. Append-only versioning, no lifecycle states. |

**Pre-design gate: PASS**

## Project Structure

### Documentation (this feature)

```text
specs/009-prompt-management/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── cli.md           # CLI command contracts
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── prompts/                    # NEW: Prompt management module
│   ├── __init__.py             # Public API exports
│   ├── models.py               # Pydantic models: Prompt, PromptVersion, PromptBinding
│   ├── store.py                # PromptStore class — SQLite CRUD, versioning, resolve()
│   ├── variables.py            # Variable substitution engine ({key} → value)
│   ├── defaults.py             # Default prompt loader (YAML → SQLite on first use)
│   └── cli.py                  # Typer subcommands: prompt create/update/list/show/delete/diff/bind/unbind/bindings/test/optimize/history/export/import
├── storage/
│   └── migrations/
│       └── 004_prompts.sql     # NEW: prompts, prompt_versions, prompt_bindings tables
├── gateway/
│   └── router.py               # MODIFIED: integrate PromptStore.resolve() into chat/embed/rerank
└── app.py                      # MODIFIED: register prompt_app subcommand tree

tests/
├── unit/
│   ├── test_prompt_models.py       # NEW: Pydantic model validation
│   ├── test_prompt_store.py        # NEW: SQLite CRUD, versioning, resolve()
│   ├── test_prompt_variables.py    # NEW: {key} substitution
│   ├── test_prompt_defaults.py     # NEW: YAML → SQLite loading
│   └── test_prompt_cli.py          # NEW: CLI subcommand unit tests
├── integration/
│   ├── test_prompt_lifecycle.py    # NEW: end-to-end create → bind → use → unbind
│   ├── test_prompt_gateway.py      # NEW: gateway integration with prompt resolution
│   └── test_prompt_memory.py       # NEW: memory budget validation
└── fixtures/
    └── prompts/                    # NEW: test prompt YAML files
        ├── extract-clauses.yaml
        └── qa-answer.yaml
```

**Structure Decision**: Single project layout (existing). New `prompts/` module follows the pattern of `pii/` and `gateway/` — models, store, CLI in separate files. Migration `004_prompts.sql` follows the existing numbered migration pattern.

## Complexity Tracking

> No violations. All constitution principles pass.

## Implementation Approach

### TDD Workflow

1. **Write failing test** — define expected behavior
2. **Write minimal code** — make test pass
3. **Refactor** — improve without breaking tests
4. **Repeat** — next test

### Phase Priorities

| Priority | What | Why |
|----------|------|-----|
| P1 | Versioned storage + CLI CRUD | Foundation for everything else |
| P1 | Prompt-to-model binding | Makes prompts operational |
| P2 | A/B testing harness | Requires benchmark infrastructure (N-3) |
| P3 | GRPO optimization | Requires benchmark + A/B testing |

### Integration Points

1. **Storage**: `004_prompts.sql` migration → `prompts/store.py` → `database.py` helpers
2. **CLI**: `prompts/cli.py` → `app.py` (register `prompt_app`)
3. **Gateway**: `prompts/store.py` → `gateway/router.py` (resolve prompt before chat/embed/rerank)
4. **Variables**: `prompts/variables.py` → called by gateway at runtime

### Memory Budget

Prompt operations are lightweight:
- SQLite queries: <1 MB
- Prompt content: <16 KB per version
- Variable substitution: in-place string replacement
- YAML export/import: stream-based

No memory concerns. All operations well under 100 MB.

## Post-Design Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Privacy First | **PASS** | No changes. Prompts are not sensitive. |
| II. Local-First, CLI-Only | **PASS** | No changes. All local. |
| III. Hardware-Bounded | **PASS** | SQLite + text content. No memory issues. |
| IV. Dependency Minimalism | **PASS** | No new deps. SQLite + PyYAML. |
| V. Spec-Driven, YAGNI | **PASS** | Append-only versioning, no lifecycle states. No speculative abstractions. |

**Post-design gate: PASS**
