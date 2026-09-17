"""Exploratory probes for the pre-flight egress modal + live cloud counter.

Stresses the egress-review ModalScreen (local vs cloud summaries, literal
bracketed text, repeated open/cancel cycles) and the status-bar cloud-call
counter refresh, all inside one ``app.run_test`` session.
"""

from __future__ import annotations

import pytest
from textual.widgets import Label, Static

from openreview_cli.tui.domain.egress import EgressSummary


@pytest.mark.slow
@pytest.mark.asyncio
async def test_egress_modal_and_status_counter_stress() -> None:
    from openreview_cli.tui.app import OpenReviewApp
    from openreview_cli.tui.screens.egress_review import EgressReviewModal

    app = OpenReviewApp()
    async with app.run_test(size=(140, 40)) as pilot:
        # ── 1. Local-only summary renders; Cancel returns False ─────────────
        local = EgressSummary(
            privacy_tier="maximum",
            pii_stripped=True,
            destinations=("ollama/qwen3:8b",),
            cloud_warning=False,
        )
        results: list[bool | None] = []
        app.push_screen(EgressReviewModal(local), results.append)
        await pilot.pause()

        body = app.screen.query_one("#egress-body", Label)
        assert body._render_markup is False
        text = str(body.render())
        assert "Privacy tier: maximum" in text
        assert "PII stripped before egress: Yes" in text
        assert "ollama/qwen3:8b" in text
        assert "uploaded" not in text.lower()

        await pilot.click("#btn-egress-cancel")
        await pilot.pause()
        assert results == [False]
        assert not any(isinstance(s, EgressReviewModal) for s in app._screen_stack)

        # ── 2. Cloud + PII-off summary shows the warning; confirm -> True ───
        risky = EgressSummary(
            privacy_tier="balanced",
            pii_stripped=False,
            destinations=("openai/gpt-4o-mini", "anthropic/claude-3"),
            cloud_warning=True,
        )
        app.push_screen(EgressReviewModal(risky), results.append)
        await pilot.pause()
        risky_text = str(app.screen.query_one("#egress-body", Label).render())
        assert "PII stripped before egress: NO" in risky_text
        assert "openai/gpt-4o-mini" in risky_text
        assert "anthropic/claude-3" in risky_text
        assert "raw document text will be uploaded" in risky_text

        await pilot.press("c")
        await pilot.pause()
        assert results == [False, True]

        # ── 3. Bracketed destinations render literally (markup=False) ───────
        bracketed = EgressSummary(
            privacy_tier="maximum",
            pii_stripped=True,
            destinations=("[Party A]/qwen3:8b",),
            cloud_warning=False,
        )
        app.push_screen(EgressReviewModal(bracketed), results.append)
        await pilot.pause()
        assert "[Party A]" in str(app.screen.query_one("#egress-body", Label).render())
        await pilot.press("escape")
        await pilot.pause()
        assert results[-1] is False

        # ── 4. Repeated rapid open/cancel cycles leave no modal behind ──────
        for _ in range(5):
            app.push_screen(EgressReviewModal(local), results.append)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert not any(isinstance(s, EgressReviewModal) for s in app._screen_stack)
        assert results[-5:] == [False] * 5

        # ── 5. Live cloud-call counter in the status bar ────────────────────
        from openreview_cli.gateway import models

        counter = app.query_one("#status-egress", Static)

        models.reset_total_cloud_calls()
        app._refresh_egress_status()
        await pilot.pause()
        assert "Cloud calls: 0" in str(counter.render())

        for _ in range(3):
            models.record_cloud_call()
        app._refresh_egress_status()
        await pilot.pause()
        assert "Cloud calls: 3" in str(counter.render())

        # Rapid increment + refresh, then reset + refresh.
        for _ in range(50):
            models.record_cloud_call()
        app._refresh_egress_status()
        await pilot.pause()
        assert "Cloud calls: 53" in str(counter.render())

        models.reset_total_cloud_calls()
        app._refresh_egress_status()
        await pilot.pause()
        assert "Cloud calls: 0" in str(counter.render())
