"""Integration tests for negotiation wizard flow (T20C)."""

from __future__ import annotations

from unittest.mock import patch

from textual.widgets import ListView


def _get_neg_wizard(app):
    """Get the NegotiationWizard from the screen stack."""
    from openreview_cli.tui.screens.negotiation_wizard import NegotiationWizard

    for screen in app._screen_stack:
        if isinstance(screen, NegotiationWizard):
            return screen
    return None


async def _open_negotiation_wizard(app, pilot):
    """Click 'New negotiation' button on Review tab, get wizard."""
    # Navigate to Review tab via Home button
    btn = app.query_one("#btn-new-review")
    btn.press()
    await pilot.pause()
    # Click "New negotiation" button
    neg_btn = app.query_one("#btn-new-negotiation")
    await pilot.click(neg_btn)
    await pilot.pause()
    wizard = _get_neg_wizard(app)
    assert wizard is not None, "NegotiationWizard should be pushed"
    return wizard


def _make_fake_report():
    """Build a minimal NegotiationReport for mock return."""
    from openreview_cli.negotiation.models import NegotiationReport, NegotiationSummary

    return NegotiationReport(
        experimental=True,
        disclaimer="EXPERIMENTAL — test",
        strategies=[],
        payoff_matrices=[],
        summary=NegotiationSummary(total_clauses=0),
        playbook_id="bundled",
        confidence_threshold=0.7,
    )


class TestNegotiationWizard:
    """T20C: Integration tests for the 2-step negotiation wizard."""

    async def test_wizard_opens_from_tab(self) -> None:
        """Wizard opens from 'New negotiation' button on Review tab."""
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.negotiation_wizard import NegotiationWizard

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _open_negotiation_wizard(app, pilot)
            assert isinstance(wizard, NegotiationWizard)

    async def test_wizard_cancel_dismisses(self) -> None:
        """Cancel button dismisses the wizard."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _open_negotiation_wizard(app, pilot)
            wizard.query_one("#btn-cancel").press()
            await pilot.pause()
            assert _get_neg_wizard(app) is None

    async def test_wizard_back_navigates(self) -> None:
        """Back button returns from step 2 to step 1."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _open_negotiation_wizard(app, pilot)

            # Step 1 -> Step 2 (Next)
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Step 2 -> Step 1 (Back)
            wizard.query_one("#btn-back").press()
            await pilot.pause()

            step_indicator = wizard.query_one("#step-indicator")
            rendered = str(step_indicator.render())
            assert "Step 1" in rendered

    async def test_step1_file_picker_visible(self) -> None:
        """Step 1 shows DirectoryTree."""
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.negotiation_wizard import (
            FilteredDirectoryTree,
        )

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _open_negotiation_wizard(app, pilot)
            # Step 1: file picker is visible immediately
            tree = wizard.query_one("#file-tree", FilteredDirectoryTree)
            assert tree is not None

    async def test_solver_step_defaults_to_qre(self) -> None:
        """Step 2: solver list defaults to qre."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _open_negotiation_wizard(app, pilot)

            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Step 2 should display solver list
            solver_list = wizard.query_one("#solver-list", ListView)
            assert solver_list is not None, "Solver list should be visible"

            # Default solver is qre
            assert wizard._selected_solver == "qre"

    async def test_bad_rationality_blocks_next(self) -> None:
        """Bad rationality input ('abc') shows error, blocks Next."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _open_negotiation_wizard(app, pilot)

            await pilot.click(wizard.query_one("#btn-next"))
            await pilot.pause()

            # Focus rationality input and type bad value
            rationality_input = wizard.query_one("#input-rationality")
            await pilot.click(rationality_input)
            # Clear existing "1.0" and type "abc"
            await pilot.press("ctrl+a", "a", "b", "c")
            await pilot.pause()

            # Try to advance
            await pilot.click(wizard.query_one("#btn-next"))
            await pilot.pause()

            # Should still be on step 2 (error shown)
            error_label = wizard.query_one("#param-error")
            error_text = str(error_label.render())
            assert "number" in error_text.lower(), f"Expected number error, got: {error_text}"

    async def test_bad_depth_blocks_next(self) -> None:
        """Depth must be >= 1."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _open_negotiation_wizard(app, pilot)

            # Advance to step 2
            await pilot.click(wizard.query_one("#btn-next"))
            await pilot.pause()

            # Set bad depth value, then call validation directly
            wizard._depth = "0"
            await wizard._handle_next()

            # Should still be on step 2 with error shown
            assert wizard._step == 2, f"Expected step 2, got {wizard._step}"
            error_label = wizard.query_one("#param-error")
            error_text = str(error_label.render())
            assert ">= 1" in error_text, f"Got: {error_text}"

    async def test_full_flow_shows_result_screen(self) -> None:
        """Full flow: wizard → progress → result screen with memo text."""
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.negotiation_result import (
            NegotiationResultScreen,
        )

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            with patch("openreview_cli.tui.domain.negotiation.run_negotiation_via_tui") as mock_run:
                mock_run.return_value = _make_fake_report()

                wizard = await _open_negotiation_wizard(app, pilot)

                # Step 1 -> Step 2 (Next)
                wizard.query_one("#btn-next").press()
                await pilot.pause()

                # Step 2 -> Run negotiation
                wizard.query_one("#btn-next").press()
                await pilot.pause()

                # Wait for async task to complete and result to appear
                for _ in range(20):
                    await pilot.pause()

                # Result screen should be on the stack
                result = None
                for s in app._screen_stack:
                    if isinstance(s, NegotiationResultScreen):
                        result = s
                        break
                assert result is not None, (
                    "NegotiationResultScreen should appear after run completes"
                )

    async def test_error_path_shows_error(self) -> None:
        """Fake raises → result screen shows error."""
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.negotiation_result import (
            NegotiationResultScreen,
        )

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            with patch("openreview_cli.tui.domain.negotiation.run_negotiation_via_tui") as mock_run:
                mock_run.side_effect = RuntimeError("test boom")

                wizard = await _open_negotiation_wizard(app, pilot)

                wizard.query_one("#btn-next").press()
                await pilot.pause()

                wizard.query_one("#btn-next").press()
                await pilot.pause()

                for _ in range(20):
                    await pilot.pause()

                result = None
                for s in app._screen_stack:
                    if isinstance(s, NegotiationResultScreen):
                        result = s
                        break
                assert result is not None, "Result screen should appear on error"
                assert result._error is not None
                assert "test boom" in result._error
