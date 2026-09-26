"""Helpers for the opt-in startup splash phase."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from textual.app import App


def defer_when_splashing(app: App[Any], callback: Callable[[], None]) -> None:
    """Run *callback* after the first paint when the splash is enabled, else inline.

    With the splash enabled the callback must run *after* the splash frame is
    painted, so it is posted with ``call_after_refresh``. Without it, the callback
    runs immediately (baseline startup behaviour).
    """
    if getattr(app, "startup_splash", False):
        app.call_after_refresh(callback)
    else:
        callback()
