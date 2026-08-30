"""Unit tests for ``_json_safe`` helper in ``openreview_cli.recovery.models``.

The C4 fix wired ``db_path`` into the production ``RecoveryCoordinator``
in ``review/runner.py``. The pipeline runner was already populating
``partial_data`` and ``saved_results`` with non-JSON-serializable
objects (e.g. ``Document``). To prevent ``json.dumps`` from crashing
the persistence layer, ``RecoveryContext.to_dict`` now passes those
fields through ``_json_safe``. This test pins that behavior so the
helper cannot regress to a strict ``json.dumps`` (which would crash
on the production code path).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from openreview_cli.recovery.models import RecoveryContext, _json_safe


class _NonSerializable:
    """A class with no JSON serializer support — simulates ``Document``."""

    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return f"_NonSerializable(x={self.x})"


@dataclass
class _NonSerializableDataclass:
    y: str


def test_json_safe_primitives_pass_through() -> None:
    """Booleans, ints, floats, strings, None pass through unchanged."""
    assert _json_safe(None) is None
    assert _json_safe(True) is True
    assert _json_safe(42) == 42
    assert _json_safe(3.14) == 3.14
    assert _json_safe("hello") == "hello"


def test_json_safe_dict_with_non_serializable_value() -> None:
    """Dicts with non-serializable values get the value coerced to repr."""
    d = {"a": 1, "b": _NonSerializable(7)}
    out = _json_safe(d)
    assert out == {"a": 1, "b": "_NonSerializable(x=7)"}
    # The result must be JSON-serializable.
    json.dumps(out)


def test_json_safe_nested_non_serializable() -> None:
    """Nested non-serializable values are coerced recursively."""
    d = {"outer": {"inner": _NonSerializable(99)}}
    out = _json_safe(d)
    assert out == {"outer": {"inner": "_NonSerializable(x=99)"}}
    json.dumps(out)


def test_json_safe_list_with_non_serializable() -> None:
    """Lists/tuples with non-serializable values are coerced element-wise."""
    lst = [1, _NonSerializable(2), "x"]
    out = _json_safe(lst)
    assert out == [1, "_NonSerializable(x=2)", "x"]
    json.dumps(out)


def test_json_safe_dataclass_coerced() -> None:
    """Dataclass values are converted via dataclasses.asdict then recursively."""
    d = {"item": _NonSerializableDataclass(y="hi")}
    out = _json_safe(d)
    assert out == {"item": {"y": "hi"}}
    json.dumps(out)


def test_json_safe_set_coerced() -> None:
    """Sets are converted to lists."""
    s = {1, 2, 3}
    out = _json_safe(s)
    assert sorted(out) == [1, 2, 3]
    json.dumps(out)


def test_recovery_context_to_dict_handles_non_serializable_partial_data() -> None:
    """End-to-end: ``RecoveryContext.to_dict`` must not crash on Document-like data."""
    ctx = RecoveryContext(
        provider_list=["openai/gpt-4"],
        partial_data={"doc": _NonSerializable(42)},
        saved_results={"parsed": _NonSerializableDataclass(y="ok")},
    )
    d = ctx.to_dict()
    # The result must be JSON-serializable.
    serialized = json.dumps(d)
    # And the coerced values are present.
    assert '"doc": "_NonSerializable(x=42)"' in serialized
    assert '"parsed": {"y": "ok"}' in serialized
