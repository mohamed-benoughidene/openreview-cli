# Implementation Plan: Privacy Tier Routing

**Branch**: (no branch created - existing `specs/020-privacy-tier-routing/` directory) | **Date**: 2026-07-05 | **Spec**: `specs/020-privacy-tier-routing/spec.md`

**Input**: Feature specification from `specs/020-privacy-tier-routing/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Three privacy tiers (Maximum/Balanced/Performance) control how user data travels during model inference. TierRouter wraps the AI Gateway and enforces rules before every model call: Maximum blocks all cloud providers, Balanced routes embeddings locally and cloud LLM only after PII stripping, Performance routes everything to cloud with PII stripping. Tier is read from `config.yml privacy.tier`, defaults to Maximum, cannot change mid-operation. PII engine failure blocks cloud calls with actionable error (fail-closed). Provider location (local vs cloud) determined by base URL inspection.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `litellm` (AI Gateway, already in project), `presidio-analyzer` + `presidio-anonymizer` (PII engine, already in project), `ollama` Python SDK (for Maximum tier direct calls if LiteLLM bypass is measured as needed — spec CL-02 says route through Gateway for now), `httpx` (for HTTP classification via URL inspection)

**Storage**: Configuration read from `config.yml` (existing config loader). No new persistent storage. PII-stripped text cached per-operation in memory (dict, operation-scoped). No database changes.

**Testing**: `pytest`. Unit tests for TierRouter in isolation (mocked Gateway). Integration tests for each tier with fake providers and seeded PII documents. Memory test for router overhead (<100 MB peak, NLP model exempt per constitution).

**Target Platform**: Linux CLI (reference: 8 GB RAM, 2-core CPU, no GPU). macOS supported but not primary.

**Project Type**: CLI tool (local, single-invocation). No server, no daemon.

**Performance Goals**: TierRouter adds <50ms overhead per call (pre-filter + PII check). No measurable impact on end-to-end review time. Memory overhead <5 MB (config object + provider cache).

**Constraints**: <100 MB peak memory (NLP model exempt). No silent cloud fallback. Fail-closed on PII failure. Tier stable per operation. Output always shows current tier.

**Scale/Scope**: 3 tiers, ~15 source files (router, config, provider classifier, report, tests). No new external services.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Privacy First — PASS
- TierRouter enforces PII stripping before cloud egress (FR-03, FR-04)
- Maximum tier blocks all external network calls (SC-01)
- PII engine failure blocks cloud calls with fail-closed error (SC-03)
- `--no-pii` flag scenario handled by FR-04 (blocks cloud calls when PII unavailable)
- No data ever sent to cloud without PII stripping
- Configuration where every model slot is local (Maximum tier) supported end-to-end per constitution rule (I, rule 5)

### II. Local-First, CLI-Only — PASS
- Maximum tier defaults to local-only — no network calls
- Balanced tier keeps local embeddings
- No server, daemon, or background process introduced
- No telemetry or phone-home
- Works offline when every slot is local (Maximum tier)
- TierRouter is a thin call wrapper, not a long-running process

### III. Hardware-Bounded — PASS
- TierRouter adds minimal memory overhead (<5 MB)
- No full-document loads in router — operates on call metadata and PII status flag
- PII engine (spaCy model) exempt from <100 MB budget per constitution
- No GPU dependency — router does not detect hardware, per CL-01 resolution
- No new heavy imports — reuses existing Gateway, config, PII engine references

### IV. Dependency Minimalism — PASS
- No new runtime dependencies — reuses existing `litellm`, `presidio-analyzer`, `presidio-anonymizer`
- No forbidden dependencies introduced (no langchain, FAISS, spaCy-for-PII, etc.)
- Stdlib `enum`, `dataclasses`, `re`, `urllib.parse` for classification
- `httpx` for URL parsing (already a dependency)
- Pydantic for TierConfig dataclass (already in project)

### V. Spec-Driven, YAGNI — PASS
- Implementation follows spec.md — no scope creep
- No speculative abstractions: TierRouter is a single class wrapping Gateway methods
- No interface with one implementation (concrete class, no abstract base)
- No unrequested features (no auto-tier-recommendation, no per-clause tiers, no runtime switching)
- Each non-trivial change leaves a runnable test

### GATE: — PASS (no violations)

## Project Structure

### Documentation (this feature)

```text
specs/020-privacy-tier-routing/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/openreview_cli/gateway/
├── __init__.py          # Public exports (Gateway, TierRouter, etc.)
├── router.py            # Existing Gateway class — TierRouter wraps this
├── tier_router.py       # NEW: TierRouter — privacy enforcement layer; includes ProviderLocationClassifier as static method
├── tier_config.py       # NEW: TierConfig — reads/validates privacy.tier from config
├── registry.py          # Existing — may extend with is_local attribute
├── models.py            # Existing — may add PrivacyTier enum, TierReport dataclass
├── errors.py            # Existing — may add TierRoutingError, PIIBlockedError
└── cost.py              # Existing — unchanged

src/openreview_cli/pii/
├── __init__.py          # Public exports — add is_available() function
├── engine.py            # Existing — add is_available() method to PiiEngine
└── ...

tests/
├── unit/
│   ├── test_tier_router.py        # NEW: TierRouter unit tests (includes ProviderLocationClassifier tests)
│   └── test_tier_config.py        # NEW: TierConfig parsing/validation
│   └── test_gateway_router.py     # Existing — may need updates
├── integration/
│   ├── test_privacy_tier.py       # NEW: tier routing integration with mocked providers
│   ├── test_privacy_tier_pii.py   # NEW: PII failure scenarios
│   └── test_no_pii_flag.py        # Existing — may need updates for tier interaction
└── fixtures/
    ├── config_tier_maximum.yml    # NEW
    ├── config_tier_balanced.yml   # NEW
    └── config_tier_performance.yml # NEW
```

**Structure Decision**: Single project (DEFAULT) — no new packages. Router lives alongside existing Gateway at `src/openreview_cli/gateway/`. All new source: 4 files. All new tests: 4 files. Test fixtures: 3 config YAMLs. ProviderLocationClassifier is a static method on TierRouter, not a standalone file.

## Complexity Tracking

No constitution violations — no complexity justification needed.

Source tree is flat (one level under `gateway/`). No new abstractions beyond what the spec defines (TierRouter, TierConfig, PrivacyTierReport). ProviderLocationClassifier lives as a static method inside TierRouter.
