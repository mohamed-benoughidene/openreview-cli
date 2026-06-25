"""Unit tests for custom Presidio recognizers (regex patterns)."""

import re
from typing import Any

from openreview_cli.pii.recognizers import CUSTOM_RECOGNIZERS


def _has_pattern(recognizer: Any, pattern_str: str) -> bool:
    return any(p.regex == pattern_str for p in recognizer.patterns)


def test_amount_recognizer_dollar_amount() -> None:
    rec = CUSTOM_RECOGNIZERS[0]
    assert "AMOUNT" in rec.supported_entities
    assert _has_pattern(rec, r"\$[\d,]+(?:\.\d{2})?")


def test_amount_recognizer_shorthand() -> None:
    rec = CUSTOM_RECOGNIZERS[0]
    assert _has_pattern(rec, r"\$\d+(?:\.\d+)?[MBKmk]\b")


def test_amount_match_dollar() -> None:
    rec = CUSTOM_RECOGNIZERS[0]
    pattern = rec.patterns[0]  # type: ignore[has-type]
    assert re.search(pattern.regex, "$5,000,000")
    assert re.search(pattern.regex, "$500")
    assert re.search(pattern.regex, "$1,234.56")


def test_amount_match_shorthand() -> None:
    rec = CUSTOM_RECOGNIZERS[0]
    pattern = rec.patterns[1]  # type: ignore[has-type]
    assert re.search(pattern.regex, "$1M")
    assert re.search(pattern.regex, "$500K")
    assert re.search(pattern.regex, "$2.5M")


def test_tax_id_recognizer_ein() -> None:
    rec = CUSTOM_RECOGNIZERS[1]
    assert "TAX_ID" in rec.supported_entities
    pattern = rec.patterns[0]  # type: ignore[has-type]
    assert re.search(pattern.regex, "12-3456789")
    assert not re.search(pattern.regex, "123-45-6789")


def test_tax_id_recognizer_ssn() -> None:
    rec = CUSTOM_RECOGNIZERS[1]
    pattern = rec.patterns[1]  # type: ignore[has-type]
    assert re.search(pattern.regex, "123-45-6789")
    assert not re.search(pattern.regex, "12-3456789")


def test_id_document_recognizer_passport() -> None:
    rec = CUSTOM_RECOGNIZERS[2]
    assert "ID_DOCUMENT" in rec.supported_entities
    pattern = rec.patterns[0]  # type: ignore[has-type]
    assert re.search(pattern.regex, "AB123456")
    assert re.search(pattern.regex, "A1234567")


def test_id_document_recognizer_dl() -> None:
    rec = CUSTOM_RECOGNIZERS[2]
    pattern = rec.patterns[1]  # type: ignore[has-type]
    assert re.search(pattern.regex, "DL9876543")
    assert re.search(pattern.regex, "DL1234567890")


def test_reg_number_recognizer() -> None:
    rec = CUSTOM_RECOGNIZERS[3]
    assert "REG_NUMBER" in rec.supported_entities
    pattern = rec.patterns[0]  # type: ignore[has-type]
    assert re.search(pattern.regex, "REG-100001")
    assert re.search(pattern.regex, "REG_200001")
    assert not re.search(pattern.regex, "XYZ-123")
