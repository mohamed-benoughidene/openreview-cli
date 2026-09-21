from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from openreview_cli.config.loader import load_config
from openreview_cli.gateway.models import CredentialField
from openreview_cli.gateway.wizard import gateway_setup


def _fake_questionary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    text_answer: str = "",
    provider_answer: str = "ollama",
) -> list[str]:
    """Install the near-identical questionary/registry fakes the wizard tests share.

    ``questionary.select`` answers ``provider_answer`` for a provider prompt and
    the first choice otherwise; ``questionary.text`` returns ``text_answer`` and
    ``questionary.password`` returns ``""``. The fake registry lists one model
    for ``ollama`` and none for any other provider. Returns the title of every
    ``questionary.select`` prompt, in order.
    """
    calls: list[str] = []

    class FakeRegistry:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def load(self) -> None:
            pass

        def list_models(self, provider: str) -> list[dict[str, object]]:
            if provider == "ollama":
                return [{"model_id": "qwen3:8b", "slots": [], "context": 0}]
            return []

        def list_providers(self) -> list[dict[str, object]]:
            return [{"name": "ollama", "env_key": None}]

    class FakeSelect:
        def __init__(self, title: str, choices: list[str]) -> None:
            self._title = title
            self._choices = choices

        def ask(self) -> str:
            calls.append(self._title)
            if "Provider" in self._title:
                return provider_answer
            return self._choices[0]

    class FakeText:
        def ask(self) -> str:
            return text_answer

    class FakePassword:
        def ask(self) -> str:
            return ""

    monkeypatch.setattr("openreview_cli.gateway.wizard.ModelRegistry", FakeRegistry)
    monkeypatch.setattr("questionary.select", FakeSelect)
    monkeypatch.setattr("questionary.text", lambda prompt: FakeText())
    monkeypatch.setattr("questionary.password", lambda prompt: FakePassword())
    return calls


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
        calls = _fake_questionary(
            monkeypatch,
            provider_answer="ollama/qwen3:8b",
            text_answer="ollama/test-model",
        )

        gateway_setup()

        assert len(calls) == 6
        assert any("reasoning" in c for c in calls)
        assert any("graph" in c for c in calls)
        assert any("grounding" in c for c in calls)

    def test_wizard_prompts_for_optional_fallback(
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
        (tmp_path / "auth.json").write_text("{}")

        backup = "anthropic/claude-3-5-haiku"
        _fake_questionary(monkeypatch, text_answer=backup)

        gateway_setup()

        models = load_config(config_path)["gateway"]["models"]
        for slot in ("reasoning", "extraction", "graph", "grounding"):
            assert models[slot]["fallback"] == backup
        for slot in ("embedding", "reranking"):
            assert models[slot].get("fallback") is None

    def test_wizard_skips_blank_fallback(
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
        (tmp_path / "auth.json").write_text("{}")

        _fake_questionary(monkeypatch)

        gateway_setup()

        models = load_config(config_path)["gateway"]["models"]
        for slot in ("reasoning", "extraction", "graph", "grounding"):
            assert models[slot]["fallback"] is None

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

    def test_wizard_collects_per_field_credentials(
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

        class FakeRegistry:
            def __init__(self, *a: object, **k: object) -> None:
                pass

            def load(self) -> None:
                pass

            def list_providers(self) -> list[dict[str, object]]:
                return [
                    {
                        "name": "bedrock",
                        "env_key": None,
                        "credentials": [
                            CredentialField(
                                env_key="AWS_REGION_NAME",
                                label="Region",
                                litellm_param="aws_region_name",
                                secret=False,
                            ),
                            CredentialField(
                                env_key="AWS_SECRET_ACCESS_KEY",
                                label="Secret",
                                litellm_param="aws_secret_access_key",
                                secret=True,
                                is_file_path=False,
                            ),
                        ],
                    }
                ]

            def list_models(self, provider: str) -> list[dict[str, str]]:
                return []

        monkeypatch.setattr("openreview_cli.gateway.wizard.ModelRegistry", FakeRegistry)

        class FakeSelect:
            def __init__(self, title: str, choices: list[str]) -> None:
                self._title = title

            def ask(self) -> str:
                return "bedrock"

        class FakeText:
            def __init__(self, prompt: str) -> None:
                self._prompt = prompt

            def ask(self) -> str:
                return "us-east-1"

        class FakePassword:
            def __init__(self, prompt: str) -> None:
                self._prompt = prompt

            def ask(self) -> str:
                return "topsecret"

        monkeypatch.setattr("questionary.select", FakeSelect)
        monkeypatch.setattr("questionary.text", FakeText)
        monkeypatch.setattr("questionary.password", FakePassword)

        gateway_setup()

        data = json.loads(auth_path.read_text())
        assert data["bedrock"] == {
            "AWS_REGION_NAME": "us-east-1",
            "AWS_SECRET_ACCESS_KEY": "topsecret",
        }

    def test_wizard_rejects_empty_required_field(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """T038 — FR-5: empty required (non-file) field must be rejected."""
        monkeypatch.setattr(
            "openreview_cli.gateway.wizard.get_config_dir",
            lambda: tmp_path,
        )
        config_path = tmp_path / "config.yml"
        config_path.write_text("gateway:\n  models: {}\n")
        auth_path = tmp_path / "auth.json"
        auth_path.write_text("{}")

        class FakeRegistry:
            def __init__(self, *a: object, **k: object) -> None:
                pass

            def load(self) -> None:
                pass

            def list_providers(self) -> list[dict[str, object]]:
                return [
                    {
                        "name": "bedrock",
                        "env_key": None,
                        "credentials": [
                            CredentialField(
                                env_key="AWS_REGION_NAME",
                                label="Region",
                                litellm_param="aws_region_name",
                                secret=False,
                                required=True,
                            ),
                        ],
                    }
                ]

            def list_models(self, provider: str) -> list[dict[str, object]]:
                return [{"model_id": "bedrock-model", "slots": [], "context": 0}]

        monkeypatch.setattr("openreview_cli.gateway.wizard.ModelRegistry", FakeRegistry)

        class FakeSelect:
            def __init__(self, title: str, choices: list[str]) -> None:
                self._title = title

            def ask(self) -> str:
                return "bedrock"

        class FakeText:
            def __init__(self, prompt: str) -> None:
                self._prompt = prompt

            def ask(self) -> str:
                return ""  # empty required field

        monkeypatch.setattr("questionary.select", FakeSelect)
        monkeypatch.setattr("questionary.text", FakeText)

        gateway_setup()

        data = json.loads(auth_path.read_text())
        assert "bedrock" not in data

    def test_wizard_rejects_missing_vertex_adc_path(
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

        missing = tmp_path / "does-not-exist.json"

        class FakeRegistry:
            def __init__(self, *a: object, **k: object) -> None:
                pass

            def load(self) -> None:
                pass

            def list_providers(self) -> list[dict[str, object]]:
                return [
                    {
                        "name": "vertex",
                        "env_key": None,
                        "credentials": [
                            CredentialField(
                                env_key="GOOGLE_APPLICATION_CREDENTIALS",
                                label="ADC path",
                                litellm_param="google_credentials_path",
                                secret=False,
                                is_file_path=True,
                            ),
                        ],
                    }
                ]

            def list_models(self, provider: str) -> list[dict[str, str]]:
                return []

        monkeypatch.setattr("openreview_cli.gateway.wizard.ModelRegistry", FakeRegistry)

        class FakeSelect:
            def __init__(self, title: str, choices: list[str]) -> None:
                self._title = title

            def ask(self) -> str:
                return "vertex"

        class FakeText:
            def __init__(self, prompt: str) -> None:
                self._prompt = prompt

            def ask(self) -> str:
                return str(missing)

        monkeypatch.setattr("questionary.select", FakeSelect)
        monkeypatch.setattr("questionary.text", FakeText)

        gateway_setup()

        data = json.loads(auth_path.read_text())
        assert "vertex" not in data

    def test_wizard_rejects_empty_vertex_adc_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """T037 — FR-7: file-based credential must be non-empty (size > 0)."""
        monkeypatch.setattr(
            "openreview_cli.gateway.wizard.get_config_dir",
            lambda: tmp_path,
        )
        config_path = tmp_path / "config.yml"
        config_path.write_text("gateway:\n  models: {}\n")
        auth_path = tmp_path / "auth.json"
        auth_path.write_text("{}")

        empty = tmp_path / "empty.json"
        empty.write_text("")  # zero bytes

        class FakeRegistry:
            def __init__(self, *a: object, **k: object) -> None:
                pass

            def load(self) -> None:
                pass

            def list_providers(self) -> list[dict[str, object]]:
                return [
                    {
                        "name": "vertex",
                        "env_key": None,
                        "credentials": [
                            CredentialField(
                                env_key="GOOGLE_APPLICATION_CREDENTIALS",
                                label="ADC path",
                                litellm_param="google_credentials_path",
                                secret=False,
                                is_file_path=True,
                            ),
                        ],
                    }
                ]

            def list_models(self, provider: str) -> list[dict[str, str]]:
                return []

        monkeypatch.setattr("openreview_cli.gateway.wizard.ModelRegistry", FakeRegistry)

        class FakeSelect:
            def __init__(self, title: str, choices: list[str]) -> None:
                self._title = title

            def ask(self) -> str:
                return "vertex"

        class FakeText:
            def __init__(self, prompt: str) -> None:
                self._prompt = prompt

            def ask(self) -> str:
                return str(empty)

        monkeypatch.setattr("questionary.select", FakeSelect)
        monkeypatch.setattr("questionary.text", FakeText)

        gateway_setup()

        data = json.loads(auth_path.read_text())
        assert "vertex" not in data
