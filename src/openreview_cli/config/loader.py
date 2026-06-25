import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, object] = {
    "version": 1,
    "privacy": {
        "tier": "balanced",
        "strip_pii": True,
        "log_ttl_days": 30,
    },
    "gateway": {
        "models": {
            "reasoning": {
                "primary": "ollama/qwen3:8b",
                "fallback": None,
                "params": {"temperature": 0.1, "max_tokens": 4000},
            },
            "extraction": {
                "primary": "ollama/qwen3:4b",
                "fallback": None,
                "params": {"temperature": 0.0, "max_tokens": 2000},
            },
            "embedding": {
                "primary": "ollama/nomic-embed-text",
            },
            "reranking": {
                "primary": "ollama/qwen3-reranker-0.6b",
            },
            "graph": {
                "primary": "ollama/qwen3:8b",
                "fallback": None,
                "params": {"temperature": 0.0, "max_tokens": 4000},
            },
        },
        "fallback": {
            "retries": 2,
            "retry_delay": 1.0,
            "timeout": 60,
            "on_failure": "error",
        },
        "cost_limits": {
            "per_review_cents": 100,
            "daily_cents": 1000,
        },
        "model_registry_refresh_days": 7,
    },
    "storage": {
        "reviews_keep_forever": True,
        "logs_keep_days": 30,
    },
}


def _env_to_config_path(env_key: str) -> str | None:
    suffix = env_key[len("OPENREVIEW_") :].lower()
    if "__" in suffix:
        return ".".join(suffix.split("__"))
    return suffix.replace("_", ".")


def _get_env_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    prefix = "OPENREVIEW_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        config_key = _env_to_config_path(key)
        if not config_key:
            continue
        parts = config_key.split(".")
        d = overrides
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = _parse_value(value)
    return overrides


def _validate_and_merge(raw: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    from pydantic import BaseModel, field_validator

    _valid_tiers = frozenset({"maximum", "balanced", "performance"})
    _valid_on_failure = frozenset({"error", "skip", "warn"})

    class ModelParams(BaseModel):
        temperature: float = 0.1
        max_tokens: int = 4000

    class ModelSlot(BaseModel):
        primary: str
        fallback: str | None = None
        params: ModelParams | None = None

    class EmbeddingSlot(BaseModel):
        primary: str

    class RerankingSlot(BaseModel):
        primary: str

    class GatewayModels(BaseModel):
        reasoning: ModelSlot = ModelSlot(
            primary="ollama/qwen3:8b", params=ModelParams(temperature=0.1, max_tokens=4000)
        )
        extraction: ModelSlot = ModelSlot(
            primary="ollama/qwen3:4b", params=ModelParams(temperature=0.0, max_tokens=2000)
        )
        embedding: EmbeddingSlot = EmbeddingSlot(primary="ollama/nomic-embed-text")
        reranking: RerankingSlot = RerankingSlot(primary="ollama/qwen3-reranker-0.6b")
        graph: ModelSlot = ModelSlot(
            primary="ollama/qwen3:8b", params=ModelParams(temperature=0.0, max_tokens=4000)
        )

    class FallbackConfig(BaseModel):
        retries: int = 2
        retry_delay: float = 1.0
        timeout: int = 60
        on_failure: str = "error"

        @field_validator("on_failure")
        @classmethod
        def _check_on_failure(cls, v: str) -> str:
            if v not in _valid_on_failure:
                raise ValueError(f"must be one of: {', '.join(sorted(_valid_on_failure))}")
            return v

    class CostLimits(BaseModel):
        per_review_cents: int = 100
        daily_cents: int = 1000

        @field_validator("per_review_cents", "daily_cents")
        @classmethod
        def _check_positive(cls, v: int) -> int:
            if v < 1:
                raise ValueError("must be ≥ 1")
            return v

    class GatewayConfig(BaseModel):
        models: GatewayModels = GatewayModels()
        fallback: FallbackConfig = FallbackConfig()
        cost_limits: CostLimits = CostLimits()
        model_registry_refresh_days: int = 7

    class PrivacyConfig(BaseModel):
        tier: str = "balanced"
        strip_pii: bool = True
        log_ttl_days: int = 30

        @field_validator("tier")
        @classmethod
        def _check_tier(cls, v: str) -> str:
            if v not in _valid_tiers:
                raise ValueError(f"must be one of: {', '.join(sorted(_valid_tiers))}")
            return v

        @field_validator("log_ttl_days")
        @classmethod
        def _check_log_ttl(cls, v: int) -> int:
            if v < 1:
                raise ValueError("must be ≥ 1")
            return v

    class StorageConfig(BaseModel):
        reviews_keep_forever: bool = True
        logs_keep_days: int = 30

        @field_validator("logs_keep_days")
        @classmethod
        def _check_logs_keep(cls, v: int) -> int:
            if v < 1:
                raise ValueError("must be ≥ 1")
            return v

    class OpenReviewConfig(BaseModel):
        version: int = 1
        privacy: PrivacyConfig = PrivacyConfig()
        gateway: GatewayConfig = GatewayConfig()
        storage: StorageConfig = StorageConfig()

    merged = _deep_merge(defaults, raw)
    validated = OpenReviewConfig(**merged)
    return validated.model_dump()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _deep_get(d: dict[str, Any], key: str) -> Any:
    keys = key.split(".")
    value: Any = d
    for k in keys:
        if not isinstance(value, dict) or k not in value:
            raise KeyError(f"Unknown config key: {key}")
        value = value[k]
    return value


def _deep_set(d: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
    keys = key.split(".")
    obj = d
    for k in keys[:-1]:
        if k not in obj or not isinstance(obj[k], dict):
            obj[k] = {}
        obj = obj[k]
    obj[keys[-1]] = value
    return d


def _parse_value(value: str) -> Any:
    if value.lower() in ("true", "false", "null"):
        import yaml

        return yaml.safe_load(value)
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def get_config_value(config: dict[str, Any], key: str) -> Any:
    return _deep_get(config, key)


def set_config_value(config_path: Path, key: str, value: str) -> dict[str, Any]:
    import shutil

    import yaml

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    backup = config_path.with_suffix(".yml.bak")
    shutil.copy2(config_path, backup)

    typed = _parse_value(value)
    _deep_set(raw, key, typed)

    validated = _validate_and_merge(raw, dict(DEFAULT_CONFIG))

    with open(config_path, "w") as f:
        yaml.safe_dump(validated, f, default_flow_style=False)

    return validated


def load_config(config_path: Path) -> dict[str, Any]:
    import yaml

    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.safe_dump(DEFAULT_CONFIG, f, default_flow_style=False)
        return dict(DEFAULT_CONFIG)

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}
    env_overrides = _get_env_overrides()
    merged = _deep_merge(raw, env_overrides)
    return _validate_and_merge(merged, dict(DEFAULT_CONFIG))
