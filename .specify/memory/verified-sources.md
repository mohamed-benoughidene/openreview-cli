# Verified Sources: Feature 032-tui-spec

**Generated**: 2026-07-12
**Method**: context7 docs + PyPI version checks

---

# Verified Sources: Feature 033-ai-gateway-v2

**Generated**: 2026-07-18
**Method**: direct read of `uv.lock` (locked versions), NOT memory/assumption. pyproject.toml declares minimum constraints; locked versions below are what is actually installed and what any streaming/CLI-flag work must target.

---

ITEM: typer
SOURCE: uv.lock (locked)
VERSION: 0.26.7 (pyproject constraint: >=0.26.7)
KEY FACTS:
- CLI framework (Typer app, gateway subcommand group)
- Prior plan.md incorrectly stated 0.27.0 — corrected 2026-07-18 from uv.lock
STATUS: CONFIRMED (from uv.lock)

---

ITEM: litellm
SOURCE: uv.lock (locked)
VERSION: 1.90.1 (pyproject constraint: >=1.90.1)
KEY FACTS:
- `completion_cost` for cost tracking (FR-6)
- `stream=True` is the streaming path for FR-8 — do NOT build a separate raw-httpx transport
- Routes auth per provider via env vars; FR-7 format correction applied in router.py call path
- Prior plan.md incorrectly stated 1.92.0 — corrected 2026-07-18 from uv.lock
STATUS: CONFIRMED (from uv.lock)

---

ITEM: httpx
SOURCE: uv.lock (locked)
VERSION: 0.28.1 (pyproject constraint: >=0.28.1)
KEY FACTS:
- Used for non-streaming requests and any direct client needs
- FR-8 streaming uses litellm `stream=True` + `asyncio.wait_for` timeouts (15s first / 45s idle), NOT `httpx.Timeout` on a separate client
STATUS: CONFIRMED (from uv.lock)

---

ITEM: platformdirs
SOURCE: uv.lock (locked)
VERSION: 4.10.0 (pyproject constraint: >=4.10.0)
KEY FACTS:
- `user_config_dir("openreview")` for registry + custom provider config storage (FR-3/FR-9)
STATUS: CONFIRMED (from uv.lock)

---

ITEM: questionary
SOURCE: uv.lock (locked)
VERSION: 2.1.1 (pyproject constraint: >=2.1.1)
KEY FACTS:
- Interactive wizard prompts (retained for non-TUI subcommands; FR-11/FR-12 add non-interactive paths)
STATUS: CONFIRMED (from uv.lock)

---

ITEM: textual
SOURCE: https://textual.textualize.io + PyPI
VERSION: 8.2.8 (current stable, confirmed 2026-07-12)
KEY FACTS:
- `app.run_test()` returns async context manager yielding `Pilot` for headless testing
- `Button.Pressed` event with `event.button.id` for handling button clicks
- `set_interval(interval, callback, *, name=None, repeat=0, pause=False)` on message pump
- `action_show_tab(tab: str)` pattern — set `TabbedContent.active` attribute
- `Input(password=True)` masks typed characters (built-in reactive attribute)
STATUS: CONFIRMED

---

ITEM: textual — TabbedContent / TabPane
SOURCE: https://textual.textualize.io/widgets/tabbed_content
VERSION: 8.2.8
KEY FACTS:
- `TabbedContent` with `TabPane("Label", id="id")` children
- `initial="tab_id"` sets default active tab
- Programmatic switch: `self.query_one(TabbedContent).active = "tab_id"`
- Nested TabbedContent supported
STATUS: CONFIRMED

---

ITEM: textual — DirectoryTree
SOURCE: https://textual.textualize.io/widgets/directory_tree
VERSION: 8.2.8
KEY FACTS:
- Subclass `DirectoryTree` and override `filter_paths(paths)` to hide files
- No built-in `show_hidden` attribute — filter via `filter_paths` method
- Spec's Ctrl-H toggle requires reactive state + `filter_paths` override
STATUS: CONFIRMED (pattern exists; no direct `show_hidden` attribute — needs custom implementation)

---

ITEM: textual — Collapsible
SOURCE: https://textual.textualize.io/widgets/collapsible
VERSION: 8.2.8
KEY FACTS:
- `Collapsible` widget with `collapsed` (bool) and `title` (str) reactive attributes
- `Toggled` event with `.collapsible` reference
- Used for collapsing/expanding content sections
STATUS: CONFIRMED

---

ITEM: textual — notify()
SOURCE: https://textual.textualize.io/api/app
VERSION: 8.2.8
KEY FACTS:
- `notify(message, *, title="", severity="information", timeout=None, markup=True)`
- Severity levels: `information`, `warning`, `error`
- Thread-safe, shows Toast notification
- Supports Rich console markup when `markup=True`
STATUS: CONFIRMED

---

ITEM: textual — action_quit_or_warn
SOURCE: context7 / Textual source
VERSION: 8.2.8
KEY FACTS:
- NOT a standard Textual built-in action
- Must be implemented as custom `action_quit_or_warn()` method on the App subclass
- Pattern: confirm quit if dirty state, else call `self.exit()`
STATUS: UNVERIFIED (custom action, not a framework primitive — needs implementation)

---

ITEM: pytest-asyncio
SOURCE: https://pytest-asyncio.readthedocs.io/en/stable + PyPI
VERSION: 1.4.0 (current stable)
KEY FACTS:
- `asyncio_mode = "auto"` in `[tool.pytest.ini_options]` auto-marks all async test functions
- Auto mode recommended for asyncio-only projects
- `strict` mode (default) requires explicit `@pytest.mark.asyncio` decorator
- Compatible with pytest 8.x and Python 3.12
STATUS: CONFIRMED

---

ITEM: pydantic
SOURCE: https://docs.pydantic.dev + PyPI
VERSION: 2.13.4 (current stable)
KEY FACTS:
- No built-in `from_config` classmethod — pattern built via `@model_validator(mode='before')` or `model_validate()`
- `ConfigDict(from_attributes=True)` for ORM/object validation
- `@classmethod` validators receive raw dict in `mode='before'`
- `model_validate(data)` creates instance from dict
STATUS: CONFIRMED (no direct `from_config`; pattern is standard Pydantic v2 practice)

---

ITEM: rich
SOURCE: https://rich.readthedocs.io + PyPI
VERSION: 15.0.0 (current stable), installed: 13.7.1
KEY FACTS:
- Rich is Textual's rendering backend — same author (Textualize)
- Rich 13.x installed in workspace; 15.0.0 available on PyPI
- No breaking changes for Textual 8.2.8 between 13.x and 15.x
- Textual pins its own Rich version requirement
STATUS: CONFIRMED

---

ITEM: typer
SOURCE: https://typer.tiangolo.com + PyPI
VERSION: 0.26.8 (current stable)
KEY FACTS:
- Existing dependency, no version pinned in plan
- Compatible with Python 3.12
- Used for CLI subcommands (unchanged by TUI feature)
STATUS: CONFIRMED

---

ITEM: questionary
SOURCE: https://github.com/tmbo/questionary + PyPI
VERSION: 2.1.1 (current stable)
KEY FACTS:
- Existing dependency, retained for non-TUI subcommands
- Uses prompt_toolkit under the hood
- TUI replaces questionary's interactive prompts within the TUI session
STATUS: CONFIRMED

---

ITEM: asyncio_mode=auto configuration
SOURCE: https://pytest-asyncio.readthedocs.io/en/stable/concepts.html
VERSION: N/A (config pattern)
KEY FACTS:
- Set in `pyproject.toml` under `[tool.pytest.ini_options]`
- `asyncio_mode = "auto"` — no per-test `@pytest.mark.asyncio` needed
- Default is `strict` if not specified
- Existing project uses this pattern (per plan.md)
STATUS: CONFIRMED

---

## Summary Counts

| Metric | Count |
|--------|-------|
| **TOTAL ITEMS** | 12 |
| **CONFIRMED** | 11 |
| **UNVERIFIED** | 1 |
| **FETCH FAILED** | 0 |

## Version Drift Notes

| Dep | Plan/Spec says | PyPI current | Drift? |
|-----|---------------|-------------|--------|
| textual | >=8.2.8 | 8.2.8 | None |
| pydantic | (no version in plan) | 2.13.4 | N/A |
| rich | (existing, no version pinned) | 15.0.0 (installed 13.7.1) | Minor — Textual handles its own Rich pin |
| typer | (existing, no version pinned) | 0.26.8 | N/A |
| questionary | (existing, no version pinned) | 2.1.1 | N/A |
| pytest-asyncio | (no version in plan) | 1.4.0 | N/A |

**No version drift concerns.** All claimed versions match current stable releases.

---

# Verified Sources: Feature 033-ai-gateway-v2

**Generated**: 2026-07-17
**Method**: web_search + web_fetch of official docs / PyPI
**Spec**: /home/mohamed/lab/openreview/specs/033-ai-gateway-v2/spec.md

Note on spec clarity: the spec contains NO explicit "NEEDS CLARIFICATION" marker.
All open questions were resolved in the spec's Clarifications section (Session 2026-07-17),
which is recorded as ground-truth decisions below rather than open items.

---

ITEM: httpx
SOURCE: https://www.python-httpx.org/ (api, advanced/timeouts, quickstart, async) + PyPI
VERSION: 0.28.1 (current stable; 1.0.dev3 pre-release exists, not stable)
KEY FACTS:
- `httpx.stream(method, url, ...)` / `AsyncClient.stream(...)` yield response incrementally without loading body into memory
- Streaming iterators: `iter_bytes()`, `iter_text()`, `iter_lines()`, `iter_raw()`, `aiter_*()` async equivalents
- Timeout model: `httpx.Timeout(read=..., connect=..., write=..., pool=...)`; `read` = max wait for a chunk; default 5s inactivity
- Dual independent timeouts (header/first-byte vs inter-chunk) achievable via `httpx.Timeout(..., connect=15, read=45)` — connect covers first-byte, read covers inter-chunk
- `stream=True` + `client.send(req)` "manual mode" requires explicit `response.aclose()`
- Proxy/SSE: `httpx-sse` (separate package) provides `connect_sse`/`iter_sse`; not required if parsing `text/event-stream` manually
STATUS: CONFIRMED

---

ITEM: litellm
SOURCE: https://docs.litellm.ai/docs/completion/token_usage + PyPI
VERSION: 1.92.0 (current stable PyPI 2026-07-12); pyproject pins >=1.90.1
KEY FACTS:
- `completion_cost(completion_response=...)` returns float USD cost; accepts litellm ModelResponse or prompt+completion strings
- `response_cost` also exposed on logging object (`kwargs["response_cost"]`) on success
- `cost_per_token`, `token_counter`, `model_cost` are companion helpers; cost map pulled from api.litellm.ai live list
- Raises exception if model not in cost map (register via custom pricing or PR)
- Companion `CostTracker.log_call()` in this repo already calls `completion_cost(response)` (see gateway/cost.py)
STATUS: CONFIRMED

---

ITEM: platformdirs
SOURCE: https://platformdirs.readthedocs.io/en/stable/ + PyPI
VERSION: 4.10.0 (current stable)
KEY FACTS:
- `platformdirs.user_config_dir(appname, appauthor=None, version=None, roaming=False, ensure_exists=False, use_site_for_root=False) -> str`
- Respects XDG (`XDG_CONFIG_HOME` on Linux), `~/Library/Application Support` on macOS, `%APPDATA%` on Windows
- Returns config dir tied to user; per-user, writable, isolated
- `user_config_path(appname)` path form also available; spec uses `user_config_dir("openreview")`
STATUS: CONFIRMED

---

ITEM: pydantic
SOURCE: https://docs.pydantic.dev + PyPI
VERSION: 2.13.4 (current stable)
KEY FACTS:
- Data validation via Python type hints; `model_validate(data)` from dict
- Pydantic V2 stable; V1 shipped alongside as `pydantic.v1` for incremental upgrade
- Compliant with JSON Schema 2020-12 (OpenAPI 3.1)
- Used in repo for ProviderModel / SlotConfig dataclasses in gateway/models.py
STATUS: CONFIRMED

---

ITEM: questionary
SOURCE: https://questionary.readthedocs.io/ + PyPI
VERSION: 2.1.1 (current stable)
KEY FACTS:
- Prompt types: text, password, path, confirm, select, rawselect, checkbox, autocomplete, press_any_key_to_continue
- `questionary.form(...).ask()` for multi-question wizard; `.ask_async()` for async
- Used by gateway wizard (interactive `gateway setup`); FR-12 keeps wizard but non-interactive path also required
- mypy override `ignore_missing_imports = true` already set in pyproject for questionary
STATUS: CONFIRMED

---

ITEM: typer
SOURCE: https://typer.tiangolo.com/ + PyPI
VERSION: 0.27.0 (current stable); pyproject pins >=0.26.7
KEY FACTS:
- `typer.Typer()` app; `@app.command()` subcommands; `typer.Argument` / `typer.Option`
- Since 0.26.0 Typer vendored Click internally (no separate click install); `click` still in pyproject deps
- `--json` flag on commands is a plain `typer.Option` returning structured data
- Used for `gateway providers`, `gateway models`, `gateway provider add`, `gateway set`, `gateway test` (FR-10/FR-11)
STATUS: CONFIRMED

---

ITEM: Anthropic — empty content-part 400 rejection
SOURCE: https://github.com/anthropics/claude-code/issues/62396, /50010, /23270; portkey.ai error library
VERSION: API behavior (stable, observed 2026-02..2026-05)
KEY FACTS:
- Anthropic rejects `{"type":"text","text":""}` content blocks with HTTP 400 `invalid_request_error`
- Error message forms: "messages: text content blocks must be non-empty" / "must contain non-whitespace text"
- Also rejects empty `content` arrays on non-final messages: "all messages must have non-empty content except for the optional final assistant message"
- FR-7 fix: strip empty content parts before send; common workaround pads with single space `" "` (langchain pattern)
- Confirmed provider-specific quirk — gateway must correct pre-emptively for pre-listed Anthropic
STATUS: CONFIRMED

---

ITEM: OpenAI-compatible API convention
SOURCE: https://platform.openai.com/docs/api-reference (Chat Completions) + provider docs below
VERSION: N/A (wire-format convention)
KEY FACTS:
- Standard `POST /v1/chat/completions`, Bearer auth, `messages` array, SSE streaming via `stream:true`
- `model` IDs are provider-specific even when request shape is compatible ("OpenAI-compatible" != same model IDs)
- Streaming errors: non-stream => standalone error JSON; mid-stream => SSE event with error field
- Response path `choices[0].message.content`; `usage` block present
STATUS: CONFIRMED

---

ITEM: Ollama — OpenAI-compatible local endpoint
SOURCE: https://docs.ollama.com/api/openai-compatibility + PyPI
VERSION: local server (default http://localhost:11434)
KEY FACTS:
- OpenAI-compatible at `http://localhost:11434/v1` (chat/completions, embeddings, models)
- `api_key='ollama'` required-but-ignored (any non-empty string since v0.1.32+); no real auth on localhost
- Used for privacy "local" classification; `classify_provider()` + URL-hostname detection path (FR-1)
- `localhost` / `127.0.0.1` hostnames are the local-detection signal; must not be coerced to "cloud"
STATUS: CONFIRMED

---

ITEM: Deepseek — OpenAI-compatible
SOURCE: https://api-docs.deepseek.com/ + DeepSeek V4 docs
VERSION: models `deepseek-v4-flash`, `deepseek-v4-pro` (legacy `deepseek-chat`/`deepseek-reasoner` retire 2026-07-24)
KEY FACTS:
- Base URL `https://api.deepseek.com` (or `/v1`); Bearer auth via `DEEPSEEK_API_KEY`
- OpenAI SDK drop-in: swap base_url + api_key; `stream:true` supported
- V4 enables thinking by default; gate via `extra_body={"thinking":{...}}` / `reasoning_effort`
- FR-2: pre-listed registry entry needs only API key + base URL + capability metadata
STATUS: CONFIRMED

---

ITEM: Qwen (Alibaba Cloud Model Studio / DashScope) — OpenAI-compatible
SOURCE: https://www.alibabacloud.com/help/en/model-studio + https://docs.qwencloud.com
VERSION: models e.g. `qwen-plus`, `qwen3.7-plus` (model-specific)
KEY FACTS:
- Base URL region-specific; OpenAI-compatible `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` (Singapore) or `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- Bearer auth via `DASHSCOPE_API_KEY`; `stream:true` + `stream_options={"include_usage":true}` for usage in last chunk
- `enable_thinking` / `thinking_budget` are Qwen-specific params passed via extra_body
- FR-2: Qwen (cloud) pre-listed entry needs env-var credential + base URL + capability flags
STATUS: CONFIRMED

---

ITEM: MiniMax — OpenAI-compatible (and Anthropic-compatible)
SOURCE: https://platform.minimax.io/docs/api-reference/text-chat-openai + tools docs
VERSION: model `MiniMax-M3` (current flagship)
KEY FACTS:
- OpenAI-compatible base URL `https://api.minimax.io/v1`; Anthropic-compatible `https://api.minimax.io/anthropic`
- Bearer auth via `MINIMAX_API_KEY` (key form `sk-cp-...` from Token Plan)
- Supports text/image/video content parts; `thinking` adaptive; `stream_options.include_usage`
- FR-2: MiniMax pre-listed entry needs env-var credential + base URL + capability metadata
STATUS: CONFIRMED

---

ITEM: OpenRouter — OpenAI-compatible aggregator
SOURCE: https://openrouter.ai/docs/api/reference + blog tutorials
VERSION: aggregator fronting 300+ models (model slug `provider/model`)
KEY FACTS:
- Base URL `https://openrouter.ai/api/v1`; Bearer auth via `OPENROUTER_API_KEY` (keys start `sk-or-`)
- Normalizes upstream errors into stable `error_type` vocabulary (authentication, rate_limit_exceeded, provider_unavailable, etc.) across Chat/Responses/Anthropic skins
- HTTP codes: 401 auth, 402 payment, 403 forbidden/guardrail, 429 rate limit, 502/503 provider down
- `Retry-After` header on 429/503 for backoff; mid-stream errors arrive as SSE events once first token sent
- FR-2/FR-5: distinct typed error classification must name the producing provider
STATUS: CONFIRMED

---

## Summary Counts (033 only)

| Metric | Count |
|--------|-------|
| **TOTAL ITEMS** | 13 |
| **CONFIRMED** | 13 |
| **UNVERIFIED** | 0 |
| **FETCH FAILED** | 0 |

## Version Drift Notes (033)

| Dep | pyproject pins | PyPI current (2026-07-17) | Drift? |
|-----|---------------|---------------------------|--------|
| httpx | >=0.28.1 | 0.28.1 | None |
| litellm | >=1.90.1 | 1.92.0 (1.94.0.dev3 pre-release) | Minor — pin allows newer; cost.py API stable |
| platformdirs | >=4.10.0 | 4.10.0 | None |
| pydantic | >=2.13.4 | 2.13.4 | None |
| questionary | >=2.1.1 | 2.1.1 | None |
| typer | >=0.26.7 | 0.27.0 | Minor — pin allows newer |

**No blocking version drift.** All pinned minimums are at-or-below current stable.
Spec's Clarifications (2026-07-17) resolve all design questions — no NEEDS CLARIFICATION items remain.
