"""Unit tests for recommendation logic."""

from __future__ import annotations

from openreview_cli.negotiation.models import PayoffMatrix, PayoffSource
from openreview_cli.negotiation.recommend import build_recommendation


def _make_payoff_matrix() -> PayoffMatrix:
    return PayoffMatrix(
        clause_id="test",
        actions=["preferred", "acceptable", "walkaway"],
        user_payoffs=[[0.9, 0.5, 0.1], [0.6, 0.4, 0.2], [0.2, 0.1, 0.0]],
        counterparty_payoffs=[[0.1, 0.5, 0.9], [0.2, 0.4, 0.6], [0.0, 0.1, 0.2]],
        symmetric=False,
        source=PayoffSource.KNOWN,
        weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
    )


class TestBuildRecommendation:
    def test_basic_recommendation(self) -> None:
        """Produces valid EquilibriumStrategy."""
        matrix = _make_payoff_matrix()
        strategy = build_recommendation(
            user_strategy=[0.6, 0.3, 0.1],
            counterparty_strategy=[0.2, 0.5, 0.3],
            matrix=matrix,
            eq_type="mixed",
            model="qre",
            model_params={"lambda": 1.0},
            confidence_threshold=0.7,
        )
        assert strategy.clause_id == "test"
        assert strategy.model == "qre"
        assert strategy.equilibrium_type == "mixed"
        assert 0.0 <= strategy.confidence <= 1.0
        assert not strategy.is_amber  # confidence should be >= 0.7

    def test_suggested_counteroffer_format(self) -> None:
        """Counteroffer must use advisory language."""
        matrix = _make_payoff_matrix()
        strategy = build_recommendation(
            user_strategy=[0.8, 0.2, 0.0],
            counterparty_strategy=[0.3, 0.6, 0.1],
            matrix=matrix,
            eq_type="pure",
            model="nash",
            model_params={},
            confidence_threshold=0.7,
        )
        assert "sign" not in strategy.suggested_counteroffer.lower()
        assert "reject" not in strategy.suggested_counteroffer.lower()
        assert "Consider" in strategy.suggested_counteroffer

    def test_amber_for_estimated_source(self) -> None:
        """Source=ESTIMATED triggers is_amber."""
        matrix = PayoffMatrix(
            clause_id="test",
            actions=["preferred", "acceptable", "walkaway"],
            user_payoffs=[[0.9, 0.5, 0.1], [0.6, 0.4, 0.2], [0.2, 0.1, 0.0]],
            counterparty_payoffs=[[0.1, 0.5, 0.9], [0.2, 0.4, 0.6], [0.0, 0.1, 0.2]],
            symmetric=True,
            source=PayoffSource.ESTIMATED,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        strategy = build_recommendation(
            user_strategy=[0.5, 0.3, 0.2],
            counterparty_strategy=[0.3, 0.4, 0.3],
            matrix=matrix,
            eq_type="mixed",
            model="qre",
            model_params={"lambda": 1.0},
            confidence_threshold=0.7,
        )
        assert strategy.is_amber

    def test_amber_for_unknown_source(self) -> None:
        """Source=UNKNOWN triggers is_amber."""
        matrix = PayoffMatrix(
            clause_id="test",
            actions=["a", "b"],
            user_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            counterparty_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            symmetric=False,
            source=PayoffSource.UNKNOWN,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        strategy = build_recommendation(
            user_strategy=[0.5, 0.5],
            counterparty_strategy=[0.5, 0.5],
            matrix=matrix,
            eq_type="mixed",
            model="nash",
            model_params={},
            confidence_threshold=0.7,
        )
        assert strategy.is_amber

    def test_amber_below_threshold(self) -> None:
        """Low confidence triggers is_amber."""
        matrix = _make_payoff_matrix()
        strategy = build_recommendation(
            user_strategy=[0.5, 0.3, 0.2],
            counterparty_strategy=[0.3, 0.4, 0.3],
            matrix=matrix,
            eq_type="no_equilibrium",
            model="qre",
            model_params={"lambda": 1.0},
            confidence_threshold=0.7,
        )
        assert strategy.is_amber

    def test_amber_for_no_equilibrium(self) -> None:
        """No equilibrium found → is_amber and explanation."""
        matrix = _make_payoff_matrix()
        strategy = build_recommendation(
            user_strategy=[0.4, 0.4, 0.2],
            counterparty_strategy=[0.3, 0.4, 0.3],
            matrix=matrix,
            eq_type="no_equilibrium",
            model="qre",
            model_params={"lambda": 1.0},
            confidence_threshold=0.7,
        )
        assert strategy.is_amber

    def test_impasse_detection(self) -> None:
        """Walkaway prob ≥ 0.8 → impasse in assumptions."""
        matrix = _make_payoff_matrix()
        strategy = build_recommendation(
            user_strategy=[0.0, 0.0, 1.0],
            counterparty_strategy=[0.0, 0.0, 1.0],
            matrix=matrix,
            eq_type="pure",
            model="nash",
            model_params={},
            confidence_threshold=0.7,
        )
        assert "impasse" in strategy.predicted_outcome.lower()

    def test_no_sign_reject_language(self) -> None:
        """Verify no prohibited language in output."""
        matrix = PayoffMatrix(
            clause_id="test",
            actions=["preferred", "acceptable"],
            user_payoffs=[[1.0, 0.0], [0.0, 1.0]],
            counterparty_payoffs=[[0.0, 1.0], [1.0, 0.0]],
            symmetric=False,
            source=PayoffSource.KNOWN,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        strategy = build_recommendation(
            user_strategy=[0.5, 0.5],
            counterparty_strategy=[0.5, 0.5],
            matrix=matrix,
            eq_type="mixed",
            model="nash",
            model_params={},
            confidence_threshold=0.7,
        )
        assert "sign" not in strategy.suggested_counteroffer.lower()
        assert "reject" not in strategy.suggested_counteroffer.lower()

    def test_amber_for_fallback(self) -> None:
        """Fallback from Nash to QRE triggers is_amber."""
        matrix = _make_payoff_matrix()
        strategy = build_recommendation(
            user_strategy=[0.4, 0.4, 0.2],
            counterparty_strategy=[0.3, 0.4, 0.3],
            matrix=matrix,
            eq_type="mixed",
            model="nash",
            confidence_threshold=0.7,
            is_fallback=True,
        )
        assert strategy.is_amber
        assert any("Fallback from Nash to QRE" in r for r in strategy.assumptions)

    def test_assumptions_listed(self) -> None:
        """Assumptions are populated based on source."""
        matrix = PayoffMatrix(
            clause_id="test",
            actions=["a", "b"],
            user_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            counterparty_payoffs=[[0.5, 0.5], [0.5, 0.5]],
            symmetric=True,
            source=PayoffSource.ESTIMATED,
            weights={"risk": 0.33, "financial": 0.33, "obligation": 0.34},
        )
        strategy = build_recommendation(
            user_strategy=[0.5, 0.5],
            counterparty_strategy=[0.5, 0.5],
            matrix=matrix,
            eq_type="mixed",
            model="qre",
            model_params={"lambda": 1.0},
            confidence_threshold=0.7,
        )
        assert len(strategy.assumptions) > 0
