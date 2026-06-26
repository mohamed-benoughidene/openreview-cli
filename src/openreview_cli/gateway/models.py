from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ModelParams:
    """Model-specific parameters for a slot."""

    temperature: float = 0.7
    max_tokens: int = 4000
    dimensions: int | None = None
    top_p: float | None = None
    stop: list[str] | None = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"temperature must be between 0.0 and 2.0, got {self.temperature}")
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")
        if self.dimensions is not None and self.dimensions <= 0:
            raise ValueError(f"dimensions must be positive, got {self.dimensions}")
        if self.top_p is not None and not (0.0 <= self.top_p <= 1.0):
            raise ValueError(f"top_p must be between 0.0 and 1.0, got {self.top_p}")


@dataclass(slots=True)
class SlotConfig:
    """Configuration for a single task slot."""

    primary: str
    fallback: str | None = None
    params: ModelParams | None = None

    def __post_init__(self) -> None:
        if not self.primary:
            raise ValueError("primary must be non-empty")
        self._validate_model_format(self.primary, "primary")
        if self.fallback is not None:
            self._validate_model_format(self.fallback, "fallback")

    def _validate_model_format(self, model: str, field_name: str) -> None:
        if not model:
            raise ValueError(f"{field_name} must be non-empty")
        if "/" in model:
            parts = model.split("/")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(
                    f"{field_name} must be in format 'provider/model-id', got '{model}'"
                )
        # If no "/", it's treated as a valid local Ollama model name (e.g. "llama3.1")


@dataclass(slots=True)
class RerankResult:
    """Single reranking result."""

    index: int
    score: float
    document: str | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"index must be non-negative, got {self.index}")


@dataclass(slots=True)
class GatewayResponse:
    """Response from a routed request."""

    content: str | list[float] | list[RerankResult] | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str
    provider: str
    slot: str
    fallback_used: bool
    latency_ms: int
    raw_response: Any | None = None

    def __post_init__(self) -> None:
        if self.input_tokens < 0:
            raise ValueError(f"input_tokens must be non-negative, got {self.input_tokens}")
        if self.output_tokens < 0:
            raise ValueError(f"output_tokens must be non-negative, got {self.output_tokens}")
        if self.cost_usd < 0.0:
            raise ValueError(f"cost_usd must be non-negative, got {self.cost_usd}")
        if not self.model:
            raise ValueError("model must be non-empty")
        if not self.provider:
            raise ValueError("provider must be non-empty")
        if self.slot not in ("reasoning", "extraction", "embedding", "reranking", "graph"):
            raise ValueError(f"invalid slot: {self.slot}")
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative, got {self.latency_ms}")


@dataclass(slots=True)
class ReviewSession:
    """Tracks a single review invocation for cost aggregation."""

    session_id: str
    started_at: float
    ended_at: float | None = None
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def __post_init__(self) -> None:
        import uuid

        try:
            uuid.UUID(self.session_id)
        except ValueError as err:
            raise ValueError(f"session_id must be a valid UUID, got {self.session_id}") from err
        if self.started_at <= 0.0:
            raise ValueError(f"started_at must be positive, got {self.started_at}")
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError(f"ended_at must be >= started_at, got {self.ended_at}")
        if self.total_cost_usd < 0.0:
            raise ValueError(f"total_cost_usd must be non-negative, got {self.total_cost_usd}")
        if self.total_input_tokens < 0:
            raise ValueError(
                f"total_input_tokens must be non-negative, got {self.total_input_tokens}"
            )
        if self.total_output_tokens < 0:
            raise ValueError(
                f"total_output_tokens must be non-negative, got {self.total_output_tokens}"
            )


@dataclass(slots=True)
class CostRecord:
    """Per-call record of token usage and cost."""

    session_id: str
    slot: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float
    fallback_used: bool
    latency_ms: int
    record_id: int | None = None

    def __post_init__(self) -> None:
        import uuid

        try:
            uuid.UUID(self.session_id)
        except ValueError as err:
            raise ValueError(f"session_id must be a valid UUID, got {self.session_id}") from err
        if self.slot not in ("reasoning", "extraction", "embedding", "reranking", "graph"):
            raise ValueError(f"invalid slot: {self.slot}")
        if not self.model:
            raise ValueError("model must be non-empty")
        if not self.provider:
            raise ValueError("provider must be non-empty")
        if self.input_tokens < 0:
            raise ValueError(f"input_tokens must be non-negative, got {self.input_tokens}")
        if self.output_tokens < 0:
            raise ValueError(f"output_tokens must be non-negative, got {self.output_tokens}")
        if self.cost_usd < 0.0:
            raise ValueError(f"cost_usd must be non-negative, got {self.cost_usd}")
        if self.timestamp <= 0.0:
            raise ValueError(f"timestamp must be positive, got {self.timestamp}")
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative, got {self.latency_ms}")
