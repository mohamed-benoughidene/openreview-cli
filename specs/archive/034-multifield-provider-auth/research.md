# Research — Spec 034 Multi-Field Provider Credential Support

Phase 0 output. All claims reference `verified-sources.md` (CONFIRMED) + direct code reads.

## Resolved Clarifications (from spec Q1–Q5)

### Q1 — Keep `base_url` top-level or move under credential/deployment concept?
**Decision: KEEP `base_url` as a top-level `ProviderInfo` field.**
- Grounded: `Gateway._get_litellm_kwargs` already maps `info.base_url → kwargs["api_base"]`
  (router.py:188-189). Azure's endpoint URL is exactly `api_base` — confirmed by
  litellm Azure docs (Context7). So `base_url` stays for the endpoint.
- Azure additionally needs a deployment name + api_version. Those become
  `CredentialField` entries (e.g. `litellm_param="api_version"`) rather than
  restructuring `base_url`. Azure deployment name can also live in the model id
  (`azure/<deployment>`), so it does not need a separate credential field unless
  the user wants it configurable. Decision: deployment name stays in model id;
  `api_version` is an optional credential field.
- No schema restructure → smallest change (Constitution Principle V).

### Q2 — Where do multi-field credential *values* get stored?
**Decision: BOTH env vars and `auth.json` fallback (same as today's single-key).**
- Grounded: single-key providers already resolve value via
  `os.environ.get(info.env_key) or self._auth.get(info.name)` (router.py:198-200).
  `auth.json` is mode 600, the existing secure store (constitution Principle I).
- For multi-field: store a flat mapping in `auth.json` under the provider name:
  `{provider: {env_key_1: value_1, env_key_2: value_2, ...}}`. Resolution order
  per field: `os.environ.get(field.env_key)` then `auth[provider][field.env_key]`.
- No new storage mechanism; reuses `self._auth`. Satisfies "no new dependency".

### Q3 — Validate `GOOGLE_APPLICATION_CREDENTIALS` as a file path?
**Decision: YES — validate existence + readability at collection time (FR-7).**
- Grounded: litellm Vertex uses Application Default Credentials; the env var is a
  FILE PATH to a service-account JSON (Context7 Vertex docs). Storing/validating
  the path is correct; the file content is NOT a secret string we hold.
- Wizard: when a `CredentialField` is marked `is_file_path=True`, run
  `os.path.isfile(value) and os.access(value, os.R_OK)`; reject otherwise.
- Q3 resolved as: yes, validate on disk.

### Q4 — How does `gateway provider add` / wizard collect N fields?
**Decision: typer repeatable `--cred env_key=LABEL` (list option) + questionary in wizard.**
- Grounded: typer supports `Annotated[list[str] | None, typer.Option()] = None`
  collecting repeated flags into a list (Context7 typer docs). `--cred A=B --cred C=D`
  → parse `key=value` pairs.
- Wizard (questionary) iterates `provider.credentials` and prompts per field,
  applying the `is_file_path` check from Q3. Reuses existing wizard infra
  (AGENTS.md: `gateway/wizard.py` is questionary-based).
- Q4 resolved: repeated `--cred` for CLI; per-field prompts for wizard.

### Q5 — `CredentialField.env_key` → litellm kwarg mapping attribute name?
**Decision: attribute name = `litellm_param`** (holds the literal litellm kwarg:
`aws_region_name`, `vertex_project`, `vertex_location`, `api_version`, etc.).
- Grounded: the literal litellm completion() kwargs are exactly those names
  (Context7 Bedrock/Vertex/Azure docs). `litellm_param` is the clearest mapping
  key; `_get_litellm_kwargs` sets `kwargs[field.litellm_param] = value`.
- Q5 resolved: `litellm_param`.

## Technical Context Resolutions (plan.md NEEDS CLARIFICATION → filled)

- **Language/Version**: Python 3.12 (fixed, constitution Constraint).
- **Primary Dependencies**: `pydantic` v2 (existing), `typer` 0.21.x (existing),
  `litellm` v1.81.x (existing). No new dependency.
- **Storage**: `auth.json` (mode 600) extended to hold per-provider field mapping;
  `models.json` gains Bedrock/Vertex/Azure entries with `credentials` lists.
- **Testing**: `pytest` — unit (ProviderInfo loads with/without credentials;
  `_get_litellm_kwargs` maps fields; per-field health) + integration live guard
  (skipped without real creds, mirroring `test_grounding_live.py`).
- **Target Platform**: local CLI (Principle II).
- **Project Type**: CLI tool, package `openreview_cli`.
- **Performance Goals**: no regression; credential resolution is O(fields), trivial.
- **Constraints**: peak memory <100 MB (N/A — no bulk); pre-commit green; no new deps.
- **Scale/Scope**: `ProviderInfo` + `CredentialField` models; registry 3 entries;
  `_get_litellm_kwargs` loop; `gateway providers --json` + TUI per-field; wizard
  loop; `auth.json` mapping; tests.

## Grounding Flow (verified)
`Gateway._get_litellm_kwargs(slot)` → `_resolve_provider_info(slot)` → `info: ProviderInfo`.
Current: sets `api_base` from `base_url`, `api_key` for custom. FR-3 adds: for each
`field in info.credentials`, `kwargs[field.litellm_param] = _resolve_field(field)`
where `_resolve_field` checks env then auth store. Single-key providers have empty
`credentials` → loop is a no-op → fully backward compatible (FR-2).

## Open implementation details (tasks will resolve)
- Exact `models.json` shape for the 3 entries (deployment name in model id vs field).
- Whether `CredentialField.is_file_path` is part of the model or a registry annotation.
  Recommend: part of `CredentialField` (cleanest; wizard + validator both read it).
- `gateway providers --json` output key rename from `api_key_env` to include
  `credentials: [{env_key, label, resolved, required}]`.
