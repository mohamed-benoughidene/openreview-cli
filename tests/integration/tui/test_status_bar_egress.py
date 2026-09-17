"""The status bar shows a live cloud-call counter (Phase 4)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_status_bar_shows_cloud_calls() -> None:
    from textual.widgets import Static

    from openreview_cli.gateway import models
    from openreview_cli.tui.app import OpenReviewApp

    models.reset_total_cloud_calls()
    models.record_cloud_call()

    app = OpenReviewApp()
    async with app.run_test(size=(140, 40)) as pilot:
        app._refresh_egress_status()
        await pilot.pause()
        text = str(app.query_one("#status-egress", Static).render())
        assert "Cloud calls: 1" in text, text
    models.reset_total_cloud_calls()
