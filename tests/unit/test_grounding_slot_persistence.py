"""Test that grounding slot persists through set_config_value.

TDD: This test was written BEFORE T007 (grounding schema fix).
It verifies that `gateway.models.grounding` in config.yml survives
a round-trip through set_config_value and config reload.
"""

from pathlib import Path

from openreview_cli.config.loader import load_config, set_config_value


def test_grounding_slot_persists_after_set(tmp_path: Path) -> None:
    import yaml

    config_path = tmp_path / "config.yml"
    initial_config = {
        "version": 1,
        "gateway": {
            "models": {
                "reasoning": {"primary": "ollama/qwen3:8b"},
                "extraction": {"primary": "ollama/qwen3:4b"},
                "embedding": {"primary": "ollama/nomic-embed-text"},
                "reranking": {"primary": "ollama/qwen3-reranker-0.6b"},
                "graph": {"primary": "ollama/qwen3:8b"},
            }
        },
    }
    with open(config_path, "w") as f:
        yaml.dump(initial_config, f)

    set_config_value(
        config_path, "gateway.models.grounding.primary", "anthropic/claude-sonnet-latest"
    )

    reloaded = load_config(config_path)
    models = reloaded.get("gateway", {}).get("models", {})
    assert "grounding" in models, "grounding slot missing after set + reload"
    assert models["grounding"]["primary"] == "anthropic/claude-sonnet-latest"
