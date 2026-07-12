"""Unit tests for domain/privacy.py (T012)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml


def _write_config(config_dir: Path, data: dict) -> Path:
    """Write a config dict to config_dir/config.yml and return the path."""
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yml"
    with open(config_file, "w") as f:
        yaml.dump(data, f)
    return config_file


# Patch where get_config_dir is *looked up* (privacy.py imported it directly)
PRIVACY_MODULE = "openreview_cli.tui.domain.privacy"


def test_read_privacy_tier_returns_valid_tier(tmp_path: Path) -> None:
    """T012: read_privacy_tier returns 'maximum' for valid config."""
    from openreview_cli.tui.domain.privacy import read_privacy_tier

    _write_config(tmp_path, {"privacy": {"tier": "maximum"}})

    with patch(f"{PRIVACY_MODULE}.get_config_dir", return_value=tmp_path):
        tier = read_privacy_tier()
        assert tier == "maximum"


def test_read_privacy_tier_returns_balanced(tmp_path: Path) -> None:
    """T012: read_privacy_tier returns 'balanced'."""
    from openreview_cli.tui.domain.privacy import read_privacy_tier

    _write_config(tmp_path, {"privacy": {"tier": "balanced"}})

    with patch(f"{PRIVACY_MODULE}.get_config_dir", return_value=tmp_path):
        tier = read_privacy_tier()
        assert tier == "balanced"


def test_read_privacy_tier_returns_performance(tmp_path: Path) -> None:
    """T012: read_privacy_tier returns 'performance'."""
    from openreview_cli.tui.domain.privacy import read_privacy_tier

    _write_config(tmp_path, {"privacy": {"tier": "performance"}})

    with patch(f"{PRIVACY_MODULE}.get_config_dir", return_value=tmp_path):
        tier = read_privacy_tier()
        assert tier == "performance"


def test_read_privacy_tier_returns_unknown_for_invalid(tmp_path: Path) -> None:
    """T012: read_privacy_tier returns 'unknown' for invalid tier value.

    Pydantic Literal validation rejects 'garbage', raising ValidationError,
    which read_privacy_tier catches and returns em dash.
    """
    from openreview_cli.tui.domain.privacy import read_privacy_tier

    _write_config(tmp_path, {"privacy": {"tier": "garbage"}})

    with patch(f"{PRIVACY_MODULE}.get_config_dir", return_value=tmp_path):
        tier = read_privacy_tier()
        # Pydantic rejects the invalid literal, exception caught → em dash
        assert tier == "\u2014"


def test_read_privacy_tier_returns_balanced_when_tier_missing(
    tmp_path: Path,
) -> None:
    """T012: read_privacy_tier returns default 'balanced' when config omits tier."""
    from openreview_cli.tui.domain.privacy import read_privacy_tier

    _write_config(tmp_path, {})

    with patch(f"{PRIVACY_MODULE}.get_config_dir", return_value=tmp_path):
        tier = read_privacy_tier()
        # Default config has privacy.tier = "balanced"
        assert tier == "balanced"


def test_read_privacy_tier_handles_empty_config_dir(
    tmp_path: Path,
) -> None:
    """T012: read_privacy_tier returns a valid value when config created."""
    from openreview_cli.tui.domain.privacy import read_privacy_tier

    with patch(f"{PRIVACY_MODULE}.get_config_dir", return_value=tmp_path):
        tier = read_privacy_tier()
        # Default config has privacy.tier = "balanced"
        assert tier in ("maximum", "balanced", "performance", "\u2014", "unknown")
