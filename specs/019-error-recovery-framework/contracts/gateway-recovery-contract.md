# Gateway-Recovery Contract

**Date**: 2026-07-05 | **Spec Reference**: spec.md §4 FR-01, FR-02, SC-02, SC-04

---

## 1. Recovery wraps every Gateway provider call

The recovery framework does not modify the AI Gateway internals. It wraps every outbound provider call at the point where `Gateway.chat()`, `Gateway.embed()`, or `Gateway.rerank()` is invoked.

The wrapping layer:
1. Calls the Gateway method with the original parameters.
2. If the call succeeds, returns the result normally — no recovery overhead.
3. If the call fails, classifies the error and executes recovery.

---

## 2. Classification of Gateway errors

The Gateway already returns provider responses with metadata. The recovery classification layer reads:

| Gateway Metadata Field | Used For |
|------------------------|----------|
| `status_code` (HTTP) | 503/429/timeout → transient; 400/401/403/404/500 → permanent |
| `error_type` (LiteLLM) | `"rate_limit"`, `"service_unavailable"`, `"auth_error"`, etc. |
| `provider_name` | Identifies which provider failed |
| `model_name` | Identifies which model was used |

**Classification logic** (pure function):

```
if status_code in (503, 429) or error_type in ("rate_limit", "service_unavailable", "timeout"):
    → ErrorCategory.transient
elif status_code in (400, 401, 403, 404) or error_type == "auth_error":
    → ErrorCategory.permanent
elif status_code == 500 or error_type == "provider_error":
    → ErrorCategory.permanent
else:
    → ErrorCategory.unknown
```

---

## 3. Retry loop (FR-01)

```
attempt = 0
while attempt < max_retries:
    attempt += 1
    emit_progress(f"Retrying provider call (attempt {attempt}/{max_retries})…")
    record RecoveryEvent(strategy="auto_retry", attempt=attempt)
    try:
        result = await gateway.chat(...)
        return result  # success
    except gateway_error:
        if attempt >= max_retries:
            break  # exhaust
        await asyncio.sleep(backoff(attempt))
# All retries exhausted → escalate to ProviderFallbackStrategy
```

---

## 4. Fallback flow (FR-02)

```
AutoRetryStrategy exhausted
  → ProviderFallbackStrategy.select_next_provider()
  → Check privacy tier (SC-04):
       If tier == "strict" and next provider is cloud:
           Stop with error: "No fallback available without cloud. Start local provider or change privacy tier."
  → emit_progress(f"Falling back to \"{next_provider}\"…")
  → record RecoveryEvent(strategy="provider_fallback", provider=next_provider)
  → Call gateway with new provider
  → If fallback also fails → retry fallback with backoff → if exhausted → try next
  → If all exhausted → escalate to UserGuidedRecoveryStrategy
```

---

## 5. Provider enumeration

The recovery framework reads the configured provider list from the Gateway's `ModelRegistry`. The gateway must expose:

```python
def get_configured_providers() -> list[str]:
    """Return the user's ordered provider list."""
```

If no providers are configured, the recovery framework returns a user-guided error directing the user to `openreview gateway setup`.

---

## 6. Cost tracking

When fallback switches providers, the recovery framework reads the cost difference from the existing cost tracking module (spec-005). The fallback notification MAY include estimated cost impact, but this is informational only — the framework never blocks a fallback based on cost alone.
