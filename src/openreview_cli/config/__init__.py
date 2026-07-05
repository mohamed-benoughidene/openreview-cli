"""App-level config dataclasses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecoveryConfig:
    """Recovery configuration settings (FR-08).

    Controls retry, interval, threshold, and enabled strategies for the
    error recovery framework.  Integrates with the main config loader
    (Phase 9) for YAML/TOML user settings.

    Attributes:
        max_retries: Maximum number of retry attempts per stage.
        base_interval_s: Base backoff interval in seconds.
        memory_threshold_pct: Percentage of budget at which degradation
            triggers (10.0 — 100.0).
        enabled_strategies: Optional list of strategy names to allow.
            None means all strategies are enabled.
    """

    max_retries: int = 4
    base_interval_s: float = 1.0
    memory_threshold_pct: float = 80.0
    enabled_strategies: list[str] | None = None

    def __post_init__(self) -> None:
        if self.max_retries < 1:
            raise ValueError(f"max_retries must be >= 1, got {self.max_retries}")
        if self.base_interval_s <= 0:
            raise ValueError(f"base_interval_s must be > 0, got {self.base_interval_s}")
        if not (10.0 <= self.memory_threshold_pct <= 100.0):
            raise ValueError(
                f"memory_threshold_pct must be in [10, 100], got {self.memory_threshold_pct}"
            )


__all__ = ["RecoveryConfig"]
