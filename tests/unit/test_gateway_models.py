from openreview_cli.gateway.models import CostRecord, ModelEntry, ProviderInfo


class TestModelEntry:
    def test_creates_with_minimal_fields(self) -> None:
        m = ModelEntry(slots=["reasoning"])
        assert m.slots == ["reasoning"]
        assert m.context is None
        assert m.dimensions is None
        assert m.recommended is False
        assert m.status is None
        assert m.note is None

    def test_creates_with_all_fields(self) -> None:
        m = ModelEntry(
            slots=["reasoning"],
            context=4096,
            dimensions=768,
            ram="4GB",
            recommended=True,
            status="stable",
            note="Recommended for chat",
        )
        assert m.context == 4096
        assert m.recommended is True


class TestProviderInfo:
    def test_creates_with_minimal_fields(self) -> None:
        p = ProviderInfo(name="ollama")
        assert p.name == "ollama"
        assert p.env_key is None
        assert p.auth_required is True
        assert p.models == {}

    def test_env_key_optional(self) -> None:
        p = ProviderInfo(name="custom", env_key="CUSTOM_API_KEY", auth_required=False)
        assert p.env_key == "CUSTOM_API_KEY"
        assert p.auth_required is False


class TestCostRecord:
    def test_creates_with_all_fields(self) -> None:
        r = CostRecord(
            id="rec-1",
            session_id="sess-1",
            slot="reasoning",
            model="openai/gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            cost_cents=2,
            created_at="2026-01-01T00:00:00",
        )
        assert r.id == "rec-1"
        assert r.cost_cents == 2
        assert r.prompt_tokens == 100

    def test_slot_optional(self) -> None:
        r = CostRecord(
            id="rec-2",
            model="openai/gpt-4",
            provider="openai",
            prompt_tokens=0,
            completion_tokens=0,
            cost_cents=0,
            created_at="2026-01-01T00:00:00",
        )
        assert r.slot is None
