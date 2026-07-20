# Spec 034 — Multi-Field Provider Credential Support

## Context

`feat/ai-gateway-v2` shipped a unified provider registry
(`gateway/models.json` + `ProviderInfo` in `src/openreview_cli/gateway/models.py:17-25`).
It models provider auth as a single `env_key`:

```python
class ProviderInfo(BaseModel):
    env_key: str | None = None   # one env var
    auth_required: bool = True
    base_url: str | None = None
    is_local: bool = False
    source: str = "bundled"
    capabilities: Capability = Capability()
    models: dict[str, ModelEntry] = {}
```

Three real providers cannot be expressed with one `env_key`. Confirmed
against litellm docs during the `033` provider-addition pass:

| Provider | Required credentials (per litellm docs) | Why single `env_key` fails |
|----------|------------------------------------------|----------------------------|
| **Azure OpenAI** | `AZURE_OPENAI_ENDPOINT` (URL) + deployment name + `AZURE_OPENAI_KEY` | Needs endpoint + deployment, not just a key |
| **AWS Bedrock** | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_REGION_NAME` | 3-field AWS credential set |
| **Google Vertex AI** | `VERTEXAI_PROJECT` + `VERTEXAI_LOCATION` + `GOOGLE_APPLICATION_CREDENTIALS` | project + region + service-account path |

Forcing them into `env_key` would either break resolution or silently
mis-route the call, so they were deliberately excluded from `033`. This
spec extends the credential model so those three can be configured
without bending the single-key pattern.

## Goal

A user can configure Azure / Bedrock / Vertex via the existing
`gateway provider add` / wizard flow, with each credential field
validated and surfaced in health checks, using only litellm's existing
provider support (no new dependency).

## Functional Requirements

- **FR-1:** `ProviderInfo` accepts an ordered list of `CredentialField`
  (each with `env_key`, `label`, `secret` flag, `required` flag, and a
  `litellm_param` mapping) in addition to the legacy single `env_key`.
- **FR-2:** Single-key providers (openai, anthropic, deepseek, qwen,
  minimax, voyage, moonshot, mistral, zai, ...) load **unchanged** from
  `env_key` — fully backward compatible, no regression.
- **FR-3:** `Gateway._get_litellm_kwargs`
  (`src/openreview_cli/gateway/router.py`, ~line 186) maps each
  `CredentialField` to the correct litellm kwarg (e.g. `api_base`,
  `aws_region_name`, `vertex_project`, `vertex_location`) when the
  provider is invoked.
- **FR-4:** `gateway providers --json` (`app.py:1346`) and the TUI health
  check (currently `os.environ.get(info.env_key)`) report **per-field**
  status; a provider is "configured" only when ALL required fields
  resolve from the environment.
- **FR-5:** The wizard / `gateway provider add` collects N fields
  (repeated `--cred env_key=LABEL`, or a structured form), validating
  presence for each required field.
- **FR-6:** A Bedrock (and separately Vertex, Azure) entry added to
  `models.json` loads via `load_registry()` and is healthy only when its
  required env vars are set; a live call through `Gateway` with those
  providers succeeds — verified with a real key, skipped otherwise (same
  guard pattern as `tests/integration/test_grounding_live.py`).
- **FR-7:** `GOOGLE_APPLICATION_CREDENTIALS` is a **file path**, not a
  secret string; when collected by the wizard it is validated to exist
  on disk and be readable (open question Q2).

## Constraints

- No new dependencies. litellm already supports all three providers;
  this is our config/credential model catching up.
- Single-key providers untouched; existing unit + integration suites
  stay green.
- `mypy --strict`, `ruff`, pre-commit all pass.
- Local-only CLI; no web server (per repo constitution).

## Out of Scope

- Defaulting these providers on vs. leaving them opt-in.
- Cost-tracking differences (Bedrock/Vertex billing ≠ per-token).
- Any change to the privacy-tier model.
- Adding the actual Azure/Bedrock/Vertex registry entries is a task
  that **depends on** this model change landing first.

## Open Questions (decision gates — resolve during planning)

- **Q1:** Does `base_url` stay a top-level `ProviderInfo` field, or move
  under a credential/deployment concept (Azure needs both endpoint AND
  deployment name)?
- **Q2:** Where do multi-field credential *values* get stored — env vars
  only (like today's single `env_key` providers), or also a fallback
  file such as the `auth.json` that existing single-key providers use?
- **Q3:** `GOOGLE_APPLICATION_CREDENTIALS` is a file path, not a secret
  string. Should the wizard validate the file actually exists (and is
  readable) when collecting it, rather than just storing the path?
- **Q4:** How does `add_custom_provider` / the wizard collect N fields?
  Extend to `--cred env_key=LABEL` repeated, or a structured form?
- **Q5:** `CredentialField.env_key` → litellm kwarg mapping attribute
  name (e.g. `litellm_param`).

## Success Criteria

1. `ProviderInfo` accepts `credentials: list[CredentialField]`; single-key
   providers unchanged and still load from `env_key` (FR-1, FR-2).
2. A new provider with `credentials` (e.g. a Bedrock entry) loads via
   `load_registry()` and reports healthy only when all required env vars
   are set (FR-4, FR-6).
3. `Gateway` maps each credential field to the correct litellm kwarg and
   makes a real call (FR-3, FR-6) — verified with a live test where
   creds exist, skipped otherwise.
4. TUI health check + CLI `gateway providers --json` show per-field
   status (FR-4).
5. mypy --strict, ruff, existing unit suite green; new unit + integration
   tests added per provider (FR-6).
