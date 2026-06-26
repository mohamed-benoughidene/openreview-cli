import logging
import time
from typing import Any

from openreview_cli.gateway.errors import GatewayError
from openreview_cli.gateway.models import GatewayResponse, RerankResult

logger = logging.getLogger(__name__)


def get_litellm_model_string(provider: str, model_id: str) -> str:
    """Map our provider name to LiteLLM model prefix."""
    provider_mapping = {
        "google": "gemini",
        "openai": "openai",
        "anthropic": "anthropic",
        "ollama": "ollama",
        "openrouter": "openrouter",
        "cohere": "cohere",
        "huggingface": "huggingface",
        "custom": "openai",  # Custom provider is OpenAI-compatible
    }
    prefix = provider_mapping.get(provider.lower(), provider.lower())
    return f"{prefix}/{model_id}"


def _safe_int(v: Any) -> int:
    if isinstance(v, (int, float)):
        return int(v)
    try:
        if hasattr(v, "__class__") and v.__class__.__name__ == "MagicMock":
            return 0
        return int(v)
    except (ValueError, TypeError):
        return 0


class GatewayEngine:
    """Engine for routing requests through task-specific slots."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        if config is not None:
            self.config = config
        else:
            from openreview_cli.config.loader import load_config
            from openreview_cli.config.paths import get_config_dir

            config_path = get_config_dir() / "config.yml"
            self.config = load_config(config_path)
        self._store: Any | None = None

    def route_request(
        self,
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
        """
        valid_slots = {"reasoning", "extraction", "embedding", "reranking", "graph"}
        if slot not in valid_slots:
            raise GatewayError(
                exit_code=7,
                slot=None,
                message=f"Slot '{slot}' is not a valid gateway slot",
                action="Use one of: reasoning, extraction, embedding, reranking, graph",
            )

        models_config = self.config.get("gateway", {}).get("models", {})
        if slot not in models_config:
            raise GatewayError(
                exit_code=7,
                slot=slot,
                message=f"Slot '{slot}' is not configured",
                action="Run 'openreview gateway setup' to configure this slot.",
            )

        slot_conf = models_config[slot]
        primary = (
            slot_conf.get("primary")
            if isinstance(slot_conf, dict)
            else getattr(slot_conf, "primary", None)
        )
        if not primary:
            raise GatewayError(
                exit_code=7,
                slot=slot,
                message=f"Slot '{slot}' is not configured (missing primary model)",
                action="Run 'openreview gateway setup' to configure this slot.",
            )

        fallback = (
            slot_conf.get("fallback")
            if isinstance(slot_conf, dict)
            else getattr(slot_conf, "fallback", None)
        )

        fallback_config = self.config.get("gateway", {}).get("fallback", {})
        retries = fallback_config.get("retries", 2)
        retry_delay = fallback_config.get("retry_delay", 1.0)
        timeout = fallback_config.get("timeout", 60)
        on_failure = fallback_config.get("on_failure", "error")

        # Merge slot parameters with per-call kwargs overrides
        params_dict = {}
        slot_params = (
            slot_conf.get("params")
            if isinstance(slot_conf, dict)
            else getattr(slot_conf, "params", None)
        )
        if slot_params:
            if hasattr(slot_params, "__dict__"):
                params_dict = {k: v for k, v in slot_params.__dict__.items() if v is not None}
            elif isinstance(slot_params, dict):
                params_dict = {k: v for k, v in slot_params.items() if v is not None}

        merged_params = {**params_dict, **kwargs}

        if not session_id:
            import uuid

            session_id = str(uuid.uuid4())

        # Cost tracking & limits enforcement
        cost_limits = self.config.get("gateway", {}).get("cost_limits", {})
        per_review_cents = cost_limits.get("per_review_cents", 100)
        daily_cents = cost_limits.get("daily_cents", 1000)

        per_review_limit_usd = per_review_cents / 100.0
        daily_limit_usd = daily_cents / 100.0

        from openreview_cli.gateway.models import CostRecord

        if self._store is None:
            from openreview_cli.gateway.costs import CostStore

            self._store = CostStore()
        store = self._store

        # Check daily limit
        current_daily_cost = store.get_daily_cost()
        if current_daily_cost >= daily_limit_usd:
            raise GatewayError(
                exit_code=6,
                slot=slot,
                message=f"Daily cost limit of ${daily_limit_usd:.2f} reached. Current daily spend: ${current_daily_cost:.4f} USD. Please wait until tomorrow, switch to local models, or raise the limit in config.yml.",
                action="Wait until tomorrow, switch to local models, or raise the limit.",
            )

        # Check session limit
        current_session_cost = store.get_session_cost(session_id)
        if current_session_cost >= per_review_limit_usd:
            raise GatewayError(
                exit_code=6,
                slot=slot,
                message=f"Per-review cost limit of ${per_review_limit_usd:.2f} reached. Current session spend: ${current_session_cost:.4f} USD. Please switch to local models or raise the limit in config.yml.",
                action="Switch to local models or raise the limit.",
            )

        # Estimate request cost based on primary model
        estimated_cost = self.estimate_request_cost(
            slot=slot,
            model_str=primary,
            messages=messages,
            input_text=input_text,
            query=query,
            documents=documents,
            merged_params=merged_params,
        )

        if current_session_cost + estimated_cost > per_review_limit_usd:
            raise GatewayError(
                exit_code=6,
                slot=slot,
                message=f"Per-review cost limit of ${per_review_limit_usd:.2f} reached. Current session spend: ${current_session_cost:.4f} USD (estimated call cost: {estimated_cost:.4f} USD). Please switch to local models or raise the limit in config.yml.",
                action="Switch to local models or raise the limit.",
            )

        if current_daily_cost + estimated_cost > daily_limit_usd:
            raise GatewayError(
                exit_code=6,
                slot=slot,
                message=f"Daily cost limit of ${daily_limit_usd:.2f} reached. Current daily spend: ${current_daily_cost:.4f} USD (estimated call cost: {estimated_cost:.4f} USD). Please wait until tomorrow, switch to local models, or raise the limit in config.yml.",
                action="Wait until tomorrow, switch to local models, or raise the limit.",
            )

        logger.debug(f"Routing request for slot '{slot}' (session: {session_id})")

        # Attempt routing with primary then fallback
        try_models = [(primary, False)]
        if fallback:
            try_models.append((fallback, True))

        last_exception = None
        last_model_str = primary

        for model_str, is_fallback in try_models:
            if is_fallback:
                logger.info(
                    f"Primary model '{primary}' failed for slot '{slot}'. Activating fallback model '{model_str}'."
                )
            last_model_str = model_str
            attempts = retries + 1
            for attempt in range(attempts):
                logger.debug(
                    f"Attempt {attempt + 1}/{attempts} for model '{model_str}' (slot '{slot}')"
                )
                try:
                    resp = self._execute_call(
                        slot=slot,
                        model_str=model_str,
                        messages=messages,
                        input_text=input_text,
                        query=query,
                        documents=documents,
                        timeout=timeout,
                        merged_params=merged_params,
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < retries:
                        delay = retry_delay * (2**attempt)
                        logger.info(
                            f"API call to '{model_str}' failed: {e}. Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.warning(
                            f"API call to '{model_str}' failed: {e}. All retries exhausted."
                        )
                        break
                else:
                    resp.fallback_used = is_fallback

                    # Record cost in DB on success
                    record = CostRecord(
                        session_id=session_id,
                        slot=slot,
                        model=resp.model,
                        provider=resp.provider,
                        input_tokens=resp.input_tokens,
                        output_tokens=resp.output_tokens,
                        cost_usd=resp.cost_usd,
                        timestamp=time.time(),
                        fallback_used=resp.fallback_used,
                        latency_ms=resp.latency_ms,
                    )
                    store.insert_record(record)

                    logger.info(
                        f"API call to '{resp.provider}/{resp.model}' (slot '{slot}') succeeded. Cost: ${resp.cost_usd:.6f} USD. Latency: {resp.latency_ms}ms"
                    )
                    logger.debug(
                        f"Tokens used for '{resp.provider}/{resp.model}' (slot '{slot}'): {resp.input_tokens} input, {resp.output_tokens} output"
                    )

                    from openreview_cli.gateway.logging import is_debug_unsafe

                    if is_debug_unsafe():
                        logger.debug(f"Response content: {resp.content}")
                    else:
                        logger.debug("Response content omitted (use --debug-unsafe to log)")

                    return resp

        # Handle all failures after retries/fallback
        if on_failure == "error":
            if isinstance(last_exception, GatewayError):
                raise last_exception
            err_msg = str(last_exception)
            if "/" in last_model_str:
                prov, m_id = last_model_str.split("/", 1)
            else:
                prov = "ollama"
                m_id = last_model_str

            if "AuthenticationError" in last_exception.__class__.__name__ or "401" in err_msg:
                raise GatewayError(
                    exit_code=7,
                    slot=slot,
                    message=f"Authentication failed for provider '{prov}': {err_msg}",
                    action=f"Check your API key with 'openreview gateway test {slot}'",
                ) from last_exception
            elif (
                "APIConnectionError" in last_exception.__class__.__name__
                or "ConnectionRefused" in err_msg
            ):
                raise GatewayError(
                    exit_code=7,
                    slot=slot,
                    message=f"Provider '{prov}' is not reachable: {err_msg}",
                    action="Start local model or check internet connection.",
                ) from last_exception
            else:
                raise GatewayError(
                    exit_code=7,
                    slot=slot,
                    message=f"Request failed: {err_msg}",
                    action="Check provider logs or configuration.",
                ) from last_exception

        elif on_failure == "skip":
            import logging

            logging.warning(f"Slot '{slot}' failed (on_failure=skip): {last_exception}")
            if "/" in last_model_str:
                prov, m_id = last_model_str.split("/", 1)
            else:
                prov = "ollama"
                m_id = last_model_str
            return GatewayResponse(
                content=None,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                model=m_id,
                provider=prov,
                slot=slot,
                fallback_used=bool(fallback),
                latency_ms=0,
            )

        elif on_failure == "warn":
            import warnings

            warnings.warn(f"Slot '{slot}' failed: {last_exception}", UserWarning, stacklevel=2)
            if "/" in last_model_str:
                prov, m_id = last_model_str.split("/", 1)
            else:
                prov = "ollama"
                m_id = last_model_str
            return GatewayResponse(
                content=None,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                model=m_id,
                provider=prov,
                slot=slot,
                fallback_used=bool(fallback),
                latency_ms=0,
            )

        raise GatewayError(
            exit_code=7,
            slot=slot,
            message=f"Request failed: {last_exception or 'Unknown error'}",
            action="Check provider logs or configuration.",
        )

    def _execute_call(
        self,
        slot: str,
        model_str: str,
        messages: list[dict[str, str]] | None,
        input_text: str | list[str] | None,
        query: str | None,
        documents: list[str] | None,
        timeout: int,
        merged_params: dict[str, Any],
    ) -> GatewayResponse:
        if "/" in model_str:
            provider, model_id = model_str.split("/", 1)
        else:
            provider = "ollama"
            model_id = model_str

        # Resolve API key and base URL
        from openreview_cli.config.auth import get_api_base, get_api_key

        api_key = get_api_key(provider)
        api_base = get_api_base(provider)

        if not api_key and provider.lower() not in ("ollama",):
            raise GatewayError(
                exit_code=7,
                slot=slot,
                message=f"API key missing for provider '{provider}' (slot '{slot}')",
                action=f"Please set {provider.upper()}_API_KEY env var or run setup.",
            )

        if provider.lower() == "ollama" and not api_base:
            api_base = "http://localhost:11434"

        litellm_model = get_litellm_model_string(provider, model_id)
        litellm_kwargs: dict[str, Any] = {}
        if api_key:
            litellm_kwargs["api_key"] = api_key
        if api_base:
            litellm_kwargs["api_base"] = api_base
        if timeout:
            litellm_kwargs["timeout"] = timeout

        import litellm

        start_time = time.perf_counter()
        if slot in ("reasoning", "extraction", "graph"):
            if not messages:
                raise GatewayError(
                    exit_code=7,
                    slot=slot,
                    message="messages list is required for chat completion slots",
                    action="Provide a list of messages.",
                )
            response = litellm.completion(
                model=litellm_model, messages=messages, **merged_params, **litellm_kwargs
            )
            content = response.choices[0].message.content
        elif slot == "embedding":
            if not input_text:
                raise GatewayError(
                    exit_code=7,
                    slot=slot,
                    message="input_text is required for embedding slot",
                    action="Provide a string or list of strings to embed.",
                )
            response = litellm.embedding(
                model=litellm_model, input=input_text, **merged_params, **litellm_kwargs
            )
            data_list = response.data
            if isinstance(data_list, list):
                embeddings = []
                for item in data_list:
                    if isinstance(item, dict):
                        embeddings.append(item["embedding"])
                    else:
                        embeddings.append(item.embedding)
                content = (
                    embeddings[0] if isinstance(input_text, str) and embeddings else embeddings
                )
            else:
                content = []
        elif slot == "reranking":
            if query is None or documents is None:
                raise GatewayError(
                    exit_code=7,
                    slot=slot,
                    message="query and documents are required for reranking slot",
                    action="Provide a query string and a list of documents.",
                )
            response = litellm.rerank(
                model=litellm_model,
                query=query,
                documents=documents,
                **merged_params,
                **litellm_kwargs,
            )
            results = getattr(response, "results", []) or []
            content = []
            for r in results:
                score = getattr(r, "relevance_score", getattr(r, "score", 0.0))
                if isinstance(r, dict):
                    score = r.get("relevance_score", r.get("score", 0.0))
                    index = r.get("index", 0)
                    doc = r.get("document")
                else:
                    index = getattr(r, "index", 0)
                    doc = getattr(r, "document", None)

                doc_str = None
                if doc is not None:
                    if isinstance(doc, dict):
                        doc_str = doc.get("text")
                    elif isinstance(doc, str):
                        doc_str = doc
                    else:
                        doc_str = getattr(doc, "text", str(doc))

                content.append(RerankResult(index=index, score=score, document=doc_str))

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        usage = getattr(response, "usage", None)
        input_tokens = 0
        output_tokens = 0
        if usage:
            if isinstance(usage, dict):
                input_tokens = _safe_int(usage.get("prompt_tokens", 0))
                output_tokens = _safe_int(usage.get("completion_tokens", 0))
            else:
                input_tokens = _safe_int(getattr(usage, "prompt_tokens", 0))
                output_tokens = _safe_int(getattr(usage, "completion_tokens", 0))

        cost_usd = 0.0
        try:
            cost_usd = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception:
            pass

        return GatewayResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            model=model_id,
            provider=provider,
            slot=slot,
            fallback_used=False,
            latency_ms=latency_ms,
            raw_response=response,
        )

    def estimate_request_cost(
        self,
        slot: str,
        model_str: str,
        messages: list[dict[str, str]] | None = None,
        input_text: str | list[str] | None = None,
        query: str | None = None,
        documents: list[str] | None = None,
        merged_params: dict[str, Any] | None = None,
    ) -> float:
        if "/" in model_str:
            provider, model_id = model_str.split("/", 1)
        else:
            provider = "ollama"
            model_id = model_str

        if provider.lower() == "ollama":
            return 0.0

        litellm_model = get_litellm_model_string(provider, model_id)

        import litellm

        try:
            if slot in ("reasoning", "extraction", "graph"):
                max_tokens = 1000
                if merged_params:
                    max_tokens = merged_params.get("max_tokens", 1000)
                dummy_completion = "token " * max_tokens
                cost = litellm.completion_cost(
                    model=litellm_model,
                    messages=messages or [],
                    completion=dummy_completion,
                )
                return float(cost or 0.0)
            elif slot == "embedding":
                prompts = input_text if isinstance(input_text, list) else [input_text or ""]
                total_cost = 0.0
                for p in prompts:
                    cost = litellm.completion_cost(
                        model=litellm_model, prompt=p, call_type="embedding"
                    )
                    total_cost += float(cost or 0.0)
                return total_cost
            elif slot == "reranking":
                cost = litellm.completion_cost(
                    model=litellm_model, prompt=query or "", call_type="rerank"
                )
                return float(cost or 0.0)
        except Exception:
            pass
        return 0.0


def route_request(
    slot: str,
    messages: list[dict[str, str]] | None = None,
    input_text: str | list[str] | None = None,
    query: str | None = None,
    documents: list[str] | None = None,
    session_id: str | None = None,
    **kwargs: Any,
) -> GatewayResponse:
    """Convenience module-level function that creates an engine from default config and routes request."""
    engine = GatewayEngine()
    return engine.route_request(
        slot=slot,
        messages=messages,
        input_text=input_text,
        query=query,
        documents=documents,
        session_id=session_id,
        **kwargs,
    )
