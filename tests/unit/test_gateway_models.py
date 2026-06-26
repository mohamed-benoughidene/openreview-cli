import pytest

from openreview_cli.gateway.errors import GatewayError
from openreview_cli.gateway.models import GatewayResponse, ModelParams, RerankResult, SlotConfig


def test_model_params_validation() -> None:
    # Valid model params
    params = ModelParams(temperature=0.5, max_tokens=100, dimensions=256, top_p=0.9, stop=["\n"])
    assert params.temperature == 0.5
    assert params.max_tokens == 100
    assert params.dimensions == 256
    assert params.top_p == 0.9
    assert params.stop == ["\n"]

    # Invalid temperatures
    with pytest.raises(ValueError, match="temperature"):
        ModelParams(temperature=-0.1)
    with pytest.raises(ValueError, match="temperature"):
        ModelParams(temperature=2.1)

    # Invalid max_tokens
    with pytest.raises(ValueError, match="max_tokens"):
        ModelParams(max_tokens=0)
    with pytest.raises(ValueError, match="max_tokens"):
        ModelParams(max_tokens=-1)

    # Invalid dimensions
    with pytest.raises(ValueError, match="dimensions"):
        ModelParams(dimensions=0)
    with pytest.raises(ValueError, match="dimensions"):
        ModelParams(dimensions=-100)

    # Invalid top_p
    with pytest.raises(ValueError, match="top_p"):
        ModelParams(top_p=-0.1)
    with pytest.raises(ValueError, match="top_p"):
        ModelParams(top_p=1.1)


def test_slot_config_validation() -> None:
    # Valid SlotConfig
    cfg = SlotConfig(primary="openai/gpt-4o", fallback="anthropic/claude-3", params=ModelParams())
    assert cfg.primary == "openai/gpt-4o"
    assert cfg.fallback == "anthropic/claude-3"

    # Valid Ollama model format (no slash)
    cfg_ollama = SlotConfig(primary="llama3.1")
    assert cfg_ollama.primary == "llama3.1"

    # Empty primary
    with pytest.raises(ValueError, match="primary"):
        SlotConfig(primary="")

    # Invalid model format (slash but invalid parts)
    with pytest.raises(ValueError, match=r"primary.*format"):
        SlotConfig(primary="openai/")
    with pytest.raises(ValueError, match=r"primary.*format"):
        SlotConfig(primary="/gpt-4o")
    with pytest.raises(ValueError, match=r"fallback.*format"):
        SlotConfig(primary="openai/gpt-4o", fallback="anthropic/")


def test_rerank_result_validation() -> None:
    # Valid RerankResult
    res = RerankResult(index=0, score=0.95, document="doc")
    assert res.index == 0
    assert res.score == 0.95
    assert res.document == "doc"

    # Invalid index
    with pytest.raises(ValueError, match="index"):
        RerankResult(index=-1, score=0.5)


def test_gateway_response_validation() -> None:
    # Valid GatewayResponse
    resp = GatewayResponse(
        content="hello",
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.01,
        model="gpt-4o",
        provider="openai",
        slot="reasoning",
        fallback_used=False,
        latency_ms=150,
    )
    assert resp.content == "hello"
    assert resp.input_tokens == 10
    assert resp.output_tokens == 20
    assert resp.cost_usd == 0.01

    # Invalid inputs
    with pytest.raises(ValueError, match="input_tokens"):
        GatewayResponse("content", -1, 20, 0.01, "m", "p", "reasoning", False, 100)
    with pytest.raises(ValueError, match="output_tokens"):
        GatewayResponse("content", 10, -1, 0.01, "m", "p", "reasoning", False, 100)
    with pytest.raises(ValueError, match="cost_usd"):
        GatewayResponse("content", 10, 20, -0.01, "m", "p", "reasoning", False, 100)
    with pytest.raises(ValueError, match="latency_ms"):
        GatewayResponse("content", 10, 20, 0.01, "m", "p", "reasoning", False, -1)
    with pytest.raises(ValueError, match="model"):
        GatewayResponse("content", 10, 20, 0.01, "", "p", "reasoning", False, 100)
    with pytest.raises(ValueError, match="provider"):
        GatewayResponse("content", 10, 20, 0.01, "m", "", "reasoning", False, 100)
    with pytest.raises(ValueError, match="slot"):
        GatewayResponse("content", 10, 20, 0.01, "m", "p", "invalid_slot", False, 100)


def test_gateway_error_validation() -> None:
    # Valid GatewayError
    err = GatewayError(exit_code=7, slot="reasoning", message="Failed", action="Fix it")
    assert err.exit_code == 7
    assert err.slot == "reasoning"
    assert str(err) == "Failed"

    # Invalid exit code
    with pytest.raises(ValueError, match="exit_code"):
        GatewayError(exit_code=5, slot="reasoning", message="Failed", action="Fix")

    # Invalid slot
    with pytest.raises(ValueError, match="slot"):
        GatewayError(exit_code=7, slot="invalid", message="Failed", action="Fix")

    # Empty message/action
    with pytest.raises(ValueError, match="message"):
        GatewayError(exit_code=7, slot="reasoning", message="", action="Fix")
    with pytest.raises(ValueError, match="action"):
        GatewayError(exit_code=7, slot="reasoning", message="Failed", action="")
