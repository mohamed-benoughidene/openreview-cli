from __future__ import annotations

import logging
import re


def redact_key(key: str, visible: int = 4) -> str:
    if not key:
        return ""
    if len(key) <= visible:
        return "*" * len(key)
    return key[:visible] + "*" * (len(key) - visible)


REDACT_PATTERNS: list[str] = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "COHERE_API_KEY",
    "HUGGINGFACE_API_KEY",
    "CUSTOM_API_KEY",
    "sk-",
    "sk-ant-",
]

_KEY_VALUE_RE = re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_\-]{12,}")


class RedactingFilter(logging.Filter):
    def __init__(self, patterns: list[str] | None = None) -> None:
        super().__init__()
        self._patterns = patterns or []

    def _redact(self, text: str) -> str:
        # Value pass FIRST: the literal "sk-" pattern below would otherwise mask
        # the prefix and leave the whole key body in place.
        text = _KEY_VALUE_RE.sub(lambda m: redact_key(m.group(0)), text)
        for pat in self._patterns:
            if pat and isinstance(pat, str) and pat in text:
                text = text.replace(pat, redact_key(pat))
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(record.getMessage())
        record.args = ()
        if record.exc_info and not record.exc_text:
            record.exc_text = self._redact(logging.Formatter().formatException(record.exc_info))
        return True


def install_on_root_handlers() -> None:
    """Attach a RedactingFilter to every root handler (idempotent per handler).

    Handlers, not the root logger: propagated records never consult a logger's
    own filters, so a logger-level filter leaves module loggers uncovered.
    """
    for handler in logging.getLogger().handlers:
        if any(isinstance(f, RedactingFilter) for f in handler.filters):
            continue
        handler.addFilter(RedactingFilter(REDACT_PATTERNS))
