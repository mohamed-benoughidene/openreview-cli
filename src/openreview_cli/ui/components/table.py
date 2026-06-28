"""Table rendering component — Rich Table, JSON, or plain fixed-width.

``SGTable`` wraps ``rich.table.Table`` and dispatches to the appropriate
output format based on ``output_format``.
"""

from __future__ import annotations

import json
import shutil
import sys

from rich.table import Table
from rich.text import Text

from openreview_cli.types import OutputFormat
from openreview_cli.ui.console import renderer


class SGTable:
    """A table that renders as Rich Table, JSON, or plain fixed-width text.

    Parameters
    ----------
    title:
        Table title (shown in Rich/plain modes).
    columns:
        Sequence of ``(name, style, width)`` tuples.
    rows:
        Sequence of row tuples.  Each tuple length must match ``columns``.
    output_format:
        One of ``OutputFormat.TABLE``, ``JSON``, or ``PLAIN``.
    """

    def __init__(
        self,
        title: str,
        columns: list[tuple[str, str, int]],
        rows: list[tuple[str, ...]],
        output_format: OutputFormat = OutputFormat.TABLE,
    ) -> None:
        self._title = title
        self._columns = columns
        self._rows = rows
        self._output_format = output_format

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Print the table to the console in the configured format."""
        if self._output_format == OutputFormat.JSON:
            self._render_json()
        elif self._output_format == OutputFormat.PLAIN:
            self._render_plain()
        else:
            self._render_rich()

    # ------------------------------------------------------------------
    # Rich (default)
    # ------------------------------------------------------------------

    def _render_rich(self) -> None:
        table = Table(title=self._title)

        for name, style, width in self._columns:
            table.add_column(name, style=style, width=width, no_wrap=True)

        if not self._rows:
            table.add_row(Text("No data", style="dim"), end_section=True)
        else:
            for row in self._rows:
                table.add_row(*row)

        renderer.console.print(table)

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def _render_json(self) -> None:
        col_names = [c[0] for c in self._columns]
        data = [dict(zip(col_names, row, strict=False)) for row in self._rows]
        sys.stdout.write(json.dumps(data) + "\n")

    # ------------------------------------------------------------------
    # Plain (fixed-width, no colour)
    # ------------------------------------------------------------------

    def _render_plain(self) -> None:
        if not self._rows:
            print("No data")
            return

        term_width = shutil.get_terminal_size(fallback=(80, 24)).columns

        # Calculate actual column widths (clamp to term width)
        widths: list[int] = []
        for _, _, w in self._columns:
            widths.append(min(w, term_width // max(len(self._columns), 1)))

        header = " ".join(name.ljust(widths[i]) for i, (name, _, _) in enumerate(self._columns))
        print(header)
        print("-" * len(header))

        for row in self._rows:
            parts = [str(row[i]).ljust(widths[i]) for i in range(len(self._columns))]
            print(" ".join(parts))

        if self._title:
            print(f"  ({self._title})")
