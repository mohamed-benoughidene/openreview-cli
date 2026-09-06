"""V0: End-to-end API-key redaction test (A7).

Verifies that a synthetic ``sk-testkey…`` credential injected via
``auth.json`` is never visible in any output surface when the user
runs ``openreview gateway status``:

1. ``result.output`` - stdout (Rich table)
2. ``result.stderr`` - logging StreamHandler output
3. ``openreview.log`` - logging FileHandler output

The test exercises the real code path:
  CLI callback → ``_init(debug=True)`` → ``Gateway()``
  → ``load_auth()`` → ``_set_env_vars()``
  → ``logger.debug("Set %s to %s", ..., redact_key(creds))``

Credential values are proactively redacted at the call site
(``redact_key()`` in router.py:205) before reaching any handler.
The ``RedactingFilter`` attached to the root logger provides
defense-in-depth for any logging call that omits proactive redaction.

No network calls are made (``gateway status`` only reads local
config/auth; ``--disable-socket`` is inherited from pyproject.toml).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openreview_cli.app import app

_SYNTHETIC_KEY = "sk-testkey123456789"

# redact_key("sk-testkey123456789", visible=4) → "sk-t***************"
_REDACTED_KEY_PREFIX = "sk-t" + "*" * (len(_SYNTHETIC_KEY) - 4)

runner = CliRunner()


@pytest.mark.integration
def test_sk_key_redacted_in_stdout_stderr_and_logfile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A synthetic sk- key in auth.json must not leak into any output surface."""
    config_dir = tmp_path / "config"
    log_dir = tmp_path / "logs"
    data_dir = tmp_path / "data"
    for d in (config_dir, log_dir, data_dir):
        d.mkdir()

    (config_dir / "config.yml").write_text("gateway:\n  models: {}\n")
    (config_dir / "auth.json").write_text(json.dumps({"openai": _SYNTHETIC_KEY}))

    # Patch path helpers at source module AND consumer modules that
    # imported the name directly (`from X import get_config_dir`).
    for dotted in (
        "openreview_cli.config.paths.get_config_dir",
        "openreview_cli.app.get_config_dir",
        "openreview_cli.gateway.router.get_config_dir",
    ):
        monkeypatch.setattr(dotted, lambda: config_dir)
    for dotted in (
        "openreview_cli.config.paths.get_log_dir",
        "openreview_cli.app.get_log_dir",
    ):
        monkeypatch.setattr(dotted, lambda: log_dir)
    for dotted in (
        "openreview_cli.config.paths.get_data_dir",
        "openreview_cli.app.get_data_dir",
        "openreview_cli.gateway.router.get_data_dir",
    ):
        monkeypatch.setattr(dotted, lambda: data_dir)

    # Ensure env var is absent so _set_env_vars fires the debug log.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # --debug: root logger level → DEBUG so router.py:205 fires.
    result = runner.invoke(app, ["--debug", "gateway", "status"])

    assert result.exit_code == 0, (
        f"`gateway status` exited {result.exit_code}\n"
        f"stdout: {result.output!r}\n"
        f"stderr: {result.stderr!r}\n"
        f"exception: {result.exception!r}"
    )

    assert "Gateway Status" in result.output, (
        f"Expected Rich table in output, got: {result.output!r}"
    )

    log_file = log_dir / "openreview.log"
    assert log_file.exists(), "openreview.log was not created"
    log_text = log_file.read_text()

    # ── Negative checks: the raw key must not appear anywhere. ────
    assert _SYNTHETIC_KEY not in result.output, "Key leaked into stdout"
    assert _SYNTHETIC_KEY not in result.stderr, "Key leaked into stderr"
    assert _SYNTHETIC_KEY not in log_text, "Key leaked into openreview.log"

    # Belt-and-suspenders: catch partial leaks (prefix only).
    assert "sk-testkey" not in result.output
    assert "sk-testkey" not in result.stderr
    assert "sk-testkey" not in log_text

    # ── Positive check: redacted form proves the debug log fired ──
    # The debug log at router.py:205 emits:
    #   "Set OPENAI_API_KEY to sk-t***************"
    # The redacted key prefix confirms redact_key() processed the
    # credential before it reached any handler.
    assert _REDACTED_KEY_PREFIX in log_text, (
        f"Redacted key prefix {_REDACTED_KEY_PREFIX!r} not found in log — "
        f"the debug log at router.py:205 may not have fired.\n"
        f"Log content:\n{log_text}"
    )

    os.environ.pop("OPENAI_API_KEY", None)
