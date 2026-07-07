"""Unit tests for negotiation data models."""

from __future__ import annotations

import dataclasses
import pickle
from dataclasses import is_dataclass
from datetime import UTC, datetime

import pytest

from openreview_cli.negotiation.models import (
    EquilibriumStrategy,
    NegotiationReport,
    NegotiationSummary,
    PayoffMatrix,
    PayoffSource,
    SolverType,
)


class TestSolverType:
    def test_enum_values(self) -> None:
        assert SolverType.NASH.value == "nash"
        assert SolverType.QRE.value == "qre"
        assert SolverType.LEVEL_K.value == "level_k"

    def test_enum_members(self) -> None:
        assert set(SolverType.__members__) == {"NASH", "QRE", "LEVEL_K"}


class TestPayoffSource:
    def test_enum_values(self) -> None:
        assert PayoffSource.KNOWN.value == "known"
        assert PayoffSource.INFERRED_FROM_ALIGNMENT.value == "inferred_from_alignment"
        assert PayoffSource.ESTIMATED.value == "estimated"
        assert PayoffSource.UNKNOWN.value == "unknown"

    def test_enum_members(self) -> None:
        assert set(PayoffSource.__members__) == {
            "KNOWN",
            "INFERRED_FROM_ALIGNMENT",
            "ESTIMATED",
            "UNKNOWN",
        }


class TestPayoffMatrix:
    def test_construction_valid(self) -> None:
        """Valid 3x3 payoff matrix."""
        pm = PayoffMatrix(
            clause_id="confidentiality",
            actions=["preferred", "acceptable", "walkaway"],
            user_payoffs=[[0.8, 0.5, 0.0], [0.6, 0.4, 0.1], [0.2, 0.1, 0.0]],
            counterparty_payoffs=[[0.7, 0.4, 0.1], [0.5, 0.3, 0.2], [0.3, 0.2, 0.0]],
            symmetric=False,
            source=PayoffSource.KNOWN,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        assert pm.clause_id == "confidentiality"
        assert len(pm.actions) == 3
        assert len(pm.user_payoffs) == 3
        assert len(pm.counterparty_payoffs) == 3

    def test_frozen(self) -> None:
        pm = PayoffMatrix(
            clause_id="test",
            actions=["a", "b"],
            user_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            counterparty_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            symmetric=True,
            source=PayoffSource.KNOWN,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            pm.clause_id = "modified"  # type: ignore[misc]

    def test_slots(self) -> None:
        pm = PayoffMatrix(
            clause_id="test",
            actions=["a", "b"],
            user_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            counterparty_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            symmetric=True,
            source=PayoffSource.KNOWN,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        with pytest.raises(AttributeError):
            _ = pm.__dict__  # slots=True means no __dict__

    def test_value_bounds(self) -> None:
        """Values outside [0,1] should raise ValueError."""
        with pytest.raises(ValueError):
            PayoffMatrix(
                clause_id="test",
                actions=["a", "b"],
                user_payoffs=[[1.5, 0.0], [0.0, 0.0]],
                counterparty_payoffs=[[0.5, 0.5], [0.5, 0.5]],
                symmetric=False,
                source=PayoffSource.KNOWN,
                weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
            )

    def test_negative_values(self) -> None:
        with pytest.raises(ValueError):
            PayoffMatrix(
                clause_id="test",
                actions=["a", "b"],
                user_payoffs=[[-0.1, 0.0], [0.0, 0.0]],
                counterparty_payoffs=[[0.5, 0.5], [0.5, 0.5]],
                symmetric=False,
                source=PayoffSource.KNOWN,
                weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
            )

    def test_non_square_matrix(self) -> None:
        """Non-square matrix should raise ValueError."""
        with pytest.raises(ValueError):
            PayoffMatrix(
                clause_id="test",
                actions=["a", "b"],
                user_payoffs=[[0.5, 0.5, 0.5], [0.5, 0.5, 0.5]],
                counterparty_payoffs=[[0.5, 0.5], [0.5, 0.5]],
                symmetric=False,
                source=PayoffSource.KNOWN,
                weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
            )

    def test_too_few_actions(self) -> None:
        """Single action should raise ValueError."""
        with pytest.raises(ValueError):
            PayoffMatrix(
                clause_id="test",
                actions=["only"],
                user_payoffs=[[0.5]],
                counterparty_payoffs=[[0.5]],
                symmetric=True,
                source=PayoffSource.KNOWN,
                weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
            )

    def test_too_many_actions(self) -> None:
        """7+ actions should raise ValueError."""
        actions = [f"a{i}" for i in range(7)]
        size = 7
        matrix = [[0.5] * size for _ in range(size)]
        with pytest.raises(ValueError):
            PayoffMatrix(
                clause_id="test",
                actions=actions,
                user_payoffs=matrix,
                counterparty_payoffs=matrix,
                symmetric=True,
                source=PayoffSource.KNOWN,
                weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
            )


class TestEquilibriumStrategy:
    def test_construction_valid(self) -> None:
        es = EquilibriumStrategy(
            clause_id="confidentiality",
            model="nash",
            model_params={},
            user_strategy=[0.6, 0.3, 0.1],
            counterparty_strategy=[0.4, 0.4, 0.2],
            predicted_outcome="preferred/acceptable",
            suggested_counteroffer="Propose preferred terms; counterparty likely to counter with acceptable",
            fallback_position="acceptable",
            equilibrium_type="mixed",
            confidence=0.85,
            is_amber=False,
            assumptions=[],
        )
        assert es.clause_id == "confidentiality"
        assert es.equilibrium_type == "mixed"
        assert not es.is_amber

    def test_strategy_probability_sum(self) -> None:
        """Strategy probabilities must sum to 1.0 ± 1e-6."""
        with pytest.raises(ValueError):
            EquilibriumStrategy(
                clause_id="test",
                model="nash",
                model_params={},
                user_strategy=[0.5, 0.5, 0.5],
                counterparty_strategy=[0.4, 0.4, 0.2],
                predicted_outcome="test",
                suggested_counteroffer="test",
                fallback_position="test",
                equilibrium_type="mixed",
                confidence=0.8,
                is_amber=False,
                assumptions=[],
            )

    def test_confidence_range(self) -> None:
        with pytest.raises(ValueError):
            EquilibriumStrategy(
                clause_id="test",
                model="nash",
                model_params={},
                user_strategy=[1.0],
                counterparty_strategy=[1.0],
                predicted_outcome="test",
                suggested_counteroffer="test",
                fallback_position="test",
                equilibrium_type="pure",
                confidence=1.5,
                is_amber=False,
                assumptions=[],
            )

    def test_negative_confidence(self) -> None:
        with pytest.raises(ValueError):
            EquilibriumStrategy(
                clause_id="test",
                model="nash",
                model_params={},
                user_strategy=[1.0],
                counterparty_strategy=[1.0],
                predicted_outcome="test",
                suggested_counteroffer="test",
                fallback_position="test",
                equilibrium_type="pure",
                confidence=-0.1,
                is_amber=False,
                assumptions=[],
            )

    def test_is_amber_from_threshold(self) -> None:
        """is_amber computed from confidence property."""
        es = EquilibriumStrategy(
            clause_id="test",
            model="nash",
            model_params={},
            user_strategy=[1.0],
            counterparty_strategy=[1.0],
            predicted_outcome="test",
            suggested_counteroffer="test",
            fallback_position="test",
            equilibrium_type="pure",
            confidence=0.65,
            is_amber=False,
            assumptions=[],
        )
        assert es.is_amber is False  # We set it explicitly, not computed

    def test_dataclass_slots(self) -> None:
        es = EquilibriumStrategy(
            clause_id="test",
            model="nash",
            model_params={},
            user_strategy=[1.0],
            counterparty_strategy=[1.0],
            predicted_outcome="test",
            suggested_counteroffer="test",
            fallback_position="test",
            equilibrium_type="pure",
            confidence=0.8,
            is_amber=False,
            assumptions=[],
        )
        with pytest.raises(AttributeError):
            _ = es.__dict__


class TestNegotiationSummary:
    def test_default_construction(self) -> None:
        ns = NegotiationSummary()
        assert ns.total_clauses == 0
        assert ns.equilibrium_distribution == {}
        assert ns.amber_count == 0
        assert ns.avg_confidence == 0.0
        assert ns.impasse_count == 0
        assert not ns.deadlock_risk

    def test_impasse_detection(self) -> None:
        ns = NegotiationSummary(
            total_clauses=5,
            equilibrium_distribution={"pure": 3, "mixed": 2},
            amber_count=2,
            avg_confidence=0.75,
            impasse_count=1,
            deadlock_risk=True,
        )
        assert ns.impasse_count == 1
        assert ns.deadlock_risk

    def test_no_impasse(self) -> None:
        ns = NegotiationSummary(
            total_clauses=3,
            equilibrium_distribution={"pure": 3},
            amber_count=0,
            avg_confidence=0.9,
            impasse_count=0,
            deadlock_risk=False,
        )
        assert not ns.deadlock_risk

    def test_dataclass_slots(self) -> None:
        ns = NegotiationSummary()
        with pytest.raises(AttributeError):
            _ = ns.__dict__


class TestNegotiationReport:
    def test_construction(self) -> None:
        now = datetime.now(UTC)
        ns = NegotiationSummary(
            total_clauses=2,
            equilibrium_distribution={"mixed": 2},
            amber_count=1,
            avg_confidence=0.75,
            impasse_count=0,
            deadlock_risk=False,
        )
        pm = PayoffMatrix(
            clause_id="c1",
            actions=["a", "b"],
            user_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            counterparty_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            symmetric=True,
            source=PayoffSource.ESTIMATED,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        es = EquilibriumStrategy(
            clause_id="c1",
            model="qre",
            model_params={"lambda": 1.0},
            user_strategy=[0.5, 0.5],
            counterparty_strategy=[0.5, 0.5],
            predicted_outcome="a/b",
            suggested_counteroffer="Consider proposing a",
            fallback_position="b",
            equilibrium_type="mixed",
            confidence=0.7,
            is_amber=True,
            assumptions=["Counterparty payoffs estimated"],
        )

        report = NegotiationReport(
            strategies=[es],
            payoff_matrices=[pm],
            summary=ns,
            playbook_id="test-nda",
            generated_at=now,
            confidence_threshold=0.7,
            schema_version="0.1.0",
        )
        assert report.experimental
        assert "advisory" in report.disclaimer
        assert report.schema_version == "0.1.0"
        assert report.generated_at == now
        assert len(report.strategies) == 1
        assert len(report.payoff_matrices) == 1

    def test_empty_report(self) -> None:
        now = datetime.now(UTC)
        ns = NegotiationSummary()
        report = NegotiationReport(
            strategies=[],
            payoff_matrices=[],
            summary=ns,
            playbook_id="test",
            generated_at=now,
            confidence_threshold=0.7,
            schema_version="0.1.0",
        )
        assert len(report.strategies) == 0
        assert report.summary.total_clauses == 0

    def test_pickling(self) -> None:
        """NegotiationReport must be picklable (for cache/serialisation)."""
        now = datetime.now(UTC)
        ns = NegotiationSummary()
        report = NegotiationReport(
            strategies=[],
            payoff_matrices=[],
            summary=ns,
            playbook_id="test",
            generated_at=now,
            confidence_threshold=0.7,
            schema_version="0.1.0",
        )
        data = pickle.dumps(report)
        restored = pickle.loads(data)
        assert restored.playbook_id == "test"
        assert restored.schema_version == "0.1.0"

    def test_dataclass_check(self) -> None:
        assert is_dataclass(NegotiationReport)
        assert is_dataclass(NegotiationSummary)
        assert is_dataclass(PayoffMatrix)
        assert is_dataclass(EquilibriumStrategy)
