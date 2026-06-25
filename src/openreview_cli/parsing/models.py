from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class ParseErrorCategory(StrEnum):
    file_not_found = "file_not_found"
    unsupported_format = "unsupported_format"
    corrupt = "corrupt"
    password_protected = "password_protected"
    empty = "empty"
    no_text = "no_text"


@dataclass(slots=True)
class Clause:
    id: str
    title: str | None
    text: str
    level: int
    parent_id: str | None
    source_page: int | None
    source_paragraph: int | None
    source_span: tuple[int, int] | None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id must be non-empty")
        if self.level < 0:
            raise ValueError(f"level must be >= 0, got {self.level}")
        if not self.text.strip():
            raise ValueError("text must be non-empty")
        if self.source_page is not None and self.source_paragraph is not None:
            raise ValueError("source_page and source_paragraph are mutually exclusive")


@dataclass
class Document:
    source_path: Path
    format: str
    page_count: int
    clause_count: int
    parse_duration_seconds: float
    warnings: list[str]

    def __post_init__(self) -> None:
        if self.format not in ("pdf", "docx"):
            raise ValueError(f"format must be 'pdf' or 'docx', got '{self.format}'")
        if self.page_count < 1:
            raise ValueError(f"page_count must be >= 1, got {self.page_count}")
        if self.clause_count < 0:
            raise ValueError(f"clause_count must be >= 0, got {self.clause_count}")
        if self.parse_duration_seconds < 0:
            raise ValueError(
                f"parse_duration_seconds must be >= 0, got {self.parse_duration_seconds}"
            )


@dataclass
class ParseError(Exception):
    exit_code: int
    category: str
    message: str
    action: str

    def __post_init__(self) -> None:
        if self.exit_code != 8:
            raise ValueError(f"exit_code must be 8, got {self.exit_code}")
        try:
            ParseErrorCategory(self.category)
        except ValueError:
            raise ValueError(f"invalid category: {self.category}") from None
        if not self.message:
            raise ValueError("message must be non-empty")
        if not self.action:
            raise ValueError("action must be non-empty")

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"ParseError({self.category}: {self.message})"


__all__ = ["Clause", "Document", "ParseError", "ParseErrorCategory"]
