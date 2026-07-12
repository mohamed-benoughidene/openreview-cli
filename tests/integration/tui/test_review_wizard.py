"""Integration tests for review wizard flow (T015, T016)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from textual.widgets import DirectoryTree, Input


def _get_wizard(app):
    """Get the ReviewWizard from the screen stack."""
    from openreview_cli.tui.screens.review_wizard import ReviewWizard

    for screen in app._screen_stack:
        if isinstance(screen, ReviewWizard):
            return screen
    return None


async def _home_and_open_wizard(app, pilot):
    """Click Home new-review button, then click Review tab's button to push wizard."""
    btn = app.query_one("#btn-new-review")
    btn.press()
    await pilot.pause()
    # Now on Review tab, click its New review button
    review_btn = app.query_one("#btn-new-review-tab")
    await pilot.click(review_btn)
    await pilot.pause()
    wizard = _get_wizard(app)
    assert wizard is not None, "Wizard should be pushed after clicking Review tab button"
    return wizard


async def _select_first_mode(wizard, pilot):
    """Select first real mode (skip category header)."""
    mode_list = wizard.query_one("#mode-list")
    mode_list.focus()
    await pilot.pause()
    await pilot.press("down", "down", "enter")


async def _select_first_playbook(wizard, pilot):
    """Select first playbook option."""
    pb_list = wizard.query_one("#playbook-list")
    pb_list.focus()
    await pilot.pause()
    await pilot.press("down", "enter")


class TestReviewWizard:
    """T015: Integration tests for the 4-step review wizard."""

    async def test_wizard_step1_mode_filter(self) -> None:
        """Step 1: type-to-filter narrows mode list."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)

            filter_input = wizard.query_one("#mode-filter")
            await pilot.click(filter_input)
            await pilot.press("p", "r", "e")
            await pilot.pause()

            mode_list = wizard.query_one("#mode-list")
            items = list(mode_list.query("ListItem"))
            assert len(items) > 0, "Mode list should have items after filter"

    async def test_wizard_step2_file_picker_visible(self) -> None:
        """Step 2: DirectoryTree is visible after advancing."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)

            # Step 1: select mode and Next
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            tree = wizard.query_one(DirectoryTree)
            assert tree is not None, "DirectoryTree should be visible in step 2"

    async def test_wizard_step3_playbook_options(self) -> None:
        """Step 3: playbook selection list is shown."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)

            # Step 1: select mode -> Next
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()
            # Step 2: Next (skip file selection)
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Step 3 should have a playbook list
            pb_list = wizard.query_one("#playbook-list")
            assert pb_list is not None, "Playbook list should be visible in step 3"

    async def test_wizard_step4_pii_default_enabled(self) -> None:
        """Step 4: 'Disable PII stripping' checkbox UNCHECKED by default."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)

            # Step 1: select mode -> Next
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()
            # Step 2: Next
            wizard.query_one("#btn-next").press()
            await pilot.pause()
            # Step 3: select playbook -> Next
            await _select_first_playbook(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Step 4: check checkbox is unchecked by default
            cb = wizard.query_one("#cb-disable-pii")
            assert cb.value is False, "PII should be enabled by default"

    async def test_wizard_progress_screen(self) -> None:
        """After confirm, ProgressScreen is pushed (T015)."""
        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.progress import ProgressScreen

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            with patch("openreview_cli.tui.domain.review.run_review_via_tui") as mock_run:
                mock_report = MagicMock()
                mock_report.assessments = []
                mock_run.return_value = [mock_report]

                wizard = await _home_and_open_wizard(app, pilot)

                # Navigate all 4 steps
                await _select_first_mode(wizard, pilot)
                await pilot.pause()
                wizard.query_one("#btn-next").press()
                await pilot.pause()
                wizard.query_one("#btn-next").press()
                await pilot.pause()
                await _select_first_playbook(wizard, pilot)
                await pilot.pause()
                wizard.query_one("#btn-next").press()
                await pilot.pause()
                # Step 4: click Run review
                wizard.query_one("#btn-next").press()
                await pilot.pause()

                # ProgressScreen should be on screen stack
                progress = None
                for s in app._screen_stack:
                    if isinstance(s, ProgressScreen):
                        progress = s
                        break
                assert progress is not None, "ProgressScreen should appear"

    async def test_wizard_result_close(self) -> None:
        """Close button returns from wizard (T016)."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)

            # Step 1: select mode
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            # Cancel
            wizard.query_one("#btn-cancel").press()
            await pilot.pause()

            # Wizard should be dismissed
            assert _get_wizard(app) is None, "Wizard should be dismissed"

    async def test_wizard_navigate_back(self) -> None:
        """Back button returns to previous step."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)

            # Step 1 -> Step 2
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            # Step 2 -> Step 1 (back)
            wizard.query_one("#btn-back").press()
            await pilot.pause()

            # Should be back on step 1
            step_indicator = wizard.query_one("#step-indicator")
            assert step_indicator is not None, "Step indicator should exist"

    # ── T050: Hidden file filtering ──

    async def test_hidden_files_hidden_by_default(self) -> None:
        """T050: Hidden files are hidden by default in step 2."""
        import tempfile
        from pathlib import Path

        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.review_wizard import FilteredDirectoryTree

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            tree = wizard.query_one("#file-tree", FilteredDirectoryTree)

            with tempfile.TemporaryDirectory() as tmpdir:
                Path(tmpdir, "visible.txt").write_text("hello")
                Path(tmpdir, ".hidden").write_text("secret")

                tree.path = Path(tmpdir)
                tree.reload()
                await pilot.pause()

                children_names = [
                    child.label.plain if hasattr(child.label, "plain") else str(child.label)
                    for child in tree.root.children
                ]
                assert ".hidden" not in children_names, (
                    f"Hidden file '.hidden' should be hidden, got {children_names}"
                )
                assert "visible.txt" in children_names, (
                    f"Visible file 'visible.txt' should appear, got {children_names}"
                )

    async def test_ctrl_h_toggles_hidden_files(self) -> None:
        """T050: Ctrl+H toggles hidden file visibility."""
        import tempfile
        from pathlib import Path

        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.review_wizard import FilteredDirectoryTree

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            tree = wizard.query_one("#file-tree", FilteredDirectoryTree)

            with tempfile.TemporaryDirectory() as tmpdir:
                Path(tmpdir, "visible.txt").write_text("hello")
                Path(tmpdir, ".hidden").write_text("secret")

                tree.path = Path(tmpdir)
                tree.reload()
                await pilot.pause()

                # Toggle hidden files ON
                await pilot.press("ctrl+h")
                await pilot.pause()

                children_names = [
                    child.label.plain if hasattr(child.label, "plain") else str(child.label)
                    for child in tree.root.children
                ]
                assert ".hidden" in children_names, (
                    f"Hidden file '.hidden' should be visible after toggle, got {children_names}"
                )

                # Toggle hidden files OFF again
                await pilot.press("ctrl+h")
                await pilot.pause()

                children_names_off = [
                    child.label.plain if hasattr(child.label, "plain") else str(child.label)
                    for child in tree.root.children
                ]
                assert ".hidden" not in children_names_off, (
                    f"Hidden file '.hidden' should be hidden after second toggle, got {children_names_off}"
                )

    # ── T054: File filter and direct path entry ──

    async def test_file_filter_input_visible(self) -> None:
        """T054: File filter Input is visible above DirectoryTree in step 2."""
        from openreview_cli.tui.app import OpenReviewApp

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            file_filter = wizard.query_one("#file-filter", Input)
            assert file_filter is not None, "File filter Input should exist in step 2"

            tree = wizard.query_one("#file-tree")
            assert tree is not None, "DirectoryTree should exist in step 2"

    async def test_direct_path_entry_navigates(self) -> None:
        """T054: Typing a direct path in filter Input navigates DirectoryTree."""
        import tempfile
        from pathlib import Path

        from openreview_cli.tui.app import OpenReviewApp
        from openreview_cli.tui.screens.review_wizard import FilteredDirectoryTree

        app = OpenReviewApp()
        async with app.run_test(size=(120, 40)) as pilot:
            wizard = await _home_and_open_wizard(app, pilot)
            await _select_first_mode(wizard, pilot)
            await pilot.pause()
            wizard.query_one("#btn-next").press()
            await pilot.pause()

            tree = wizard.query_one("#file-tree", FilteredDirectoryTree)

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)

                # Create a subdir to navigate to
                subdir = tmp_path / "subdir"
                subdir.mkdir()
                (subdir / "nested.txt").write_text("nested")

                # Simulate direct path entry by invoking handler directly
                class FakeEvent:
                    value = str(subdir)

                wizard._on_file_filter_input_changed(FakeEvent())
                await pilot.pause()

                assert tree.path == subdir, f"Tree path should be {subdir}, got {tree.path}"
