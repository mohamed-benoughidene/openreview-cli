from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from openreview_cli.app import app
from openreview_cli.prompts.io import parse_prompts_yaml
from openreview_cli.prompts.store import PromptStore


def _valid_item(name: str = "alpha") -> dict[str, Any]:
    return {
        "name": name,
        "versions": [{"version": 1, "content": "hello", "created_at": "2026-01-01T00:00:00Z"}],
    }


class TestParsePromptsYamlAccepts:
    def test_single_mapping_is_wrapped_in_a_list(self) -> None:
        result = parse_prompts_yaml(yaml.dump(_valid_item()))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "alpha"

    def test_list_of_mappings(self) -> None:
        text = yaml.dump([_valid_item("a"), _valid_item("b")])
        result = parse_prompts_yaml(text)
        assert [item["name"] for item in result] == ["a", "b"]

    def test_version_with_created_at_is_accepted(self) -> None:
        result = parse_prompts_yaml(yaml.dump(_valid_item()))
        assert result[0]["versions"][0]["created_at"] == "2026-01-01T00:00:00Z"

    def test_multi_byte_content_is_accepted(self) -> None:
        item = _valid_item()
        item["versions"][0]["content"] = "€" * 100
        result = parse_prompts_yaml(yaml.dump(item))
        assert result[0]["versions"][0]["content"] == "€" * 100

    def test_large_body_is_accepted_because_size_is_the_store_rule(self) -> None:
        item = _valid_item()
        item["versions"][0]["content"] = "x" * 40000
        result = parse_prompts_yaml(yaml.dump(item))
        assert len(result[0]["versions"][0]["content"]) == 40000

    def test_real_export_round_trips(self, tmp_path: Path) -> None:
        store = PromptStore(tmp_path / "prompts.db")
        store.init()
        store.create("roundtrip", "Original", tags=["tag1"], description="desc")
        store.update("roundtrip", "Updated")
        exported = store.export("roundtrip")
        result = parse_prompts_yaml(yaml.dump(exported))
        assert result == [exported]


class TestParsePromptsYamlRejects:
    def test_scalar_document(self) -> None:
        with pytest.raises(ValueError, match="must be a mapping or a list"):
            parse_prompts_yaml("just a scalar")

    def test_empty_document(self) -> None:
        with pytest.raises(ValueError, match="must be a mapping or a list"):
            parse_prompts_yaml("")

    def test_item_without_name(self) -> None:
        text = yaml.dump([{"versions": [{"version": 1, "content": "x", "created_at": "z"}]}])
        with pytest.raises(ValueError, match="missing 'name'"):
            parse_prompts_yaml(text)

    def test_versions_absent(self) -> None:
        with pytest.raises(ValueError, match="missing 'versions'"):
            parse_prompts_yaml(yaml.dump({"name": "alpha"}))

    def test_versions_null(self) -> None:
        with pytest.raises(ValueError, match="null 'versions'"):
            parse_prompts_yaml(yaml.dump({"name": "alpha", "versions": None}))

    def test_versions_empty(self) -> None:
        with pytest.raises(ValueError, match="empty 'versions'"):
            parse_prompts_yaml(yaml.dump({"name": "alpha", "versions": []}))

    def test_version_not_a_mapping(self) -> None:
        with pytest.raises(ValueError, match="is not a mapping"):
            parse_prompts_yaml(yaml.dump({"name": "alpha", "versions": ["nope"]}))

    def test_version_without_content(self) -> None:
        text = yaml.dump({"name": "alpha", "versions": [{"version": 1, "created_at": "z"}]})
        with pytest.raises(ValueError, match="missing 'content'"):
            parse_prompts_yaml(text)

    def test_version_without_created_at(self) -> None:
        text = yaml.dump({"name": "alpha", "versions": [{"version": 1, "content": "x"}]})
        with pytest.raises(ValueError, match="missing 'created_at'"):
            parse_prompts_yaml(text)

    def test_duplicate_version_within_item(self) -> None:
        text = yaml.dump(
            {
                "name": "alpha",
                "versions": [
                    {"version": 1, "content": "x", "created_at": "z"},
                    {"version": 1, "content": "y", "created_at": "z"},
                ],
            }
        )
        with pytest.raises(ValueError, match="duplicate version"):
            parse_prompts_yaml(text)


# --- Defect 1: `prompt import` error paths exit 2, never a traceback ---------
#
# Regression: ``prompt_import`` caught only ``ValueError`` around
# ``file_path.read_text()``, so ``IsADirectoryError`` and ``PermissionError``
# (both ``OSError``, neither a ``ValueError``) escaped as a traceback with
# exit 1.  The fix widens the catch to ``(ValueError, OSError)``.


class TestPromptImportCliErrorPaths:
    """A path that cannot be read or decoded must exit 2 with a message."""

    @pytest.fixture(autouse=True)
    def _xdg(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    @staticmethod
    def _invoke(path: Path) -> Any:
        return CliRunner().invoke(app, ["prompt", "import", str(path)])

    def test_directory_exits_two_without_traceback(self, tmp_path: Path) -> None:
        directory = tmp_path / "a-directory"
        directory.mkdir()

        result = self._invoke(directory)

        assert result.exit_code == 2, result.output
        # A clean ``typer.Exit`` is a ``SystemExit``; a leaked error is not.
        assert isinstance(result.exception, SystemExit)
        assert "Traceback" not in result.output

    def test_non_utf8_file_exits_two_without_traceback(self, tmp_path: Path) -> None:
        target = tmp_path / "not-utf8.yaml"
        target.write_bytes(b"\xff\xfe raw bytes")

        result = self._invoke(target)

        assert result.exit_code == 2, result.output
        assert isinstance(result.exception, SystemExit)
        assert "Traceback" not in result.output
