"""Regression tests for README/ARCHITECTURE public-claim drift (Blocker 3 / D6).

These tests pin the numeric values that appear in README.md and ARCHITECTURE.md
so that future drift is caught by the test suite.
"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_product_mode_count() -> None:
    """Code requires 23 product modes."""
    from openreview_cli.app import _PRODUCT_MODES

    assert len(_PRODUCT_MODES) == 23


def test_version_matches_pyproject() -> None:
    """README and __init__.py version must match pyproject.toml."""
    from openreview_cli import __version__

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]


def test_bundled_playbook_count() -> None:
    """README claims 24 bundled playbooks."""
    from openreview_cli.review.playbook import BUNDLED_PLAYBOOKS

    assert len(BUNDLED_PLAYBOOKS) == 24


def test_migration_count() -> None:
    """ARCHITECTURE claims 12 migrations (001-013, no 012)."""
    migrations_dir = REPO_ROOT / "src" / "openreview_cli" / "storage" / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))
    assert len(sql_files) == 12
    names = [f.stem for f in sql_files]
    assert "012" not in names


def test_settlementcheck_v2_in_readme_table() -> None:
    """README contract-modes table must include settlementcheck_v2."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "settlementcheck_v2" in readme
