# Implementation Plan: 034 — Multi-Field Provider Credential Support

**Branch**: `feat/034-multifield-provider-auth` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `./spec.md`

## Summary

`feat/ai-gateway-v2` models provider auth as a single `env_key`. Azure / AWS
Bedrock / Google Vertex need multiple credential fields simultaneously, so they
were excluded from `033`. This spec extends `ProviderInfo` with an ordered
`credentials: list[CredentialField]` (each carrying `env_key`, `label`, `secret`,
`required`, `litellm_param`, `is_file_path`) while keeping single-key providers
loading unchanged from `env_key` (backward compatible). `Gateway._get_litellm_kwargs`
maps each field to its litellm kwarg (e.g. `aws_region_name`, `vertex_project`);
`gateway providers --json` and the TUI report per-field status; the wizard collects
N fields. No new dependency — litellm already supports all three providers.

## Technical Context

**Language/Version**: Python 3.12 (fixed by constitution Constraint).

**Primary Dependencies**: `pydantic` v2 (existing), `typer` 0.21.x (existing), `litellm` v1.81.x (existing). **No new dependency.**

**Storage**: `auth.json` (mode 600) extended to a per-provider field mapping; `models.json` gains Bedrock / Vertex / Azure entries with `credentials` lists. SQLite unchanged.

**Testing**: `pytest` — unit (`ProviderInfo` loads with/without `credentials`; `_get_litellm_kwargs` maps fields; per-field health logic) + integration live guard (skipped without real creds, same pattern as `tests/integration/test_grounding_live.py`).

**Target Platform**: local CLI (Linux/macOS/Windows), Principle II.

**Project Type**: CLI tool (`openreview` command), package `openreview_cli`.

**Performance Goals**: no regression; credential resolution is O(fields), trivial cost.

**Constraints**: peak memory <100 MB (N/A — no bulk load); pre-commit (ruff, ruff-format, mypy --strict, pytest-fast) must pass; no new deps; Python ≥3.12.

**Scale/Scope**: 2 pydantic models (`CredentialField`, `ProviderInfo.credentials`); registry 3 entries; `_get_litellm_kwargs` loop; `gateway providers --json` + TUI per-field; wizard loop; `auth.json` mapping; tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Justification |
|-----------|---------|---------------|
| I. Privacy First | Pass | `auth.json` stays mode 600; file-path creds (Vertex) are validated not stored as secrets; no PII/log change. |
| II. Local-First, CLI-Only | Pass | Pure local config/CLI change; no server, no network at config time. |
| III. Hardware-Bounded | Pass | No bulk in-memory load; credential resolution is O(fields). |
| IV. Dependency Minimalism | Pass | No new dependency; reuses pydantic/typer/litellm + existing `auth.json` store. |
| V. Spec-Driven, YAGNI | Pass | Smallest change: one list field + loop; no new abstraction layer. |
| Constraints (Python/uv/AGPL) | Pass | No version bump, no new dep, license unchanged. |
| Dev Workflow (pre-commit/CI) | Pass | ruff/mypy/pytest all must stay green; new unit + integration tests added. |

No violations → gate passes. Re-checked post-design: unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/034-multifield-provider-auth/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (ProviderInfo + CLI contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
src/openreview_cli/
├── gateway/
│   ├── models.py            # + CredentialField; ProviderInfo.credentials: list[...]
│   ├── router.py            # _get_litellm_kwargs: map each credential field -> litellm kwarg
│   ├── registry.py          # load_registry reads credentials list (unchanged API)
│   └── models.json          # + bedrock / vertex / azure entries with credentials
├── config/
│   └── loader.py            # auth store: per-provider field mapping in auth.json
├── app.py                   # gateway providers --json: per-field status; gateway provider add --cred (repeatable)
└── gateway/wizard.py        # questionary loop over provider.credentials (file-path validation)

tests/
├── unit/
│   ├── test_gateway_models.py        # NEW: CredentialField + ProviderInfo backward compat
│   ├── test_gateway_router.py        # extend: _get_litellm_kwargs maps fields
│   └── test_gateway_registry.py      # bedrock/vertex/azure load + health
└── integration/
    └── test_provider_live.py         # NEW: live call w/ real creds, skipped otherwise
```

**Structure Decision**: Single project (CLI). Changes confined to the gateway credential
model + registry + CLI/TUI surfacing + auth store. No new package, no server.

## Complexity Tracking

> None — Constitution Check has no violations requiring justification.
