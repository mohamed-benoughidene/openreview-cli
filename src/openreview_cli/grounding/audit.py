"""Local file audit trail for grounding discrimination decisions."""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.grounding.models import DiscriminationAuditEntry

logger = logging.getLogger(__name__)


class GroundingAuditLog:
    """Local file audit trail for grounding discrimination decisions.

    Writes entries as JSON lines (.jsonl) to {output_dir}/grounding-audit.jsonl.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self._path = Path(output_dir) / "grounding-audit.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Audit log: %s", self._path)

    def append(self, entry: DiscriminationAuditEntry) -> None:
        """Write a single audit entry as a JSON line (immediately flushed)."""
        data = dataclasses.asdict(entry)
        data["verdict"] = entry.verdict.value  # Ensure string serialization
        data["provenances"] = [dataclasses.asdict(p) for p in entry.provenances]
        # Convert timestamp to ISO string for JSON
        if entry.timestamp is not None:
            data["timestamp"] = entry.timestamp.isoformat()
        line = json.dumps(data, ensure_ascii=False, default=str)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
