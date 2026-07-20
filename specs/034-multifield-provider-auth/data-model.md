# Data Model — Spec 034 Multi-Field Provider Credential Support

Phase 1 output. Entities derived from `./spec.md` + grounded code
(`gateway/models.py`, `gateway/router.py`, `app.py`, `config/loader.py`).

## Entities

### `CredentialField` (new pydantic model)

| Field | Type | Notes |
|-------|------|-------|
| env_key | `str` | Environment variable name (e.g. `AWS_REGION_NAME`, `GOOGLE_APPLICATION_CREDENTIALS`). |
| label | `str` | Human label for wizard / `--cred` prompt. |
| secret | `bool` | True → value treated as secret (stored in `auth.json` 600, redacted in JSON output). |
| required | `bool` | True → provider "configured" only if this field resolves. |
| litellm_param | `str` | The literal litellm completion() kwarg name (`aws_region_name`, `vertex_project`, `vertex_location`, `api_version`). Mapped in `_get_litellm_kwargs`. |
| is_file_path | `bool` | True → value is a filesystem path; wizard validates existence + readability (FR-7). |

### `ProviderInfo` (extended)

| Field | Type | Change |
|-------|------|--------|
| name, env_key, auth_required, base_url, is_local, source, capabilities, models | unchanged | — |
| credentials | `list[CredentialField]` | **NEW**, default `[]`. Backward compatible: existing `models.json` entries omit it and load fine (pydantic v2 default). |

**Backward compatibility (FR-2):** single-key providers (openai, anthropic, deepseek,
qwen, minimax, voyage, moonshot, mistral, zai, ...) keep `env_key` only; `credentials=[]`
→ no behavioral change. Confirmed by pydantic v2 default-field semantics (Context7).

## Relationships

- `ProviderInfo.credentials` → list of `CredentialField`. 1:N.
- `CredentialField.litellm_param` → the kwarg key set on the litellm `completion()` call
  in `Gateway._get_litellm_kwargs`.
- `CredentialField.env_key` → resolved value source: `os.environ.get(env_key)` then
  `auth[provider_name][env_key]` (the `auth.json` mapping, mode 600).

## Validation Rules (from spec requirements)

- A provider is "configured" (FR-4) iff every `CredentialField` with `required=True`
  resolves to a non-empty value. Single-key providers: configured iff `env_key` resolves
  (unchanged).
- `is_file_path=True` fields must point to an existing, readable file at collection time
  (wizard) and ideally at resolution time (warn if missing).
- `secret=True` values MUST NOT appear in `gateway providers --json` output (redact to
  `"***"`), per constitution Principle I (no secret leakage in logs/JSON).
- `litellm_param` values must match real litellm kwargs: confirmed set =
  `{aws_access_key_id, aws_secret_access_key, aws_region_name, vertex_project,
  vertex_location, api_version}` (+ existing `api_base`, `api_key`).

## State Transitions

None new at runtime. Configuration state is read-only resolution:
`env/store → resolved value → kwarg injection`. The only structural transition is the
`ProviderInfo` schema gaining an optional list — no migration, no data loss (models.json
entries simply gain a `credentials` key for the 3 new providers).
