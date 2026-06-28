from __future__ import annotations

from types import MappingProxyType

import pytest

from openreview_cli.ui.components.key_bindings import KEY_BINDINGS

# All actions that should be valid per the Action literal type
_ALL_ACTIONS = frozenset(
    {
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
    }
)

# The keys that must exist in KEY_BINDINGS
_EXPECTED_KEYS = frozenset(
    {
        "up",
        "down",
        "enter",
        "space",
        "escape",
        "ctrl-c",
        "tab",
        "shift-tab",
        "home",
        "end",
    }
)


class TestKeyBindingsConstants:
    """T023: Key binding constants are correct."""

    def test_all_expected_keys_present(self) -> None:
        assert KEY_BINDINGS.keys() == _EXPECTED_KEYS

    def test_no_extra_keys(self) -> None:
        assert KEY_BINDINGS.keys() == _EXPECTED_KEYS

    def test_each_binding_is_action_tuple(self) -> None:
        for key, value in KEY_BINDINGS.items():
            assert isinstance(value, tuple), f"Binding for {key!r} is not a tuple"
            assert len(value) == 3, f"Binding for {key!r} does not have 3 elements"
            action, description, component = value
            assert isinstance(action, str), f"Action for {key!r} is not a string"
            assert isinstance(description, str), f"Description for {key!r} is not a string"
            assert isinstance(component, str), f"Component for {key!r} is not a string"

    def test_all_bound_actions_are_valid(self) -> None:
        bound_actions = {action for action, _, _ in KEY_BINDINGS.values()}
        assert bound_actions.issubset(_ALL_ACTIONS)

    def test_action_names_are_correct(self) -> None:
        expected = {
            "up": "move_up",
            "down": "move_down",
            "enter": "confirm",
            "space": "toggle",
            "escape": "cancel",
            "ctrl-c": "exit",
            "tab": "cycle_forward",
            "shift-tab": "cycle_backward",
            "home": "jump_start",
            "end": "jump_end",
        }
        for key, expected_action in expected.items():
            actual_action = KEY_BINDINGS[key][0]
            assert actual_action == expected_action, (
                f"{key!r} expected action {expected_action!r}, got {actual_action!r}"
            )

    def test_descriptions_are_non_empty(self) -> None:
        for key in KEY_BINDINGS:
            desc = KEY_BINDINGS[key][1]
            assert desc, f"Description for {key!r} is empty"

    def test_components_are_non_empty(self) -> None:
        for key in KEY_BINDINGS:
            component = KEY_BINDINGS[key][2]
            assert component, f"Component for {key!r} is empty"


class TestKeyBindingsConflicts:
    """T023: No two actions use the same key."""

    def test_no_duplicate_keys(self) -> None:
        keys = list(KEY_BINDINGS.keys())
        assert len(keys) == len(set(keys))

    def test_no_duplicate_actions(self) -> None:
        actions = [action for action, _, _ in KEY_BINDINGS.values()]
        assert len(actions) == len(set(actions)), "Two keys are bound to the same action"


class TestKeyBindingsImmutability:
    """T023: KEY_BINDINGS dict is immutable."""

    def test_is_mappingproxy(self) -> None:
        assert isinstance(KEY_BINDINGS, MappingProxyType)

    def test_cannot_add_key(self) -> None:
        with pytest.raises(TypeError):
            KEY_BINDINGS["f1"] = ("filter", "Filter", "general")  # type: ignore[index]

    def test_cannot_remove_key(self) -> None:
        with pytest.raises(TypeError):
            del KEY_BINDINGS["tab"]  # type: ignore[attr-defined]
