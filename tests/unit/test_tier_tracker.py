"""Unit tests for TierTracker — file IO atomicity, change detection."""

from __future__ import annotations

import json
from pathlib import Path

from openreview_cli.gateway.tier_tracker import TierTracker


class TestTierTracker:
    """TierTracker file IO and change detection."""

    def test_last_tier_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns None."""
        tracker = TierTracker(state_path=tmp_path / ".last_tier")
        assert tracker.last_tier() is None

    def test_last_tier_corrupt_file(self, tmp_path: Path) -> None:
        """Corrupt JSON returns None."""
        state = tmp_path / ".last_tier"
        state.write_text("not json")
        tracker = TierTracker(state_path=state)
        assert tracker.last_tier() is None

    def test_last_tier_missing_key(self, tmp_path: Path) -> None:
        """Valid JSON but missing 'tier' key returns None."""
        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"other": "value"}))
        tracker = TierTracker(state_path=state)
        assert tracker.last_tier() is None

    def test_last_tier_valid(self, tmp_path: Path) -> None:
        """Valid file returns the stored tier."""
        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"tier": "maximum"}))
        tracker = TierTracker(state_path=state)
        assert tracker.last_tier() == "maximum"

    def test_record_creates_file(self, tmp_path: Path) -> None:
        """record() writes .last_tier file."""
        tracker = TierTracker(state_path=tmp_path / ".last_tier")
        tracker.record("balanced")
        assert (tmp_path / ".last_tier").exists()
        data = json.loads((tmp_path / ".last_tier").read_text())
        assert data["tier"] == "balanced"

    def test_record_overwrites(self, tmp_path: Path) -> None:
        """record() overwrites existing file."""
        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"tier": "maximum"}))
        tracker = TierTracker(state_path=state)
        tracker.record("performance")
        data = json.loads(state.read_text())
        assert data["tier"] == "performance"

    def test_record_atomicity(self, tmp_path: Path) -> None:
        """Write .tmp then rename — .tmp file is cleaned up."""
        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"tier": "maximum"}))
        tracker = TierTracker(state_path=state)
        tracker.record("balanced")
        assert not state.with_suffix(".tmp").exists()

    def test_check_and_record_first_run(self, tmp_path: Path) -> None:
        """No previous file — no change message, file created."""
        tracker = TierTracker(state_path=tmp_path / ".last_tier")
        msg = tracker.check_and_record("performance")
        assert msg is None
        data = json.loads((tmp_path / ".last_tier").read_text())
        assert data["tier"] == "performance"

    def test_check_and_record_no_change(self, tmp_path: Path) -> None:
        """Same tier — no change message."""
        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"tier": "maximum"}))
        tracker = TierTracker(state_path=state)
        msg = tracker.check_and_record("maximum")
        assert msg is None

    def test_check_and_record_change(self, tmp_path: Path) -> None:
        """Different tier — change message returned."""
        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"tier": "maximum"}))
        tracker = TierTracker(state_path=state)
        msg = tracker.check_and_record("balanced")
        assert msg == "Tier changed from maximum to balanced"

    def test_check_and_record_file_updated(self, tmp_path: Path) -> None:
        """File updated to current tier after check_and_record."""
        state = tmp_path / ".last_tier"
        state.write_text(json.dumps({"tier": "maximum"}))
        tracker = TierTracker(state_path=state)
        tracker.check_and_record("balanced")
        data = json.loads(state.read_text())
        assert data["tier"] == "balanced"

    def test_check_and_record_change_any_tier(self, tmp_path: Path) -> None:
        """All tier transitions detected."""
        for prev, curr in [
            ("maximum", "balanced"),
            ("maximum", "performance"),
            ("balanced", "maximum"),
            ("balanced", "performance"),
            ("performance", "maximum"),
            ("performance", "balanced"),
        ]:
            state = tmp_path / ".last_tier"
            state.write_text(json.dumps({"tier": prev}))
            tracker = TierTracker(state_path=state)
            msg = tracker.check_and_record(curr)
            assert msg == f"Tier changed from {prev} to {curr}"
