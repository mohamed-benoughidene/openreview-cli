"""Guard: the reranker feature was removed (spec 035 follow-up).

The ``reranking`` gateway socket was deleted in spec 035, so the reranker could
never reach a provider. Rather than leave inert ``--rerank*`` flags, the whole
feature was removed. These assertions pin the new surface.
"""

from __future__ import annotations

import importlib

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app


def test_rerank_module_is_gone() -> None:
    """The ``retrieval.rerank`` wrapper must no longer be importable."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("openreview_cli.retrieval.rerank")


def test_retrieve_help_has_no_rerank_flags() -> None:
    """``retrieve --help`` must not list any ``--rerank*`` option."""
    result = CliRunner().invoke(app, ["retrieve", "--help"])
    assert result.exit_code == 0, result.output
    assert "--rerank" not in result.output
    assert "--rerank-depth" not in result.output
    assert "--force-rerank" not in result.output
