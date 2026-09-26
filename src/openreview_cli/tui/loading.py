"""Reusable per-tab loading state.

Tabs that perform a (potentially slow) domain fetch mount a :class:`LoadingState`
*visible* while the fetch is in flight and hide it (``display = False``) once the
data has landed.  The fetch itself runs off the event loop, so the spinner keeps
animating and the UI never looks frozen.

The widget owns the two-way display transition so each tab does not repeat it:
``begin(content)`` while a load is in flight and ``end(content)`` when it lands
(success *or* failure).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widget import Widget
from textual.widgets import LoadingIndicator, Static

__all__ = ["LoadingState"]

# Fixed, non-user-supplied message; never Rich markup so it renders literally.
_MESSAGE = "Loading …"


class LoadingState(Container):
    """Centered spinner plus a muted message, shown while a tab is loading.

    Args:
        id: Optional widget id (tabs use ``"<tab>-loading"``).
    """

    DEFAULT_CSS = """
    LoadingState { width: 100%; height: 1fr; align: center middle; }
    LoadingState Vertical { width: auto; height: auto; }
    LoadingState LoadingIndicator { width: auto; height: 1; }
    LoadingState .loading-message { width: auto; }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        # Intrinsic sizes: the inner Vertical is width: auto, so its children
        # must also be auto (width: 100% of an auto parent is circular and
        # resolves to 0 — the spinner would never paint).
        with Vertical():
            yield LoadingIndicator()
            # markup=False: the message is plain text, never Rich markup.
            yield Static(_MESSAGE, markup=False, classes="loading-message")

    def begin(self, content: Widget) -> None:
        """Show the spinner and hide *content* while a load is in flight."""
        self.display = True
        content.display = False

    def end(self, content: Widget) -> None:
        """Hide the spinner and reveal *content*."""
        content.display = True
        self.display = False
