# Verified Sources (Spec 034 — Multi-Field Provider Credential Support)

Generated via Context7 (user-mandated up-to-date docs) + direct project-code grounding.
Sources fetched: litellm v1.81.x, pydantic v2, typer. Project code read:
gateway/models.py, gateway/router.py, app.py.

---

## ITEM: litellm — Bedrock kwargs
SOURCE: https://docs.litellm.ai/docs/providers/bedrock (Context7: /berriai/litellm v1.81.x)
VERSION: v1.81.x (stable)
KEY FACTS:
- Bedrock completion() accepts `aws_access_key_id`, `aws_secret_access_key`,
  `aws_region_name` as kwargs, OR reads env `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`.
- Model id form: `bedrock/<model-id>` (e.g. bedrock/anthropic.claude-3-sonnet-...).
- So CredentialField.litellm_param values for Bedrock = `aws_access_key_id`,
  `aws_secret_access_key`, `aws_region_name`.
STATUS: CONFIRMED

## ITEM: litellm — Vertex AI kwargs
SOURCE: https://docs.litellm.ai/docs/providers/vertex (Context7: /berriai/litellm)
VERSION: v1.81.x
KEY FACTS:
- Set via module-level `litellm.vertex_project` / `litellm.vertex_location`, OR
  per-call kwargs `vertex_project`, `vertex_location`.
- Requires Application Default Credentials (ADC); `GOOGLE_APPLICATION_CREDENTIALS`
  is the standard env path to the service-account JSON (a FILE PATH, not a secret
  string — matches spec FR-7 / Q3).
- CredentialField.litellm_param values for Vertex = `vertex_project`,
  `vertex_location`; the file-path credential maps to env
  `GOOGLE_APPLICATION_CREDENTIALS` (validated to exist on disk, FR-7).
STATUS: CONFIRMED

## ITEM: litellm — Azure OpenAI kwargs
SOURCE: https://docs.litellm.ai/docs/providers/azure (Context7: /berriai/litellm)
VERSION: v1.81.x
KEY FACTS:
- Azure completion() accepts `api_base` (endpoint URL), `api_version`,
  `azure_ad_token` / api_key. Model id form `azure/<deployment-name>`.
- `api_base` already populated by Gateway._get_litellm_kwargs from
  `info.base_url` (router.py:188-189). So Azure endpoint → base_url (top-level
  field, resolves Q1: keep base_url top-level). Deployment name → a credential
  field (`api_version` or a deployment param) OR part of model id.
STATUS: CONFIRMED

## ITEM: pydantic v2 — BaseModel field extension
SOURCE: https://docs.pydantic.dev/latest/concepts/models (Context7: /pydantic/pydantic)
VERSION: v2 (current)
KEY FACTS:
- Adding a new field `credentials: list[CredentialField] = []` to an existing
  BaseModel is fully backward compatible — existing serialized dicts lacking the
  key load fine (field takes default).
- `model_dump()` / `model_validate()` are the v2 API (renamed from dict()/parse_obj()).
- Defaults via direct assignment or `Field(default=...)`.
- Implication: extending ProviderInfo with `credentials` list does NOT break
  existing models.json load (FR-2). Single-key providers simply omit the key.
STATUS: CONFIRMED

## ITEM: typer — repeatable options (multiple --cred)
SOURCE: https://typer.tiangolo.com/tutorial/multiple-values/multiple-options
VERSION: typer 0.21.x (Context7: /websites/typer_tiangolo)
KEY FACTS:
- `Annotated[list[str] | None, typer.Option()] = None` collects repeated flag
  occurrences into a list. e.g. `--cred A=B --cred C=D` → ["A=B","C=D"].
- Callbacks (`typer.Option(callback=...)`) can parse/validate each value.
- Implication: FR-5 (`gateway provider add --cred env_key=LABEL` repeated) is
  directly supported by typer's list-option; no custom argparse needed.
STATUS: CONFIRMED

---

## PROJECT CODE GROUNDING (read, not fetched)
- `gateway/models.py:17-25` `ProviderInfo` — has `env_key`, `base_url`, `is_local`,
  `source`, `capabilities`, `models`. Target for `credentials: list[CredentialField]`.
- `gateway/router.py:186-203` `_get_litellm_kwargs` — sets `kwargs["api_base"]=info.base_url`
  and for custom providers injects `api_key` from `os.environ.get(info.env_key)`.
  FR-3: extend to also iterate `info.credentials` and set `kwargs[field.litellm_param] =
  os.environ.get(field.env_key)` (or from auth store).
- `app.py:1346-1384` `gateway_providers` — emits `api_key_env: p.env_key` (single).
  FR-4: emit per-field `credentials` list with resolved/status; "configured" only when
  all required fields resolve.
- `app.py` wizard (`gateway wizard`) uses questionary (per AGENTS.md) — FR-5 collects
  N fields; typer list-option pattern confirmed above applies to `gateway provider add`.
- `config/loader.py` — single-key providers store value in `auth.json` (mode 600) via
  `self._auth.get(info.name)`; FR-3 reads from same store for custom multi-field too.
STATUS: GROUNDED
