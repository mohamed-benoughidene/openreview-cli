"""Key binding constants for the openreview TUI.

Provides a single immutable mapping from key names to (action, description,
component) tuples.  Every action is a member of the ``Action`` literal type.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal

# ── Action type ────────────────────────────────────────────────────────

Action = Literal[
    "move_up",
    "move_down",
    "confirm",
    "cancel",
    "exit",
    "toggle",
    "filter",
    "complete",
    "cycle_forward",
    "cycle_backward",
    "jump_start",
    "jump_end",
]

# ── Key-to-action mapping ──────────────────────────────────────────────

_KEY_BINDINGS: dict[str, tuple[Action, str, str]] = {
    "up": ("move_up", "Move cursor up", "list"),
    "down": ("move_down", "Move cursor down", "list"),
    "enter": ("confirm", "Confirm selection", "general"),
    "space": ("toggle", "Toggle item selection", "list"),
    "escape": ("cancel", "Cancel current action", "general"),
    "ctrl-c": ("exit", "Exit application", "global"),
    "tab": ("cycle_forward", "Cycle to next item", "general"),
    "shift-tab": ("cycle_backward", "Cycle to previous item", "general"),
    "home": ("jump_start", "Jump to first item", "list"),
    "end": ("jump_end", "Jump to last item", "list"),
}

KEY_BINDINGS: MappingProxyType[str, tuple[Action, str, str]] = MappingProxyType(_KEY_BINDINGS)
