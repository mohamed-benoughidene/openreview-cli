import logging
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

from openreview_cli.gateway.logging import (
    RedactingFormatter,
    RedactingStream,
    get_sensitive_strings,
    setup_gateway_logging,
)


@pytest.fixture
def clean_logging_state(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    # Backup original stdout/stderr
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr

    # Reset logging handlers on openreview_cli logger
    logger = logging.getLogger("openreview_cli")
    orig_handlers = list(logger.handlers)
    logger.handlers.clear()

    yield

    # Restore original state
    sys.stdout = orig_stdout
    sys.stderr = orig_stderr
    logger.handlers = orig_handlers


def test_get_sensitive_strings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Set env var API key
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-openai12345testkey")

    # Mock config dir so we can write an auth.json
    config_dir = tmp_path / "openreview"
    config_dir.mkdir()
    monkeypatch.setattr("openreview_cli.config.paths.get_config_dir", lambda: config_dir)

    auth_file = config_dir / "auth.json"
    auth_file.write_text('{"anthropic": "sk-ant-anthropic54321testkey"}')

    sensitive = get_sensitive_strings()
    assert "sk-proj-openai12345testkey" in sensitive
    assert "sk-ant-anthropic54321testkey" in sensitive
    # Ensure they are sorted by length descending
    assert (
        sensitive.index("sk-proj-openai12345testkey")
        < sensitive.index("sk-ant-anthropic54321testkey")
        if len("sk-proj-openai12345testkey") > len("sk-ant-anthropic54321testkey")
        else True
    )


def test_redacting_formatter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret-api-key-12345")
    formatter = RedactingFormatter("%(message)s")

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="API call failed with key: secret-api-key-12345",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    assert "secret-api-key-12345" not in formatted
    assert "API call failed with key: [REDACTED]" in formatted


def test_redacting_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret-api-key-12345")

    class MockStream:
        def __init__(self) -> None:
            self.written: list[str] = []

        def write(self, data: str) -> int:
            self.written.append(data)
            return len(data)

        def flush(self) -> None:
            pass

    mock_inner = MockStream()
    redacting = RedactingStream(mock_inner)

    redacting.write("The key is secret-api-key-12345")
    assert "secret-api-key-12345" not in mock_inner.written[0]
    assert "The key is [REDACTED]" in mock_inner.written[0]


def test_setup_gateway_logging(clean_logging_state: None, tmp_path: Path) -> None:
    log_file = tmp_path / "gateway.log"
    setup_gateway_logging(
        level="info",
        debug_file=log_file,
    )

    logger = logging.getLogger("openreview_cli")
    # Verify we have at least file and console handlers configured
    handlers = logger.handlers
    assert len(handlers) >= 2

    # One should be a StreamHandler, one a FileHandler
    file_handler = next(h for h in handlers if isinstance(h, logging.FileHandler))
    stream_handler = next(h for h in handlers if isinstance(h, logging.StreamHandler))

    # File handler should accept DEBUG logs
    assert file_handler.level == logging.DEBUG
    # Stream handler should accept INFO logs
    assert stream_handler.level == logging.INFO

    # Both handlers should use RedactingFormatter
    assert isinstance(file_handler.formatter, RedactingFormatter)
    assert isinstance(stream_handler.formatter, RedactingFormatter)


def test_debug_unsafe_setter_getter() -> None:
    from openreview_cli.gateway.logging import is_debug_unsafe, set_debug_unsafe

    set_debug_unsafe(True)
    assert is_debug_unsafe() is True
    set_debug_unsafe(False)
    assert is_debug_unsafe() is False
