import re
from collections.abc import Sequence
from typing import Any

from openreview_cli.parsing.models import Clause

_NUPUNKT: Any = None


def count_paragraphs(text: str) -> int:
    if not text.strip():
        return 1
    return max(1, len([p for p in text.split("\n\n") if p.strip()]))


_count_paragraphs = count_paragraphs  # ponytail: compat alias, remove after callers migrate


def _get_nupunkt() -> Any:
    global _NUPUNKT
    if _NUPUNKT is None:
        from nupunkt import sent_spans

        _NUPUNKT = sent_spans
    return _NUPUNKT


def nupunkt_detect_boundaries(text: str) -> list[Any]:
    sent_spans = _get_nupunkt()
    return sent_spans(text)  # type: ignore[no-any-return]


# A dotted clause number -- ``1.1``, ``2.3.4``, ``1.1.1.``. Every component is
# capped at three digits so that numeric literals which are not clause numbers
# cannot win: a year (``1.3.2019``), a decimal (``1.2005``), a document number
# (``1162967.3``). Real clause numbers fit well inside the cap -- deep CUAD
# contracts number ``1.1.107`` and ``9.02.5.1.4``. Both ``detect_numbering_pattern``
# (the level rule) and ``detect_clause_starts`` (the segmentation rule) use this
# one definition, so a line cannot be levelled without being a start, or vice versa.
_DOTTED_NUMBER = r"\d{1,3}(?:\.\d{1,3})+"

# ...and the number must not run on. ``1.3.2019`` is a date: matching its
# ``1.3`` prefix would hand a level to a line that is not a clause number at all,
# so the match has to end where the number ends (a digit, or a dot followed by a
# digit, means more components are coming) and at a word boundary. The word
# boundary is also the requirement that *something* separates the number from what
# follows -- glued text (``1.1X``) is not a clause number -- and it tolerates any
# non-word separator, not just whitespace: ``1.1: Payment``, ``1.1) Payment`` and
# ``1.2.3-beta tag`` end the number at ``:``, ``)`` and ``-``. Both rules share
# this one trailer, so the level rule cannot tolerate a separator the start rule
# rejects: ``detect_numbering_pattern`` levels exactly the dotted numbers that
# ``detect_clause_starts`` splits on, by construction. ``1.1.`` is fine -- the dot
# there ends the number rather than continuing it.
_DOTTED_NUMBER_END = r"(?!\d)(?!\.\d)\b"

_NUMBERING_PATTERNS = [
    (r"^\s*(?:ARTICLE|Article|SECTION|Section)\s+[IVXLCDM]+\b", 0),
    (r"^\s*(?:ARTICLE|Article|SECTION|Section)\s+\d+\.\d+", 1),
    (r"^\s*(?:ARTICLE|Article|SECTION|Section)\s+\d+\b", 0),
    (r"^\s*(?:Clause|clause)\s+\d+(?:\.\d+)*", 0),
    (rf"^\s*{_DOTTED_NUMBER}{_DOTTED_NUMBER_END}", 1),
    (r"^\s*\d+\.\s", 0),
    (r"^\s*\([a-z]\)", 2),
    (r"^\s*\(\d+\)", 2),
    (r"^\s*\([ivxlcdm]+\)", 2),
]


def detect_numbering_pattern(line: str) -> dict[str, Any] | None:
    for pattern, level in _NUMBERING_PATTERNS:
        if re.match(pattern, line.strip()):
            return {"level": level, "pattern": pattern}
    return None


def _extract_numbering_level(line: str) -> int | None:
    """Return the numbering level of *line*, or None when it declares no number."""
    match = detect_numbering_pattern(line)
    return match["level"] if match else None


def detect_clause_starts(text: str) -> list[tuple[int, dict[str, Any]]]:
    """Return ``(offset, match_info)`` for every line that starts a clause.

    The ``level`` in each returned dict is a placeholder (``auto``): the real
    numbering level of a clause comes from ``detect_numbering_pattern`` on the
    clause's first line, which the parsers feed to ``link_parent_ids``. The two
    functions must agree on what a numbered line is -- a line that the level rule
    recognises has to be a start here too, or its number claims a rung of the
    hierarchy while its text stays folded into the clause above.
    """
    starts: list[tuple[int, dict[str, Any]]] = []
    for match in re.finditer(
        r"(?m)^\s*(?:(?:ARTICLE|Article|SECTION|Section)\s+(?:[IVXLCDM]+|\d+)[:\s.]"
        r"|(?:Clause|clause)\s+\d+"
        # A dotted number starts a clause whether or not it carries a trailing dot:
        # ``1.1 Confidentiality``, ``1.1. Confidentiality``, ``2.3.4 Title``. This
        # reuses the level rule's ``_DOTTED_NUMBER`` and ``_DOTTED_NUMBER_END``, so
        # the two rules accept exactly the same numbers and the same separators
        # (whitespace, ``:``, ``)``, ``-``, ...); a line the level rule levels can
        # never be skipped here. The trailer's word boundary is what requires
        # something to separate the number from what follows, so glued text never
        # matches, and neither does anything mid-line, since ``^`` anchors every
        # alternative.
        rf"|{_DOTTED_NUMBER}{_DOTTED_NUMBER_END}"
        r"|\d+\.\s"
        r"|Section\s+\d+\.\d+"
        r"|\([a-z]\)|\(\d+\)|\([ivxlcdm]+\))",
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


def annotate_clauses(clauses: list[Clause]) -> list[str]:
    """Set ``Clause.is_non_english`` in place; return document-level parse warnings."""
    languages: set[str] = set()
    has_tofu = False
    for clause in clauses:
        language = detect_non_english(clause.text)
        clause.is_non_english = language is not None
        if language:
            languages.add(language)
        if not has_tofu and detect_tofu(clause.text):
            has_tofu = True

    warnings = [
        f"The contract appears to be in {language}. Results may be less accurate"
        for language in sorted(languages)
    ]
    if has_tofu:
        warnings.append("Some text could not be read correctly. Results may contain errors")
    return warnings


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
                            paragraph_count=count_paragraphs(text),
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
                    paragraph_count=count_paragraphs(text),
                )
            )
            counter += 1

    return clauses


def link_parent_ids(
    clauses: Sequence[Clause],
    open_levels: list[tuple[int, str]],
    *,
    levels: Sequence[int | None] | None = None,
) -> None:
    """Set ``Clause.parent_id`` from each clause's numbering level (0 = top).

    ``levels`` supplies the level per clause (the DOCX parser passes its heading
    level where it has one; the PDF parser passes the numbering level). ``None``
    is an unlevelled clause: it attaches to the deepest open ancestor if one is
    open, and never becomes an ancestor itself. The stack is a parameter, not a
    local, so the PDF parser's page loop can carry it across pages -- a section
    that opens on page 3 must parent the clauses on page 4.
    """
    for index, clause in enumerate(clauses):
        level = levels[index] if levels is not None else None
        if level is None:
            clause.parent_id = open_levels[-1][1] if open_levels else None
            continue
        while open_levels and open_levels[-1][0] >= level:
            open_levels.pop()
        clause.parent_id = open_levels[-1][1] if open_levels else None
        open_levels.append((level, clause.id))
