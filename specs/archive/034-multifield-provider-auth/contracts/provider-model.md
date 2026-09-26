# Contract — Provider Credential Model (Spec 034)

Phase 1 output. The pydantic + registry contract.

## `CredentialField` (new — gateway/models.py)

```python
from pydantic import BaseModel

class CredentialField(BaseModel):
    env_key: str
    label: str
    secret: bool = False
    required: bool = True
    litellm_param: str          # literal completion() kwarg, e.g. "aws_region_name"
    is_file_path: bool = False  # FR-7: validate path exists + readable
```

## `ProviderInfo` (extended — gateway/models.py:17)

```python
class ProviderInfo(BaseModel):
    name: str
    env_key: str | None = None          # legacy single-key (unchanged)
    auth_required: bool = True
    base_url: str | None = None         # KEEP top-level (Q1: Azure endpoint -> api_base)
    is_local: bool = False
    source: str = "bundled"
    capabilities: Capability = Capability()
    models: dict[str, ModelEntry] = {}
    credentials: list[CredentialField] = []   # NEW — backward compatible default
```

## `models.json` entry shape (new providers)

```json
{
  "bedrock": {
    "env_key": null,
    "base_url": null,
    "auth_required": true,
    "source": "bundled",
    "credentials": [
      {"env_key": "AWS_ACCESS_KEY_ID",      "label": "AWS Access Key",   "secret": true,  "required": true,  "litellm_param": "aws_access_key_id"},
      {"env_key": "AWS_SECRET_ACCESS_KEY",  "label": "AWS Secret Key",  "secret": true,  "required": true,  "litellm_param": "aws_secret_access_key"},
      {"env_key": "AWS_REGION_NAME",        "label": "AWS Region",      "secret": false, "required": true,  "litellm_param": "aws_region_name"}
    ],
    "models": { "bedrock/anthropic.claude-3-sonnet-...": { "slots": ["chat"], ... } }
  },
  "vertex": {
    "credentials": [
      {"env_key": "VERTEXAI_PROJECT",                  "label": "Project", "secret": false, "required": true, "litellm_param": "vertex_project"},
      {"env_key": "VERTEXAI_LOCATION",                "label": "Location", "secret": false, "required": true, "litellm_param": "vertex_location"},
      {"env_key": "GOOGLE_APPLICATION_CREDENTIALS",   "label": "ADC Path", "secret": false, "required": true, "litellm_param": "vertex_location", "is_file_path": true}
    ]
  },
  "azure": {
    "base_url": "<endpoint>",   # -> api_base (Q1)
    "credentials": [
      {"env_key": "AZURE_OPENAI_KEY", "label": "Key", "secret": true, "required": true, "litellm_param": "api_key"},
      {"env_key": "AZURE_API_VERSION", "label": "API Version", "secret": false, "required": false, "litellm_param": "api_version"}
    ]
  }
}
```

## `Gateway._get_litellm_kwargs` mapping contract (router.py:186)

Pseudocode addition (FR-3), appended after existing `api_base`/`api_key` logic:

```python
info = self._resolve_provider_info(slot)
if info is not None:
    for field in info.credentials:                       # no-op for single-key (empty list)
        value = os.environ.get(field.env_key) or self._auth.get(info.name, {}).get(field.env_key)
        if value:
            kwargs[field.litellm_param] = value
```

Single-key providers: `info.credentials == []` → loop skipped → unchanged behavior (FR-2).
