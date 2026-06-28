"""Interactive wizard state machine (spec §2.11).

Provides the ``Wizard`` class — a pluggable state machine for interactive
CLI setup flows.  Each step is a ``StepDef`` (id + title) with a
corresponding ``_step_{id}`` method on the subclass.

Navigation:
  - Enter on a prompt → advance to the next step.
  - Esc on a prompt → go back to the previous step.
  - Ctrl-C at any point → exit with ``SystemExit(1)``.
"""

from __future__ import annotations

import sys
from typing import Any, NamedTuple

from openreview_cli.ui.components.header import step_indicator
from openreview_cli.ui.console import SGRenderer
from openreview_cli.ui.console import renderer as default_renderer

# ---------------------------------------------------------------------------
# Step definition
# ---------------------------------------------------------------------------


class StepDef(NamedTuple):
    """A single wizard step.

    Attributes
    ----------
    id:
        Machine-readable identifier (e.g. ``"entry"``, ``"confirm"``).
        Used to look up the handler method ``_step_{id}``.
    title:
        Human-readable label shown in the step indicator (spec §2.11).
    """

    id: str
    title: str


# ---------------------------------------------------------------------------
# Default — matches the WizardStep literal in openreview_cli.types
# ---------------------------------------------------------------------------

DEFAULT_STEPS: list[StepDef] = [
    StepDef("entry", "Welcome"),
    StepDef("mode_selection", "Select Mode"),
    StepDef("configuration", "Configure"),
    StepDef("confirm", "Confirm"),
    StepDef("processing", "Processing"),
    StepDef("results", "Results"),
]


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------


class Wizard:
    """Pluggable interactive wizard state machine.

    Usage::

        class MyWizard(Wizard):
            def _step_entry(self) -> str | None:
                return self._next()

            def _step_done(self) -> str | None:
                return None

        wiz = MyWizard(steps=[StepDef("entry", "Start"),
                               StepDef("done", "Finish")])
        data = wiz.run()

    Step methods should return:
      * A step ID (string) — navigate to that step (use ``self._next()``
        to advance or ``self._back()`` to go back).
      * ``None`` — exit the wizard.

    Subclass and override ``_step_*`` methods to add prompt logic for
    each step.  Use ``self.data`` to accumulate results.
    """

    def __init__(
        self,
        steps: list[StepDef] | None = None,
        renderer: SGRenderer | None = None,
    ) -> None:
        self._steps: list[StepDef] = steps or DEFAULT_STEPS
        self._renderer: SGRenderer = renderer or default_renderer
        self._current: int = 0
        self.data: dict[str, Any] = {}

    # -- public API ---------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Execute the wizard flow, returning collected data.

        Steps are visited in order.  ``Ctrl-C`` is caught and converted
        to ``SystemExit(1)``.
        """
        try:
            while 0 <= self._current < len(self._steps):
                step_id, title = self._steps[self._current]
                step_indicator(
                    self._current + 1,
                    len(self._steps),
                    title,
                )
                method = getattr(self, f"_step_{step_id}", self._step_default)
                result: str | None = method()
                if result is None:
                    break
                next_idx: int | None = self._step_index(result)
                if next_idx is None:
                    break
                self._current = next_idx
        except KeyboardInterrupt:
            self._handle_interrupt()
        return self.data

    # -- navigation helpers ------------------------------------------------

    def _next(self) -> str | None:
        """Return the step ID of the next step, or ``None`` at the end."""
        next_idx = self._current + 1
        if next_idx < len(self._steps):
            return self._steps[next_idx].id
        return None

    def _back(self) -> str | None:
        """Return the step ID of the previous step, or ``None`` at the
        start."""
        prev_idx = self._current - 1
        if prev_idx >= 0:
            return self._steps[prev_idx].id
        return None

    # -- internal helpers --------------------------------------------------

    def _step_default(self) -> str | None:
        """Fallback handler — auto-advance.

        Override individual ``_step_{id}`` methods in subclasses to
        customise behaviour.
        """
        return self._next()

    def _step_index(self, step_id: str) -> int | None:
        """Return the index of *step_id* in ``self._steps``, or ``None``."""
        for i, (sid, _) in enumerate(self._steps):
            if sid == step_id:
                return i
        return None

    @staticmethod
    def _handle_interrupt() -> None:
        """Print a cancellation message and exit with code 1."""
        print("Setup was interrupted. Run `openreview setup` to try again later.", file=sys.stderr)
        sys.exit(1)
