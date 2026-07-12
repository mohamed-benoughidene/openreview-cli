"""TTY entry point — checks stdin isatty before launching TUI."""

from __future__ import annotations

import sys

from openreview_cli.config.paths import get_data_dir
from openreview_cli.storage.database import init_database


def launch_tui() -> int:
    """If stdin is not a TTY, print friendly message and exit 0. Otherwise launch."""
    if not sys.stdin.isatty():
        print(
            "openreview needs an interactive terminal.\n"
            "Run with a TTY, or use a subcommand like `openreview --help`."
        )
        return 0
    from openreview_cli.tui.app import OpenReviewApp  # fmt: skip

    db_path = get_data_dir() / "openreview.db"
    try:
        init_database(db_path)
    except Exception as exc:
        from openreview_cli.tui.screens.db_error import DatabaseErrorScreen

        # ponytail: stub wiring — push error screen on init failure
        app = OpenReviewApp()
        app.push_screen(DatabaseErrorScreen(str(exc)))
        return app.run() or 0

    return OpenReviewApp().run() or 0
