import json
from dataclasses import dataclass

import httpx

from openreview_cli.config.paths import get_cache_dir


@dataclass(slots=True)
class ModelRegistryEntry:
    provider: str
    model_id: str
    display_name: str
    slot_compatibility: list[str]
    context_window: int | None = None
    ram_required_mb: int | None = None
    pricing_input_usd_per_mtok: float | None = None
    pricing_output_usd_per_mtok: float | None = None
    is_local: bool = False


BUILTIN_MODELS = [
    # openai
    ModelRegistryEntry(
        provider="openai",
        model_id="gpt-4o",
        display_name="GPT-4o",
        slot_compatibility=["reasoning", "extraction", "graph"],
        context_window=128000,
        pricing_input_usd_per_mtok=5.0,
        pricing_output_usd_per_mtok=15.0,
        is_local=False,
    ),
    ModelRegistryEntry(
        provider="openai",
        model_id="gpt-4o-mini",
        display_name="GPT-4o-mini",
        slot_compatibility=["extraction", "graph"],
        context_window=128000,
        pricing_input_usd_per_mtok=0.15,
        pricing_output_usd_per_mtok=0.60,
        is_local=False,
    ),
    ModelRegistryEntry(
        provider="openai",
        model_id="text-embedding-3-small",
        display_name="Text Embedding 3 Small",
        slot_compatibility=["embedding"],
        context_window=8192,
        pricing_input_usd_per_mtok=0.02,
        pricing_output_usd_per_mtok=0.02,
        is_local=False,
    ),
    # anthropic
    ModelRegistryEntry(
        provider="anthropic",
        model_id="claude-3-5-sonnet-latest",
        display_name="Claude 3.5 Sonnet",
        slot_compatibility=["reasoning", "extraction", "graph"],
        context_window=200000,
        pricing_input_usd_per_mtok=3.0,
        pricing_output_usd_per_mtok=15.0,
        is_local=False,
    ),
    ModelRegistryEntry(
        provider="anthropic",
        model_id="claude-3-5-haiku-latest",
        display_name="Claude 3.5 Haiku",
        slot_compatibility=["extraction", "graph"],
        context_window=200000,
        pricing_input_usd_per_mtok=0.80,
        pricing_output_usd_per_mtok=4.0,
        is_local=False,
    ),
    # cohere
    ModelRegistryEntry(
        provider="cohere",
        model_id="command-r-plus",
        display_name="Command R+",
        slot_compatibility=["reasoning", "extraction", "graph"],
        context_window=128000,
        pricing_input_usd_per_mtok=2.50,
        pricing_output_usd_per_mtok=10.0,
        is_local=False,
    ),
    ModelRegistryEntry(
        provider="cohere",
        model_id="embed-english-v3.0",
        display_name="Embed English v3.0",
        slot_compatibility=["embedding"],
        context_window=512,
        pricing_input_usd_per_mtok=0.10,
        pricing_output_usd_per_mtok=0.10,
        is_local=False,
    ),
    ModelRegistryEntry(
        provider="cohere",
        model_id="rerank-english-v3.0",
        display_name="Rerank English v3.0",
        slot_compatibility=["reranking"],
        context_window=512,
        pricing_input_usd_per_mtok=2.00,
        pricing_output_usd_per_mtok=2.00,
        is_local=False,
    ),
    # google
    ModelRegistryEntry(
        provider="google",
        model_id="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        slot_compatibility=["reasoning", "extraction", "graph"],
        context_window=2000000,
        pricing_input_usd_per_mtok=1.25,
        pricing_output_usd_per_mtok=5.00,
        is_local=False,
    ),
    ModelRegistryEntry(
        provider="google",
        model_id="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        slot_compatibility=["extraction", "graph"],
        context_window=1000000,
        pricing_input_usd_per_mtok=0.075,
        pricing_output_usd_per_mtok=0.30,
        is_local=False,
    ),
    # ollama
    ModelRegistryEntry(
        provider="ollama",
        model_id="qwen3:8b",
        display_name="Qwen 3 (8B)",
        slot_compatibility=["reasoning", "extraction", "graph"],
        context_window=32768,
        ram_required_mb=8192,
        is_local=True,
    ),
    ModelRegistryEntry(
        provider="ollama",
        model_id="qwen3:4b",
        display_name="Qwen 3 (4B)",
        slot_compatibility=["extraction", "graph"],
        context_window=32768,
        ram_required_mb=4096,
        is_local=True,
    ),
    ModelRegistryEntry(
        provider="ollama",
        model_id="nomic-embed-text",
        display_name="Nomic Embed Text",
        slot_compatibility=["embedding"],
        context_window=8192,
        ram_required_mb=1024,
        is_local=True,
    ),
    ModelRegistryEntry(
        provider="ollama",
        model_id="qwen3-reranker-0.6b",
        display_name="Qwen 3 Reranker (0.6B)",
        slot_compatibility=["reranking"],
        context_window=8192,
        ram_required_mb=1024,
        is_local=True,
    ),
    # openrouter
    ModelRegistryEntry(
        provider="openrouter",
        model_id="openai/gpt-4o-mini",
        display_name="GPT-4o-mini (via OpenRouter)",
        slot_compatibility=["reasoning", "extraction", "graph"],
        context_window=128000,
        pricing_input_usd_per_mtok=0.15,
        pricing_output_usd_per_mtok=0.60,
        is_local=False,
    ),
    ModelRegistryEntry(
        provider="openrouter",
        model_id="openai/text-embedding-3-small",
        display_name="Text Embedding 3 Small (via OpenRouter)",
        slot_compatibility=["embedding"],
        context_window=8192,
        pricing_input_usd_per_mtok=0.02,
        pricing_output_usd_per_mtok=0.02,
        is_local=False,
    ),
    ModelRegistryEntry(
        provider="openrouter",
        model_id="anthropic/claude-3.5-sonnet",
        display_name="Claude 3.5 Sonnet (via OpenRouter)",
        slot_compatibility=["reasoning", "extraction", "graph"],
        context_window=200000,
        pricing_input_usd_per_mtok=3.0,
        pricing_output_usd_per_mtok=15.0,
        is_local=False,
    ),
    # huggingface
    ModelRegistryEntry(
        provider="huggingface",
        model_id="HuggingFaceH4/zephyr-7b-beta",
        display_name="Zephyr 7B Beta",
        slot_compatibility=["reasoning", "extraction", "graph"],
        context_window=4096,
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        is_local=False,
    ),
    ModelRegistryEntry(
        provider="huggingface",
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        display_name="All MiniLM L6 v2",
        slot_compatibility=["embedding"],
        context_window=256,
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        is_local=False,
    ),
]


class ModelRegistry:
    """Manages local model cache and fetches updates from remote."""

    def __init__(self) -> None:
        self.cache_dir = get_cache_dir()
        self.cache_file = self.cache_dir / "model_registry.json"

    def get_all_models(self) -> list[ModelRegistryEntry]:
        if not self.cache_file.exists():
            return list(BUILTIN_MODELS)
        try:
            content = self.cache_file.read_text()
            data = json.loads(content)
            if not isinstance(data, list):
                raise ValueError("Expected list of models")
            models = []
            for item in data:
                models.append(
                    ModelRegistryEntry(
                        provider=item["provider"],
                        model_id=item["model_id"],
                        display_name=item["display_name"],
                        slot_compatibility=item["slot_compatibility"],
                        context_window=item.get("context_window"),
                        ram_required_mb=item.get("ram_required_mb"),
                        pricing_input_usd_per_mtok=item.get("pricing_input_usd_per_mtok"),
                        pricing_output_usd_per_mtok=item.get("pricing_output_usd_per_mtok"),
                        is_local=item.get("is_local", False),
                    )
                )
            return models
        except Exception:
            return list(BUILTIN_MODELS)

    def save_to_cache(self, models: list[ModelRegistryEntry]) -> None:
        data = []
        for m in models:
            data.append(
                {
                    "provider": m.provider,
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "slot_compatibility": m.slot_compatibility,
                    "context_window": m.context_window,
                    "ram_required_mb": m.ram_required_mb,
                    "pricing_input_usd_per_mtok": m.pricing_input_usd_per_mtok,
                    "pricing_output_usd_per_mtok": m.pricing_output_usd_per_mtok,
                    "is_local": m.is_local,
                }
            )
        from openreview_cli.gateway.utils import atomic_write

        atomic_write(self.cache_file, json.dumps(data, indent=2))

    def refresh(self, remote_url: str) -> None:
        response = httpx.get(remote_url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("Registry JSON must be a list of models")

        new_models = []
        for item in data:
            new_models.append(
                ModelRegistryEntry(
                    provider=item["provider"],
                    model_id=item["model_id"],
                    display_name=item["display_name"],
                    slot_compatibility=item["slot_compatibility"],
                    context_window=item.get("context_window"),
                    ram_required_mb=item.get("ram_required_mb"),
                    pricing_input_usd_per_mtok=item.get("pricing_input_usd_per_mtok"),
                    pricing_output_usd_per_mtok=item.get("pricing_output_usd_per_mtok"),
                    is_local=item.get("is_local", False),
                )
            )

        self.save_to_cache(new_models)
