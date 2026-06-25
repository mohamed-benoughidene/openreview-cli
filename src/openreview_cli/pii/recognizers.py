"""Custom Presidio recognizers for contract-specific entity types."""

from presidio_analyzer import Pattern, PatternRecognizer

# AMOUNT recognizer: $5,000,000 and $1M shorthand
amount_recognizer = PatternRecognizer(
    supported_entity="AMOUNT",
    patterns=[
        Pattern("dollar_amount", r"\$[\d,]+(?:\.\d{2})?", 1.0),
        Pattern("dollar_shorthand", r"\$\d+(?:\.\d+)?[MBKmk]\b", 1.0),
    ],
)

# TAX_ID recognizer: EIN (12-3456789) and SSN
tax_id_recognizer = PatternRecognizer(
    supported_entity="TAX_ID",
    patterns=[
        Pattern("ein", r"\b\d{2}-\d{7}\b", 1.0),
        Pattern("ssn", r"\b\d{3}-\d{2}-\d{4}\b", 1.0),
    ],
)

# ID_DOCUMENT recognizer: passport, driver's license patterns
id_document_recognizer = PatternRecognizer(
    supported_entity="ID_DOCUMENT",
    patterns=[
        Pattern("passport", r"\b[A-Z]{1,2}\d{6,9}\b", 0.8),
        Pattern("drivers_license", r"\bDL\d{7,10}\b", 0.8),
    ],
)

# REG_NUMBER recognizer: company registration numbers
reg_number_recognizer = PatternRecognizer(
    supported_entity="REG_NUMBER",
    patterns=[
        Pattern("reg_number", r"\bREG[-_]\d{6,10}\b", 1.0),
    ],
)

CUSTOM_RECOGNIZERS = [
    amount_recognizer,
    tax_id_recognizer,
    id_document_recognizer,
    reg_number_recognizer,
]

__all__ = ["CUSTOM_RECOGNIZERS"]
