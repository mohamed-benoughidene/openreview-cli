from __future__ import annotations

import contextlib
import io
import logging
from collections.abc import Iterator

from openreview_cli.gateway.redaction import (
    REDACT_PATTERNS,
    RedactingFilter,
    install_on_root_handlers,
)

_PROBE_KEY = "sk-testkey123456789"


@contextlib.contextmanager
def _root_stream() -> Iterator[io.StringIO]:
    root = logging.getLogger()
    saved = [(handler, list(handler.filters)) for handler in root.handlers]
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    root.addHandler(handler)
    try:
        yield stream
    finally:
        root.removeHandler(handler)
        for owned, filters in saved:
            owned.filters[:] = filters


def test_child_logger_record_is_redacted_through_root_handler() -> None:
    with _root_stream() as stream:
        install_on_root_handlers()
        logging.getLogger("openreview_cli.parsing.pdf_parser").warning(
            "probe ANTHROPIC_API_KEY=%s", _PROBE_KEY
        )
    rendered = stream.getvalue()
    # Positive check: the record actually reached the handler. Without this a
    # dropped record would satisfy all three negative checks vacuously.
    assert "probe" in rendered
    assert "ANTHROPIC_API_KEY" not in rendered
    assert _PROBE_KEY not in rendered
    assert "testkey123456789" not in rendered


def test_install_on_root_handlers_is_idempotent() -> None:
    with _root_stream():
        install_on_root_handlers()
        install_on_root_handlers()
        for handler in logging.getLogger().handlers:
            assert sum(isinstance(f, RedactingFilter) for f in handler.filters) == 1


def test_install_does_not_touch_non_root_loggers() -> None:
    child = logging.getLogger("openreview_cli.parsing.install_probe")
    with _root_stream():
        install_on_root_handlers()
        assert child.filters == []


def test_filter_redacts_exception_text() -> None:
    record = logging.LogRecord(
        "test",
        logging.ERROR,
        "",
        0,
        "failure",
        (),
        (ValueError, ValueError("boom ANTHROPIC_API_KEY=sk-x"), None),
    )
    assert RedactingFilter(REDACT_PATTERNS).filter(record)
    assert record.exc_text is not None
    assert "ANTHROPIC_API_KEY" not in record.exc_text


def test_filter_redacts_key_value_body() -> None:
    record = logging.LogRecord(
        "test", logging.INFO, "", 0, "using sk-live-abcdefghijklmn", (), None
    )
    assert RedactingFilter(REDACT_PATTERNS).filter(record)
    assert "abcdefghijklmn" not in record.getMessage()
