"""The cloud-call counter lives in a litellm-free module (Phase 4)."""

from __future__ import annotations


def test_counter_counts_and_resets() -> None:
    from openreview_cli.gateway import models

    models.reset_total_cloud_calls()
    assert models.get_total_cloud_calls() == 0
    models.record_cloud_call()
    models.record_cloud_call()
    assert models.get_total_cloud_calls() == 2

    # The router re-exports the same functions for existing importers.
    from openreview_cli.gateway.router import get_total_cloud_calls, reset_total_cloud_calls

    assert get_total_cloud_calls() == 2
    reset_total_cloud_calls()
    assert models.get_total_cloud_calls() == 0


def test_counter_import_does_not_pull_litellm() -> None:
    import subprocess
    import sys

    code = (
        "import sys; import openreview_cli.gateway.models as m; "
        "sys.exit(0 if 'litellm' not in sys.modules else 1)"
    )
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
