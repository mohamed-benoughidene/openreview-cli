"""First-run detection and setup for the openreview CLI.

Provides two functions:

* ``is_first_run(config_path)`` — checks whether the config file exists.
* ``mark_first_run_done(config_path)`` — creates the config directory and
  writes a minimal marker file so subsequent calls to ``is_first_run``
  return ``False``.
"""

from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pathlib import Path


def is_first_run(config_path: Path) -> bool:
    """Return ``True`` if *config_path* does not exist (i.e. this is the
    first time the tool has been launched).

    Parameters
    ----------
    config_path:
        The path to the configuration file (e.g. ``~/.config/openreview/config.yml``).
    """
    return not config_path.exists()


def mark_first_run_done(config_path: Path) -> None:
    """Mark the first run as complete by creating the config directory
    (if missing) and writing a minimal YAML config file.

    The write is performed atomically (write to a unique temp file, then
    rename) so that concurrent processes do not produce a partial file.

    Parameters
    ----------
    config_path:
        The path where the config file should be written.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, suffix=".yml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump({"version": 1}, f, default_flow_style=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, config_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
