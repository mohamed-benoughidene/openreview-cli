"""Determinism guards for scripts/benchmark_product_modes.py."""

from __future__ import annotations

import os
import subprocess
import sys

from tests.helpers.benchmark_scripts import REPO_ROOT, load_benchmark_script

BENCH = load_benchmark_script("benchmark_product_modes")

_POSITIONS_SNIPPET = """
import json

from tests.helpers.benchmark_scripts import load_benchmark_script

bench = load_benchmark_script("benchmark_product_modes")
out = {}
for mode, category_ids in sorted(bench.MODE_CATEGORIES.items()):
    for category_id in category_ids:
        for idx in range(5):
            out[f"{mode}|{category_id}|{idx}"] = bench._expected_position(category_id, idx)
print(json.dumps(out, sort_keys=True))
"""

GENERATOR = REPO_ROOT / "scripts" / "benchmark_product_modes.py"


def _positions_in_subprocess(hash_seed: str) -> str:
    """Return all expected positions computed in a fresh interpreter."""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run(
        [sys.executable, "-c", _POSITIONS_SNIPPET],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=120,
        check=True,
    )
    return result.stdout.strip()


def test_expected_position_is_stable_across_processes() -> None:
    """Position cycling must not depend on the salted builtin hash()."""
    assert _positions_in_subprocess("1") == _positions_in_subprocess("2")
