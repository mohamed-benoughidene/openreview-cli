# Verified Sources — 006-slm-model-params

**Generated**: 2026-07-01

## Dependencies

ITEM: LiteLLM
SOURCE: https://docs.litellm.ai/docs/completion/provider_specific_params
VERSION: 1.90.1 (installed)
KEY FACTS:
- LiteLLM forwards any non-OpenAI parameter as a provider-specific kwarg to the underlying provider
- Ollama provider supported — uses `ollama/` prefix (e.g. `ollama/llama2`)
- Provider-specific params work via SDK, YAML config, and `extra_body` in proxy mode
- `completion(**kwargs)` signature accepts arbitrary kwargs and routes them through
- Embedding function follows the same pattern
STATUS: CONFIRMED

ITEM: Pydantic
SOURCE: https://docs.pydantic.dev/latest/
VERSION: 2.13.4 (installed)
KEY FACTS:
- `dict[str, Any]` fields supported natively in BaseModel
- Optional fields with `None` default via `field: dict[str, Any] | None = None`
- Nested dicts serialize/deserialize correctly via JSON
STATUS: CONFIRMED

ITEM: Python stdlib logging
SOURCE: https://docs.python.org/3.12/library/logging.html
VERSION: Python 3.12.3 (stdlib)
KEY FACTS:
- `logger.debug()` and `logger.warning()` are the methods needed
- No new imports required — already used in `router.py`
STATUS: CONFIRMED
