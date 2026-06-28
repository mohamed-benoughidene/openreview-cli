"""Unit tests for the Wizard state machine (spec §2.11).

Verifies state transitions, back-navigation, interrupt handling,
step-indicator progression, and non-TTY bypass.
"""

from __future__ import annotations

from unittest.mock import PropertyMock, patch

import pytest

from openreview_cli.ui.components.wizard import StepDef, Wizard

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracking_wizard_visited() -> tuple[type[Wizard], list[str]]:
    """Return (TrackingWizard, visited_list) for asserting step order."""
    visited: list[str] = []

    class TrackingWizard(Wizard):
        def _step_entry(self) -> str | None:
            visited.append("entry")
            return self._next()

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

    return TrackingWizard, visited


# ---------------------------------------------------------------------------
# State machine - linear forward flow
# ---------------------------------------------------------------------------


class TestForwardTransitions:
    """Every step auto-advances to the next in order."""

    def test_two_step_flow(self) -> None:
        """Wizard walks entry → mode_selection and exits."""

        class TwoStepWizard(Wizard):
            def _step_entry(self) -> str | None:
                return self._next()

            def _step_mode_selection(self) -> str | None:
                return None

        wiz = TwoStepWizard(
            steps=[
                StepDef("entry", "Start"),
                StepDef("mode_selection", "Pick"),
            ]
        )
        wiz.run()
        # No assertion needed — the test passes if it doesn't loop or crash.

    def test_full_flow_entry_to_results(
        self, tracking_wizard_visited: tuple[type[Wizard], list[str]]
    ) -> None:
        """All six default steps are visited in order."""
        wiz_cls, visited = tracking_wizard_visited
        wiz = wiz_cls()
        wiz.run()
        assert visited == [
            "entry",
            "mode_selection",
            "configuration",
            "confirm",
            "processing",
            "results",
        ]

    def test_step_returns_none_terminates(self) -> None:
        """Returning None from any step exits the wizard immediately."""

        class EarlyExitWizard(Wizard):
            def _step_entry(self) -> str | None:
                return None  # exit immediately

            def _step_mode_selection(self) -> str | None:
                raise AssertionError("should not be reached")

        wiz = EarlyExitWizard()
        wiz.run()  # should not crash


# ---------------------------------------------------------------------------
# Back-navigation  (Esc)
# ---------------------------------------------------------------------------


class TestBackNavigation:
    """Esc from a step navigates to the previous step."""

    def test_back_from_second_step(self) -> None:
        """Returning _back() from mode_selection returns to entry."""
        visited: list[str] = []

        class BackWizard(Wizard):
            def _step_entry(self) -> str | None:
                visited.append("entry")
                if self.data.get("re_entry"):
                    return None  # exit on 2nd visit
                self.data["re_entry"] = True
                return self._next()

            def _step_mode_selection(self) -> str | None:
                visited.append("mode_selection")
                return self._back()  # Esc → go back

            def _step_configuration(self) -> str | None:
                visited.append("configuration")
                return None

        st = [
            StepDef("entry", "Start"),
            StepDef("mode_selection", "Pick"),
            StepDef("configuration", "Config"),
        ]
        wiz = BackWizard(steps=st)
        wiz.run()

        # entry → mode (Esc) → entry → exit
        assert visited == ["entry", "mode_selection", "entry"]

    def test_back_at_first_step_exits(self) -> None:
        """_back() on the first step returns None, exiting the wizard."""

        class FirstStepBackWizard(Wizard):
            def _step_entry(self) -> str | None:
                return self._back()  # first step — should exit

        wiz = FirstStepBackWizard(steps=[StepDef("entry", "Start")])
        wiz.run()  # should not crash


# ---------------------------------------------------------------------------
# Interrupt handling  (Ctrl-C)
# ---------------------------------------------------------------------------


class TestInterruptHandling:
    """Ctrl-C raises SystemExit with code 1 and a message."""

    def test_ctrl_c_raises_system_exit(self, capsys: pytest.CaptureFixture[str]) -> None:
        """KeyboardInterrupt is caught and converted to SystemExit(1)."""

        class InterruptWizard(Wizard):
            def _step_entry(self) -> str | None:
                raise KeyboardInterrupt()

        wiz = InterruptWizard(steps=[StepDef("entry", "Start")])
        with pytest.raises(SystemExit) as exc_info:
            wiz.run()
        assert exc_info.value.code == 1

    def test_ctrl_c_prints_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The message 'Setup was interrupted.' is printed on stderr."""

        class InterruptWizard(Wizard):
            def _step_entry(self) -> str | None:
                raise KeyboardInterrupt()

        wiz = InterruptWizard(steps=[StepDef("entry", "Start")])
        with pytest.raises(SystemExit):
            wiz.run()
        captured = capsys.readouterr()
        assert "Setup was interrupted." in captured.err

    def test_ctrl_c_prints_message_on_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The interrupt message goes to stderr."""

        class InterruptWizard(Wizard):
            def _step_entry(self) -> str | None:
                raise KeyboardInterrupt()

        wiz = InterruptWizard(steps=[StepDef("entry", "Start")])
        with pytest.raises(SystemExit):
            wiz.run()
        captured = capsys.readouterr()
        assert "Setup was interrupted" in captured.err.strip()
        assert "openreview setup" in captured.err.strip()


# ---------------------------------------------------------------------------
# Step indicator rendering
# ---------------------------------------------------------------------------


class TestStepIndicator:
    """step_indicator is called with correct (current, total, title) for
    each step position."""

    def test_step_indicator_progression(self) -> None:
        """Calls: (1,2,"A"), (2,2,"B") for a 2-step flow."""
        calls: list[tuple[int, int, str]] = []

        with patch(
            "openreview_cli.ui.components.wizard.step_indicator",
            side_effect=lambda c, t, title: calls.append((c, t, title)),
        ):

            class TwoStepWizard(Wizard):
                def _step_a(self) -> str | None:
                    return self._next()

                def _step_b(self) -> str | None:
                    return None

            wiz = TwoStepWizard(
                steps=[
                    StepDef("a", "First Step"),
                    StepDef("b", "Second Step"),
                ]
            )
            wiz.run()

        assert calls == [(1, 2, "First Step"), (2, 2, "Second Step")]

    def test_step_indicator_single_step(self) -> None:
        """A single-step wizard calls indicator once."""
        calls: list[tuple[int, int, str]] = []

        with patch(
            "openreview_cli.ui.components.wizard.step_indicator",
            side_effect=lambda c, t, title: calls.append((c, t, title)),
        ):

            class SingleWizard(Wizard):
                def _step_only(self) -> str | None:
                    return None

            wiz = SingleWizard(steps=[StepDef("only", "Solo")])
            wiz.run()

        assert calls == [(1, 1, "Solo")]


# ---------------------------------------------------------------------------
# Non-TTY bypass
# ---------------------------------------------------------------------------


class TestNonTTY:
    """When is_interactive is False, the wizard completes without calling
    interactive prompts."""

    def test_non_tty_auto_advances(self) -> None:
        """All steps execute and the wizard completes in non-TTY mode."""
        visited: list[str] = []

        class NonTTYWizard(Wizard):
            def _step_entry(self) -> str | None:
                visited.append("entry")
                return self._next()

            def _step_mode_selection(self) -> str | None:
                visited.append("mode_selection")
                return None

        wiz = NonTTYWizard(
            steps=[
                StepDef("entry", "Start"),
                StepDef("mode_selection", "Pick"),
            ]
        )
        # Simulate non-TTY by patching is_interactive
        with patch.object(
            type(wiz._renderer),
            "is_interactive",
            PropertyMock(return_value=False),
        ):
            wiz.run()

        assert visited == ["entry", "mode_selection"]

    def test_non_tty_accumulates_data(self) -> None:
        """Wizard.data is populated correctly in non-TTY mode."""

        class NonTTYWizard(Wizard):
            def _step_entry(self) -> str | None:
                self.data["greeting"] = "hello"
                return self._next()

            def _step_mode_selection(self) -> str | None:
                self.data["mode"] = "auto"
                return None

        wiz = NonTTYWizard(
            steps=[
                StepDef("entry", "Start"),
                StepDef("mode_selection", "Pick"),
            ]
        )
        with patch.object(
            type(wiz._renderer),
            "is_interactive",
            PropertyMock(return_value=False),
        ):
            result = wiz.run()

        assert result == {"greeting": "hello", "mode": "auto"}
        assert result is wiz.data  # same object


# ---------------------------------------------------------------------------
# Pluggable steps (US1 / US2)
# ---------------------------------------------------------------------------


class TestPluggableSteps:
    """Steps can be customized via constructor arguments — US1 and US2
    provide their own StepDef lists and corresponding step methods."""

    def test_custom_step_list(self) -> None:
        """Steps are defined as a list of StepDef tuples."""

        steps = [
            StepDef("greet", "Greeting"),
            StepDef("farewell", "Farewell"),
        ]
        visited: list[str] = []

        class GreetWizard(Wizard):
            def _step_greet(self) -> str | None:
                visited.append("greet")
                return self._next()

            def _step_farewell(self) -> str | None:
                visited.append("farewell")
                return None

        wiz = GreetWizard(steps=steps)
        wiz.run()
        assert visited == ["greet", "farewell"]

    def test_different_step_method_per_subclass(self) -> None:
        """Two subclasses with different step methods don't interfere."""

        class WizardA(Wizard):
            def _step_phase(self) -> str | None:
                self.data["a"] = 1
                return None

        class WizardB(Wizard):
            def _step_phase(self) -> str | None:
                self.data["b"] = 2
                return None

        a = WizardA(steps=[StepDef("phase", "A")])
        b = WizardB(steps=[StepDef("phase", "B")])

        assert a.run() == {"a": 1}
        assert b.run() == {"b": 2}


# ---------------------------------------------------------------------------
# Default steps constant
# ---------------------------------------------------------------------------


class TestDefaults:
    """The module-level DEFAULT_STEPS matches the WizardStep literal."""

    def test_default_steps_matches_wizard_step_literal(self) -> None:
        """DEFAULT_STEPS contains the six canonical steps."""
        from openreview_cli.ui.components.wizard import DEFAULT_STEPS

        ids = [s.id for s in DEFAULT_STEPS]
        assert ids == [
            "entry",
            "mode_selection",
            "configuration",
            "confirm",
            "processing",
            "results",
        ]
