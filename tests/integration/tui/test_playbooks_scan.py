"""The playbook corruption scan must not sit on the render path.

``list_playbooks_via_tui`` used to parse every stored playbook (a full
YAML/pydantic load per row, ~4.5ms each) just to set a ``corrupt`` flag, so on a
large database the list took ~24s to appear.  The scan now runs in a second
phase: the rows render immediately, then ``corrupt_playbook_ids_via_tui`` runs
off the event loop and the "(corrupt)" badge is applied when it lands.

These tests hold that second phase open on a ``threading.Event`` and prove the
list is already visible and populated while the verification is still blocked.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import suppress
from typing import Any
from unittest.mock import patch

from textual.widgets import Label, ListItem, ListView
from textual.worker import WorkerCancelled

_RAW_ROWS: list[dict[str, Any]] = [
    {
        "id": "clean-pb",
        "latest_version": 1,
        "current_version": 1,
        "created_at": "2026-01-01",
        "corrupt": False,
    },
    {
        "id": "bad-pb",
        "latest_version": 1,
        "current_version": 1,
        "created_at": "2026-01-02",
        "corrupt": False,
    },
]


def _list_item_text(item: ListItem) -> str:
    """Extract visible text from a ListItem (same helper as the sibling tests)."""
    try:
        return str(item.query_one(Label).render())
    except Exception:
        return str(item.render())


def _fresh_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in _RAW_ROWS]


async def test_corruption_scan_does_not_delay_the_list() -> None:
    """Phase 1 renders the rows; phase 2's blocked scan does not hold them back."""
    gate = threading.Event()
    started = threading.Event()

    def _blocking_scan(playbook_ids: list[str]) -> set[str]:
        started.set()
        gate.wait(timeout=10)
        return {"bad-pb"}

    with (
        patch(
            "openreview_cli.tui.domain.playbooks.list_playbooks_via_tui",
            side_effect=_fresh_rows,
        ),
        patch(
            "openreview_cli.tui.domain.playbooks.corrupt_playbook_ids_via_tui",
            side_effect=_blocking_scan,
        ),
    ):
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("4")
            await pilot.pause()

            # Let phase 2 actually start and block, without blocking the loop.
            for _ in range(200):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert started.is_set(), "corruption scan phase never started"

            playbook_list = app.query_one("#playbook-list", ListView)
            assert playbook_list.display is True
            texts = [_list_item_text(item) for item in playbook_list.children]
            joined = "\n".join(texts)
            assert "clean-pb" in joined
            assert "bad-pb" in joined
            # The badge is still optimistic: the verification has not landed.
            assert "(corrupt)" not in joined

            # Release the scan; the flagged id gains its marker.
            gate.set()
            with suppress(WorkerCancelled):
                await app.workers.wait_for_complete()
            await pilot.pause()

            marked = [
                text
                for text in (_list_item_text(item) for item in playbook_list.children)
                if "(corrupt)" in text
            ]
            assert len(marked) == 1
            assert "bad-pb" in marked[0]
            assert app.is_running
