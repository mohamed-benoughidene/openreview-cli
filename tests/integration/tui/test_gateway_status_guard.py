"""Regression test for the gateway-status refresh timer.

The 5s interval timer (``OpenReviewApp.on_mount``) can fire when the
``#status-gateway`` button is absent from the DOM (mount gap or teardown
under event-loop load). ``_refresh_gateway_status`` must no-op then instead
of raising ``NoMatches`` — see docs/test-FAILURES.md failures 2-4.
"""

from openreview_cli.tui.app import OpenReviewApp


async def test_refresh_gateway_status_tolerates_missing_button() -> None:
    """Direct call with the button removed from the DOM must not raise."""
    app = OpenReviewApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await app.query_one("#status-gateway").remove()
        await pilot.pause()
        app._refresh_gateway_status()  # must not raise textual NoMatches
