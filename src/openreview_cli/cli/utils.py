import os
import sys
from typing import Callable

import questionary


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"


def _add_hint(message: str, hint: str = "") -> str:
    return f"{message} ({hint})" if hint else message


def _select(
    message: str,
    choices: list[str],
    default: str | None = None,
    hint: str = "use arrow keys",
) -> str | None:
    result = questionary.select(
        _add_hint(message, hint),
        choices=choices,
        default=default or choices[0],
    ).ask()
    return result  # type: ignore[no-any-return]


def _checkbox(
    message: str,
    choices: list[str],
    hint: str = "space to toggle, enter to confirm",
) -> list[str] | None:
    result = questionary.checkbox(
        _add_hint(message, hint),
        choices=choices,
    ).ask()
    return result  # type: ignore[no-any-return]


def _autocomplete(
    message: str,
    choices: list[str],
    default: str | None = None,
    hint: str = "type to filter",
) -> str | None:
    result = questionary.autocomplete(
        _add_hint(message, hint),
        choices=choices,
        default=default or "",
    ).ask()
    return result  # type: ignore[no-any-return]


def _confirm(
    message: str,
    default: bool = True,
    hint: str = "",
) -> bool | None:
    result = questionary.confirm(
        _add_hint(message, hint),
        default=default,
    ).ask()
    return result  # type: ignore[no-any-return]


def _text(
    message: str,
    validate: Callable[[str], str | bool] | None = None,
    default: str | None = None,
    hint: str = "",
) -> str | None:
    result = questionary.text(
        _add_hint(message, hint),
        validate=validate,
        default=default or "",
    ).ask()
    return result  # type: ignore[no-any-return]


def _password(
    message: str,
    validate: Callable[[str], str | bool] | None = None,
    hint: str = "input will be masked",
) -> str | None:
    result = questionary.password(
        _add_hint(message, hint),
        validate=validate,
    ).ask()
    return result  # type: ignore[no-any-return]
