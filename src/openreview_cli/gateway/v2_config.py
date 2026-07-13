from __future__ import annotations

import enum

from pydantic import BaseModel, Field, field_validator


class FallbackConfig(BaseModel):
    retries: int = 2
    timeout: int = 60


class CostLimits(BaseModel):
    per_session_cents: int | None = None
    daily_cents: int | None = None


class ApiKeySource(enum.StrEnum):
    KEYRING = "keyring"
    FILE = "file"
    ENV = "env"


class ProviderConfig(BaseModel):
    name: str
    api_key_source: ApiKeySource = ApiKeySource.FILE
    env_key: str
    base_url: str | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not v.islower() or not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("name must be lowercase alphanumeric with hyphens/underscores")
        return v

    @field_validator("env_key")
    @classmethod
    def _validate_env_key(cls, v: str) -> str:
        import re

        if not re.match(r"^[A-Z][A-Z0-9_]*$", v):
            raise ValueError("env_var_name must match ^[A-Z][A-Z0-9_]*$")
        return v


class SlotAssignment(BaseModel):
    provider: str
    model: str
    fallback: SlotAssignment | None = None


class V2Config(BaseModel):
    version: int = Field(default=2, ge=1)
    providers: dict[str, ProviderConfig]
    slots: dict[str, SlotAssignment]
    default_model: str | None = None
    fallback: FallbackConfig = FallbackConfig()
    cost_limits: CostLimits | None = None

    @field_validator("slots")
    @classmethod
    def _validate_slot_keys(cls, v: dict[str, SlotAssignment]) -> dict[str, SlotAssignment]:
        valid = frozenset(
            {"reasoning", "extraction", "embedding", "reranking", "graph", "grounding"}
        )
        extra = set(v.keys()) - valid
        if extra:
            raise ValueError(f"invalid slot names: {', '.join(sorted(extra))}")
        return v

    @field_validator("providers")
    @classmethod
    def _require_at_least_one_enabled(
        cls, v: dict[str, ProviderConfig]
    ) -> dict[str, ProviderConfig]:
        if not any(p.enabled for p in v.values()):
            raise ValueError("at least one provider must be enabled")
        return v
