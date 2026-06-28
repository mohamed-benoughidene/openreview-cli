"""Unit tests for ui prompt wrappers (select, checkbox, confirm, text, password).

Tests verify:
  - Delegation to questionary.* and unsafe_ask()
  - auto_yes flag on confirm()
  - Non-interactive session raises SystemExit with USAGE_ERROR code
  - Escape returns None
  - Ctrl-C raises SystemExit(1)
  - Validate callback wired correctly for text()
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest
import questionary

from openreview_cli.errors import USAGE_ERROR
from openreview_cli.ui.components.prompt import (
    checkbox,
    confirm,
    password,
    select,
    text,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make sure renderer.is_interactive is True by default for all tests
    that don't explicitly override it."""
    from openreview_cli.ui.console import renderer as _r

    p = PropertyMock(return_value=True)
    monkeypatch.setattr(type(_r), "is_interactive", p)


def _mock_q(monkeypatch: pytest.MonkeyPatch, q_func: str, return_value: object) -> MagicMock:
    """Return a MagicMock that stands for a questionary Question whose
    ``unsafe_ask()`` returns *return_value*.

    The mock is patched into ``questionary.{q_func}``.
    """
    mock_q = MagicMock()
    mock_q.unsafe_ask.return_value = return_value
    monkeypatch.setattr(questionary, q_func, MagicMock(return_value=mock_q))
    return mock_q


# ---------------------------------------------------------------------------
# select()
# ---------------------------------------------------------------------------


def test_select_calls_questionary_and_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "select", "bravo")
    result = select("Pick one", choices=["alpha", "bravo"])
    assert result == "bravo"


def test_select_passes_message_and_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "select", "x")
    select("message", choices=["a", "b"])
    questionary.select.assert_called_once()  # type: ignore[attr-defined]
    call_kwargs = questionary.select.call_args[1]  # type: ignore[attr-defined]
    assert "message" in questionary.select.call_args[0][0] or call_kwargs.get("message")  # type: ignore[attr-defined]
    assert call_kwargs.get("choices") == ["a", "b"]


def test_select_escape_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "select", None)
    result = select("Pick one", choices=["a", "b"])
    assert result is None


def test_select_ctrlc_raises_systemexit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_q = MagicMock()
    mock_q.unsafe_ask.side_effect = KeyboardInterrupt
    monkeypatch.setattr(questionary, "select", MagicMock(return_value=mock_q))

    with pytest.raises(SystemExit) as exc:
        select("Pick one", choices=["a", "b"])
    assert exc.value.code == 1


def test_select_non_interactive_raises_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from openreview_cli.ui.console import renderer as _r

    p = PropertyMock(return_value=False)
    monkeypatch.setattr(type(_r), "is_interactive", p)
    monkeypatch.setattr(questionary, "select", MagicMock())

    with pytest.raises(SystemExit) as exc:
        select("Pick one", choices=["a", "b"])
    assert exc.value.code == USAGE_ERROR
    questionary.select.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# checkbox()
# ---------------------------------------------------------------------------


def test_checkbox_calls_questionary_and_returns_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "checkbox", ["a", "c"])
    result = checkbox("Pick", choices=["a", "b", "c"])
    assert result == ["a", "c"]


def test_checkbox_escape_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "checkbox", None)
    result = checkbox("Pick", choices=["a", "b"])
    assert result is None


def test_checkbox_ctrlc_raises_systemexit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_q = MagicMock()
    mock_q.unsafe_ask.side_effect = KeyboardInterrupt
    monkeypatch.setattr(questionary, "checkbox", MagicMock(return_value=mock_q))

    with pytest.raises(SystemExit) as exc:
        checkbox("Pick", choices=["a", "b"])
    assert exc.value.code == 1


def test_checkbox_non_interactive_raises_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from openreview_cli.ui.console import renderer as _r

    p = PropertyMock(return_value=False)
    monkeypatch.setattr(type(_r), "is_interactive", p)
    monkeypatch.setattr(questionary, "checkbox", MagicMock())

    with pytest.raises(SystemExit) as exc:
        checkbox("Pick", choices=["a", "b"])
    assert exc.value.code == USAGE_ERROR
    questionary.checkbox.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# confirm()
# ---------------------------------------------------------------------------


def test_confirm_calls_questionary_and_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "confirm", True)
    result = confirm("Proceed?")
    assert result is True


def test_confirm_default_true_passed_to_questionary(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "confirm", True)
    confirm("Proceed?", default=True)
    call_kwargs = questionary.confirm.call_args[1]  # type: ignore[attr-defined]
    assert call_kwargs.get("default") is True


def test_confirm_default_false_passed_to_questionary(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "confirm", False)
    confirm("Proceed?", default=False)
    call_kwargs = questionary.confirm.call_args[1]  # type: ignore[attr-defined]
    assert call_kwargs.get("default") is False


def test_confirm_auto_yes_returns_default_without_questionary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(questionary, "confirm", MagicMock())
    result = confirm("Proceed?", default=False, auto_yes=True)
    assert result is False
    questionary.confirm.assert_not_called()  # type: ignore[attr-defined]


def test_confirm_auto_yes_with_true_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(questionary, "confirm", MagicMock())
    result = confirm("Proceed?", default=True, auto_yes=True)
    assert result is True
    questionary.confirm.assert_not_called()  # type: ignore[attr-defined]


def test_confirm_non_interactive_without_auto_yes_raises_usage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openreview_cli.ui.console import renderer as _r

    p = PropertyMock(return_value=False)
    monkeypatch.setattr(type(_r), "is_interactive", p)
    monkeypatch.setattr(questionary, "confirm", MagicMock())

    with pytest.raises(SystemExit) as exc:
        confirm("Proceed?")
    assert exc.value.code == USAGE_ERROR
    questionary.confirm.assert_not_called()  # type: ignore[attr-defined]


def test_confirm_ctrlc_raises_systemexit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_q = MagicMock()
    mock_q.unsafe_ask.side_effect = KeyboardInterrupt
    monkeypatch.setattr(questionary, "confirm", MagicMock(return_value=mock_q))

    with pytest.raises(SystemExit) as exc:
        confirm("Proceed?")
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# text()
# ---------------------------------------------------------------------------


def test_text_calls_questionary_and_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "text", "hello")
    result = text("Enter:")
    assert result == "hello"


def test_text_escape_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "text", None)
    result = text("Enter:")
    assert result is None


def test_text_ctrlc_raises_systemexit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_q = MagicMock()
    mock_q.unsafe_ask.side_effect = KeyboardInterrupt
    monkeypatch.setattr(questionary, "text", MagicMock(return_value=mock_q))

    with pytest.raises(SystemExit) as exc:
        text("Enter:")
    assert exc.value.code == 1


def test_text_validate_callback_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate callback must be passed through to questionary."""

    def validate(val: str) -> str | bool:
        if len(val) < 3:
            return "Too short"
        return True

    _mock_q(monkeypatch, "text", "hello")
    text("Enter:", validate=validate)
    call_kwargs = questionary.text.call_args[1]  # type: ignore[attr-defined]
    assert call_kwargs.get("validate") is validate


def test_text_non_interactive_raises_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from openreview_cli.ui.console import renderer as _r

    p = PropertyMock(return_value=False)
    monkeypatch.setattr(type(_r), "is_interactive", p)
    monkeypatch.setattr(questionary, "text", MagicMock())

    with pytest.raises(SystemExit) as exc:
        text("Enter:")
    assert exc.value.code == USAGE_ERROR
    questionary.text.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# password()
# ---------------------------------------------------------------------------


def test_password_calls_questionary_and_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "password", "secret")
    result = password("Enter password:")
    assert result == "secret"


def test_password_escape_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_q(monkeypatch, "password", None)
    result = password("Enter password:")
    assert result is None


def test_password_ctrlc_raises_systemexit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_q = MagicMock()
    mock_q.unsafe_ask.side_effect = KeyboardInterrupt
    monkeypatch.setattr(questionary, "password", MagicMock(return_value=mock_q))

    with pytest.raises(SystemExit) as exc:
        password("Enter password:")
    assert exc.value.code == 1


def test_password_non_interactive_raises_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from openreview_cli.ui.console import renderer as _r

    p = PropertyMock(return_value=False)
    monkeypatch.setattr(type(_r), "is_interactive", p)
    monkeypatch.setattr(questionary, "password", MagicMock())

    with pytest.raises(SystemExit) as exc:
        password("Enter password:")
    assert exc.value.code == USAGE_ERROR
    questionary.password.assert_not_called()  # type: ignore[attr-defined]
