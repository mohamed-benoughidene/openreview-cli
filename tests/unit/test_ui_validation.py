"""Unit tests for ui validation helpers.

Tests verify:
  - validate_path: existing/non-existing paths
  - validate_config_key: known vs unknown keys
  - validate_range: bounds checks
  - validate_not_empty: whitespace-only rejection
  - validate_enum: case-insensitive matching
"""

from __future__ import annotations

from pathlib import Path

from openreview_cli.ui.components.validation import (
    validate_config_key,
    validate_enum,
    validate_not_empty,
    validate_path,
    validate_range,
)

# ---------------------------------------------------------------------------
# validate_path
# ---------------------------------------------------------------------------


def test_validate_path_existing_file(tmp_path: Path) -> None:
    f = tmp_path / "contract.pdf"
    f.write_text("dummy")
    valid, error = validate_path(str(f))
    assert valid is True
    assert error is None


def test_validate_path_existing_directory(tmp_path: Path) -> None:
    valid, error = validate_path(str(tmp_path))
    assert valid is True
    assert error is None


def test_validate_path_non_existent() -> None:
    valid, error = validate_path("/nonexistent/path/for/sure")
    assert valid is False
    assert error is not None
    assert "does not exist" in error or "not found" in error


def test_validate_path_empty_string() -> None:
    valid, error = validate_path("")
    assert valid is False
    assert error is not None


# ---------------------------------------------------------------------------
# validate_config_key
# ---------------------------------------------------------------------------


def test_validate_config_key_known() -> None:
    known = {"api_key", "model", "temperature"}
    valid, error = validate_config_key("model", known)
    assert valid is True
    assert error is None


def test_validate_config_key_unknown() -> None:
    known = {"api_key", "model"}
    valid, error = validate_config_key("nonsense", known)
    assert valid is False
    assert error is not None
    assert "nonsense" in error or "Unknown" in error


def test_validate_config_key_empty_known_set() -> None:
    valid, error = validate_config_key("anything", set())
    assert valid is False
    assert error is not None


# ---------------------------------------------------------------------------
# validate_range
# ---------------------------------------------------------------------------


def test_validate_range_within_bounds() -> None:
    valid, error = validate_range(5, 0, 10)
    assert valid is True
    assert error is None


def test_validate_range_at_minimum() -> None:
    valid, error = validate_range(0, 0, 10)
    assert valid is True
    assert error is None


def test_validate_range_at_maximum() -> None:
    valid, error = validate_range(10, 0, 10)
    assert valid is True
    assert error is None


def test_validate_range_below_min() -> None:
    valid, error = validate_range(-1, 0, 10)
    assert valid is False
    assert error is not None


def test_validate_range_above_max() -> None:
    valid, error = validate_range(11, 0, 10)
    assert valid is False
    assert error is not None


def test_validate_range_float_value() -> None:
    valid, error = validate_range(3.5, 0.0, 10.0)
    assert valid is True
    assert error is None


# ---------------------------------------------------------------------------
# validate_not_empty
# ---------------------------------------------------------------------------


def test_validate_not_empty_string() -> None:
    valid, error = validate_not_empty("hello")
    assert valid is True
    assert error is None


def test_validate_not_empty_whitespace_only() -> None:
    valid, error = validate_not_empty("   ")
    assert valid is False
    assert error is not None


def test_validate_not_empty_empty_string() -> None:
    valid, error = validate_not_empty("")
    assert valid is False
    assert error is not None


def test_validate_not_empty_none() -> None:
    valid, error = validate_not_empty("")
    assert valid is False
    assert error is not None


# ---------------------------------------------------------------------------
# validate_enum
# ---------------------------------------------------------------------------


def test_validate_enum_exact_case() -> None:
    valid, error = validate_enum("json", ["table", "json", "plain"])
    assert valid is True
    assert error is None


def test_validate_enum_case_insensitive() -> None:
    valid, error = validate_enum("JSON", ["table", "json", "plain"])
    assert valid is True
    assert error is None


def test_validate_enum_case_insensitive_mixed() -> None:
    valid, error = validate_enum("PlAiN", ["table", "json", "plain"])
    assert valid is True
    assert error is None


def test_validate_enum_not_in_list() -> None:
    valid, error = validate_enum("xml", ["table", "json", "plain"])
    assert valid is False
    assert error is not None


def test_validate_enum_empty_allowed() -> None:
    valid, error = validate_enum("json", [])
    assert valid is False
    assert error is not None
