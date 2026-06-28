import pytest

from openreview_cli.errors import (
    CONFIG_ERROR,
    GENERAL_ERROR,
    INPUT_ERROR,
    NETWORK_ERROR,
    SUCCESS,
    USAGE_ERROR,
    config_error,
    cost_limit_error,
    gateway_error,
    pii_error,
)


def test_config_error_exits_with_code_5() -> None:
    with pytest.raises(SystemExit) as exc:
        config_error("missing file")
    assert exc.value.code == 5


def test_config_error_prints_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        config_error("broken config")
    stderr = capsys.readouterr().err
    assert "Config error:" in stderr
    assert "broken config" in stderr


def test_cost_limit_error_exits_with_code_6() -> None:
    with pytest.raises(SystemExit) as exc:
        cost_limit_error("daily cap reached")
    assert exc.value.code == 6


def test_cost_limit_error_prints_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cost_limit_error("over $10")
    stderr = capsys.readouterr().err
    assert "Cost limit exceeded:" in stderr
    assert "over $10" in stderr


def test_pii_error_exits_with_code_9() -> None:
    with pytest.raises(SystemExit) as exc:
        pii_error("detection failed")
    assert exc.value.code == 9


def test_pii_error_prints_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        pii_error("no model loaded")
    stderr = capsys.readouterr().err
    assert "PII error:" in stderr
    assert "no model loaded" in stderr


def test_gateway_error_exits_with_code_7() -> None:
    with pytest.raises(SystemExit) as exc:
        gateway_error("provider unreachable")
    assert exc.value.code == 7


def test_gateway_error_prints_message_and_slot(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        gateway_error("rate limited", slot="reasoning")
    stderr = capsys.readouterr().err
    assert "Gateway error:" in stderr
    assert "rate limited" in stderr
    assert "Slot: reasoning" in stderr


def test_gateway_error_without_slot(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        gateway_error("generic failure")
    stderr = capsys.readouterr().err
    assert "Slot:" not in stderr


# ── Exit code constants ──────────────────────────────────────────────────────


class TestExitCodeConstants:
    def test_success_is_0(self) -> None:
        assert SUCCESS == 0

    def test_general_error_is_1(self) -> None:
        assert GENERAL_ERROR == 1

    def test_usage_error_is_2(self) -> None:
        assert USAGE_ERROR == 2

    def test_config_error_is_3(self) -> None:
        assert CONFIG_ERROR == 3

    def test_input_error_is_4(self) -> None:
        assert INPUT_ERROR == 4

    def test_network_error_is_5(self) -> None:
        assert NETWORK_ERROR == 5
