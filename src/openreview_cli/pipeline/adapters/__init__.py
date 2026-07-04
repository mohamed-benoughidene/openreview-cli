"""Stage adapters wrapping existing capability modules.

Adapter base utilities and exports.
"""

from openreview_cli.pipeline.adapters.chunk import ChunkStage
from openreview_cli.pipeline.adapters.generate import GenerateStage
from openreview_cli.pipeline.adapters.parse import ParseStage
from openreview_cli.pipeline.adapters.retrieve import RetrieveStage
from openreview_cli.pipeline.adapters.strip import StripStage

__all__ = [
    "ChunkStage",
    "GenerateStage",
    "ParseStage",
    "RetrieveStage",
    "StripStage",
]
