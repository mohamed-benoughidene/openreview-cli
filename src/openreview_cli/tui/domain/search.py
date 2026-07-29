"""TUI domain wrapper for global search across reviews, clients, playbooks."""

from __future__ import annotations

from typing import Any


def search_all_via_tui(query: str) -> dict[str, list[dict[str, Any]]]:
    """Search across all data types, returning grouped results.

    Results are grouped by type: ``reviews``, ``clients``, ``playbooks``.
    """
    from openreview_cli.storage.search import search_all as _search_all
    from openreview_cli.tui.domain.clients import get_db_path

    return _search_all(get_db_path(), query)
