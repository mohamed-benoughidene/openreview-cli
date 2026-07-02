import uuid
from pathlib import Path

import pytest

from openreview_cli.prompts.defaults import load_defaults
from openreview_cli.prompts.store import PromptStore


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / f"test_{uuid.uuid4().hex}.db"


@pytest.fixture
def store(db_path: Path) -> PromptStore:
    s = PromptStore(db_path)
    s.init()
    return s


class TestDefaultPrompts:
    def test_load_defaults_into_empty_store(self, store: PromptStore) -> None:
        load_defaults(store)
        prompts = store.list()
        assert len(prompts) > 0

    def test_defaults_have_expected_slots(self, store: PromptStore) -> None:
        load_defaults(store)
        names = {p.name for p in store.list()}
        expected_slots = {"extraction", "reasoning", "embedding", "reranking", "graph"}
        assert expected_slots.issubset(names)

    def test_defaults_only_load_once(self, store: PromptStore) -> None:
        load_defaults(store)
        count1 = len(store.list())
        load_defaults(store)
        count2 = len(store.list())
        assert count1 == count2

    def test_defaults_dont_overwrite_existing(self, store: PromptStore) -> None:
        store.create("extraction", "Custom extraction prompt")
        load_defaults(store)
        assert store.get_latest("extraction").content == "Custom extraction prompt"

    def test_import_cannot_overwrite_defaults(self, store: PromptStore) -> None:
        load_defaults(store)
        data = {
            "name": "extraction",
            "versions": [
                {"version": 1, "content": "Override attempt", "created_at": "2026-01-01T00:00:00Z"},
            ],
        }
        with pytest.raises(ValueError, match="already exists"):
            store.import_prompt(data)
