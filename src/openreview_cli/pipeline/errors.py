"""Pipeline error hierarchy."""


class PipelineError(Exception):
    """Base error for all pipeline-related errors."""


class StageError(PipelineError):
    """Non-critical stage error -- pipeline continues after capturing the error."""


class CriticalStageError(StageError):
    """Critical stage error -- pipeline halts immediately.

    The exception carries a ``pipeline_report`` attribute with the partial
    ``PipelineReport`` collected up to the failing stage.
    """

    def __init__(self, message: str, pipeline_report: object = None) -> None:
        super().__init__(message)
        self.pipeline_report = pipeline_report


class MemoryBudgetError(PipelineError):
    """Memory budget exceeded during pipeline execution."""
