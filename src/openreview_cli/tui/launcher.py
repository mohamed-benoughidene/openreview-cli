"""TTY entry point — checks stdin isatty before launching TUI."""

from __future__ import annotations

import sys


def launch_tui() -> int:
    """If stdin is not a TTY, print friendly message and exit 0. Otherwise launch."""
    if not sys.stdin.isatty():
        print(
            "openreview needs an interactive terminal.\n"
            "Run with a TTY, or use a subcommand like `openreview --help`."
        )
        return 0
    from openreview_cli.tui.app import OpenReviewApp  # fmt: skip

    return OpenReviewApp().run() or 0
