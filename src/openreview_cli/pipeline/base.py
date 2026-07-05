"""Core pipeline abstractions: Stage ABC, StageResult, PipelineContext."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

PipelineContext = dict[str, Any]


@dataclass
class StageResult:
    """Record of a single stage execution.

    Attributes:
        stage_name: Human-readable stage name.
        duration_s: Wall-clock duration in seconds.
        error: Error message if the stage failed (None on success).
        output_keys: Keys written to the shared context by this stage.
        skipped: Whether the stage was skipped.
        memory_mb: Peak memory delta attributed to this stage (None if not measured).
    """

    stage_name: str
    duration_s: float
    error: str | None = None
    output_keys: list[str] = field(default_factory=list)
    skipped: bool = False
    memory_mb: float | None = None


class Stage(ABC):
    """Abstract base class for all pipeline stages.

    Subclasses must define ``name``, ``critical`` (optional), and implement
    ``run()``.

    Attributes:
        name: Human-readable stage name.
        critical: If True, stage failure halts the pipeline immediately.
        max_concurrency: Hint for internal IO-bound parallelism within the
            stage (runner does not enforce; stages may use ``asyncio.gather``).
        disposable_keys: Keys produced by this stage that should be removed
            from the shared context after the next subsequent stage completes.
    """

    name: str = ""
    critical: bool = False
    max_concurrency: int = 1
    disposable_keys: ClassVar[set[str]] = set()

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> dict[str, Any] | None:
        """Execute this stage.

        Args:
            ctx: Shared pipeline context. Read prior stage outputs from this.

        Returns:
            Dict of keys to merge into the shared context, or None to
            indicate a no-op (nothing merged).
        """
        ...

    def cleanup(self, ctx: PipelineContext) -> None:
        """Release stage-local resources after the result is merged.

        Override in subclasses that hold large references (clauses, documents)
        that should be freed as soon as their output is in the shared context.
        Called by the runner after ``context.update(result)`` and before
        the progress event for the next stage.
        """
        return

    def should_skip(self, ctx: PipelineContext) -> bool:
        """Return True to skip this stage entirely.

        Override to dynamically skip execution based on context (e.g., when
        ``no_pii`` is set).  The default returns ``False`` (always run).
        """
        return False

    # ponytail: spec-required extension hook, no consumer yet
    def supports_degradation(self) -> bool:
        """Return True if this stage supports degraded execution modes.

        Override to signal capacity to run with reduced resources (smaller
        batch, lighter model, simplified processing).
        """
        return False

    # ponytail: spec-required extension hook, no consumer yet
    def apply_degradation(self, action: str) -> None:
        """Apply a degradation *action* to reduce resource usage.

        Called by the coordinator before re-running a stage under memory
        pressure.  The default is a no-op; override to implement specific
        degradation behavior (e.g., switching to a lighter model).
        """
        return


def dispose_context_keys(ctx: PipelineContext, keys: set[str]) -> None:
    """Remove *keys* from *ctx*, ignoring any that are missing.

    Used by the runner to evict ``disposable_keys`` after the next stage.
    """
    for key in keys:
        ctx.pop(key, None)
