import pytest
from pydantic import ValidationError

from openreview_cli.prompts.models import Prompt, PromptBinding, PromptVersion


class TestPromptVersion:
    def test_creates_with_minimal_fields(self) -> None:
        pv = PromptVersion(name="test", version=1, content="Hello")
        assert pv.name == "test"
        assert pv.version == 1
        assert pv.content == "Hello"
        assert pv.tags is None
        assert pv.description is None
        assert pv.test_results is None
        assert pv.optimization_meta is None

    def test_creates_with_all_fields(self) -> None:
        pv = PromptVersion(
            name="test",
            version=2,
            content="Hello world",
            tags=["tag1", "tag2"],
            description="A test prompt",
            test_results=[{"f1": 0.95, "precision": 0.94}],
            optimization_meta={"source_version": 1, "iterations": 5},
        )
        assert pv.tags == ["tag1", "tag2"]
        assert pv.description == "A test prompt"
        assert pv.test_results == [{"f1": 0.95, "precision": 0.94}]
        assert pv.optimization_meta == {"source_version": 1, "iterations": 5}

    def test_rejects_content_exceeding_16kb(self) -> None:
        with pytest.raises(ValidationError):
            PromptVersion(name="test", version=1, content="x" * 16385)

    def test_accepts_content_at_16kb_boundary(self) -> None:
        pv = PromptVersion(name="test", version=1, content="x" * 16384)
        assert len(pv.content) == 16384

    def test_accepts_content_under_16kb(self) -> None:
        pv = PromptVersion(name="test", version=1, content="x" * 100)
        assert len(pv.content) == 100

    def test_created_at_defaults_to_iso_format(self) -> None:
        pv = PromptVersion(name="test", version=1, content="Hello")
        assert "T" in pv.created_at
        assert pv.created_at.endswith("Z")

    def test_tags_defaults_to_none(self) -> None:
        pv = PromptVersion(name="test", version=1, content="Hello")
        assert pv.tags is None

    def test_description_defaults_to_none(self) -> None:
        pv = PromptVersion(name="test", version=1, content="Hello")
        assert pv.description is None

    def test_test_results_defaults_to_none(self) -> None:
        pv = PromptVersion(name="test", version=1, content="Hello")
        assert pv.test_results is None

    def test_optimization_meta_defaults_to_none(self) -> None:
        pv = PromptVersion(name="test", version=1, content="Hello")
        assert pv.optimization_meta is None

    def test_optimization_meta_with_nested_dict(self) -> None:
        pv = PromptVersion(
            name="test",
            version=1,
            content="Hello",
            optimization_meta={
                "source_version": 1,
                "iterations": 3,
                "per_iteration_metrics": [
                    {"iteration": 1, "f1": 0.8},
                    {"iteration": 2, "f1": 0.85},
                    {"iteration": 3, "f1": 0.9},
                ],
            },
        )
        assert pv.optimization_meta is not None
        assert len(pv.optimization_meta["per_iteration_metrics"]) == 3

    def test_serializes_to_dict(self) -> None:
        pv = PromptVersion(name="test", version=1, content="Hello")
        d = pv.model_dump()
        assert d["name"] == "test"
        assert d["version"] == 1
        assert d["content"] == "Hello"


class TestPromptBinding:
    def test_creates_with_required_fields(self) -> None:
        pb = PromptBinding(slot="extraction", prompt_name="test", prompt_version=1)
        assert pb.slot == "extraction"
        assert pb.prompt_name == "test"
        assert pb.prompt_version == 1

    def test_created_at_defaults_to_iso_format(self) -> None:
        pb = PromptBinding(slot="extraction", prompt_name="test", prompt_version=1)
        assert "T" in pb.created_at
        assert pb.created_at.endswith("Z")


class TestPrompt:
    def test_creates_with_required_fields(self) -> None:
        p = Prompt(name="test", latest_version=1)
        assert p.name == "test"
        assert p.latest_version == 1

    def test_created_at_defaults_to_iso_format(self) -> None:
        p = Prompt(name="test", latest_version=1)
        assert "T" in p.created_at
        assert p.created_at.endswith("Z")
