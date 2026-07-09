"""TierTracker — persist and detect privacy tier changes between operations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openreview_cli.config.paths import get_config_dir

if TYPE_CHECKING:
    from pathlib import Path


class TierTracker:
    """Track last-used privacy tier to detect changes between operations.

    Persists tier name to a JSON file in the config directory.
    File is written atomically (write to .tmp, rename) to prevent
    partial writes from corrupting the state.
    """

    def __init__(self, state_path: Path | None = None) -> None:
        self._state_path = state_path or get_config_dir() / ".last_tier"

    @property
    def state_path(self) -> Path:
        """Path to the persisted state file."""
        return self._state_path

    def last_tier(self) -> str | None:
        """Read last recorded tier from state file.

        Returns None if file is missing, corrupt, or missing 'tier' key.
        """
        try:
            raw = self._state_path.read_text()
            data: dict[str, object] = json.loads(raw)
            tier = data.get("tier")
            return str(tier) if isinstance(tier, str) else None
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def record(self, tier: str) -> None:
        """Write tier to state file atomically.

        Creates parent directory if needed. Writes to a .tmp sibling
        then renames to guarantee atomic replace.
        """
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"tier": tier}))
        tmp.replace(self._state_path)

    def check_and_record(self, current_tier: str) -> str | None:
        """Compare current tier to last used tier.

        Returns a diff message ("Tier changed from X to Y") if the tier
        changed, or None if unchanged or first use. Updates persisted tier
        on every call regardless of whether there was a change.
        """
        previous = self.last_tier()
        self.record(current_tier)
        if previous is not None and previous != current_tier:
            return f"Tier changed from {previous} to {current_tier}"
        return None
