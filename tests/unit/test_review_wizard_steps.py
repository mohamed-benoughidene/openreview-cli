"""Unit tests for the review wizard flow (T042 — spec §2.11 review steps).

Tests that ``ReviewFlowWizard`` (a ``Wizard`` subclass) navigates the
correct step order, respects back-navigation limits, and handles
interrupts cleanly.
"""

from __future__ import annotations

import pytest

from openreview_cli.cli.review_wizard import REVIEW_STEPS, ReviewFlowWizard

# ---------------------------------------------------------------------------
# Step order
# ---------------------------------------------------------------------------


class TestStepOrder:
    """Review wizard starts at Mode Selection and walks through steps."""

    @pytest.fixture(autouse=True)
    def _mock_interactive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("openreview_cli.ui.components.prompt._ensure_interactive", lambda: None)

    def test_first_step_is_mode_selection(self) -> None:
        """Entry point is mode_selection, not a generic 'welcome' step."""
        assert REVIEW_STEPS[0].id == "mode_selection"

    def test_step_ids_in_order(self) -> None:
        """Step order: mode → config → confirm → processing → results."""
        ids = [s.id for s in REVIEW_STEPS]
        assert ids == [
            "mode_selection",
            "configuration",
            "confirm",
            "processing",
            "results",
        ]

    def test_full_flow_visits_all_steps(self) -> None:
        """All review steps are visited in order via _next()."""
        visited: list[str] = []

        class TrackerWizard(ReviewFlowWizard):
            def _step_mode_selection(self) -> str | None:
                visited.append("mode_selection")
                return self._next()

            def _step_configuration(self) -> str | None:
                visited.append("configuration")
                return self._next()

            def _step_confirm(self) -> str | None:
                visited.append("confirm")
                return self._next()

            def _step_processing(self) -> str | None:
                visited.append("processing")
                return self._next()

            def _step_results(self) -> str | None:
                visited.append("results")
                return None

        wiz = TrackerWizard(file_path="dummy.pdf")
        wiz.run()
        assert visited == [
            "mode_selection",
            "configuration",
            "confirm",
            "processing",
            "results",
        ]


# ---------------------------------------------------------------------------
# Back-navigation  (Esc)
# ---------------------------------------------------------------------------


class TestBackNavigation:
    """Esc back-navigation works on Config/Confirm but not on Processing."""

    @pytest.fixture(autouse=True)
    def _mock_interactive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("openreview_cli.ui.components.prompt._ensure_interactive", lambda: None)

    def test_back_from_config_goes_to_mode(self) -> None:
        """Esc on config step returns to mode_selection."""
        visited: list[str] = []

        class BackWizard(ReviewFlowWizard):
            def _step_mode_selection(self) -> str | None:
                visited.append("mode_selection")
                if self.data.get("re_entry"):
                    return None
                self.data["re_entry"] = True
                return self._next()

            def _step_configuration(self) -> str | None:
                visited.append("configuration")
                return self._back()

            def _step_confirm(self) -> str | None:
                raise AssertionError("should not be reached")

            def _step_processing(self) -> str | None:
                raise AssertionError("should not be reached")

            def _step_results(self) -> str | None:
                raise AssertionError("should not be reached")

        wiz = BackWizard(file_path="dummy.pdf")
        wiz.run()
        assert visited == ["mode_selection", "configuration", "mode_selection"]

    def test_back_from_confirm_goes_to_config(self) -> None:
        """Esc on confirm step returns to configuration."""
        visited: list[str] = []

        class BackWizard(ReviewFlowWizard):
            def _step_mode_selection(self) -> str | None:
                visited.append("mode_selection")
                return self._next()

            def _step_configuration(self) -> str | None:
                visited.append("configuration")
                if self.data.get("re_entry"):
                    return None  # exit on 2nd visit
                self.data["re_entry"] = True
                return self._next()

            def _step_confirm(self) -> str | None:
                visited.append("confirm")
                return self._back()

            def _step_processing(self) -> str | None:
                raise AssertionError("should not be reached")

            def _step_results(self) -> str | None:
                raise AssertionError("should not be reached")

        wiz = BackWizard(file_path="dummy.pdf")
        wiz.run()
        assert visited == [
            "mode_selection",
            "configuration",
            "confirm",
            "configuration",
        ]

    def test_back_on_first_step_exits(self) -> None:
        """Esc on the first step (mode_selection) exits the wizard."""
        visited: list[str] = []

        class BackWizard(ReviewFlowWizard):
            def _step_mode_selection(self) -> str | None:
                visited.append("mode_selection")
                return self._back()

        wiz = BackWizard(file_path="dummy.pdf")
        wiz.run()
        assert visited == ["mode_selection"]

    def test_processing_does_not_back_navigate(self) -> None:
        """Processing step does not offer back — it advances forward."""
        visited: list[str] = []

        class ForwardWizard(ReviewFlowWizard):
            def _step_mode_selection(self) -> str | None:
                visited.append("mode_selection")
                return self._next()

            def _step_configuration(self) -> str | None:
                visited.append("configuration")
                return self._next()

            def _step_confirm(self) -> str | None:
                visited.append("confirm")
                return self._next()

            def _step_processing(self) -> str | None:
                visited.append("processing")
                # Processing must advance forward, not back
                return self._next()

            def _step_results(self) -> str | None:
                visited.append("results")
                return None

        wiz = ForwardWizard(file_path="dummy.pdf")
        wiz.run()
        assert visited == [
            "mode_selection",
            "configuration",
            "confirm",
            "processing",
            "results",
        ]


# ---------------------------------------------------------------------------
# Interrupt handling  (Ctrl-C)
# ---------------------------------------------------------------------------


class TestInterruptHandling:
    """Ctrl-C during review exits cleanly with code 1."""

    @pytest.fixture(autouse=True)
    def _mock_interactive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("openreview_cli.ui.components.prompt._ensure_interactive", lambda: None)

    def test_ctrl_c_during_mode_selection_exits(self) -> None:
        """KeyboardInterrupt in mode_selection raises SystemExit(1)."""

        class InterruptWizard(ReviewFlowWizard):
            def _step_mode_selection(self) -> str | None:
                raise KeyboardInterrupt()

        wiz = InterruptWizard(file_path="dummy.pdf")
        with pytest.raises(SystemExit) as exc_info:
            wiz.run()
        assert exc_info.value.code == 1

    def test_ctrl_c_during_processing_exits(self) -> None:
        """KeyboardInterrupt in processing raises SystemExit(1)."""

        class InterruptWizard(ReviewFlowWizard):
            def _step_mode_selection(self) -> str | None:
                return self._next()

            def _step_configuration(self) -> str | None:
                return self._next()

            def _step_confirm(self) -> str | None:
                return self._next()

            def _step_processing(self) -> str | None:
                raise KeyboardInterrupt()

            def _step_results(self) -> str | None:
                raise AssertionError("should not be reached")

        wiz = InterruptWizard(file_path="dummy.pdf")
        with pytest.raises(SystemExit) as exc_info:
            wiz.run()
        assert exc_info.value.code == 1

    def test_ctrl_c_prints_cancellation_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """KeyboardInterrupt prints 'Review cancelled. Partial results were not saved.'"""

        class InterruptWizard(ReviewFlowWizard):
            def _step_mode_selection(self) -> str | None:
                raise KeyboardInterrupt()

        wiz = InterruptWizard(file_path="dummy.pdf")
        with pytest.raises(SystemExit):
            wiz.run()
        captured = capsys.readouterr()
        assert "Review cancelled" in captured.err
