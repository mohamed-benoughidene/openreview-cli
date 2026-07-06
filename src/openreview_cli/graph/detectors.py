from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.parsing.models import Clause

# Default cross-reference patterns
_DEFAULT_CROSS_REF_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Section\s+(\d+(?:\.\d+)*)"),
    re.compile(r"as\s+(?:described|set forth|provided)\s+in\s+(?:Section\s+)?(\d+(?:\.\d+)*)"),
    re.compile(r"pursuant\s+to\s+(?:Section\s+)?(\d+(?:\.\d+)*)"),
]

# Definition patterns
_DEFINITION_QUOTED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"""(?:'|")([^'"]+)(?:'|")\s+means\b"""),
    re.compile(r"""(?:'|")([^'"]+)(?:'|")\s+shall\s+mean\b"""),
    re.compile(r"""(?:'|")([^'"]+)(?:'|")\s+refers?\s+to\b"""),
]

# Capitalised term heuristic
_CAPITALISED_TERM_PATTERN = re.compile(r"([A-Z][A-Za-z\s]+)\s+means\b")

# Term reference pattern
_TERM_REF_PATTERN = re.compile(r"""(?:'|")([^'"]+)(?:'|")""")


class CrossReferenceDetector:
    """Detect cross-references to other sections in clause text.

    Uses configurable list of regex patterns to find section references.
    Default patterns cover common English legal phrasing:
    - ``Section X.Y``
    - ``as set forth in Section X.Y``
    - ``pursuant to Section X.Y``
    """

    def __init__(self) -> None:
        self.patterns = _DEFAULT_CROSS_REF_PATTERNS

    def detect(self, text: str) -> list[str]:
        """Return list of section numbers referenced in text.

        Returns the first capture group from each pattern match
        (e.g., "3.2" from "Section 3.2"), which is then resolved
        against an index of numeric labels in the builder.
        """
        refs: list[str] = []
        for pattern in self.patterns:
            refs.extend(pattern.findall(text))
        return refs


class DefinitionDetector:
    """Detect defined terms and references to them in clause text.

    Detects:
    - Quoted terms followed by ``means`` / ``shall mean`` / ``refers to``
    - Capitalised terms followed by ``means`` (heuristic — bound false positives)
    """

    def extract_definitions(self, clauses: list[Clause]) -> dict[str, str]:
        """Return dict mapping defined term to the clause ID where it's defined."""
        definitions: dict[str, str] = {}
        for clause in clauses:
            text = (clause.title or "") + " " + clause.text
            # Check quoted definitions
            for pattern in _DEFINITION_QUOTED_PATTERNS:
                for match in pattern.finditer(text):
                    term = match.group(1).strip()
                    definitions[term] = clause.id
            # Check capitalised term heuristic
            for match in _CAPITALISED_TERM_PATTERN.finditer(text):
                term = match.group(1).strip()
                if term not in definitions:
                    definitions[term] = clause.id
        return definitions

    def count_references(self, text: str, definitions: dict[str, str]) -> list[tuple[str, str]]:
        """Return list of (term, clause_id) pairs for terms referenced in text."""
        refs: list[tuple[str, str]] = []
        for match in _TERM_REF_PATTERN.finditer(text):
            term = match.group(1).strip()
            if term in definitions:
                refs.append((term, definitions[term]))
        return refs


__all__ = [
    "CrossReferenceDetector",
    "DefinitionDetector",
]  # fmt: skip
