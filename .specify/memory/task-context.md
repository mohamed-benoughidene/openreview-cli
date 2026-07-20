# Task Context (Spec 034 — Multi-Field Provider Credential Support)

Generated per task-grounding hook intent (verified-sources.md already present from
the plan step). Grounded against the real filesystem.

## Verified Dependencies
- litellm | VERSION: v1.81.x | SOURCE: Context7 /berriai/litellm (CONFIRMED: bedrock aws_*, vertex_*, azure api_base kwargs)
- pydantic | VERSION: v2 | SOURCE: Context7 /pydantic/pydantic (CONFIRMED: default-field backward compat)
- typer | VERSION: 0.21.x | SOURCE: Context7 /websites/typer_tiangolo (CONFIRMED: list-option repeatable)

## Project Structure (actual)
```
src/openreview_cli/
├── gateway/
│   ├── models.py          EXISTS
│   ├── router.py          EXISTS
│   ├── registry.py        EXISTS
│   ├── models.json        EXISTS
│   └── wizard.py          EXISTS
├── config/
│   └── loader.py          EXISTS
└── app.py                 EXISTS

tests/unit/
├── test_gateway_models.py     EXISTS
├── test_gateway_router.py     EXISTS
└── test_gateway_registry.py   EXISTS
```

## Existing Files
- src/openreview_cli/gateway/models.py — ProviderInfo at :17, Capability at :9
- src/openreview_cli/gateway/router.py — _get_litellm_kwargs at :186 (api_base/base_url)
- src/openreview_cli/gateway/registry.py — load_registry()
- src/openreview_cli/gateway/models.json — bundled providers
- src/openreview_cli/gateway/wizard.py — questionary wizard
- src/openreview_cli/config/loader.py — auth store (auth.json)
- src/openreview_cli/app.py — gateway_providers at :1346
- tests/unit/test_gateway_models.py, test_gateway_router.py, test_gateway_registry.py — exist

## Plan vs Filesystem
- plan.md references: gateway/models.py, gateway/router.py, gateway/registry.py,
  gateway/models.json, config/loader.py, app.py, gateway/wizard.py — ALL EXIST.
- tests referenced: tests/unit/test_gateway_models.py, test_gateway_router.py,
  test_gateway_registry.py, tests/integration/test_provider_live.py — first three
  EXIST; test_provider_live.py is NEW (to be created).
- No MISMATCH. All plan paths resolve to real files.

## Notes
- No new dependencies required (litellm/pydantic/typer already installed).
- TDD applies per repo AGENTS.md convention; test tasks included.
