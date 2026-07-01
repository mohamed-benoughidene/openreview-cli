from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ProviderInfo(BaseModel):
    name: str
    env_key: str | None = None
    auth_required: bool = True
    models: dict[str, ModelEntry] = {}


class ModelEntry(BaseModel):
    slots: list[str]
    context: int | None = None
    dimensions: int | None = None
    ram: str | None = None
    recommended: bool = False
    status: str | None = None
    note: str | None = None
    extra_params: dict[str, Any] | None = None


class CostRecord(BaseModel):
    id: str
    session_id: str | None = None
    slot: str | None = None
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cost_cents: int
    created_at: str
