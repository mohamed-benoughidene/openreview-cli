import json
import logging
import os
import sys
from pathlib import Path
from typing import Any


def get_sensitive_strings() -> list[str]:
    keys = []
    # 1. From auth.json
    try:
        from openreview_cli.config.paths import get_config_dir

        path = get_config_dir() / "auth.json"
        if path.exists():
            data = json.loads(path.read_text())
            for k, v in data.items():
                if (
                    isinstance(v, str)
                    and v
                    and not k.endswith("_api_base")
                    and not k.endswith("_base_url")
                ):
                    keys.append(v)
    except Exception:
        pass

    # 2. From env vars
    for k, v in os.environ.items():
        if k.endswith("_API_KEY") and v:
            keys.append(v)

    # Filter out empty or very short strings to avoid corrupting logs
    return sorted({k for k in keys if len(k) > 3}, key=len, reverse=True)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for key in get_sensitive_strings():
            formatted = formatted.replace(key, "[REDACTED]")
        return formatted


class RedactingStream:
    def __init__(self, original_stream: Any) -> None:
        self.original_stream = original_stream

    def write(self, data: str) -> int:
        if isinstance(data, str) and data:
            for key in get_sensitive_strings():
                data = data.replace(key, "[REDACTED]")
        return int(self.original_stream.write(data))

    def flush(self) -> None:
        self.original_stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.original_stream, name)


def setup_cli_redaction() -> None:
    if not isinstance(sys.stdout, RedactingStream):
        sys.stdout = RedactingStream(sys.stdout)
    if not isinstance(sys.stderr, RedactingStream):
        sys.stderr = RedactingStream(sys.stderr)


def setup_gateway_logging(
    level: str = "info",
    debug_file: Path | str = "~/.openreview/gateway.log",
) -> None:
    if isinstance(debug_file, str):
        if debug_file.startswith("~"):
            debug_path = Path(os.path.expanduser(debug_file))
        else:
            debug_path = Path(debug_file)
    else:
        debug_path = debug_file

    import contextlib

    with contextlib.suppress(Exception):
        debug_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("openreview_cli")
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    # Console handler
    sh = logging.StreamHandler(sys.stderr)
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    sh.setLevel(level_map.get(level.lower(), logging.INFO))
    sh.setFormatter(RedactingFormatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(sh)

    # File handler
    try:
        fh = logging.FileHandler(debug_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(RedactingFormatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"Could not create gateway debug log file at {debug_path}: {e}")

    setup_cli_redaction()


_state = {"debug_unsafe": False}


def set_debug_unsafe(val: bool) -> None:
    _state["debug_unsafe"] = val


def is_debug_unsafe() -> bool:
    return _state["debug_unsafe"]
