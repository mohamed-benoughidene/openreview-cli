from pathlib import Path
from typing import Any

from openreview_cli.config.defaults import DEFAULT_CONFIG


def _validate_and_merge(raw: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    from pydantic import BaseModel

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

    class CostLimits(BaseModel):
        per_review_cents: int = 100
        daily_cents: int = 1000

    class GatewayConfig(BaseModel):
        models: GatewayModels = GatewayModels()
        fallback: FallbackConfig = FallbackConfig()
        cost_limits: CostLimits = CostLimits()
        model_registry_refresh_days: int = 7

    class PrivacyConfig(BaseModel):
        tier: str = "balanced"
        strip_pii: bool = True
        log_ttl_days: int = 30

    class StorageConfig(BaseModel):
        reviews_keep_forever: bool = True
        logs_keep_days: int = 30

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


def load_config(config_path: Path) -> dict[str, Any]:
    import yaml

    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.safe_dump(DEFAULT_CONFIG, f, default_flow_style=False)
        return dict(DEFAULT_CONFIG)

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}
    return _validate_and_merge(raw, dict(DEFAULT_CONFIG))
