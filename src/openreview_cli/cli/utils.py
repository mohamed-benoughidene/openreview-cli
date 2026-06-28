import questionary

from openreview_cli.ui.components.prompt import _add_hint


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
