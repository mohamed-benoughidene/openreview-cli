import re
from typing import Any

from openreview_cli.parsing.models import Clause

_NUPUNKT: Any = None


def _get_nupunkt() -> Any:
    global _NUPUNKT
    if _NUPUNKT is None:
        from nupunkt import sent_spans

        _NUPUNKT = sent_spans
    return _NUPUNKT


def nupunkt_detect_boundaries(text: str) -> list[Any]:
    sent_spans = _get_nupunkt()
    return sent_spans(text)  # type: ignore[no-any-return]


_NUMBERING_PATTERNS = [
    (r"^\s*(?:ARTICLE|Article|SECTION|Section)\s+(?:[IVXLCDM]+|\d+)[:\s.]", 0),
    (r"^\s*(?:Clause|clause)\s+\d+", 0),
    (r"^\s*\d+\.(?:\d+\.)*\s", 1),
    (r"^\s*Section\s+\d+\.\d+", 1),
    (r"^\s*\([a-z]\)", 2),
    (r"^\s*\(\d+\)", 2),
    (r"^\s*\([ivxlcdm]+\)", 2),
]


def detect_numbering_pattern(line: str) -> dict[str, Any] | None:
    for pattern, level in _NUMBERING_PATTERNS:
        if re.match(pattern, line.strip()):
            return {"level": level, "pattern": pattern}
    return None


def detect_clause_starts(text: str) -> list[tuple[int, dict[str, Any]]]:
    starts: list[tuple[int, dict[str, Any]]] = []
    for match in re.finditer(
        r"(?m)^\s*(?:(?:ARTICLE|Article|SECTION|Section)\s+(?:[IVXLCDM]+|\d+)[:\s.]|(?:Clause|clause)\s+\d+|\d+\.(?:\d+\.)*\s|Section\s+\d+\.\d+|\([a-z]\)|\(\d+\)|\([ivxlcdm]+\))",
        text,
    ):
        starts.append((match.start(), {"level": 1, "pattern": "auto"}))
    return starts


_UNICODE_RANGES = {
    "Arabic": range(0x0600, 0x06FF + 1),
    "CJK": range(0x4E00, 0x9FFF + 1),
    "Cyrillic": range(0x0400, 0x04FF + 1),
}

_LANGUAGE_MAP = {
    "Arabic": "Arabic",
    "CJK": "Chinese/Japanese/Korean",
    "Cyrillic": "Russian/Ukrainian/Bulgarian",
}


def detect_non_english(text: str) -> str | None:
    for name, rng in _UNICODE_RANGES.items():
        for ch in text:
            if ord(ch) in rng:
                return _LANGUAGE_MAP.get(name, name)
    return None


def detect_tofu(text: str) -> bool:
    return "\ufffd" in text


def build_hierarchy(
    boundaries: list[tuple[int, int]],
    clause_starts: list[tuple[int, dict[str, Any]]],
    headings: list[tuple[int, str, int]],
    page_num: int,
    start_counter: int,
    page_text: str = "",
) -> list[Clause]:
    clauses: list[Clause] = []
    counter = start_counter

    if not clause_starts and not headings:
        if boundaries:
            for start, end in boundaries:
                text = page_text[start:end].strip()
                if text:
                    clauses.append(
                        Clause(
                            id=f"clause-{counter}",
                            title=None,
                            text=text,
                            level=0,
                            parent_id=None,
                            source_page=page_num,
                            source_paragraph=None,
                            source_span=(start, end),
                        )
                    )
                    counter += 1
        return clauses

    sorted_starts = sorted(clause_starts, key=lambda x: x[0])
    for i, (start_pos, match) in enumerate(sorted_starts):
        end_pos = sorted_starts[i + 1][0] if i + 1 < len(sorted_starts) else len(page_text)
        text = page_text[start_pos:end_pos].strip()
        if text:
            clauses.append(
                Clause(
                    id=f"clause-{counter}",
                    title=None,
                    text=text,
                    level=match["level"] if isinstance(match, dict) else 1,
                    parent_id=None,
                    source_page=page_num,
                    source_paragraph=None,
                    source_span=(start_pos, end_pos),
                )
            )
            counter += 1

    return clauses
