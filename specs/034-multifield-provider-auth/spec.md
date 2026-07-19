# Spec 034 — Multi-Field Provider Credential Support

**Status:** Draft (mini-spec). Follow-up to `033-ai-gateway-v2`.
**Trigger:** Pick up only after `feat/ai-gateway-v2` merges to `main`.
**Do NOT** add Azure / AWS Bedrock / Google Vertex AI to the registry until
this spec is implemented. They are intentionally excluded from `033`.

## Problem

`ProviderInfo` (`src/openreview_cli/gateway/models.py:17-25`) models provider
auth as a single field:

```python
class ProviderInfo(BaseModel):
    env_key: str | None = None   # one env var
    auth_required: bool = True
    base_url: str | None = None
```

Three real providers cannot be expressed with one `env_key`:

| Provider | Required credentials (per litellm docs) | Why single `env_key` fails |
|----------|------------------------------------------|----------------------------|
| **Azure OpenAI** | `AZURE_OPENAI_ENDPOINT` (URL) + deployment name + `AZURE_OPENAI_KEY` | Needs endpoint + deployment, not just a key |
| **AWS Bedrock** | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_REGION_NAME` | 3-field AWS credential set |
| **Google Vertex AI** | `VERTEXAI_PROJECT` + `VERTEXAI_LOCATION` + `GOOGLE_APPLICATION_CREDENTIALS` | project + region + service-account path |

Forcing them into `env_key` would either break resolution or silently
mis-route the call. They were confirmed against litellm's docs during the
`033` provider-addition pass and deliberately left out.

## Proposed model extension (design to validate, not final)

Extend `ProviderInfo` with an ordered list of required credential fields
instead of (or in addition to) a single `env_key`:

```python
class CredentialField(BaseModel):
    env_key: str                 # e.g. "AWS_ACCESS_KEY_ID"
    label: str                   # human-facing, for the wizard
    secret: bool = True          # redact in logs / --json output
    required: bool = True

class ProviderInfo(BaseModel):
    ...
    # keep `env_key` for single-key providers (backward compatible)
    env_key: str | None = None
    # new: multi-field auth for cloud providers
    credentials: list[CredentialField] | None = None
```

Open questions to resolve during implementation:
- Does `base_url` stay a top-level field, or move under a credential/deployment
  concept (Azure needs both endpoint AND deployment name)?
- How does the TUI gateway health check (currently consults
  `os.environ.get(info.env_key)`) surface multi-field status? Each field
  resolved independently; provider healthy only if ALL required fields present.
- How does `add_custom_provider` / the wizard collect N fields? Today it takes
  one `--env-key`. Extend to `--cred env_key=LABEL` repeated, or a structured
  form.
- `Gateway` (`router.py:_get_litellm_kwargs`, line ~186) currently sets
  `api_base` from `info.base_url` and `api_key` from one key. Multi-field
  providers need each field mapped to the correct litellm param
  (e.g. `aws_region_name`, `vertex_project`, `api_base`). Map
  `CredentialField.env_key` → litellm kwarg by a `litellm_param` attribute.

## Scope guard

- This spec covers ONLY the registry/router/credential-model change needed to
  support multi-field providers. Adding the actual Azure/Bedrock/Vertex
  registry entries is a separate task that depends on this landing.
- No new dependencies. litellm already supports all three providers; this is
  purely our config/credential model catching up.

## Acceptance criteria (draft)

1. `ProviderInfo` accepts `credentials: list[CredentialField]`; single-key
   providers unchanged and still load from `env_key`.
2. A new provider with `credentials` (e.g. a Bedrock entry) loads via
   `load_registry()` and reports healthy only when all 3 env vars are set.
3. `Gateway` maps each credential field to the correct litellm kwarg and makes
   a real call (verified with a live test where creds exist, skipped otherwise
   — same pattern as `tests/integration/test_grounding_live.py`).
4. TUI health check + CLI `gateway providers --json` show per-field status.
5. mypy --strict, ruff, existing unit suite green; new unit + integration
   tests added per provider.

## Out of scope

- Whether to default these providers on or leave opt-in.
- Cost tracking differences (Bedrock/Vertex billing differs from per-token).
- Any change to the privacy-tier model.
