import logging
import sys
from pathlib import Path


def setup_logging(log_dir: Path, debug: bool = False) -> None:
    log_file = log_dir / "openreview.log"
    log_dir.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if debug else logging.INFO
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    root = logging.getLogger()
    root.setLevel(level)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)
