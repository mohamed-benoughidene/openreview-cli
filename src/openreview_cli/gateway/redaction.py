from __future__ import annotations

import logging


def redact_key(key: str, visible: int = 4) -> str:
    if not key:
        return ""
    if len(key) <= visible:
        return "*" * len(key)
    return key[:visible] + "*" * (len(key) - visible)


class RedactingFilter(logging.Filter):
    def __init__(self, patterns: list[str] | None = None) -> None:
        super().__init__()
        self._patterns = patterns or []

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pat in self._patterns:
            if pat and isinstance(pat, str) and pat in msg:
                idx = msg.index(pat)
                record.msg = msg[: idx + len(pat)] + "****"
        return True
