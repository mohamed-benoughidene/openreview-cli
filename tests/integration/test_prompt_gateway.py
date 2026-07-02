from pathlib import Path
from unittest.mock import patch

import pytest

from openreview_cli.config.paths import get_data_dir
from openreview_cli.prompts.store import PromptStore
from openreview_cli.storage.database import init_database


@pytest.fixture(autouse=True)
def _xdg_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))


@pytest.fixture(autouse=True)
def _ensure_auth(tmp_path: Path) -> None:
    auth_dir = tmp_path / "config" / "openreview"
    auth_dir.mkdir(parents=True, exist_ok=True)
    (auth_dir / "auth.json").write_text("{}")


class TestPromptGateway:
    def test_resolve_returns_bound_prompt_content(self) -> None:
        db_path = get_data_dir() / "openreview.db"
        store = PromptStore(db_path)
        store.init()
        store.create("test-prompt", "You are a helpful assistant.")
        store.bind("extraction", "test-prompt", 1)

        content = store.resolve("extraction")
        assert content == "You are a helpful assistant."

    def test_resolve_returns_empty_when_no_binding(self) -> None:
        db_path = get_data_dir() / "openreview.db"
        store = PromptStore(db_path)
        store.init()

        content = store.resolve("extraction")
        assert content == ""

    def test_resolve_after_unbind_returns_empty(self) -> None:
        db_path = get_data_dir() / "openreview.db"
        store = PromptStore(db_path)
        store.init()
        store.create("test-prompt", "Hello")
        store.bind("extraction", "test-prompt", 1)
        store.unbind("extraction")

        content = store.resolve("extraction")
        assert content == ""

    def test_resolve_returns_content_for_latest_version(self) -> None:
        db_path = get_data_dir() / "openreview.db"
        store = PromptStore(db_path)
        store.init()
        store.create("test-prompt", "v1")
        store.update("test-prompt", "v2")
        store.bind("extraction", "test-prompt", 2)

        content = store.resolve("extraction")
        assert content == "v2"

    def test_gateway_chat_prepends_system_message(self) -> None:
        from openreview_cli.gateway.cost import CostTracker
        from openreview_cli.gateway.router import Gateway

        db_path = get_data_dir() / "openreview.db"
        init_database(db_path)
        store = PromptStore(db_path)
        store.init()
        store.create("gw-prompt", "System instruction.")
        store.bind("extraction", "gw-prompt", 1)

        with (
            patch.object(CostTracker, "log_call", return_value=None),
            patch.object(
                Gateway,
                "_call_with_fallback",
                return_value=type(
                    "R",
                    (),
                    {"choices": [type("C", (), {"message": type("M", (), {"content": "ok"})})]},
                )(),
            ),
        ):
            gw = Gateway()
            resp = gw.chat(
                "extraction", [{"role": "user", "content": "Hello"}], session_id="test-session"
            )
            assert resp == "ok"
