"""User-facing feedback: format_error, format_success.

Provides structured error/success display with PII-redacted verbose logging.
Each function prints a Rich panel and returns a structured ``dict`` so the
caller (e.g. a CLI command) can decide whether to exit.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from rich.panel import Panel
from rich.text import Text

from openreview_cli.ui.components.panel import success_panel
from openreview_cli.ui.console import get_icon, renderer

_logger = logging.getLogger(__name__)

# ── PII redaction ──────────────────────────────────────────────────────


def _redact_pii(text: str) -> str:
    """Replace sensitive patterns with safe markers for log output.

    Redacts:
    * Absolute Unix file paths  → ``[path]``
    * Inline API keys / tokens  → ``[key]``
    """
    text = re.sub(r"/[\w/.-]+", " [path]", text)
    text = re.sub(
        r"(?:api[ _-]?key|token|secret)\s*[:=]\s*\S+",
        "[key]",
        text,
        flags=re.IGNORECASE,
    )
    return text


# ── Public API ─────────────────────────────────────────────────────────


def format_error(
    what: str,
    why: str,
    fix: str,
    exit_code: int = 1,
) -> dict[str, Any]:
    """Print a three-part error panel (What / Why / How to fix).

    Unlike ``error_panel`` (which calls ``SystemExit``), this function
    returns normally so the caller can decide when to exit.

    Returns a structured dict with the provided fields for programmatic
    inspection.
    """
    icon = get_icon("error", ascii_fallback=not renderer.supports_unicode)
    border = "" if not renderer.supports_color else "red"
    if "help" not in fix.lower():
        fix = fix + "\n\nRun `openreview --help` for usage."
    body = (
        f"[bold]What failed:[/bold] {what}\n\n"
        f"[bold]Why:[/bold] {why}\n\n"
        f"[bold]How to fix:[/bold] {fix}"
    )
    panel = Panel(body, title=Text(f" {icon} "), border_style=border)
    renderer.console.print(panel)

    result: dict[str, Any] = {
        "what": what,
        "why": why,
        "fix": fix,
        "exit_code": exit_code,
    }
    _logger.debug("format_error: %s", _redact_pii(str(result)))
    return result


def format_success(message: str, detail: str = "") -> dict[str, Any]:
    """Print a success panel and return a structured result dict.

    When *detail* is provided it is appended below the main message.
    """
    text = message
    if detail:
        text = f"{message}\n\n{detail}"
    success_panel(text)

    result: dict[str, Any] = {
        "message": message,
        "detail": detail,
    }
    _logger.debug("format_success: %s", _redact_pii(str(result)))
    return result
