"""Pipeline framework — async stage orchestration with error isolation,
cancellation, progress reporting, and memory tracking.

Usage::

    from openreview_cli.pipeline import Pipeline, Stage, PipelineReport

    class MyStage(Stage):
        name = "my_stage"
        async def run(self, ctx):
            return {"result": 42}

    pipeline = Pipeline(stages=[MyStage()])
    report = await pipeline.run({})
"""

from openreview_cli.pipeline.base import (
    PipelineContext,
    Stage,
    StageResult,
    dispose_context_keys,
)
from openreview_cli.pipeline.errors import (
    CriticalStageError,
    MemoryBudgetError,
    PipelineError,
    StageError,
)
from openreview_cli.pipeline.progress import ProgressCallback, ProgressEvent
from openreview_cli.pipeline.runner import Pipeline, PipelineReport

__all__ = [
    "CriticalStageError",
    "MemoryBudgetError",
    "Pipeline",
    "PipelineContext",
    "PipelineError",
    "PipelineReport",
    "ProgressCallback",
    "ProgressEvent",
    "Stage",
    "StageError",
    "StageResult",
    "dispose_context_keys",
]
