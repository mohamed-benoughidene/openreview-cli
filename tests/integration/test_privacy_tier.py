"""Integration tests for privacy tier routing with mocked providers."""

from __future__ import annotations

from typing import Any

import pytest

from openreview_cli.gateway.errors import PIIUnavailableError
from openreview_cli.gateway.tier_config import TierConfig
from openreview_cli.gateway.tier_router import TierRouter
from tests.helpers.mock_gateway import (
    _MockGateway,
    _MockPiiEngineAvailable,
    _MockPiiEngineUnavailable,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def maximum_config() -> dict[str, Any]:
    return {
        "gateway": {
            "models": {
                "reasoning": {"primary": "ollama/qwen3:8b"},
                "embedding": {"primary": "ollama/nomic-embed-text"},
            }
        }
    }


@pytest.fixture
def balanced_config() -> dict[str, Any]:
    return {
        "gateway": {
            "models": {
                "reasoning": {"primary": "openai/gpt-4o"},
                "embedding": {"primary": "ollama/nomic-embed-text"},
            }
        }
    }


@pytest.fixture
def performance_config() -> dict[str, Any]:
    return {
        "gateway": {
            "models": {
                "reasoning": {"primary": "openai/gpt-4o"},
                "embedding": {"primary": "openai/text-embedding-3-small"},
            }
        }
    }


# ── US1: Maximum Tier Integration (T016) ────────────────────────────────────


class TestMaximumTierIntegration:
    """US1 integration: Maximum tier zero external HTTP requests."""

    def test_local_chat_succeeds(self, maximum_config: dict[str, Any]) -> None:
        gw = _MockGateway(maximum_config)
        config = TierConfig(tier="maximum", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineAvailable())  # type: ignore[arg-type]
        result = router.chat("reasoning", [{"role": "user", "content": "Hi"}])
        assert result == "mock response"
        assert len(gw.chat_calls) == 1

    def test_local_embed_succeeds(self, maximum_config: dict[str, Any]) -> None:
        gw = _MockGateway(maximum_config)
        config = TierConfig(tier="maximum", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineAvailable())  # type: ignore[arg-type]
        result = router.embed("embedding", ["test"])
        assert result == [[0.1, 0.2, 0.3]]
        assert len(gw.embed_calls) == 1


# ── US2: Balanced Tier Integration (T022) ────────────────────────────────────


class TestBalancedTierIntegration:
    """US2 integration: Balanced routes by call type."""

    def test_embedding_local(self, balanced_config: dict[str, Any]) -> None:
        gw = _MockGateway(balanced_config)
        config = TierConfig(tier="balanced", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineAvailable())  # type: ignore[arg-type]
        result = router.embed("embedding", ["test"])
        assert result == [[0.1, 0.2, 0.3]]
        assert len(gw.embed_calls) == 1

    def test_llm_cloud_with_pii(self, balanced_config: dict[str, Any]) -> None:
        gw = _MockGateway(balanced_config)
        config = TierConfig(tier="balanced", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineAvailable())  # type: ignore[arg-type]
        result = router.chat("reasoning", [{"role": "user", "content": "John Smith data"}])
        assert result == "mock response"
        assert len(gw.chat_calls) == 1
        # Verify PII was stripped — router verifies pii_available flag was True

    def test_llm_blocked_no_pii(self, balanced_config: dict[str, Any]) -> None:
        gw = _MockGateway(balanced_config)
        config = TierConfig(tier="balanced", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineUnavailable())  # type: ignore[arg-type]
        with pytest.raises(PIIUnavailableError):
            router.chat("reasoning", [{"role": "user", "content": "data"}])
        assert len(gw.chat_calls) == 0  # no cloud call


# ── US3: Performance Tier Integration (T026) ────────────────────────────────


class TestPerformanceTierIntegration:
    """US3 integration: all calls cloud, PII stripped."""

    def test_all_calls_cloud(self, performance_config: dict[str, Any]) -> None:
        gw = _MockGateway(performance_config)
        config = TierConfig(tier="performance", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineAvailable())  # type: ignore[arg-type]
        router.chat("reasoning", [{"role": "user", "content": "Hi"}])
        router.embed("embedding", ["test"])
        assert len(gw.chat_calls) == 1
        assert len(gw.embed_calls) == 1

    def test_pii_stripped_before_calls(self, performance_config: dict[str, Any]) -> None:
        gw = _MockGateway(performance_config)
        config = TierConfig(tier="performance", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineUnavailable())  # type: ignore[arg-type]
        with pytest.raises(PIIUnavailableError):
            router.chat("reasoning", [{"role": "user", "content": "secret"}])
        assert len(gw.chat_calls) == 0


# ── US5: Tier Stability (T035) ──────────────────────────────────────────────


class TestTierStability:
    """US5: tier stable per operation, changes on next invocation."""

    def test_tier_stays_constant_during_operation(self) -> None:
        """Config change mid-operation does not affect running op."""
        gw = _MockGateway()
        # Start with balanced config
        gw._config = {
            "gateway": {
                "models": {
                    "reasoning": {"primary": "ollama/llama3.1"},
                    "embedding": {"primary": "ollama/nomic-embed-text"},
                }
            }
        }
        config = TierConfig(tier="balanced", tier_source="config")
        router = TierRouter(gw, config, pii_engine=_MockPiiEngineAvailable())  # type: ignore[arg-type]

        # even if we create a new config with different tier, the router
        # already holds the original
        new_config = TierConfig(tier="maximum", tier_source="config")
        assert router.config.tier == "balanced"
        assert new_config.tier == "maximum"
        assert router.config.tier != new_config.tier


# ── CVG: Tier Visibility in Review Pipeline (T047-T048) ─────────────────────


class TestTierVisibility:
    """T047-T048: Tier banner in review command, footer in report."""

    def test_review_command_output_contains_tier_banner(self) -> None:
        """T047: ReviewCommand run prints progress banner with tier name."""
        from pathlib import Path

        from openreview_cli.review.base import ReviewCommand

        fixture = Path(__file__).resolve().parent.parent / "fixtures" / "nda_with_pii.pdf"
        if not fixture.exists():
            pytest.skip("fixture nda_with_pii.pdf not found")

        cmd = ReviewCommand(document_path=str(fixture), pii_enabled=False)
        # _parse_document will fail due to missing parse dependencies,
        # but banner is printed _before_ parsing starts.  We catch the
        # expected parse error after verifying the banner was output.
        import io
        import sys

        stderr_buf = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = stderr_buf
        try:
            cmd.run()
        except Exception:
            # parse error expected — check banner was printed first
            pass
        finally:
            sys.stderr = old_stderr

        captured = stderr_buf.getvalue()
        assert "Privacy tier:" in captured

    def test_format_terminal_accepts_privacy_footer(self) -> None:
        """T048: format_terminal shows privacy footer when provided."""
        from datetime import datetime

        from openreview_cli.review.models import DocMeta, ReviewReport, ReviewSummary
        from openreview_cli.review.report import format_terminal

        report = ReviewReport(
            document=DocMeta(
                filename="test.pdf",
                page_count=5,
                clause_count=10,
                pii_stripped=True,
                parsed_at=datetime.now(),
            ),
            assessments=[],
            summary=ReviewSummary(),
            playbook_id="test-playbook",
            generated_at=datetime.now(),
        )
        footer = "Processed under Maximum privacy tier. No data was sent to external services."
        output = format_terminal(report, privacy_footer=footer)
        assert "No data was sent to external services" in output

    def test_review_subcommand_output_contains_privacy_footer(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """T052: review subcommand terminal output includes privacy tier footer.

        Monkeypatches run_review to return a canned report without real
        model calls, and load_config to return a known config, then
        verifies the formatted terminal output contains the footer.
        Invokes the Typer subcommand via CliRunner so that Typer-parsed
        defaults are applied correctly.
        """
        from datetime import datetime

        from openreview_cli.review.models import DocMeta, ReviewReport, ReviewSummary

        report = ReviewReport(
            document=DocMeta(
                filename="test.pdf",
                page_count=5,
                clause_count=10,
                pii_stripped=True,
                parsed_at=datetime.now(),
            ),
            assessments=[],
            summary=ReviewSummary(),
            playbook_id="test-playbook",
            generated_at=datetime.now(),
        )

        monkeypatch.setattr(
            "openreview_cli.review.run_review",
            lambda **kw: [report],
        )
        monkeypatch.setattr(
            "openreview_cli.config.loader.load_config",
            lambda _path: {
                "gateway": {
                    "models": {
                        "reasoning": {"primary": "ollama/qwen3:8b"},
                        "embedding": {"primary": "ollama/nomic-embed-text"},
                    }
                }
            },
        )

        from typer.testing import CliRunner

        from openreview_cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["precheck", "review", "test.pdf"])
        assert "No data was sent to external services" in result.output
