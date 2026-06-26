# Phase 4 Report: AI Gateway

## Part 1 — Status

We have completed the implementation of Phase 4 (AI Gateway) to enable unified, privacy-first, local-first routing for LLM and specialty model operations. This includes retry/fallback resilience, database cost tracking/limits, full CLI configuration management (Phase 7), YAML configuration import capabilities (Phase 8), and three-tier logging & privacy protection (Phase 9).

### What Changed
- **Gateway Package**: Created a new sub-package under `src/openreview_cli/gateway/` containing `errors.py`, `models.py`, `providers.py`, `engine.py`, `costs.py`, `wizard.py`, `registry.py`, `importer.py`, and `logging.py`.
- **LiteLLM Translation Layer**: Integrated `litellm` to act as a unified translation layer, routing models to cloud providers (OpenAI, Anthropic, Cohere) and local providers (Ollama, custom endpoints) without changing application-level code.
- **CLI Wiring**: Added a `gateway` subcommand group to the Typer app in `src/openreview_cli/app.py` supporting `setup`, `status`, `providers`, `models`, `set`, `test`, `refresh`, `costs`, `install-models`, and `import`, with support for `--debug-unsafe` to permit response body logging.
- **Unified Slot Configuration**: Configured 5 specific routing slots in `config.yml` (reasoning, extraction, embedding, reranking, graph), validating that all slots are configured at startup.
- **Local-First Capabilities**: Handled automatic fallback to local Ollama/custom models when internet connection is lost, and integrated Ollama model lookup and connection detection.
- **Credentials Storage**: Handled secure local storing of keys in `auth.json` with strict `chmod 600` permissions.
- **Automatic Fallback and Retry (Phase 5)**: Implemented slot-level request retry mechanism with exponential backoff and timeout handling. Added secondary fallback model transition when primary attempts are exhausted. Added `fallback_used` monitoring flag to trace model routing outcomes.
- **Cost Tracking and Limits (Phase 6)**: Implemented persistent tracking of API token usage and latency in SQLite (`gateway.db`). Configured and enforced strict pre-call cost limits (per-review and daily).
- **CLI Management (Phase 7)**: Implemented diagnostic subcommands to check slot reachability (`test`), show current status (`status`), list compatible models (`models`), and update parameter bindings (`set`).
- **YAML Configuration Import (Phase 8)**: Implemented validation and parsing of standalone YAML configurations, importing routing setups and securely writing environment-mapped API keys to local credentials storage.
- **Three-Tier Logging and API Key Redaction (Phase 9)**: Implemented redacting logging handlers to block API key leakage on stdout/stderr and file logs. Setup file-based DEBUG logs and CLI-based INFO logs. Prevented logging response bodies unless explicitly configured via `--debug-unsafe`.

### What Was Verified
- **Unit Tests**:
  - `tests/unit/test_gateway_models.py`: Verified constraints, validation rules, and serialization for configuration and response dataclasses.
  - `tests/unit/test_gateway_engine.py`: Verified slot existence checks, parameter merging, and model validation.
  - `tests/unit/test_gateway_wizard.py`: Verified validation of API keys, timeout handling, and configuration grouping logic.
  - `tests/unit/test_gateway_costs.py`: Verified SQLite `CostStore` operations including session lifecycle, cost logging, totals updating, and daily cost calculation.
  - `tests/unit/test_gateway_registry.py`: Verified cache loading, remote model registry refresh, and built-in minimal fallback registry loading.
  - `tests/unit/test_gateway_importer.py`: Verified YAML format parsing, missing-slot validation, disallowed inline secrets detection, and environment key extraction.
  - `tests/unit/test_gateway_logging.py`: Verified API key extraction, formatter-based redaction, stdout/stderr stream filtering, and three-tier level routing.
- **Integration Tests**:
  - `tests/integration/test_gateway_routing.py`: Verified end-to-end routing of Chat Completion, Embedding, and Reranking requests, offline local mode, cost record insertion, and cost limits enforcement.
  - `tests/integration/test_gateway_cli.py`: Verified CLI non-interactive flag inputs, interactive wizard invocation, subcommands (`status`, `providers`, `models`, `set`, `test`, `refresh`, `costs`, `install-models`), and YAML configurations importing.
  - `tests/integration/test_gateway_fallback.py`: Verified automatic switching to fallback models upon API timeout or network failure, exponential backoff retries, and failure modes handling (`error`, `skip`, `warn`).
  - `tests/integration/test_gateway_benchmark.py`: Verified gateway routing latency overhead vs direct model calls is under 50ms (measured at ~25ms).
  - `tests/integration/test_gateway_privacy.py`: Verified 100% network isolation, asserting that all outbound API traffic goes exclusively to the user-configured endpoints.
- **Overall Quality**: Ran the full test suite (253 tests passed), strict type checking via `mypy` (0 errors), and formatting/checks via `ruff` (all checks passed).

### What's Next
- **Phase 5 (Overall Project)**: Implement chunking and embedding pipelines for contract ingestion.

---

## Part 2 — Concepts: AI Gateway Routing Slots

### 1. Pain
Different stages of contract review require completely different kinds of AI models. For example, summarizing complex legal issues (reasoning) requires a high-intelligence model like GPT-4o, whereas splitting sentences (extraction) can be handled by a cheaper model, and finding relevant clauses (reranking/embedding) requires specialty search models.

If we hardcode a single provider like OpenAI throughout the code, it becomes very expensive and locks us into a single cloud vendor. On the other hand, writing separate custom code for OpenAI, Anthropic, Cohere, and local Ollama APIs everywhere creates massive duplication, is highly error-prone, and makes it impossible to switch models without rewrites.

### 2. Recipe
We solve this by defining 5 centralized "slots" in our configuration. We write our application code to request a slot (e.g. "reasoning") rather than a specific model. The `GatewayEngine` then translates this request to the configured provider using a unified wrapper:

```python
import litellm

# Router translates slot requests to the configured provider/model format
def call_reasoning_slot(model_string: str, messages: list):
    # If model_string is "openai/gpt-4o", litellm translates it to OpenAI
    # If model_string is "ollama/llama3", litellm translates it to local Ollama
    response = litellm.completion(
        model=model_string,
        messages=messages
    )
    return response.choices[0].message.content
```
- `litellm.completion` = the translation post-office that wraps multiple APIs.
- `model` = the destination address (e.g. `openai/gpt-4o`).
- `messages` = the letter content (chat history).

### 3. In Practice
When the system needs to run a task:
1. It requests the specific slot (e.g., `route_request(slot="reasoning", messages=...)`).
2. The `GatewayEngine` reads the configuration to see what model is configured for that slot.
3. It fetches the credentials securely from `auth.json` (such as `OPENAI_API_KEY`).
4. It calls the unified `litellm` method, which routes the request to the correct cloud endpoint or local Ollama port.
5. If the request fails, it automatically retries with the slot's configured fallback model.

---

## Part 3 — Concepts: Cost Tracking and Limits

### 1. Pain
Calling commercial cloud LLM APIs is metered per token and can rapidly become expensive when analyzing long documents or running iterative reasoning loops. Without centralized visibility and strict boundaries, a rogue script or large document run could accidentally rack up hundreds of dollars in API charges before anyone notices.

### 2. Recipe
We solve this by checking the total accrued cost of the current session and the day *before* making any API call. We estimate the cost of the upcoming request based on the model's pricing and the prompt token length. If the estimated cost exceeds either the per-review limit or the daily limit, we abort the execution immediately and inform the user. When a request completes successfully, we record its exact token usage and cost in a SQLite database table.

```python
# Check session limit before calling LiteLLM
current_spend = db.get_session_cost(session_id)
estimated_call_cost = estimate_cost(model, prompt)

if current_spend + estimated_call_cost > per_review_limit:
    raise CostLimitError("Per-review cost limit reached.")
```
- `db.get_session_cost` = Queries SQLite for the running total cost of the active session.
- `estimate_cost` = Estimates prompt cost based on character length and known token pricing.
- `per_review_limit` = The configurable limit (e.g., $1.00 per contract review session).

### 3. In Practice
Every time `route_request` is invoked:
1. The gateway queries `gateway.db` to get the current session total cost and the day's total cost.
2. It estimates the prompt cost for the configured model.
3. If the spend exceeds the limits, it throws a `GatewayError` with exit code 6.
4. If allowed, it makes the API call, captures the actual response tokens/cost, and saves a `CostRecord` in the database.

---

## Part 4 — Concepts: YAML Import and Key Redirection

### 1. Pain
When deploying the application in CI/CD pipelines or sharing configurations among multiple developers, checking API keys directly into git repositories or typing them into an interactive console is extremely dangerous. Hardcoded API keys get leaked easily, and writing custom env var checking routines for each slot's provider is redundant and brittle.

### 2. Recipe
We solve this by allowing users to import a YAML file that refers to environment variable names instead of inline secrets. The YAML config loader maps slot definitions and references to environment variables, resolves their values during the import process, validates them, and writes the keys safely to a local `auth.json` file.

```yaml
gateway:
  slots:
    reasoning:
      model: anthropic/claude-3-5-sonnet
      fallback: openai/gpt-4o-mini
  api_key_env:
    anthropic: ANTHROPIC_API_KEY
    openai: OPENAI_API_KEY
```
- `api_key_env` = The redirection map telling the importer where to fetch credentials.
- `anthropic/openai` = The provider name keys whose credentials will be written securely to the encrypted/chmod 600 credentials file.

### 3. In Practice
During a YAML import run:
1. The developer runs `openreview gateway import config.yml`.
2. The importer parses the YAML file and validates that all five slots are configured.
3. It checks the `api_key_env` mapping, verifies that the named environment variables exist on the user's shell, and grabs their values.
4. It saves the gateway configurations to `config.yml` and writes the resolved API keys to `auth.json` with strict file permissions.

---

## Part 5 — Concepts: Three-Tier Logging and API Key Redaction

### 1. Pain
When troubleshooting failures in production, developers need detailed traces of model calls, latency times, and token details. However, logging raw application streams can easily leak sensitive API keys or private user contract details into log files, consoles, or monitoring systems. Once a secret is written to plain text log files, the security perimeter is breached.

### 2. Recipe
We solve this by setting up a custom, redacting log formatter and intercepting standard system output streams. We automatically scan all logged output and active consoles against a set of dynamically resolved sensitive API keys, replacing matching key substrings with `[REDACTED]`. Additionally, we segregate logs into three tiers: console `INFO` level, detailed local `DEBUG` file level, and raw response body logging which remains completely disabled unless unsafe debugging is explicitly unlocked by the developer.

```python
class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for key in get_sensitive_strings():
            formatted = formatted.replace(key, "[REDACTED]")
        return formatted
```
- `get_sensitive_strings()` = Fetches active keys from env vars and local storage.
- `formatted.replace(...)` = Intercepts and redacts any matching credential substring.

### 3. In Practice
During a CLI execution run:
1. The app starts and triggers `setup_gateway_logging()`.
2. It initializes a console `INFO` stream handler and a local `DEBUG` file handler (`gateway.log`).
3. Standard stdout and stderr are wrapped in a `RedactingStream` to intercept raw output.
4. If a call crashes or prints a traceback containing a key, the streams and logger catch it, redact the credentials, and log `[REDACTED]` instead.
5. If the developer runs with `--debug-unsafe`, raw LLM response payloads are logged; otherwise, payloads are omitted.

---

## Part 6 — Walkthrough

Here is the plain-English mapping of the files added or modified in this phase:

- **`src/openreview_cli/gateway/__init__.py`**
  Exposes public API functions like `route_request` and `GatewayEngine` to clean up package imports.
- **`src/openreview_cli/gateway/errors.py`**
  Defines gateway-specific exceptions, including connection failures, missing credentials, and invalid slot requests.
- **`src/openreview_cli/gateway/models.py`**
  Defines the validation schemas for model parameters (temperature, max tokens) and response dataclasses (tokens used, latency, pricing).
- **`src/openreview_cli/gateway/providers.py`**
  Implements the local/remote model registry lookup, fetching available Ollama models, and resolving base URLs.
- **`src/openreview_cli/gateway/engine.py`**
  The central routing engine. Translates and executes completion, embedding, and reranking requests, and implements the automatic failover retry logic.
- **`src/openreview_cli/gateway/costs.py`**
  Implements the SQLite database connection, table initialization, and CRUD/aggregation operations for tracking sessions and logging costs.
- **`src/openreview_cli/gateway/wizard.py`**
  Implements the interactive setup wizard using `rich.prompt`, verifying API keys on-the-fly and grouping slots to make setup fast.
- **`src/openreview_cli/gateway/registry.py`**
  Implements the `ModelRegistry` manager which handles fetching online model indexes, loading fallback lists, and caching available models locally.
- **`src/openreview_cli/gateway/importer.py`**
  Handles validation of configuration YAML structures, checks required slot parameters, checks for inline credentials, and resolves redirecting env vars.
- **`src/openreview_cli/gateway/logging.py`**
  Implements dynamically resolved sensitive string retrieval, custom redacting formatting/streams, and three-tier file and console logging orchestration.
- **`tests/unit/test_gateway_models.py`**
  Validates that inputs for model configuration and response schemas are strictly checked.
- **`tests/unit/test_gateway_engine.py`**
  Checks slot existence enforcement and parameter inheritance/overrides.
- **`tests/unit/test_gateway_costs.py`**
  Unit tests verifying `CostStore` behavior, session lifecycle, token aggregations, and daily cost tracking.
- **`tests/unit/test_gateway_wizard.py`**
  Verifies API key check timeouts and slot grouping options.
- **`tests/unit/test_gateway_registry.py`**
  Verifies registry loading fallback strategies on missing or corrupted cache structures.
- **`tests/unit/test_gateway_importer.py`**
  Verifies that YAML validator correctly flags incomplete configs and handles key redirections.
- **`tests/unit/test_gateway_logging.py`**
  Unit tests verifying formatting redirection, stream redaction, and correct level and formatter attachment.
- **`tests/integration/test_gateway_routing.py`**
  Tests routing of completion, embedding, and reranking requests, as well as offline local mode.
- **`tests/integration/test_gateway_cli.py`**
  Tests CLI execution of both non-interactive configuration, interactive wizard triggers, and subcommands including `import`.
- **`tests/integration/test_gateway_fallback.py`**
  Verifies that network or provider errors automatically fall back to secondary models.
- **`tests/integration/test_gateway_benchmark.py`**
  Integration benchmark test confirming that gateway overhead remains under the 50ms threshold.
- **`tests/integration/test_gateway_privacy.py`**
  Integration test verifying that HTTP request targets are strictly locked to user-specified base URLs.
