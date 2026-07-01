from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from openreview_cli.gateway.wizard import gateway_setup


class TestGatewayWizard:
    def test_wizard_calls_questionary_for_each_slot(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "openreview_cli.gateway.wizard.get_config_dir",
            lambda: tmp_path,
        )
        config_path = tmp_path / "config.yml"
        config_path.write_text("gateway:\n  models: {}\n")
        auth_path = tmp_path / "auth.json"
        auth_path.write_text("{}")
        reg_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "openreview_cli"
            / "gateway"
            / "models.json"
        )
        monkeypatch.setattr(
            "openreview_cli.gateway.wizard.Path",
            lambda *a: reg_path if "models.json" in str(a[-1]) else Path(*a),
        )
        calls: list[str] = []

        class FakeSelect:
            def __init__(self, title: str, choices: list[str]) -> None:
                self._title = title

            def ask(self) -> str:
                calls.append(self._title)
                return "ollama/qwen3:8b"

        class FakeText:
            def ask(self) -> str:
                return "ollama/test-model"

        class FakePassword:
            def ask(self) -> str:
                return ""

        monkeypatch.setattr("questionary.select", FakeSelect)
        monkeypatch.setattr("questionary.text", lambda prompt: FakeText())
        monkeypatch.setattr("questionary.password", lambda prompt: FakePassword())

        gateway_setup()

        assert len(calls) == 5
        assert any("reasoning" in c for c in calls)
        assert any("graph" in c for c in calls)

    def test_wizard_aborts_on_none(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "openreview_cli.gateway.wizard.get_config_dir",
            lambda: tmp_path,
        )
        config_path = tmp_path / "config.yml"
        config_path.write_text("gateway:\n  models: {}\n")
        auth_path = tmp_path / "auth.json"
        auth_path.write_text("{}")
        reg_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "openreview_cli"
            / "gateway"
            / "models.json"
        )
        monkeypatch.setattr(
            "openreview_cli.gateway.wizard.Path",
            lambda *a: reg_path if "models.json" in str(a[-1]) else Path(*a),
        )

        class FakeSelectNone:
            def ask(self) -> None:
                return None

        monkeypatch.setattr("questionary.select", lambda title, choices: FakeSelectNone())

        gateway_setup()

        assert config_path.exists()
