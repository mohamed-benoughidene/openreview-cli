"""Prompts domain wrapper — TUI-facing functions for prompt history and diffs.

Resolves the data directory at call time (never at import) so per-test
``XDG_*`` overrides in the ``isolated_xdg`` fixture are honored.
"""

from __future__ import annotations

from difflib import unified_diff
from typing import Any

from openreview_cli.config.paths import get_data_dir
from openreview_cli.prompts.store import PromptStore


def _store() -> PromptStore:
    """Build a ``PromptStore`` against the *current* data directory.

    ``get_data_dir()`` is called here, at call time, rather than cached at
    module import, because ``isolated_xdg`` patches the environment per test.
    """
    store = PromptStore(get_data_dir() / "openreview.db")
    store.init()
    return store


def _normalize_created_at(value: Any) -> str:
    """Coerce a SQL NULL coerced to the literal string ``"None"`` to ``""``."""
    text = str(value)
    return "" if text == "None" else text


def list_prompts_via_tui() -> list[dict[str, Any]]:
    """List prompts as dicts shaped ``{name, latest_version, created_at}``.

    Requests an explicit ``per_page=100``, so it returns up to 100 prompts.
    Prompts beyond the first 100 are not included (the store's default 25-item
    cap is not the limiting factor here, but a cap of 100 still applies).
    """
    prompts = _store().list(per_page=100)
    return [
        {
            "name": p.name,
            "latest_version": p.latest_version,
            "created_at": p.created_at,
        }
        for p in prompts
    ]


def get_prompt_history_via_tui(name: str) -> dict[str, Any]:
    """Return ``{rows, current_version, found}`` for prompt ``name``.

    Each row is ``{version, created_at}``, sorted by version.  Versions are
    enumerated through ``PromptStore.export`` (ordered by version) rather than
    ``range(1, latest + 1)``, so imported prompts with gaps or non-1-based
    numbering are handled without raising.  A missing prompt yields
    ``{"rows": [], "current_version": 0, "found": False}``.
    """
    try:
        data = _store().export(name)
    except ValueError:
        return {"rows": [], "current_version": 0, "found": False}

    # ``export(name)`` returns a single dict when a name is supplied.
    assert isinstance(data, dict)
    rows: list[dict[str, Any]] = [
        {
            "version": int(version["version"]),
            "created_at": _normalize_created_at(version.get("created_at")),
        }
        for version in data["versions"]
    ]
    rows.sort(key=lambda row: row["version"])
    current_version = max((row["version"] for row in rows), default=0)
    return {"rows": rows, "current_version": current_version, "found": True}


def get_prompt_version_diff(name: str, v1: int, v2: int) -> str:
    """Return a unified diff between versions ``v1`` and ``v2`` of ``name``.

    Mirrors the CLI ``prompt diff`` command.  Raises ``ValueError`` (propagated
    from the store) when either version is missing.
    """
    store = _store()
    pv_from = store.get(name, v1)
    pv_to = store.get(name, v2)
    diff = unified_diff(
        pv_from.content.splitlines(keepends=True),
        pv_to.content.splitlines(keepends=True),
        fromfile=f"v{v1}",
        tofile=f"v{v2}",
    )
    return "".join(diff)
