"""Integration test for P3-C4: Recovery persistence wired in production runner.

P3-C4 defect: ``src/openreview_cli/review/runner.py:248-251`` constructs
``RecoveryCoordinator`` without passing ``db_path``, so the coordinator
never persists recovery state to disk. The mechanism works (proven by
``tests/unit/test_recovery_persistence.py``) but the production call
site does not enable it.

The fix wires ``db_path=str(get_data_dir() / "recovery.db")`` into the
production call site.

This test asserts:
1. (text-based) the production call site at ``review/runner.py``
   constructs ``RecoveryCoordinator`` with a non-None ``db_path``
   pointing under ``get_data_dir()``.
2. (behavioral) a ``RecoveryCoordinator`` constructed with the same
   ``db_path`` and invoked through ``evaluate_pre_stage`` actually
   writes a row to the recovery DB.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

RUNNER_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "openreview_cli" / "review" / "runner.py"
)


@pytest.fixture(scope="module")
def runner_text() -> str:
    assert RUNNER_PATH.exists(), f"runner.py not found at {RUNNER_PATH}"
    return RUNNER_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Text-based structural tests.
# ---------------------------------------------------------------------------


def test_runner_passes_db_path_to_recovery_coordinator(runner_text: str) -> None:
    """P3-C4: the production call site must pass db_path to RecoveryCoordinator."""
    match = re.search(
        r"coordinator\s*=\s*RecoveryCoordinator\((?P<body>[^)]*)\)",
        runner_text,
        re.DOTALL,
    )
    assert match, "P3-C4: RecoveryCoordinator(...) call not found in runner.py"

    body = match.group("body")
    assert "db_path" in body, (
        "P3-C4 defect: the production call to RecoveryCoordinator(...) at runner.py omits "
        "'db_path'. This means recovery state is never persisted to disk in production."
    )


def test_runner_db_path_points_to_data_dir(runner_text: str) -> None:
    """P3-C4: the db_path must point under get_data_dir() (not /tmp or cwd)."""
    match = re.search(
        r"coordinator\s*=\s*RecoveryCoordinator\([^)]*?db_path\s*=\s*(?P<val>[^,\n)]+)",
        runner_text,
        re.DOTALL,
    )
    assert match, "P3-C4: db_path not passed to RecoveryCoordinator at runner.py"
    value = match.group("val").strip()
    assert "get_data_dir" in value, (
        f"P3-C4: db_path={value!r} does not reference get_data_dir(). "
        "The recovery DB must live under the platform's user data dir."
    )


# ---------------------------------------------------------------------------
# Behavioral test: drive a RecoveryCoordinator end-to-end and verify a row
# is written to the recovery DB.
# ---------------------------------------------------------------------------


def test_recovery_coordinator_actually_persists_to_db() -> None:
    """P3-C4 M-2: behavioral assertion that recovery persistence works.

    Constructs a real RecoveryCoordinator with a temporary ``db_path``,
    drives a pre-stage evaluation (which should call ``_persist_context``),
    and asserts that a row exists in the ``recovery_state`` table.
    """
    import asyncio
    import json

    from openreview_cli.config import RecoveryConfig
    from openreview_cli.recovery.coordinator import RecoveryCoordinator

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "recovery.db"
        coord = RecoveryCoordinator(
            config=RecoveryConfig(),
            db_path=str(db_path),
        )
        ctx = coord.create_context(provider_list=["openai/gpt-4o"])
        # evaluate_pre_stage is async; must be awaited
        asyncio.run(
            coord.evaluate_pre_stage(
                stage_name="parse",
                critical=True,
                memory_bytes=1_000_000,  # well below threshold so PROCEED path
                ctx=ctx,
            )
        )
        # Verify a row was written
        assert db_path.exists(), f"P3-C4: recovery DB not created at {db_path}"
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT pipeline_id, stage_name, context_json FROM recovery_state"
            ).fetchone()
        assert row is not None, "P3-C4: no row written to recovery_state table"
        assert row[0] == coord._pipeline_id, "P3-C4: pipeline_id mismatch"
        assert row[1] == "parse", "P3-C4: stage_name mismatch"
        # The context_json should be valid JSON (proving _json_safe did its job)
        parsed = json.loads(row[2])
        assert parsed["user_privacy_tier"] in ("strict", "standard", "none")
