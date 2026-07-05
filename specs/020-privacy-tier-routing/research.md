# Phase 0 Research: Privacy Tier Routing

**Status**: Complete — all technical unknowns resolved via context7 docs, tavily web search, and existing codebase analysis.

## Research Sources

| Source | Type | Topics |
|--------|------|--------|
| LiteLLM docs (context7: `/berriai/litellm`) | API docs + cookbooks | Completion routing, Ollama integration, model_list config, fallbacks, cost tracking |
| Ollama Python SDK docs (context7: `/ollama/ollama-python`) | API docs | Chat, embedding, custom Client, async, host config |
| Presidio docs (context7: `/microsoft/presidio`) | API docs | AnalyzerEngine, AnonymizerEngine, custom recognizers, operator config |
| LiteLLM + Ollama + Semantic Routing (YouTube, Mar 2026) | Tutorial | Routing patterns for local + cloud models |
| LiteLLM AI Gateway guide (localaimaster.com, 2026) | Article | Production routing between local Ollama and cloud providers |
| Microsoft Presidio official docs (microsoft.github.io/presidio) | Reference | Engine architecture, recognizer registry, error handling |
| Existing codebase: `src/openreview_cli/gateway/` | Code audit | Current Gateway interface, model registry, provider config |

## Resolved Unknowns

### U1: Can LiteLLM distinguish embedding calls from LLM calls? (affects Balanced tier)

**Decision**: Yes — but not natively through a single `completion()` function. LiteLLM exposes separate `embedding()` and `completion()` functions. The existing Gateway already wraps these separately (per spec Assumption §7, CL-03 resolution). TierRouter wraps each Gateway method individually, giving direct call-type knowledge.

**Rationale**: Wrapping typed methods avoids changing Gateway interface. Call type is known from which wrapper was invoked. No need for model-type inference.

**Alternatives considered**:
- Single `call()` with model_type parameter — requires changing Gateway interface signatures across all callers
- Infer from provider registry metadata — fragile, indirect, misses custom models

### U2: How to classify a provider as local vs cloud?

**Decision**: Inspect provider's base URL against known localhost patterns. Use `urllib.parse.urlparse()` on the provider's `api_base` or `host` field. If netloc matches `localhost`, `127.0.0.1`, `[::1]`, or is a Unix socket path (no scheme/host), classify as local. Otherwise cloud.

**Rationale**: URL inspection is deterministic, stateless, and needs no external data. The Model Registry may already store a `local` flag; if present that takes precedence.

**Alternatives considered**:
- Provider-type attribute in registry — requires schema change
- Try-connect heuristic — slow, unreliable on offline machines

### U3: How to check if PII engine is available before a cloud call?

**Decision**: Add `PiiEngine.is_available()` method that returns boolean. Implementation: attempt a lightweight analysis on a known-safe string (e.g., `"test"`). If AnalyzerEngine initializes and returns results without error → available. If spaCy model missing, engine OOM, or import fails → unavailable.

**Rationale**: Spec §7 Assumption requires a synchronous readiness check. A lightweight test analysis is the simplest reliable detection. Caching the result per-operation avoids repeated checks.

**Alternatives considered**:
- Try-import at module level — doesn't catch runtime errors (model missing, OOM)
- Always attempt analysis and catch exception — works but mixes detection with processing

### U4: LiteLLM routing overhead for Maximum tier calls (bypass vs route-through)

**Decision**: Route through Gateway always (per CL-02 resolution). LiteLLM's `completion()` with `model="ollama/..."` and `api_base="http://localhost:11434"` adds negligible overhead (<10ms) for a CLI tool.

**Rationale**: Avoiding dual code paths keeps testing simple, cost tracking consistent, and error handling unified. If profiling later shows overhead >100ms on Maximum tier, a direct Ollama SDK bypass can be added then.

**Data**: LiteLLM cookbook confirms `ollama/llama2` call with `api_base` parameter works identically to cloud calls. Ollama Python SDK provides `client.chat()` and `client.embed()` as alternative if bypass path is needed later.

### U5: Default tier behavior when config key is missing or invalid

**Decision**: Default to Maximum. Show warning on first operation per operation (not per-call). Warning is: "privacy.tier not configured. Defaulting to Maximum. Set privacy.tier in config.yml to suppress this warning."

**Rationale**: Maximum is safest default (no data leaves machine). Per-operation warning avoids noise while ensuring user is informed. Spec FR-05 requires this behavior.

### U6: PII stripping caching per operation

**Decision**: Cache PII-stripped text per operation in an operation-scoped dict. Keyed by document path + config hash. If a cloud call references the same document, return cached stripped text. Clear cache at end of operation.

**Rationale**: Spec §7 Assumption notes PII stripping is idempotent. Caching avoids redundant processing on the same document for multiple cloud calls (e.g., parallel QA questions). Dict cache has negligible memory cost for typical document sizes.

### U7: Provider ambiguity — when a provider could be either local or cloud (e.g., self-hosted vLLM on a remote server)

**Decision**: Treat non-localhost URLs as cloud. A self-hosted vLLM on a remote server is treated as cloud for tier purposes — Maximum tier blocks it, Balanced/Performance require PII stripping. User can override by setting an explicit `local: true` flag in the provider config.

**Rationale**: Conservative approach — if we cannot confirm it's local, treat it as external. The explicit flag gives users control for legitimate non-localhost local setups.

### U8: Do we need to modify the Model Registry?

**Decision**: No changes required for MVP. Provider classification uses URL inspection (U2). If the model registry already stores `local` flag, that takes precedence. If not, URL-based classification is sufficient. Registry changes are deferred until the registry schema is revised independently.

## Architecture Decisions Summary

| ID | Decision | Rationale |
|----|----------|-----------|
| AD-01 | TierRouter wraps individual Gateway methods (chat, embed) for call-type detection | Avoids Gateway interface changes; call type implicit from wrapper |
| AD-02 | URL-based provider classification with explicit override flag | Deterministic, stateless, no registry dependency |
| AD-03 | PII readiness via `is_available()` lightweight probe | Reliable, per-operation cached, separates detection from processing |
| AD-04 | Route through Gateway on all tiers, no bypass | Single code path, consistent cost tracking, simpler testing |
| AD-05 | Default to Maximum on missing/invalid config | Safest default; warning per operation |
| AD-06 | Operation-scoped PII cache | Idempotent stripping, avoids redundant work, negligible memory |
| AD-07 | Non-localhost URLs classified as cloud | Conservative privacy stance; explicit `local: true` override available |
| AD-08 | No Model Registry changes for MVP | URL inspection sufficient; registry changes deferred |

## LiteLLM Integration Notes

- LiteLLM `completion()` with `model="ollama/llama3.1"` and `api_base="http://localhost:11434"` works out of the box for local calls
- For cloud calls, LiteLLM uses the model prefix (`openai/`, `anthropic/`, etc.) to route to the correct provider
- The `model_list` YAML config in the Gateway supports per-model `api_base` override — useful for Ollama
- LiteLLM's `Router` class (separate from this project's TierRouter) provides built-in fallbacks, rate limiting, and cost tracking — but this project already has its own Gateway wrapping LiteLLM

## Ollama Integration Notes

- Ollama Python SDK provides `Client` with custom `host` param for non-default ports
- `client.chat()`, `client.embed()` are the relevant methods
- `ollama.list()` returns available models — useful for pre-flight check on Maximum tier
- AsyncClient available but the existing Gateway uses synchronous calls
- Models too large for 8GB RAM will OOM — Ollama handles this naturally (CL-01)

## Presidio Integration Notes

- `AnalyzerEngine()` initialization loads spaCy model (~500 MB) — this load is exempt from memory budget per constitution
- `analyzer.analyze(text, language="en")` returns list of `RecognizerResult` with `start`, `end`, `entity_type`, `score`
- `AnonymizerEngine().anonymize(text, analyzer_results)` replaces PII spans with placeholders
- Custom recognizers registered via `analyzer.registry.add_recognizer()`
- Engine availability check: `AnalyzerEngine()` constructor fails if spaCy model is missing — catch this in `is_available()`
- Multiple entity types: 16+ supported out of the box (PERSON, EMAIL, PHONE, CREDIT_CARD, etc.)

## Key Differences from Prior Spec Assumptions (verified)

| Spec Assumption | Research Verdict |
|-----------------|------------------|
| Gateway exposes separate chat/embed methods | ✅ Confirmed — LiteLLM has `completion()` and `embedding()`; Gateway wraps these |
| PII engine has synchronous readiness check | ✅ Can implement via lightweight `analyze("test")` catch |
| Local providers identified by localhost URL | ✅ `urllib.parse` deterministic, matches spec |
| LiteLLM handles Ollama as a provider | ✅ Confirmed — `model="ollama/<name>"` with `api_base` |
| Gateway overhead negligible on Maximum | ✅ LiteLLM completion <10ms overhead for local calls |
