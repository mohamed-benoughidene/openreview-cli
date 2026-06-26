# Contract: Routing API

**Date**: 2026-06-25 | **Spec**: [spec.md](../../specs/004-ai-gateway/spec.md)

## Overview

The routing API is the primary interface between the review engine and the AI Gateway. Engine code calls a single routing function with a slot name and request parameters. The gateway handles provider selection, authentication, retry, fallback, and cost tracking.

## Core Function: `route_request()`

```python
def route_request(
    slot: str,
    messages: list[dict[str, str]] | None = None,
    input_text: str | list[str] | None = None,
    query: str | None = None,
    documents: list[str] | None = None,
    session_id: str | None = None,
    **kwargs: Any,
) -> GatewayResponse:
    """
    Route a request through the configured slot.
    
    Args:
        slot: Slot name (reasoning, extraction, embedding, reranking, graph)
        messages: Chat messages for chat completion (reasoning, extraction, graph)
        input_text: Text(s) to embed (embedding slot)
        query: Query text for reranking (reranking slot)
        documents: Documents to rerank (reranking slot)
        session_id: Review session UUID for cost tracking
        **kwargs: Additional provider-specific parameters
    
    Returns:
        GatewayResponse with response data, token usage, cost, and metadata
    
    Raises:
        GatewayError: If slot not configured, provider fails, or cost limit exceeded
    """
```

## Response Types

### GatewayResponse

```python
@dataclass(slots=True)
class GatewayResponse:
    """Response from a routed request."""
    
    # Response data (type depends on slot)
    content: str | list[float] | list[RerankResult]
    
    # Token usage
    input_tokens: int
    output_tokens: int
    
    # Cost tracking
    cost_usd: float
    
    # Metadata
    model: str
    provider: str
    slot: str
    fallback_used: bool
    latency_ms: int
    
    # Raw response (for debugging, never logged by default)
    raw_response: Any | None = None
```

### RerankResult

```python
@dataclass(slots=True)
class RerankResult:
    """Single reranking result."""
    index: int
    score: float
    document: str | None = None
```

## Request Types by Slot

### Chat Completion (reasoning, extraction, graph)

```python
response = route_request(
    slot="reasoning",
    messages=[
        {"role": "system", "content": "You are a contract analyst."},
        {"role": "user", "content": "Compare clause X vs playbook Y."}
    ],
    session_id="550e8400-e29b-41d4-a716-446655440000",
    temperature=0.1,  # override slot config
    max_tokens=4000,
)

# response.content: str (assistant message)
# response.input_tokens: int
# response.output_tokens: int
# response.cost_usd: float
```

### Embedding (embedding)

```python
response = route_request(
    slot="embedding",
    input_text=["chunk 1", "chunk 2", "chunk 3"],
    session_id="550e8400-e29b-41d4-a716-446655440000",
)

# response.content: list[float] (single text) or list[list[float]] (multiple texts)
# response.input_tokens: int
# response.cost_usd: float
```

### Reranking (reranking)

```python
response = route_request(
    slot="reranking",
    query="What is the termination clause?",
    documents=["clause 1 text", "clause 2 text", "clause 3 text"],
    session_id="550e8400-e29b-41d4-a716-446655440000",
    top_n=5,
)

# response.content: list[RerankResult]
# response.input_tokens: int
# response.cost_usd: float
```

## Error Handling

### GatewayError

```python
@dataclass
class GatewayError(Exception):
    """Gateway error with exit code and context."""
    exit_code: int
    slot: str | None
    message: str
    action: str
    
    def __str__(self) -> str:
        return self.message
```

### Error Scenarios

| Scenario | Exit Code | Message Example | Action |
|----------|-----------|-----------------|--------|
| Slot not configured | 7 | "Slot 'reasoning' is not configured" | "Run `openreview gateway setup` or `openreview gateway set reasoning <provider/model>`" |
| API key invalid | 7 | "Authentication failed for provider 'openai'" | "Check your API key with `openreview gateway test reasoning`" |
| Provider unreachable | 7 | "Provider 'ollama' is not reachable" | "Start Ollama with `ollama serve`" |
| Cost limit exceeded | 6 | "Per-review cost limit exceeded ($1.00)" | "Increase limit in config or reduce usage" |
| All retries failed | 7 | "All retries exhausted for slot 'extraction'" | "Check provider status or switch to fallback" |
| Invalid response format | 7 | "Unexpected response format from provider 'anthropic'" | "Try a different model or contact support" |

## Retry & Fallback Behavior

### Retry Logic

```python
# Per-slot configuration (from config.yml)
gateway:
  fallback:
    retries: 2  # number of retry attempts
    retry_delay: 1.0  # initial delay in seconds (exponential backoff)
    timeout: 60  # request timeout in seconds
    on_failure: "error"  # error | skip | warn
```

### Fallback Chain

```
1. Try primary model (with retries)
   ↓ (if all retries fail)
2. Try fallback model (if configured, with retries)
   ↓ (if fallback fails or not configured)
3. Apply on_failure behavior:
   - "error": raise GatewayError, halt review
   - "skip": log warning, continue without result
   - "warn": emit user-visible warning, continue with partial results
```

## Cost Tracking

### Pre-Call Check

```python
# Before each API call, check cost limits
if session_total_cost + estimated_cost > per_review_limit:
    raise GatewayError(
        exit_code=6,
        slot=slot,
        message=f"Per-review cost limit exceeded (${per_review_limit:.2f})",
        action="Increase limit in config or reduce usage"
    )

if daily_total_cost + estimated_cost > daily_limit:
    raise GatewayError(
        exit_code=6,
        slot=slot,
        message=f"Daily cost limit exceeded (${daily_limit:.2f})",
        action="Wait until tomorrow or increase limit in config"
    )
```

### Post-Call Recording

```python
# After each API call, record cost
cost_record = CostRecord(
    session_id=session_id,
    slot=slot,
    model=model,
    provider=provider,
    input_tokens=response.usage.prompt_tokens,
    output_tokens=response.usage.completion_tokens,
    cost_usd=completion_cost(completion_response=response),
    timestamp=time.time(),
    fallback_used=fallback_used,
    latency_ms=latency_ms
)
costs_db.insert(cost_record)
```

## Async Support

```python
async def aroute_request(
    slot: str,
    messages: list[dict[str, str]] | None = None,
    input_text: str | list[str] | None = None,
    query: str | None = None,
    documents: list[str] | None = None,
    session_id: str | None = None,
    **kwargs: Any,
) -> GatewayResponse:
    """Async version of route_request for concurrent API calls."""
```

## Implementation Notes

- All provider-specific imports are lazy (inside `route_request()`)
- LiteLLM handles provider abstraction (no custom provider classes)
- Cost estimation uses LiteLLM's `completion_cost()` function
- Token counts come from LiteLLM response object (`response.usage`)
- Session ID is optional (for cost tracking); if not provided, cost is not recorded
- Response bodies are never logged unless `--debug-unsafe` flag is used
- API keys are redacted in all log output
