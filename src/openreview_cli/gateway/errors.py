from dataclasses import dataclass


@dataclass
class GatewayError(Exception):
    """Gateway error with exit code and context."""

    exit_code: int
    slot: str | None
    message: str
    action: str

    def __post_init__(self) -> None:
        if self.exit_code not in (6, 7):
            raise ValueError(f"exit_code must be 6 or 7, got {self.exit_code}")
        if self.slot is not None and self.slot not in (
            "reasoning",
            "extraction",
            "embedding",
            "reranking",
            "graph",
        ):
            raise ValueError(f"invalid slot: {self.slot}")
        if not self.message:
            raise ValueError("message must be non-empty")
        if not self.action:
            raise ValueError("action must be non-empty")

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"GatewayError({self.exit_code}, slot={self.slot}: {self.message})"
