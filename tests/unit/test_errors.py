"""Unit tests for the central exit-code registry and error helpers (P2T1).

``openreview_cli.errors`` is the single source of truth for process exit codes;
these tests pin the numeric contract and the printed text of every helper so a
future renumber or message tweak cannot slip through unnoticed.
"""

from __future__ import annotations

import pytest

from openreview_cli import errors


class TestExitCodeRegistry:
    """Every canonical exit code has a stable, documented value."""

    def test_success_is_zero(self) -> None:
        assert errors.EXIT_SUCCESS == 0

    def test_user_error_is_one(self) -> None:
        assert errors.EXIT_USER_ERROR == 1

    def test_usage_is_two(self) -> None:
        assert errors.EXIT_USAGE == 2

    def test_not_found_is_three(self) -> None:
        assert errors.EXIT_NOT_FOUND == 3

    def test_gateway_is_four(self) -> None:
        assert errors.EXIT_GATEWAY == 4

    def test_config_is_five(self) -> None:
        assert errors.EXIT_CONFIG == 5

    def test_cost_limit_is_six(self) -> None:
        assert errors.EXIT_COST_LIMIT == 6

    def test_parse_error_is_eight(self) -> None:
        assert errors.EXIT_PARSE_ERROR == 8

    def test_pii_is_nine(self) -> None:
        assert errors.EXIT_PII == 9

    def test_retrieval_index_not_found_is_forty(self) -> None:
        assert errors.EXIT_RETRIEVAL_INDEX_NOT_FOUND == 40

    def test_retrieval_index_corrupt_is_forty_one(self) -> None:
        assert errors.EXIT_RETRIEVAL_INDEX_CORRUPT == 41

    def test_retrieval_index_outdated_is_forty_two(self) -> None:
        assert errors.EXIT_RETRIEVAL_INDEX_OUTDATED == 42

    def test_retrieval_dim_mismatch_is_forty_three(self) -> None:
        assert errors.EXIT_RETRIEVAL_DIM_MISMATCH == 43

    def test_benchmark_regression_is_seventy_five(self) -> None:
        assert errors.EXIT_BENCHMARK_REGRESSION == 75

    def test_benchmark_config_is_seventy_eight(self) -> None:
        assert errors.EXIT_BENCHMARK_CONFIG == 78


class TestNoStaleAliases:
    """The pre-centralisation bare ``RETRIEVAL_*`` aliases were dropped."""

    @pytest.mark.parametrize(
        "name",
        [
            "RETRIEVAL_INDEX_NOT_FOUND",
            "RETRIEVAL_EMBEDDING_FAILED",
            "RETRIEVAL_NO_RESULTS",
            "RETRIEVAL_RERANKER_DEGRADATION",
        ],
    )
    def test_stale_alias_absent(self, name: str) -> None:
        assert not hasattr(errors, name), f"stale alias {name} should be gone"


class TestFailHelper:
    """``fail`` is the single primitive every helper delegates to."""

    def test_fail_default_prefix_and_code(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as ei:
            errors.fail("boom", errors.EXIT_USER_ERROR)
        assert ei.value.code == errors.EXIT_USER_ERROR
        assert capsys.readouterr().err == "Error: boom\n"

    def test_fail_custom_prefix_and_code(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as ei:
            errors.fail("boom", errors.EXIT_USAGE, prefix="Usage")
        assert ei.value.code == errors.EXIT_USAGE
        assert capsys.readouterr().err == "Usage: boom\n"


class TestSpecialisedHelpers:
    """Each helper prints its documented prefix and exits with its code."""

    @pytest.mark.parametrize(
        ("helper", "code", "needle"),
        [
            (errors.config_error, errors.EXIT_CONFIG, "Config error: boom"),
            (errors.cost_limit_error, errors.EXIT_COST_LIMIT, "Cost limit exceeded: boom"),
            (errors.pii_error, errors.EXIT_PII, "PII error: boom"),
            (errors.parse_error, errors.EXIT_PARSE_ERROR, "Parse error: boom"),
            (errors.usage_error, errors.EXIT_USAGE, "Error: boom"),
        ],
    )
    def test_helper_exits_and_prints(
        self,
        helper: object,
        code: int,
        needle: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(SystemExit) as ei:
            helper("boom")  # type: ignore[operator]
        assert ei.value.code == code
        assert needle in capsys.readouterr().err


class TestRetrievalError:
    """``retrieval_error`` defaults to the not-found code and accepts overrides."""

    def test_default_code(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as ei:
            errors.retrieval_error("no index")
        assert ei.value.code == errors.EXIT_RETRIEVAL_INDEX_NOT_FOUND
        assert "Retrieval error: no index" in capsys.readouterr().err

    def test_custom_code(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as ei:
            errors.retrieval_error("corrupt", code=errors.EXIT_RETRIEVAL_INDEX_CORRUPT)
        assert ei.value.code == errors.EXIT_RETRIEVAL_INDEX_CORRUPT
        assert "Retrieval error: corrupt" in capsys.readouterr().err
