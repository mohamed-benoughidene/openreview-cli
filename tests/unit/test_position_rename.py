"""Unit tests for US1: Position enum rename (favorable→preferred, etc.).

Tests T003-T006: enum values, legacy key aliasing with DeprecationWarning,
default_position mapping, and colour mapping.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from openreview_cli.review.colors import assign_colors
from openreview_cli.review.models import (
    ClauseAssessment,
    Position,
    QAVerdict,
)


class TestPositionEnum:
    """T003: Position enum exposes new values."""

    def test_new_values(self) -> None:
        assert Position.PREFERRED.value == "preferred"
        assert Position.ACCEPTABLE.value == "acceptable"
        assert Position.WALKAWAY.value == "walkaway"
        assert Position.UNCERTAIN.value == "uncertain"

    def test_old_values_no_longer_exist(self) -> None:
        with pytest.raises(AttributeError):
            _ = Position.favorable  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            _ = Position.neutral  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            _ = Position.unfavorable  # type: ignore[attr-defined]

    def test_from_string_new_values(self) -> None:
        assert Position("preferred") == Position.PREFERRED
        assert Position("acceptable") == Position.ACCEPTABLE
        assert Position("walkaway") == Position.WALKAWAY
        assert Position("uncertain") == Position.UNCERTAIN

    def test_from_string_old_values_raises(self) -> None:
        with pytest.raises(ValueError):
            Position("favorable")
        with pytest.raises(ValueError):
            Position("neutral")
        with pytest.raises(ValueError):
            Position("unfavorable")


class TestLegacyKeyAliasing:
    """T004: Legacy YAML keys map to new values with DeprecationWarning."""

    def test_legacy_keys_mapped_with_warning(self) -> None:
        """_parse_category should accept 'favorable'/'neutral'/'unfavorable'
        and emit DeprecationWarning."""
        from openreview_cli.review.playbook import _parse_category

        raw = {
            "id": "test-cat",
            "name": "Test",
            "description": "Test category",
            "favorable": {"description": "Good", "exemplars": ["example A"]},
            "neutral": {"description": "OK", "exemplars": ["example B"]},
            "unfavorable": {"description": "Bad", "exemplars": ["example C"]},
            "default_position": "favorable",
        }

        with pytest.warns(DeprecationWarning, match="favorable.*preferred"):
            cat = _parse_category(raw)

        assert cat.preferred.description == "Good"
        assert cat.acceptable.description == "OK"
        assert cat.walkaway.description == "Bad"
        assert cat.default_position == Position.PREFERRED

    def test_new_keys_no_warning(self) -> None:
        """_parse_category with new keys should NOT emit DeprecationWarning."""
        from openreview_cli.review.playbook import _parse_category

        raw = {
            "id": "test-cat",
            "name": "Test",
            "description": "Test category",
            "preferred": {"description": "Good", "exemplars": ["example A"]},
            "acceptable": {"description": "OK", "exemplars": ["example B"]},
            "walkaway": {"description": "Bad", "exemplars": ["example C"]},
            "default_position": "preferred",
        }

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            cat = _parse_category(raw)

        assert cat.preferred.description == "Good"

    def test_legacy_default_position_maps(self) -> None:
        """T005: default_position in legacy YAML maps through the same alias."""
        from openreview_cli.review.playbook import _parse_category

        raw = {
            "id": "test-cat",
            "name": "Test",
            "description": "Test",
            "favorable": {"description": "G", "exemplars": ["a"]},
            "neutral": {"description": "N", "exemplars": ["b"]},
            "unfavorable": {"description": "U", "exemplars": ["c"]},
            "default_position": "favorable",
        }

        with pytest.warns(DeprecationWarning):
            cat = _parse_category(raw)
        assert cat.default_position == Position.PREFERRED

        # neutral and unfavorable should also work
        raw["default_position"] = "neutral"
        with pytest.warns(DeprecationWarning):
            cat = _parse_category(raw)
        assert cat.default_position == Position.ACCEPTABLE

        raw["default_position"] = "unfavorable"
        with pytest.warns(DeprecationWarning):
            cat = _parse_category(raw)
        assert cat.default_position == Position.WALKAWAY

    def test_mixed_legacy_and_new_uses_new(self) -> None:
        """When both old and new keys are present, new keys take precedence
        and no warning is emitted."""
        from openreview_cli.review.playbook import _parse_category

        raw = {
            "id": "test-cat",
            "name": "Test",
            "description": "Test",
            "favorable": {"description": "OLD", "exemplars": ["old"]},
            "preferred": {"description": "NEW", "exemplars": ["new"]},
            "neutral": {"description": "N_OLD", "exemplars": ["n_old"]},
            "acceptable": {"description": "N_NEW", "exemplars": ["n_new"]},
            "unfavorable": {"description": "U_OLD", "exemplars": ["u_old"]},
            "walkaway": {"description": "U_NEW", "exemplars": ["u_new"]},
            "default_position": "preferred",
        }

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            cat = _parse_category(raw)

        assert cat.preferred.description == "NEW"
        assert cat.acceptable.description == "N_NEW"
        assert cat.walkaway.description == "U_NEW"


class TestLegacyPlaybookLoad:
    """T004+005: Full playbook load with legacy keys."""

    LEGACY_YAML = """\
id: legacy-test
mode: precheck
metadata:
  version: "1.0"
  description: Legacy test playbook
  author: test
categories:
  - id: conf
    name: Confidentiality
    description: Test
    favorable:
      description: Good
      exemplars:
        - "example A"
    neutral:
      description: OK
      exemplars:
        - "example B"
    unfavorable:
      description: Bad
      exemplars:
        - "example C"
    default_position: "neutral"
"""

    def test_legacy_playbook_loads(self, tmp_path: Path) -> None:
        """A full legacy YAML playbook loads with DeprecationWarning."""
        from openreview_cli.review.playbook import load_playbook

        p = tmp_path / "legacy.yaml"
        p.write_text(self.LEGACY_YAML)

        with pytest.warns(DeprecationWarning):
            playbook = load_playbook(p)

        assert playbook.id == "legacy-test"
        assert len(playbook.categories) == 1
        cat = playbook.categories[0]
        assert cat.preferred.description == "Good"
        assert cat.acceptable.description == "OK"
        assert cat.walkaway.description == "Bad"
        assert cat.default_position == Position.ACCEPTABLE


class TestColourMapping:
    """T006: Colour mapping uses new position keys."""

    def test_preferred_is_green(self) -> None:
        ca = ClauseAssessment(
            clause_id="c1",
            clause_text="text",
            playbook_category="test",
            confidence=0.9,
            citation="text",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
            position=Position.PREFERRED,
        )
        assign_colors([ca])
        assert ca.color == "green"

    def test_acceptable_is_green(self) -> None:
        ca = ClauseAssessment(
            clause_id="c1",
            clause_text="text",
            playbook_category="test",
            confidence=0.9,
            citation="text",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
            position=Position.ACCEPTABLE,
        )
        assign_colors([ca])
        assert ca.color == "green"

    def test_walkaway_is_red(self) -> None:
        ca = ClauseAssessment(
            clause_id="c1",
            clause_text="text",
            playbook_category="test",
            confidence=0.9,
            citation="text",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
            position=Position.WALKAWAY,
        )
        assign_colors([ca])
        assert ca.color == "red"

    def test_walkaway_low_conf_is_amber(self) -> None:
        """Walkaway with low confidence should be amber, not red."""
        ca = ClauseAssessment(
            clause_id="c1",
            clause_text="text",
            playbook_category="test",
            confidence=0.3,
            citation="text",
            qa_verdict=QAVerdict.agree,
            extraction_model="m1",
            qa_model="m1",
            position=Position.WALKAWAY,
        )
        assign_colors([ca])
        assert ca.color == "amber"
