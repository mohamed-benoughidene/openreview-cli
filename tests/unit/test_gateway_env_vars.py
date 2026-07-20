from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from openreview_cli.gateway.router import Gateway


def _make_gateway(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auth_text: str) -> Gateway:
    import uuid

    import openreview_cli.gateway.cost as cost_mod

    monkeypatch.setattr(cost_mod, "db_log_cost", lambda *a, **kw: str(uuid.uuid4()))
    monkeypatch.setattr(
        cost_mod,
        "db_get_session_cost",
        lambda *a, **kw: {"prompt_tokens": 0, "completion_tokens": 0, "cost_cents": 0},
    )
    monkeypatch.setattr(cost_mod, "completion_cost", lambda r: 0.0)

    config_path = tmp_path / "config.yml"
    config_path.write_text("gateway:\n  models: {}\n")
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(auth_text)
    db_path = tmp_path / "data.db"
    from openreview_cli.storage.database import init_database

    init_database(db_path)
    return Gateway(config_path, auth_path, db_path)


def test_set_env_vars_handles_both_shapes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_set_env_vars must set legacy string keys AND dict-shaped multi-field
    keys into the environment."""
    for key in ("OPENAI_API_KEY", "AWS_REGION_NAME", "AWS_ACCESS_KEY_ID"):
        monkeypatch.delenv(key, raising=False)

    auth_text = json.dumps(
        {
            "openai": "sk-legacy",
            "bedrock": {
                "AWS_REGION_NAME": "us-east-1",
                "AWS_ACCESS_KEY_ID": "AKIA",
            },
        }
    )
    gw = _make_gateway(tmp_path, monkeypatch, auth_text)

    assert os.environ.get("OPENAI_API_KEY") == "sk-legacy"
    assert os.environ.get("AWS_REGION_NAME") == "us-east-1"
    assert os.environ.get("AWS_ACCESS_KEY_ID") == "AKIA"
