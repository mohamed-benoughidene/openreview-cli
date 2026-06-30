# Research: AI Gateway

**Date**: 2026-06-25 | **Spec**: [spec.md](../specs/004-ai-gateway/spec.md)

## 1. LiteLLM API (Context7 docs, v1.83.3-stable)

### Decision
Use LiteLLM as the provider abstraction layer for chat completion, embedding, and reranking.

### Rationale
- Single API for 100+ providers (OpenAI, Anthropic, Ollama, Google, Cohere, HuggingFace, OpenRouter, Custom)
- Built-in retry, timeout, fallback, and cost tracking
- Approved in constitution (not on forbidden list)
- Actively maintained, stable API

### Alternatives Considered
- **Custom provider classes**: Rejected — LiteLLM already handles this, YAGNI
- **Direct provider SDKs**: Rejected — would require custom abstraction layer, more code to maintain

### Key Findings

**Chat Completion** (`litellm.completion()`):
```python
from litellm import completion

response = completion(
    model="openai/gpt-4o",  # or "anthropic/claude-3-5-sonnet", "ollama/llama3.1"
    messages=[{"role": "user", "content": "..."}],
    temperature=0.7,
    max_tokens=4000,
    timeout=60,  # seconds
    api_key="...",  # optional, falls back to env var
    base_url="...",  # for Custom provider
)
# response.usage.prompt_tokens, response.usage.completion_tokens
# response.choices[0].message.content
```

**Embedding** (`litellm.embedding()`):
```python
from litellm import embedding

response = embedding(
    model="openai/text-embedding-3-small",  # or "ollama/nomic-embed-text"
    input=["text1", "text2"],
    dimensions=512,  # optional
    api_key="...",
)
# response.data[i].embedding (list of floats)
```

**Reranking** (`litellm.rerank()`):
```python
from litellm import rerank

response = rerank(
    model="cohere/rerank-3.5",  # or "vertex_ai/semantic-ranker"
    query="query text",
    documents=["doc1", "doc2"],
    top_n=5,
    api_key="...",
)
# response.results[i].index, response.results[i].relevance_score
```

**Retry & Timeout**:
```python
import litellm
litellm.num_retries = 3  # global default
litellm.request_timeout = 60  # seconds

# Per-call override
response = completion(model="...", messages=[...], num_retries=2, timeout=30)
```

**Cost Tracking**:
```python
from litellm import completion_cost

response = completion(model="gpt-4o", messages=[...])
cost = completion_cost(completion_response=response)  # USD
# response.usage.prompt_tokens, response.usage.completion_tokens
```

**Provider Model Format**: `<provider>/<model-id>`
- OpenAI: `gpt-4o`, `gpt-4o-mini` (no prefix needed)
- Anthropic: `anthropic/claude-3-5-sonnet-20241022`
- Ollama: `ollama/llama3.1`, `ollama/nomic-embed-text`
- Google: `gemini/gemini-1.5-pro` or `vertex_ai/gemini-1.5-pro`
- Cohere: `cohere/command-r-plus`, `cohere/rerank-3.5`
- OpenRouter: `openrouter/openai/gpt-4o`
- Custom: `custom/model-name` (requires `base_url` param)

---

## 2. Pydantic v2 Configuration (Context7 docs)

### Decision
Use Pydantic v2 `BaseSettings` for gateway config validation, with YAML loading via `YamlConfigSettingsSource`.

### Rationale
- Explicitly permitted in constitution
- Built-in validation, nested models, env var overrides
- YAML loading supported natively
- JSON schema generation for documentation

### Alternatives Considered
- **Plain dict validation**: Rejected — Pydantic provides better error messages and type safety
- **attrs + custom validation**: Rejected — Pydantic already in deps, YAGNI

### Key Findings

**BaseSettings with YAML**:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import YamlConfigSettingsSource

class GatewayConfig(BaseSettings):
    model_config = SettingsConfigDict(yaml_file="config.yml")

    reasoning: SlotConfig
    extraction: SlotConfig
    embedding: SlotConfig
    reranking: SlotConfig
    graph: SlotConfig

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

class SlotConfig(BaseModel):
    primary: str
    fallback: str | None = None
    params: ModelParams | None = None

class ModelParams(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 4000
    dimensions: int | None = None  # for embedding
```

**Validators**:
```python
from pydantic import field_validator

class SlotConfig(BaseModel):
    primary: str

    @field_validator("primary")
    @classmethod
    def validate_model_format(cls, v: str) -> str:
        if "/" not in v and not v.startswith("ollama/"):
            raise ValueError("model must be in format 'provider/model-id'")
        return v
```

**Constrained Types**:
```python
from pydantic import BaseModel, Field, SecretStr

class AuthConfig(BaseModel):
    api_key: SecretStr  # redacted in repr/logs
    base_url: str | None = None
```

---

## 3. Provider APIs (Tavily research, June 2026)

### Decision
Rely on LiteLLM for provider API abstraction. Document provider-specific details for reference.

### Rationale
- LiteLLM handles provider-specific API differences
- Reduces maintenance burden
- Provider updates handled by LiteLLM version bumps

### Key Findings

| Provider | Base URL | Auth | Chat Endpoint | Embed Endpoint | Rerank Endpoint |
|----------|----------|------|---------------|----------------|-----------------|
| **OpenAI** | `api.openai.com/v1` | `Authorization: Bearer` | `/chat/completions` | `/embeddings` | — |
| **Anthropic** | `api.anthropic.com` | `x-api-key` + `anthropic-version` | `/v1/messages` | — | — |
| **Ollama** | `localhost:11434` | None | `/api/chat` or `/v1/chat/completions` | `/api/embeddings` | — |
| **Google** | `generativelanguage.googleapis.com/v1beta` | `?key=` query param | `/models/{model}:generateContent` | `/models/{model}:embedContent` | — |
| **Cohere** | `api.cohere.com/v2` | `Authorization: Bearer` | `/chat` | `/embed` | `/rerank` |
| **OpenRouter** | `openrouter.ai/api/v1` | `Authorization: Bearer` | `/chat/completions` | — | — |

> **Note**: Reranking is optional and disabled by default. LightRAG graph retrieval replaces it as the primary precision filter. The LiteLLM reranking path remains available for users who prefer a cross-encoder.

**Current Models (June 2026)**:
- OpenAI: `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `text-embedding-3-small`
- Anthropic: `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5`
- Ollama: `llama3.1`, `qwen3:8b`, `nomic-embed-text`, `qwen3-reranker`
- Google: `gemini-2.5-flash`, `gemini-2.0-flash`, `text-embedding-004`
- Cohere: `command-a-plus-05-2026`, `embed-v4.0`, `rerank-4-pro`
- OpenRouter: 300+ models via single API

**API Key Validation**:
- OpenAI, OpenRouter, Anthropic, Custom: `GET /v1/models` (zero cost)
- Fallback: 1-token chat completion on cheapest model

---

## 4. Codebase Patterns (existing code analysis)

### Decision
Follow existing patterns: lazy imports, dataclass models, dict-based config, atomic file writes, Typer sub-apps.

### Rationale
- Consistency with existing code
- Proven patterns in this codebase
- Reduces cognitive load for contributors

### Key Findings

**Lazy Imports**:
```python
# Heavy deps imported inside function body
def route_request(self, slot: str, **kwargs):
    from litellm import completion
    ...
```

**Dataclass Models**:
```python
@dataclass(slots=True)
class CostRecord:
    session_id: str
    slot: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float

    def __post_init__(self) -> None:
        if self.input_tokens < 0:
            raise ValueError("input_tokens must be non-negative")
```

**Config as dict**:
```python
config = load_config(config_path)
primary_model = config["gateway"]["models"]["reasoning"]["primary"]
```

**Atomic File Writes**:
```python
import tempfile
import os

def atomic_write(path: Path, content: str) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp_path, path)
    except:
        os.unlink(tmp_path)
        raise
```

**Error Handling**:
```python
@dataclass
class GatewayError(Exception):
    exit_code: int
    slot: str | None
    message: str
    action: str

    def __str__(self) -> str:
        return self.message

def gateway_error(message: str, slot: str | None = None) -> NoReturn:
    print(f"Gateway error: {message}", file=sys.stderr)
    if slot:
        print(f"Slot: {slot}", file=sys.stderr)
    sys.exit(7)  # new exit code for gateway errors
```

**CLI Structure**:
```python
gateway_app = typer.Typer(name="gateway", help="AI model gateway management")
app.add_typer(gateway_app)

@gateway_app.command("status")
def gateway_status() -> None:
    from rich.console import Console
    from rich.table import Table
    ...
```

---

## 5. Resolved Unknowns

| Unknown | Resolution | Source |
|---------|------------|--------|
| How to abstract provider APIs? | LiteLLM `completion()`, `embedding()`, `rerank()` | Context7 |
| How to validate config? | Pydantic v2 `BaseSettings` + `YamlConfigSettingsSource` | Context7 |
| How to handle retries/fallback? | LiteLLM `num_retries`, custom fallback logic in `engine.py` | Context7 |
| How to track costs? | LiteLLM `completion_cost()`, SQLite storage | Context7 |
| How to validate API keys? | `GET /v1/models` or 1-token completion | Tavily |
| How to discover models? | LiteLLM model list, Ollama `/api/tags`, cached registry | Tavily |
| How to structure gateway package? | Follow `pii/` pattern: flat modules, dataclass models | Codebase |
| How to handle config files? | Atomic writes, chmod 600 for auth, YAML for config | Codebase |
| How to build interactive wizard? | Rich `Prompt`, `Confirm`, `Progress` | Codebase |
| How to enforce cost limits? | SQLite aggregation, pre-call check | Spec FR-010 |

All NEEDS CLARIFICATION items resolved.
