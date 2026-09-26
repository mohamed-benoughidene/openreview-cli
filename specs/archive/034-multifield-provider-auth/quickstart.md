# Quickstart — Spec 034 Multi-Field Provider Credential Support

Phase 1 output. Runnable validation proving the feature works end-to-end.
References `./data-model.md` and `./contracts/`.

## Prerequisites

- Repo on `feat/034-multifield-provider-auth`, `uv` installed.
- No new dependency; `pydantic`, `typer`, `litellm` already present.
- Optional: real AWS / GCP / Azure creds for live path (else skipped).

## Setup

```bash
uv sync
uv run pre-commit run --all-files   # ruff, ruff-format, mypy --strict, pytest-fast
```

## Validation Scenarios

### 1. Backward compatibility — single-key provider loads unchanged (FR-2)
```bash
uv run pytest tests/unit/test_gateway_registry.py -q
```
Assert `load_registry()` returns e.g. `openai` with `credentials == []` and `env_key`
intact; a model call via existing single-key path still works (existing tests green).

### 2. CredentialField + ProviderInfo model (FR-1)
New `tests/unit/test_gateway_models.py`:
- `ProviderInfo(credentials=[CredentialField(env_key="X", label="x", litellm_param="y")])`
  constructs; `model_dump()` includes `credentials`.
- A `ProviderInfo` serialized WITHOUT `credentials` re-loads with `credentials == []`
  (backward compat proven).

### 3. `_get_litellm_kwargs` maps fields (FR-3)
Extend `tests/unit/test_gateway_router.py`: with a fake provider whose `credentials`
include `aws_region_name`, set `AWS_REGION_NAME=us-east-1` in env, call
`_get_litellm_kwargs(slot)` and assert `kwargs["aws_region_name"] == "us-east-1"`.
Single-key provider → no extra kwargs (FR-2).

### 4. Per-field health + `--json` (FR-4)
`tests/unit/test_gateway_cli.py` (or app tests): with partial env set, assert
`gateway providers --json` emits `credentials` list with correct `resolved` flags and
`configured=false` until all required resolve. `secret=true` values absent from JSON.

### 5. Wizard / `provider add` collects N fields (FR-5)
Unit: invoke `gateway provider add bedrock --cred AWS_REGION_NAME=us-east-1 ...`
(capture stdout / monkeypatch `auth.json` write) and assert `auth.json` holds the
mapping. Wizard: questionary loop mocked, asserts per-field prompts + file-path check
for Vertex ADC.

### 6. Live provider call (FR-6, integration, optional)
```bash
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION_NAME=... \
  uv run pytest tests/integration/test_provider_live.py -q
```
Skipped without creds (guard like `test_grounding_live.py`). With creds: a Bedrock
`Gateway.chat` succeeds and the kwargs carried `aws_region_name` etc. (proves FR-3+FR-6).

### 7. Vertex file-path validation (FR-7)
Unit: wizard/path validation rejects a non-existent `GOOGLE_APPLICATION_CREDENTIALS`
path; accepts an existing readable file.

## Expected Outcomes Summary
- `ProviderInfo.credentials` added; single-key providers untouched.
- `_get_litellm_kwargs` injects per-field litellm kwargs.
- `gateway providers --json` + TUI show per-field status; secrets redacted.
- Wizard/`provider add` collect N fields; Vertex path validated.
- 3 registry entries (bedrock/vertex/azure) load + report health.
- Pre-commit green; no new dependency.
