"""Custom Presidio recognizers for contract-specific entity types.

Lazy import: presidio_analyzer is loaded only when get_custom_recognizers()
is called, so importing this module does not trigger spaCy/model loading.
"""

from typing import Any


def get_custom_recognizers() -> list[Any]:
    """Return the list of custom PatternRecognizer instances."""
    from presidio_analyzer import Pattern, PatternRecognizer

    return [
        PatternRecognizer(
            supported_entity="AMOUNT",
            patterns=[
                Pattern("dollar_amount", r"\$[\d,]+(?:\.\d{2})?", 1.0),
                Pattern("dollar_shorthand", r"\$\d+(?:\.\d+)?[MBKmk]\b", 1.0),
            ],
        ),
        PatternRecognizer(
            supported_entity="TAX_ID",
            patterns=[
                Pattern("ein", r"\b\d{2}-\d{7}\b", 1.0),
                Pattern("ssn", r"\b\d{3}-\d{2}-\d{4}\b", 1.0),
            ],
        ),
        PatternRecognizer(
            supported_entity="ID_DOCUMENT",
            patterns=[
                Pattern("passport", r"\b[A-Z]{1,2}\d{6,9}\b", 0.8),
                Pattern("drivers_license", r"\bDL\d{7,10}\b", 0.8),
            ],
        ),
        PatternRecognizer(
            supported_entity="REG_NUMBER",
            patterns=[
                Pattern("reg_number", r"\bREG[-_]\d{6,10}\b", 1.0),
            ],
        ),
    ]


__all__ = ["get_custom_recognizers"]
