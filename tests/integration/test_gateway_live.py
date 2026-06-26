"""Live integration tests using a real OpenRouter API key.

Set the OPENROUTER_API_KEY environment variable to run these tests:
  export OPENROUTER_API_KEY="sk-or-v1-..."
  uv run pytest tests/integration/test_gateway_live.py -v

These tests are excluded from CI (marked @pytest.mark.live).
"""

import os
import uuid
from pathlib import Path

import pytest

from openreview_cli.gateway.engine import route_request
from openreview_cli.gateway.models import GatewayResponse

pytestmark = pytest.mark.live

SHARED_SESSION_ID = str(uuid.uuid4())


@pytest.fixture
def openrouter_key() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")


@pytest.fixture
def live_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    cfg = config_dir / "openreview" / "config.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        """version: 1
gateway:
  models:
    reasoning:
      primary: openrouter/openai/gpt-4o-mini
      params:
        temperature: 0.1
        max_tokens: 500
    extraction:
      primary: openrouter/openai/gpt-4o-mini
      params:
        temperature: 0.0
    embedding:
      primary: openrouter/openai/text-embedding-3-small
    graph:
      primary: openrouter/openai/gpt-4o-mini
      params:
        temperature: 0.0
    reranking:
      primary: openrouter/openai/gpt-4o-mini
  cost_limits:
    per_review_cents: 500
    daily_cents: 5000
  fallback:
    retries: 1
    retry_delay: 0.5
    timeout: 30
    on_failure: error
"""
    )
    return config_dir


def _assert_chat_response(resp: GatewayResponse) -> None:
    assert isinstance(resp.content, str)
    assert len(resp.content) > 0
    assert resp.input_tokens > 0
    assert resp.output_tokens > 0
    assert resp.cost_usd >= 0.0
    assert resp.provider == "openrouter"


def test_live_chat_reasoning(openrouter_key: None, live_env: Path) -> None:
    resp = route_request(
        slot="reasoning",
        messages=[{"role": "user", "content": "Reply with exactly 'Hello from reasoning'"}],
        session_id=SHARED_SESSION_ID,
    )
    _assert_chat_response(resp)
    assert isinstance(resp.content, str)
    assert "hello" in resp.content.lower()


def test_live_extraction(openrouter_key: None, live_env: Path) -> None:
    resp = route_request(
        slot="extraction",
        messages=[
            {
                "role": "system",
                "content": "Extract the price and date from the text. Reply with JSON only.",
            },
            {"role": "user", "content": "The total cost is $1,200 due by December 31, 2025."},
        ],
        session_id=SHARED_SESSION_ID,
    )
    _assert_chat_response(resp)


def test_live_graph_extraction(openrouter_key: None, live_env: Path) -> None:
    resp = route_request(
        slot="graph",
        messages=[
            {"role": "system", "content": "Extract named entities as JSON."},
            {"role": "user", "content": "Acme Corp and Beta LLC signed a agreement."},
        ],
        session_id=SHARED_SESSION_ID,
    )
    _assert_chat_response(resp)


def test_live_embedding(openrouter_key: None, live_env: Path) -> None:
    resp = route_request(
        slot="embedding",
        input_text=["This is a test sentence for embedding."],
        session_id=SHARED_SESSION_ID,
    )
    assert resp.content is not None
    assert isinstance(resp.content, list)
    assert len(resp.content) == 1
    emb = resp.content[0]
    assert isinstance(emb, list)
    assert len(emb) > 0
    assert resp.input_tokens > 0
    assert resp.provider == "openrouter"


def test_live_cost_tracking(openrouter_key: None, live_env: Path) -> None:
    resp = route_request(
        slot="reasoning",
        messages=[{"role": "user", "content": "Reply with 'ok'"}],
        session_id=SHARED_SESSION_ID,
    )
    assert resp.input_tokens > 0
    assert resp.output_tokens > 0

    from openreview_cli.gateway.costs import CostStore

    store = CostStore()
    summary = store.get_summary(session_id=SHARED_SESSION_ID)
    assert summary["total_calls"] >= 1
    assert summary["total_input"] > 0
    assert summary["total_output"] > 0


@pytest.mark.xfail(reason="LiteLLM does not support reranking via OpenRouter")
def test_live_reranking(openrouter_key: None, live_env: Path) -> None:
    resp = route_request(
        slot="reranking",
        query="What is Python?",
        documents=[
            "Python is a programming language.",
            "Java is also a programming language.",
            "Snakes are reptiles.",
        ],
        session_id=SHARED_SESSION_ID,
    )
    assert resp.content is not None
    assert isinstance(resp.content, list)
    assert len(resp.content) > 0
    assert resp.slot == "reranking"
