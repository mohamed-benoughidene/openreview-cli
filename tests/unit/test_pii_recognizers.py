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


def test_phone_recognizer_local_number() -> None:
    rec = get_custom_recognizers()[4]
    assert "PHONE_NUMBER" in rec.supported_entities
    pattern = rec.patterns[0]
    assert re.search(pattern.regex, "555-0101")
    assert re.search(pattern.regex, "Call 555-1234 today")
    # The regex is the standard local-number format; a 7-digit local
    # segment embedded in a longer string still matches (no special
    # casing of the 10-digit fiction range).
    assert re.search(pattern.regex, "555-010-1234")


def test_phone_recognizer_does_not_match_10_digit() -> None:
    # The 10-digit fiction range is NOT special-cased; a plain 10-digit
    # string without hyphens is not a local-number match.
    rec = get_custom_recognizers()[4]
    pattern = rec.patterns[0]
    assert not re.search(pattern.regex, "5550101234")


def test_id_document_recognizer_passport_word() -> None:
    rec = get_custom_recognizers()[2]
    assert "ID_DOCUMENT" in rec.supported_entities
    assert any(p.regex == r"\bPASSPORT\d{6,9}\b" for p in rec.patterns)


def test_id_document_passport_word_matches() -> None:
    rec = get_custom_recognizers()[2]
    pattern = next(p for p in rec.patterns if p.name == "passport_word")
    assert re.search(pattern.regex, "PASSPORT123457")
    assert re.search(pattern.regex, "PASSPORT1234567")
    assert not re.search(pattern.regex, "PASSPORT12345X")
    assert not re.search(pattern.regex, "PASSPORT12345")  # 5 digits < min


def test_id_document_keeps_existing_patterns() -> None:
    rec = get_custom_recognizers()[2]
    pattern = rec.patterns[0]  # existing passport regex
    assert re.search(pattern.regex, "AB123456")
    assert re.search(pattern.regex, "A1234567")


def test_acct_recognizer_iban() -> None:
    rec = get_custom_recognizers()[5]
    assert "ACCT" in rec.supported_entities
    pattern = rec.patterns[0]
    assert re.search(pattern.regex, "GB29NWBK60161331926801")
    assert re.search(pattern.regex, "DE89370400440532013000")
    assert not re.search(pattern.regex, "GB29 NWBK 6016 1331 9268 01")  # spaced IBAN not matched
