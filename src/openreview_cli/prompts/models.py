from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class PromptVersion(BaseModel):
    name: str
    version: int
    content: str = Field(max_length=16384)
    created_at: str = Field(default_factory=_now)
    tags: list[str] | None = None
    description: str | None = None
    test_results: list[dict[str, Any]] | None = None
    optimization_meta: dict[str, Any] | None = None


class PromptBinding(BaseModel):
    slot: str
    prompt_name: str
    prompt_version: int
    created_at: str = Field(default_factory=_now)


class Prompt(BaseModel):
    name: str
    latest_version: int
    created_at: str = Field(default_factory=_now)
