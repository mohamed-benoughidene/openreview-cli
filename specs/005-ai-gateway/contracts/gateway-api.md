# Gateway API Contract

**Date**: 2026-07-01
**Feature**: specs/005-ai-gateway

## Public Python API

### `Gateway` class

```python
from openreview_cli.gateway import Gateway, GatewayError

class Gateway:
    def __init__(
        self,
        config_path: Path | None = None,
        auth_path: Path | None = None,
    ) -> None:
        """Load config and auth. Defaults to platformdirs paths."""

    def chat(
        self,
        slot: str,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Send a chat completion request to the model assigned to this slot.
        Returns the model's response text.
        Raises: SlotNotConfiguredError, AllProvidersFailedError
        """

    def embed(
        self,
        slot: str,
        texts: list[str],
        *,
        session_id: str | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.
        Returns list of float vectors.
        Raises: SlotNotConfiguredError, AllProvidersFailedError
        """

    def rerank(
        self,
        slot: str,
        query: str,
        documents: list[str],
        top_n: int = 5,
        *,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Rerank documents by relevance to query.
        Returns list of {"index": int, "relevance_score": float}.
        Raises: SlotNotConfiguredError, AllProvidersFailedError
        """

    def get_cost(self, session_id: str) -> dict[str, Any]:
        """Get token usage and estimated cost for a session."""

    def health_check(self) -> dict[str, Any]:
        """Check which configured providers are reachable."""

    def list_providers(self) -> list[dict[str, Any]]:
        """List all supported providers with status."""

    def list_models(self, provider: str) -> list[dict[str, Any]]:
        """List available models for a provider."""

    def set_model(self, slot: str, model: str) -> None:
        """Assign a model to a slot (writes to config.yml)."""
```

### Error Hierarchy

```python
from openreview_cli.gateway import (
    GatewayError,
    ProviderError,
    SlotNotConfiguredError,
    AllProvidersFailedError,
)
```

### Valid Slot Names

```python
VALID_SLOTS = {"reasoning", "extraction", "embedding", "reranking", "graph"}
```

## CLI Commands

All commands are under the `openreview gateway` subcommand group.

| Command | Arguments | Description |
|---------|-----------|-------------|
| `gateway setup` | — | Interactive setup wizard |
| `gateway status` | — | Show configured slots and provider reachability |
| `gateway providers` | — | List all supported providers |
| `gateway models` | `<provider>` | List models for a provider |
| `gateway set` | `<slot> <model>` | Assign a model to a slot |
| `gateway refresh` | — | Refresh model registry from remote |
| `gateway test` | `<slot>` | Send a test request to a slot's model |
| `gateway costs` | `--today` / `--session <id>` | Show cost summary |

## Configuration Contract

### config.yml (gateway section)

```yaml
gateway:
  models:
    reasoning:
      primary: "openai/gpt-4o"
      fallback: "ollama/qwen3:8b"
      params:
        temperature: 0.1
        max_tokens: 4000
      extra_params:          # NEW — provider-specific pass-through
        seed: 42
    extraction:
      primary: "anthropic/claude-haiku-latest"
      fallback: "ollama/qwen3:4b"
      params:
        temperature: 0.0
        max_tokens: 2000
    embedding:
      primary: "ollama/nomic-embed-text"
    reranking:
      primary: "ollama/qwen3-reranker-0.6b"
    graph:
      primary: "openai/gpt-4o-mini"
      fallback: "ollama/qwen3:8b"
      params:
        temperature: 0.0
        max_tokens: 4000
  fallback:
    retries: 2
    retry_delay: 1.0
    timeout: 60
    on_failure: "error"
  cost_limits:
    per_review_cents: 100
    daily_cents: 1000
  model_registry_refresh_days: 7
```

### auth.json

```json
{
  "openai": "sk-proj-...",
  "anthropic": "sk-ant-...",
  "google": "AIza..."
}
```

Environment variables override auth.json values.
