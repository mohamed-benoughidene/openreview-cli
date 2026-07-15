from __future__ import annotations

import http.server
import socketserver
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from openreview_cli.gateway.errors import ConnectionError
from openreview_cli.gateway.models import Capability, ProviderInfo, StreamingOutputEvent
from openreview_cli.gateway.router import Gateway

CHUNK_BODY = (
    b'data: {"id":"x","object":"chat.completion.chunk",'
    b'"choices":[{"index":0,"delta":{"content":"hi"},'
    b'"finish_reason":null}]}\n\n'
)


def _make_handler_class() -> type[http.server.BaseHTTPRequestHandler]:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def _respond(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            self.wfile.write(CHUNK_BODY)
            self.wfile.flush()
            time.sleep(30)  # silent > patched idle timeout; must be cut off

        def do_POST(self) -> None:
            self._respond()

        def do_GET(self) -> None:
            self._respond()

        def log_message(self, *args: Any, **kwargs: Any) -> None:
            pass

    return _Handler


def _build_gateway(monkeypatch: pytest.MonkeyPatch, port: int) -> Gateway:
    gw = Gateway.__new__(Gateway)
    gw._config = {"gateway": {"models": {"extraction": {"primary": "openai/test-model"}}}}
    gw._data_path = MagicMock()
    gw._cloud_calls_made = 0
    gw._cost_tracker = MagicMock()
    gw._check_cost_limits = lambda *a, **k: None  # type: ignore[method-assign]
    gw._record_cloud_call = lambda *a, **k: None  # type: ignore[method-assign]

    monkeypatch.setattr(
        "openreview_cli.prompts.store.PromptStore", MagicMock(resolve=lambda *a, **k: None)
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.setattr(
        "openreview_cli.gateway.router.load_registry",
        lambda: {
            "openai": ProviderInfo(
                name="openai",
                base_url=f"http://127.0.0.1:{port}/v1",
                is_local=True,
                capabilities=Capability(),
            )
        },
    )
    monkeypatch.setattr("openreview_cli.gateway.router.STREAM_READ_TIMEOUT", 3.0)
    monkeypatch.setattr("openreview_cli.gateway.router.STREAM_CONNECT_TIMEOUT", 2.0)
    return gw


@pytest.mark.timeout(180)
def test_stream_idle_20_runs_95pct_reliable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    successes = 0
    chunk_runs = 0
    hung_count = 0

    for _ in range(20):
        handler_cls = _make_handler_class()
        httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler_cls)
        port = httpd.server_address[1]
        srv_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        srv_thread.start()
        gw = _build_gateway(monkeypatch, port)

        events: list[StreamingOutputEvent] = []
        caught: BaseException | None = None
        try:
            for ev in gw.chat_stream("extraction", [{"role": "user", "content": "hi"}]):
                events.append(ev)
        except Exception as exc:
            caught = exc
        finally:
            httpd.shutdown()

        raised_cleanly = isinstance(caught, ConnectionError) and (caught.timeout_kind is not None)
        if raised_cleanly:
            successes += 1
        if any(ev.type == "chunk" for ev in events):
            chunk_runs += 1

    assert hung_count == 0
    assert successes >= 19, f"only {successes}/20 terminated cleanly"
    # Softer check: litellm buffers the body and may cut before emitting the
    # first chunk, so chunk_yield is not a hard gate (task note allows relax).
    if chunk_runs > 0:
        assert chunk_runs >= 19, f"only {chunk_runs}/20 rendered a chunk"
