"""Startup splash overlay painted on the first frame."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import LoadingIndicator, Static

from openreview_cli import __version__

__all__ = ["StartupSplash"]


class StartupSplash(Container):
    """Blocking-aware startup overlay: centered card covering the whole screen."""

    DEFAULT_CSS = """
    StartupSplash {
        layer: splash;
        width: 100%;
        height: 100%;
        align: center middle;
        background: $surface;
    }
    StartupSplash > Vertical {
        width: 52;
        height: auto;
        padding: 1 2;
        background: $panel;
        border: thick $primary;
    }
    #splash-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $primary;
    }
    #splash-version {
        width: 100%;
        text-align: center;
        color: $text-muted;
    }
    #splash-spinner {
        width: 100%;
        height: 1;
        text-align: center;
        color: $primary;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("openreview", id="splash-title", markup=False)
            yield Static(f"v{__version__}", id="splash-version", markup=False)
            yield LoadingIndicator(id="splash-spinner")
