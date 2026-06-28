from __future__ import annotations

import enum
from typing import Literal, NamedTuple

WizardStep = Literal[
    "entry",
    "mode_selection",
    "configuration",
    "confirm",
    "processing",
    "results",
]


class ColorRole(NamedTuple):
    color: str
    no_color: str
    icon: str
    icon_ascii: str


class OutputFormat(enum.StrEnum):
    TABLE = "table"
    JSON = "json"
    PLAIN = "plain"
