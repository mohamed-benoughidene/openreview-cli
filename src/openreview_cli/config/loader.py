import os
from pathlib import Path
from typing import Any, Literal

DEFAULT_CONFIG: dict[str, object] = {
    "version": 1,
    "privacy": {
        "tier": "balanced",
        "strip_pii": True,
        "log_ttl_days": 30,
        "pii_threshold": 0.7,
        "pii_encryption_key": "12345678901234561234567890123456",
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
            "grounding": {
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
    "retrieval": {
        "default_method": "hybrid",
        "top_k": 5,
        "rrf_k": 60,
        "embedding_model": "nomic-embed-text",
        "embedding_dimension": 1024,
        "reranker_model": None,
        "rerank_enabled": False,
        "rerank_depth": 20,
        "db_dir": None,
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
    from pydantic import BaseModel, Field, field_validator

    class ModelParams(BaseModel):
        temperature: float = 0.1
        max_tokens: int = 4000

    class ModelSlot(BaseModel):
        primary: str
        fallback: str | None = None
        params: ModelParams | None = None
        extra_params: dict[str, Any] | None = None

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
        grounding: ModelSlot = ModelSlot(
            primary="ollama/qwen3:8b", params=ModelParams(temperature=0.0, max_tokens=4000)
        )

    class FallbackConfig(BaseModel):
        retries: int = 2
        retry_delay: float = 1.0
        timeout: int = 60
        on_failure: Literal["error", "skip", "warn"] = "error"

    class CostLimits(BaseModel):
        per_review_cents: int = Field(default=100, ge=1)
        daily_cents: int = Field(default=1000, ge=1)

    class GatewayConfig(BaseModel):
        models: GatewayModels = GatewayModels()
        fallback: FallbackConfig = FallbackConfig()
        cost_limits: CostLimits = CostLimits()
        model_registry_refresh_days: int = 7
        custom_providers: list[Any] = []

    _valid_recognizers = frozenset(
        {
            "person",
            "date",
            "money",
            "address",
            "email",
            "phone",
            "organization",
            "location",
            "nationality",
            "date_of_birth",
            "passport_number",
            "credit_card",
            "social_security",
            "driver_license",
            "ip_address",
            "url",
        }
    )

    class PrivacyConfig(BaseModel):
        tier: Literal["maximum", "balanced", "performance"] = "balanced"
        strip_pii: bool = True
        log_ttl_days: int = Field(default=30, ge=1)
        pii_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
        pii_encryption_key: str = "12345678901234561234567890123456"
        retention_days: int = Field(default=30, ge=1, le=365)
        enabled_recognizers: list[str] = []
        placeholder_format: str = "[{type}]"

        @field_validator("pii_encryption_key")
        @classmethod
        def _check_pii_encryption_key(cls, v: str) -> str:
            if len(v.encode("utf-8")) not in (16, 24, 32):
                raise ValueError("encryption key must be exactly 16, 24, or 32 bytes")
            return v

        @field_validator("enabled_recognizers")
        @classmethod
        def _check_enabled_recognizers(cls, v: list[str]) -> list[str]:
            if not v:
                return v
            invalid = set(v) - _valid_recognizers
            if invalid:
                raise ValueError(f"invalid recognizers: {', '.join(sorted(invalid))}")
            return v

        @field_validator("placeholder_format")
        @classmethod
        def _check_placeholder_format(cls, v: str) -> str:
            if "{type}" not in v:
                raise ValueError("must contain '{type}' placeholder")
            return v

    class StorageConfig(BaseModel):
        reviews_keep_forever: bool = True
        logs_keep_days: int = Field(default=30, ge=1)

    class RetrievalConfig(BaseModel):
        default_method: Literal["sparse", "dense", "hybrid"] = "hybrid"
        top_k: int = Field(default=5, ge=1, le=50)
        rrf_k: int = Field(default=60, ge=1)
        embedding_model: str = "nomic-embed-text"
        embedding_dimension: int = 1024
        reranker_model: str | None = None
        rerank_enabled: bool = False
        rerank_depth: int = Field(default=20, ge=1)
        db_dir: str | None = None

    class OpenReviewConfig(BaseModel):
        version: int = 1
        privacy: PrivacyConfig = PrivacyConfig()
        gateway: GatewayConfig = GatewayConfig()
        storage: StorageConfig = StorageConfig()
        retrieval: RetrievalConfig = RetrievalConfig()

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


def add_custom_provider(
    config_path: Path,
    name: str,
    base_url: str,
    api_key_env: str,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a custom provider to config.yml and return the validated config.

    No collision check here — callers (registry.add_custom_provider) check first.
    """
    import shutil

    import yaml

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    backup = config_path.with_suffix(".yml.bak")
    shutil.copy2(config_path, backup)

    entry = {
        "name": name,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "capabilities": capabilities,
        "source": "custom",
    }
    gateway = raw.setdefault("gateway", {})
    custom = gateway.setdefault("custom_providers", [])
    custom.append(entry)

    validated = _validate_and_merge(raw, dict(DEFAULT_CONFIG))
    with open(config_path, "w") as f:
        yaml.safe_dump(validated, f, default_flow_style=False)
    return validated


def get_custom_providers(config_path: Path) -> list[dict[str, Any]]:
    """Return the list of custom providers declared in config.yml."""
    gateway = load_config(config_path).get("gateway", {})
    providers: list[dict[str, Any]] = gateway.get("custom_providers", [])
    return providers
