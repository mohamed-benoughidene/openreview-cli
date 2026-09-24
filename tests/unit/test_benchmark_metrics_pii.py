"""Unit tests for PII accuracy matching semantics (R8 amendment).

The match predicate is span-level (type-agnostic) partial matching: a
detection is correct when its value overlaps a ground-truth value as a
substring (either direction) or via at least one shared non-trivial token
(tokens split on whitespace and non-alphanumerics). The entity type label is
deliberately ignored — a wrong-type placeholder still redacts the right span.
"""

from openreview_cli.benchmark.metrics_pii import (
    _tokenize_match,
    _values_match,
    evaluate_pii_accuracy,
)


def test_tokenize_splits_on_whitespace_and_non_alphanumerics() -> None:
    assert _tokenize_match("100 Auto Blvd, Suite 1, San Francisco, CA 94107") == [
        "100",
        "Auto",
        "Blvd",
        "Suite",
        "1",
        "San",
        "Francisco",
        "CA",
        "94107",
    ]
    assert _tokenize_match("$5,000.00") == ["5", "000", "00"]
    assert _tokenize_match("AutoName1 Smith") == ["AutoName1", "Smith"]
    assert _tokenize_match("GB29NWBK60161331926801") == ["GB29NWBK60161331926801"]


def test_exact_match_after_normalization() -> None:
    assert _values_match("AutoName1 Smith", "autoname1 smith")
    assert _values_match("555-0101", "555-0101")
    assert _values_match("AutoCompanyA1 Inc.", "autocompanya1 inc.")


def test_detection_is_substring_of_ground_truth() -> None:
    # Detector emits a span ("San Francisco", "AutoName1") of a longer GT value.
    assert _values_match("100 Auto Blvd, Suite 1, San Francisco, CA 94107", "san francisco")
    assert _values_match("AutoName1 Smith", "autoname1")
    assert _values_match("AutoCompanyA1 Inc.", "autocompanya1")


def test_ground_truth_is_substring_of_detection() -> None:
    assert _values_match("AutoName1", "autoname1 smith")
    assert _values_match("San Francisco", "100 auto blvd san francisco ca")


def test_token_set_overlap_counts_as_match() -> None:
    # Different tokenization boundaries but a shared non-trivial token.
    assert _values_match("AutoCompanyA1 Inc.", "AutoCompanyA1")
    assert _values_match("REG-100001", "100001")
    assert _values_match("12-3456789", "3456789")


def test_type_label_is_ignored_by_matching() -> None:
    # The predicate is type-agnostic: value overlap alone decides the match, so
    # a wrong-type detection covering the right span is credited (it still
    # redacts the PII). ``_values_match`` takes no type arguments at all.
    documents = [
        (
            "doc1",
            "AutoName1 Smith works at AutoCompanyA1 Inc.",
            [
                {"value": "AutoName1 Smith", "type": "PERSON"},
                {"value": "AutoCompanyA1 Inc.", "type": "ORGANIZATION"},
            ],
        ),
    ]

    def detect_fn(text: str) -> list[dict[str, str]]:
        # Correct spans, deliberately wrong type labels.
        return [
            {"value": "AutoName1 Smith", "type": "LOCATION"},
            {"value": "AutoCompanyA1 Inc.", "type": "PERSON"},
        ]

    metrics = evaluate_pii_accuracy(documents, detect_fn)
    assert metrics["pii_recall"].value == 1.0
    assert metrics["pii_precision"].value == 1.0
    assert metrics["pii_recall_person"].value == 1.0
    assert metrics["pii_recall_organization"].value == 1.0


def test_disjoint_values_do_not_match() -> None:
    # No shared tokens and no substring relation → no match. (Note: two
    # different people sharing a surname DO match under token-overlap
    # semantics — the shared token is non-trivial — which is why span-level
    # PERSON detection works. Truly disjoint values do not match.)
    assert not _values_match("AutoName1 Smith", "AutoCompanyA1 Inc.")
    assert not _values_match("100 Auto Blvd", "200 Market Road")
    assert not _values_match("auto_email_1@example.com", "PASSPORT123457")
    assert not _values_match("REG-100001", "555-0101")


def test_empty_and_degenerate_values() -> None:
    # Exact normalized equality always matches.
    assert _values_match("$", "$")
    # Single-character substrings do NOT match (minimum-length guard prevents
    # trivial fragments like "$" in "$1" from inflating precision).
    assert not _values_match("$", "$1")
    # Empty strings are special-cased: "" is a substring of everything, so an
    # empty value only matches an empty value (avoiding trivial all-match).
    assert not _values_match("", "autoname1")
    assert not _values_match("AutoName1 Smith", "")
    assert _values_match("", "")


def test_full_evaluation_uses_token_overlap_matching() -> None:
    """End-to-end: exact-match evaluator would score 0; overlap scores 2/2."""
    documents = [
        (
            "doc1",
            "AutoName1 Smith works at AutoCompanyA1 Inc. in San Francisco.",
            [
                {"value": "AutoName1 Smith", "type": "PERSON"},
                {"value": "AutoCompanyA1 Inc.", "type": "ORGANIZATION"},
                {"value": "San Francisco", "type": "LOCATION"},
            ],
        ),
    ]

    def detect_fn(text: str) -> list[dict[str, str]]:
        return [
            {"value": "AutoName1", "type": "PERSON"},
            {"value": "AutoCompanyA1", "type": "ORGANIZATION"},
            {"value": "San Francisco", "type": "LOCATION"},
        ]

    metrics = evaluate_pii_accuracy(documents, detect_fn)
    assert metrics["pii_recall"].value == 1.0
    assert metrics["pii_precision"].value == 1.0
    assert metrics["pii_recall"].n == 3
    assert metrics["pii_precision"].n == 3


def test_false_positive_lowers_precision() -> None:
    """A detection that matches no GT value at all counts against precision."""
    documents = [
        (
            "doc1",
            "AutoName1 Smith",
            [{"value": "AutoName1 Smith", "type": "PERSON"}],
        ),
    ]

    def detect_fn(text: str) -> list[dict[str, str]]:
        return [
            {"value": "AutoName1 Smith", "type": "PERSON"},
            {"value": "Somewhere Else", "type": "LOCATION"},  # false positive
        ]

    metrics = evaluate_pii_accuracy(documents, detect_fn)
    assert metrics["pii_recall"].value == 1.0
    assert metrics["pii_precision"].value == 0.5


def test_single_detection_credits_multiple_same_type_gt_entities() -> None:
    """A merged span covering two GT entities of the same type credits both (MUC)."""
    documents = [
        (
            "doc1",
            "ManualCompanyA1 Corp and ManualCompanyB1 Ltd.",
            [
                {"value": "ManualCompanyA1 Corp", "type": "ORGANIZATION"},
                {"value": "ManualCompanyB1 Ltd", "type": "ORGANIZATION"},
            ],
        ),
    ]

    def detect_fn(text: str) -> list[dict[str, str]]:
        return [{"value": "ManualCompanyA1 Corp and ManualCompanyB1 Ltd.", "type": "ORGANIZATION"}]

    metrics = evaluate_pii_accuracy(documents, detect_fn)
    assert metrics["pii_recall"].value == 1.0
    assert metrics["pii_recall"].n == 2
    assert metrics["pii_recall_organization"].n == 2
    assert metrics["pii_recall_organization"].value == 1.0
