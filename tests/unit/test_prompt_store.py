import uuid
from pathlib import Path

import pytest

from openreview_cli.prompts.models import Prompt
from openreview_cli.prompts.store import PromptStore


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / f"test_{uuid.uuid4().hex}.db"


@pytest.fixture
def store(db_path: Path) -> PromptStore:
    s = PromptStore(db_path)
    s.init()
    return s


class TestPromptStore:
    def test_create_version_1(self, store: PromptStore) -> None:
        pv = store.create("test", "Hello")
        assert pv.name == "test"
        assert pv.version == 1
        assert pv.content == "Hello"

    def test_create_duplicate_name_raises(self, store: PromptStore) -> None:
        store.create("test", "Hello")
        with pytest.raises(ValueError, match="already exists"):
            store.create("test", "World")

    def test_create_content_exceeds_16kb_raises(self, store: PromptStore) -> None:
        with pytest.raises(ValueError, match="16384"):
            store.create("test", "x" * 16385)

    def test_update_auto_increments(self, store: PromptStore) -> None:
        store.create("test", "v1")
        pv2 = store.update("test", "v2")
        assert pv2.version == 2
        assert pv2.content == "v2"

    def test_update_nonexistent_raises(self, store: PromptStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.update("nonexistent", "content")

    def test_get_specific_version(self, store: PromptStore) -> None:
        store.create("test", "v1")
        store.update("test", "v2")
        pv1 = store.get("test", 1)
        assert pv1.content == "v1"
        pv2 = store.get("test", 2)
        assert pv2.content == "v2"

    def test_get_nonexistent_version_raises(self, store: PromptStore) -> None:
        store.create("test", "v1")
        with pytest.raises(ValueError, match="not found"):
            store.get("test", 99)

    def test_get_latest(self, store: PromptStore) -> None:
        store.create("test", "v1")
        store.update("test", "v2")
        latest = store.get_latest("test")
        assert latest.version == 2
        assert latest.content == "v2"

    def test_get_latest_single_version(self, store: PromptStore) -> None:
        store.create("test", "v1")
        latest = store.get_latest("test")
        assert latest.version == 1

    def test_get_latest_nonexistent_raises(self, store: PromptStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.get_latest("nonexistent")

    def test_list_empty(self, store: PromptStore) -> None:
        result = store.list()
        assert result == []

    def test_list_single_page(self, store: PromptStore) -> None:
        for i in range(3):
            store.create(f"prompt-{i}", f"Content {i}")
        result = store.list()
        assert len(result) == 3
        assert all(isinstance(p, Prompt) for p in result)

    def test_list_pagination(self, store: PromptStore) -> None:
        for i in range(5):
            store.create(f"prompt-{i}", f"Content {i}")
        page1 = store.list(page=1, per_page=2)
        assert len(page1) == 2
        page2 = store.list(page=2, per_page=2)
        assert len(page2) == 2

    def test_delete_removes_all_versions(self, store: PromptStore) -> None:
        store.create("test", "v1")
        store.update("test", "v2")
        store.delete("test")
        with pytest.raises(ValueError, match="not found"):
            store.get_latest("test")
        assert store.list() == []

    def test_delete_nonexistent_raises(self, store: PromptStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.delete("nonexistent")

    def test_create_with_tags_and_description(self, store: PromptStore) -> None:
        pv = store.create("test", "Hello", tags=["tag1"], description="A test")
        assert pv.tags == ["tag1"]
        assert pv.description == "A test"

    def test_update_preserves_old_versions(self, store: PromptStore) -> None:
        store.create("test", "v1")
        store.update("test", "v2")
        v1 = store.get("test", 1)
        v2 = store.get("test", 2)
        assert v1.content == "v1"
        assert v2.content == "v2"

    def test_multiple_prompts_isolated(self, store: PromptStore) -> None:
        store.create("alpha", "Alpha content")
        store.create("beta", "Beta content")
        assert store.get_latest("alpha").content == "Alpha content"
        assert store.get_latest("beta").content == "Beta content"


class TestPromptBindings:
    def test_bind_valid_slot(self, store: PromptStore) -> None:
        store.create("test", "Hello")
        pb = store.bind("extraction", "test", 1)
        assert pb.slot == "extraction"
        assert pb.prompt_name == "test"
        assert pb.prompt_version == 1

    def test_bind_invalid_slot(self, store: PromptStore) -> None:
        store.create("test", "Hello")
        with pytest.raises(ValueError, match="Invalid slot"):
            store.bind("invalid_slot", "test", 1)

    def test_bind_nonexistent_version(self, store: PromptStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.bind("extraction", "nonexistent", 1)

    def test_unbind_existing(self, store: PromptStore) -> None:
        store.create("test", "Hello")
        store.bind("extraction", "test", 1)
        store.unbind("extraction")
        assert store.bindings() == []

    def test_unbind_no_binding(self, store: PromptStore) -> None:
        with pytest.raises(ValueError, match="No binding"):
            store.unbind("extraction")

    def test_bindings_empty(self, store: PromptStore) -> None:
        assert store.bindings() == []

    def test_bindings_with_entries(self, store: PromptStore) -> None:
        store.create("a", "A")
        store.create("b", "B")
        store.bind("extraction", "a", 1)
        store.bind("reasoning", "b", 1)
        bs = store.bindings()
        assert len(bs) == 2
        slots = {b.slot for b in bs}
        assert slots == {"extraction", "reasoning"}

    def test_resolve_with_binding(self, store: PromptStore) -> None:
        store.create("test", "Hello world")
        store.bind("extraction", "test", 1)
        content = store.resolve("extraction")
        assert content == "Hello world"

    def test_resolve_without_binding_falls_back_to_default(self, store: PromptStore) -> None:
        content = store.resolve("extraction")
        assert content == ""

    def test_resolve_after_unbind_returns_empty(self, store: PromptStore) -> None:
        store.create("test", "Hello")
        store.bind("extraction", "test", 1)
        store.unbind("extraction")
        content = store.resolve("extraction")
        assert content == ""

    def test_bind_replaces_existing_binding(self, store: PromptStore) -> None:
        store.create("a", "Version A")
        store.create("b", "Version B")
        store.bind("extraction", "a", 1)
        store.bind("extraction", "b", 1)
        assert store.resolve("extraction") == "Version B"


class TestExportImport:
    def test_export_single_prompt(self, store: PromptStore) -> None:
        store.create("test", "Hello")
        data = store.export("test")
        assert isinstance(data, dict)
        assert data["name"] == "test"
        assert len(data["versions"]) == 1
        assert data["versions"][0]["content"] == "Hello"

    def test_export_all(self, store: PromptStore) -> None:
        store.create("alpha", "Alpha")
        store.create("beta", "Beta")
        data = store.export()
        assert isinstance(data, list)
        assert len(data) == 2
        names = {d["name"] for d in data}
        assert names == {"alpha", "beta"}

    def test_export_unknown_raises(self, store: PromptStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.export("nonexistent")

    def test_import_preserves_versions(self, store: PromptStore) -> None:
        data = {
            "name": "imported",
            "versions": [
                {"version": 1, "content": "v1", "created_at": "2026-01-01T00:00:00Z"},
                {"version": 3, "content": "v3", "created_at": "2026-01-03T00:00:00Z"},
            ],
        }
        store.import_prompt(data)
        assert store.get("imported", 1).content == "v1"
        assert store.get("imported", 3).content == "v3"
        assert store.get_latest("imported").version == 3

    def test_import_no_overwrite(self, store: PromptStore) -> None:
        store.create("test", "Existing")
        data = {
            "name": "test",
            "versions": [
                {"version": 1, "content": "New", "created_at": "2026-01-01T00:00:00Z"},
            ],
        }
        with pytest.raises(ValueError, match="already exists"):
            store.import_prompt(data)

    def test_import_invalid_format(self, store: PromptStore) -> None:
        with pytest.raises(ValueError, match="must contain"):
            store.import_prompt({"name": "test"})

    def test_export_import_round_trip(self, store: PromptStore) -> None:
        store.create("roundtrip", "Original", tags=["tag1"], description="desc")
        store.update("roundtrip", "Updated")
        exported = store.export("roundtrip")
        assert isinstance(exported, dict)
        store.delete("roundtrip")
        store.import_prompt(exported)
        assert store.get("roundtrip", 1).content == "Original"
        assert store.get("roundtrip", 2).content == "Updated"
        assert store.get("roundtrip", 1).tags == ["tag1"]
