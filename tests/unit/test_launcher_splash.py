"""Production launch must enable the startup splash."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from openreview_cli.tui.launcher import launch_tui


def test_launch_tui_enables_splash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    mock_app = MagicMock()
    mock_app.run.return_value = 0

    with (
        patch("openreview_cli.tui.launcher.init_database"),
        patch("openreview_cli.tui.app.OpenReviewApp", return_value=mock_app) as mock_cls,
    ):
        result = launch_tui()

    assert result == 0
    mock_cls.assert_called_once_with(show_splash=True)
