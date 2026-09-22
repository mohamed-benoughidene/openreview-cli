"""Shared loader for the standalone benchmark scripts under scripts/."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def load_benchmark_script(name: str) -> Any:
    """Import scripts/<name>.py as a module without running main()."""
    script_path = REPO_ROOT / "scripts" / f"{name}.py"
    assert script_path.exists(), f"missing benchmark script: {script_path}"
    spec = importlib.util.spec_from_file_location(name, script_path)
    assert spec is not None, f"cannot build a module spec for {script_path}"
    assert spec.loader is not None, f"no loader for {script_path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
