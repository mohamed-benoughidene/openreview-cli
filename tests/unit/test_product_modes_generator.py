"""Determinism guards for scripts/benchmark_product_modes.py."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


def _fingerprint(root: Path) -> dict[str, str]:
    """Map relative path -> sha256 for every generated file under root."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _generate_into(root: Path) -> dict[str, str]:
    ground_truth = BENCH._generate_pdfs(root)
    BENCH._save_ground_truth(ground_truth, root)
    return _fingerprint(root)


def _run_generate_only(fixtures_dir: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the generator with --generate-only from an isolated working directory.

    The subprocess runs with cwd inside the temp tree, so even on a HEAD build
    that ignores argv and falls back to the cwd-relative FIXTURES constant it can
    never write into the real tests/fixtures/benchmark. PYTHONPATH keeps the repo
    importable while cwd is elsewhere. A timeout is a test failure, not an error:
    on HEAD --generate-only is ignored and the full pipeline runs.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    try:
        return subprocess.run(
            [
                sys.executable,
                str(GENERATOR),
                "--generate-only",
                "--fixtures-dir",
                str(fixtures_dir),
            ],
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=170,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "--generate-only did not exit within 170 s; on HEAD main() ignores the flag and runs "
            "the full pipeline instead of writing the fixtures and returning."
        )


def test_generation_is_byte_stable_within_one_directory(tmp_path: Path) -> None:
    """Two generations into the SAME directory must produce identical bytes.

    On HEAD this fails because doc.save() writes a fresh random trailer /ID.
    """
    first = _generate_into(tmp_path / "same")
    second = _generate_into(tmp_path / "same")
    assert first == second


def test_generation_is_byte_stable_across_directories(tmp_path: Path) -> None:
    """Two generations into different directories must produce identical bytes."""
    first = _generate_into(tmp_path / "first")
    second = _generate_into(tmp_path / "second")
    assert first == second


@pytest.mark.timeout(180)
def test_generate_only_is_idempotent_in_a_temp_dir(tmp_path: Path) -> None:
    """--generate-only must honour --fixtures-dir and be a no-op on a second run.

    The subprocess runs with its cwd inside tmp_path, so it can never write into
    the real tests/fixtures/benchmark. The real-worktree clean-tree check is a
    manual command (C3 Step 6 and the Definition of Done); no unit test mutates
    the checkout.
    """
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    fixtures_dir = tmp_path / "idem"

    first = _run_generate_only(fixtures_dir, workdir)
    assert first.returncode == 0, first.stderr
    before = _fingerprint(fixtures_dir)
    assert before, (
        "the subprocess wrote no files under --fixtures-dir; on HEAD main() ignores argv "
        f"and writes to its cwd-relative FIXTURES instead. stdout: {first.stdout!r}"
    )
    assert not (workdir / "tests").exists(), (
        "the generator wrote outside --fixtures-dir; on HEAD it falls back to "
        "FIXTURES = Path('tests/fixtures/benchmark') relative to cwd"
    )

    second = _run_generate_only(fixtures_dir, workdir)
    assert second.returncode == 0, second.stderr
    assert _fingerprint(fixtures_dir) == before


def test_generator_never_touches_the_hand_made_v2_fixture(tmp_path: Path) -> None:
    """privacycheck/doc_1_v2.pdf is hand-made and must not be regenerated."""
    generated = _generate_into(tmp_path / "check")
    hand_made = "privacycheck/doc_1_v2.pdf"
    assert hand_made not in generated
    assert (BENCH.FIXTURES / hand_made).exists()


def test_default_paths_are_unchanged() -> None:
    assert Path("tests/fixtures/benchmark") == BENCH.FIXTURES
    assert Path(".benchmark-reports") == BENCH.REPORTS_DIR


def test_committed_fixtures_match_a_fresh_generation(tmp_path: Path) -> None:
    """The tracked fixtures must be exactly what the generator produces."""
    fresh = _generate_into(tmp_path / "fresh")
    for relative_path, digest in fresh.items():
        committed = BENCH.FIXTURES / relative_path
        assert committed.exists(), f"missing committed fixture: {committed}"
        actual = hashlib.sha256(committed.read_bytes()).hexdigest()
        assert actual == digest, f"stale committed fixture: {committed}"
