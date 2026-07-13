"""Centralized output formatting for CLI commands.

Supports ``text`` (Rich tables / human-readable) and ``json``
(machine-parseable) output formats. Used by all gateway commands.
"""

from __future__ import annotations

import json as _json
import sys
from typing import Any


def format_output(
    data: dict[str, Any],
    fmt: str,
    *,
    error: str | None = None,
    code: int = 0,
    message: str = "",
) -> str:
    """Format *data* as *fmt* (``text`` or ``json``).

    When ``fmt == "json"`` and *error* is set, produces a JSON error
    object ``{"error": str, "code": int, "message": str}`` to stderr
    instead of stdout.
    """
    if fmt != "json":
        # Text mode — caller must produce its own text output
        return ""  # pragma: no cover

    if error:
        err_obj: dict[str, Any] = {
            "error": error,
            "code": code,
            "message": message,
        }
        _json.dump(err_obj, sys.stderr, indent=2)
        sys.stderr.write("\n")
        return ""

    return _json.dumps(data, indent=2, default=str)


def format_error_json(error: str, code: int, message: str) -> str:
    """Build a JSON error string (for direct use with ``typer.echo``)."""
    return _json.dumps({"error": error, "code": code, "message": message}, indent=2)
