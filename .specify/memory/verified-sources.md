# Verified Sources — AI Gateway (Phase 4)

**Generated**: 2026-07-01
**Feature**: specs/005-ai-gateway

## Dependencies

ITEM: litellm
SOURCE: https://github.com/berriai/litellm | https://pypi.org/project/litellm/
VERSION: 1.81.9-stable (latest stable as of 2026-06-30)
KEY FACTS:
- `litellm.completion(model="provider/model", messages=[...])` — unified chat completion
- `litellm.embedding(model="provider/model", input=[...])` — unified embedding
- `litellm.rerank(model="provider/model", query=..., documents=[...], top_n=N)` — unified rerank
- `litellm.completion_cost(response)` — returns cost in USD from response object
- Response object contains `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`
- Ollama models prefixed `ollama/model_name`, api_base defaults to `http://localhost:11434`
- Supports `fallbacks` parameter for automatic model fallback
- Environment variables: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, etc.
STATUS: CONFIRMED

ITEM: httpx
SOURCE: https://pypi.org/project/httpx/
VERSION: >=0.28.1 (pinned in pyproject.toml)
KEY FACTS:
- Already a runtime dependency, used for HTTP requests
- Used by the registry refresh to fetch models.json from GitHub
STATUS: CONFIRMED

ITEM: pydantic
SOURCE: https://pypi.org/project/pydantic/
VERSION: >=2.13.4 (pinned in pyproject.toml)
KEY FACTS:
- Already a runtime dependency
- Used extensively in config/loader.py for GatewayConfig, ModelSlot, etc.
- BaseModel with field_validator for config validation
STATUS: CONFIRMED

ITEM: typer
SOURCE: https://pypi.org/project/typer/
VERSION: >=0.26.7 (pinned in pyproject.toml)
KEY FACTS:
- Already a runtime dependency
- CLI framework, used for all subcommands in app.py
- Supports nested Typer apps (client_app, config_app, pii_app already exist)
STATUS: CONFIRMED

ITEM: rich
SOURCE: https://pypi.org/project/rich/
VERSION: >=15.0.0 (pinned in pyproject.toml)
KEY FACTS:
- Already a runtime dependency
- Used for Table output in CLI commands
- Console() for styled output
STATUS: CONFIRMED

ITEM: PyYAML
SOURCE: https://pypi.org/project/pyyaml/
VERSION: >=6.0.3 (pinned in pyproject.toml)
KEY FACTS:
- Already a runtime dependency
- Used in config/loader.py for yaml.safe_load / yaml.safe_dump
STATUS: CONFIRMED

ITEM: platformdirs
SOURCE: https://pypi.org/project/platformdirs/
VERSION: >=4.10.0 (pinned in pyproject.toml)
KEY FACTS:
- Already a runtime dependency
- Used in config/paths.py for user_config_dir, user_data_dir, user_log_dir
STATUS: CONFIRMED

ITEM: sqlite3
SOURCE: Python stdlib
VERSION: Built-in (Python 3.12)
KEY FACTS:
- Used in storage/database.py for all DB operations
- WAL mode, foreign keys enabled
- cost_logs table already exists in 001_initial.sql
STATUS: CONFIRMED

## Existing Infrastructure (from codebase scan)

ITEM: config/loader.py GatewayConfig
SOURCE: src/openreview_cli/config/loader.py
VERSION: N/A (local code)
KEY FACTS:
- GatewayModels Pydantic model already defines 5 slots: reasoning, extraction, embedding, reranking, graph
- ModelSlot has primary, fallback, params (temperature, max_tokens)
- EmbeddingSlot and RerankingSlot are simpler (primary only)
- FallbackConfig has retries, retry_delay, timeout, on_failure
- CostLimits has per_review_cents, daily_cents
- model_registry_refresh_days = 7
STATUS: CONFIRMED

ITEM: config/auth.py
SOURCE: src/openreview_cli/config/auth.py
VERSION: N/A (local code)
KEY FACTS:
- load_auth() reads auth.json, overlays env vars
- key_to_env() maps provider names to env var names (openai→OPENAI_API_KEY, etc.)
- ensure_auth() creates auth.json with 600 permissions
- _check_permissions() warns and fixes world-readable auth.json
STATUS: CONFIRMED

ITEM: storage/database.py cost_logs
SOURCE: src/openreview_cli/storage/database.py
VERSION: N/A (local code)
KEY FACTS:
- log_cost() inserts into cost_logs table
- check_daily_limit() sums cost_cents for today
- check_review_limit() sums cost_cents for a review_id
- cost_logs schema: id, review_id, model, provider, prompt_tokens, completion_tokens, cost_cents, created_at
STATUS: CONFIRMED

ITEM: config/paths.py
SOURCE: src/openreview_cli/config/paths.py
VERSION: N/A (local code)
KEY FACTS:
- get_config_dir() → ~/.config/openreview/ (via platformdirs)
- get_data_dir() → user data dir
- get_log_dir() → user log dir
STATUS: CONFIRMED
