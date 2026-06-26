import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, content: str) -> None:
    """Write text content to path atomically using tempfile, flush, fsync and rename."""
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
