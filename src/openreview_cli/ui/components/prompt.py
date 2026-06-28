"""Interactive prompt wrappers around questionary.

Each function handles:
  - Interactive check via ``SGRenderer().is_interactive``
  - ``auto_yes`` flag (auto-answers ``confirm()`` with the default)
  - ``unsafe_ask()`` so Ctrl-C raises ``KeyboardInterrupt`` (mapped to ``SystemExit(1)``)
  - Esc returns ``None``
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, cast

import questionary

from openreview_cli.errors import USAGE_ERROR
from openreview_cli.ui.console import renderer

if TYPE_CHECKING:
    from collections.abc import Callable


def _ensure_interactive() -> None:
    """Exit with USAGE_ERROR if the session is not interactive."""
    if not renderer.is_interactive:
        print("Error: interactive input required (not a TTY)", file=sys.stderr)
        sys.exit(USAGE_ERROR)


def _add_hint(message: str, hint: str = "") -> str:
    return f"{message} ({hint})" if hint else message


def _unsafe_ask(question: questionary.Question) -> Any:
    """Call ``unsafe_ask()`` on *question* and map ``KeyboardInterrupt``
    to ``SystemExit(1)``."""
    try:
        return question.unsafe_ask()
    except KeyboardInterrupt:
        sys.exit(1)


def select(
    message: str,
    choices: list[str],
    default: str | None = None,
    hint: str = "use arrow keys",
) -> str | None:
    """Prompt the user to pick one option from *choices*.

    Returns the selected value, or ``None`` if the user pressed Esc.
    """
    _ensure_interactive()
    question = questionary.select(
        _add_hint(message, hint),
        choices=choices,
        default=default or choices[0],
    )
    return cast("str | None", _unsafe_ask(question))


def checkbox(
    message: str,
    choices: list[str],
    hint: str = "space to toggle, enter to confirm",
) -> list[str] | None:
    """Prompt the user to select zero or more options from *choices*.

    Returns the selected values, or ``None`` if the user pressed Esc.
    """
    _ensure_interactive()
    question = questionary.checkbox(
        _add_hint(message, hint),
        choices=choices,
    )
    return cast("list[str] | None", _unsafe_ask(question))


def confirm(
    message: str,
    default: bool = True,
    hint: str = "",
    auto_yes: bool = False,
) -> bool:
    """Prompt the user with a yes/no confirmation.

    When *auto_yes* is ``True``, *default* is returned immediately
    without displaying a prompt.
    """
    if auto_yes:
        return default
    _ensure_interactive()
    question = questionary.confirm(
        _add_hint(message, hint),
        default=default,
    )
    result = _unsafe_ask(question)
    return bool(result)  # unsafer_ask may return None on Esc; treat as False


def text(
    message: str,
    validate: Callable[[str], str | bool] | None = None,
    default: str | None = None,
    hint: str = "",
) -> str | None:
    """Prompt the user for free-form text input.

    Returns the entered text, or ``None`` if the user pressed Esc.
    """
    _ensure_interactive()
    question = questionary.text(
        _add_hint(message, hint),
        validate=validate,
        default=default or "",
    )
    return cast("str | None", _unsafe_ask(question))


def password(
    message: str,
    validate: Callable[[str], str | bool] | None = None,
    hint: str = "input will be masked",
) -> str | None:
    """Prompt the user for a masked password.

    Returns the entered text, or ``None`` if the user pressed Esc.
    """
    _ensure_interactive()
    question = questionary.password(
        _add_hint(message, hint),
        validate=validate,
    )
    return cast("str | None", _unsafe_ask(question))
