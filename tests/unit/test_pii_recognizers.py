"""Unit tests for custom Presidio recognizers (regex patterns).

Lazy import: get_custom_recognizers() is called inside each test so
that presidio_analyzer is not loaded at collection time.
"""

import re
from typing import Any

from openreview_cli.pii.recognizers import get_custom_recognizers


def _has_pattern(recognizer: Any, pattern_str: str) -> bool:
    return any(p.regex == pattern_str for p in recognizer.patterns)


def test_amount_recognizer_dollar_amount() -> None:
    rec = get_custom_recognizers()[0]
    assert "AMOUNT" in rec.supported_entities
    assert _has_pattern(rec, r"\$[\d,]+(?:\.\d{2})?")


def test_amount_recognizer_shorthand() -> None:
    rec = get_custom_recognizers()[0]
    assert _has_pattern(rec, r"\$\d+(?:\.\d+)?[MBKmk]\b")


def test_amount_match_dollar() -> None:
    pattern = get_custom_recognizers()[0].patterns[0]  # dollar_amount
    assert re.search(pattern.regex, "$5,000,000")
    assert re.search(pattern.regex, "$500")
    assert re.search(pattern.regex, "$1,234.56")


def test_amount_match_shorthand() -> None:
    pattern = get_custom_recognizers()[0].patterns[1]
    assert re.search(pattern.regex, "$1M")
    assert re.search(pattern.regex, "$500K")
    assert re.search(pattern.regex, "$2.5M")


def test_tax_id_recognizer_ein() -> None:
    rec = get_custom_recognizers()[1]
    assert "TAX_ID" in rec.supported_entities
    pattern = rec.patterns[0]
    assert re.search(pattern.regex, "12-3456789")
    assert not re.search(pattern.regex, "123-45-6789")


def test_tax_id_recognizer_ssn() -> None:
    rec = get_custom_recognizers()[1]
    pattern = rec.patterns[1]
    assert re.search(pattern.regex, "123-45-6789")
    assert not re.search(pattern.regex, "12-3456789")


def test_id_document_recognizer_passport() -> None:
    rec = get_custom_recognizers()[2]
    assert "ID_DOCUMENT" in rec.supported_entities
    pattern = rec.patterns[0]
    assert re.search(pattern.regex, "AB123456")
    assert re.search(pattern.regex, "A1234567")


def test_id_document_recognizer_dl() -> None:
    rec = get_custom_recognizers()[2]
    pattern = rec.patterns[1]
    assert re.search(pattern.regex, "DL9876543")
    assert re.search(pattern.regex, "DL1234567890")


def test_reg_number_recognizer() -> None:
    rec = get_custom_recognizers()[3]
    assert "REG_NUMBER" in rec.supported_entities
    pattern = rec.patterns[0]
    assert re.search(pattern.regex, "REG-100001")
    assert re.search(pattern.regex, "REG_200001")
    assert not re.search(pattern.regex, "XYZ-123")
