# Data Model: Privacy Tier Routing

**Feature**: `020-privacy-tier-routing`
**Phase**: 1 (Design & Contracts)
**Date**: 2026-07-05

## Entities

### PrivacyTier (enum)

Three-tier enumeration governing how model calls are routed.

| Value | Description | Embedding Routing | LLM Routing | PII Required Before Cloud |
|-------|-------------|-------------------|-------------|---------------------------|
| `maximum` | All inference local | Local only | Local only | No (no cloud calls) |
| `balanced` | Local embeddings, cloud LLM with PII stripped | Local only | Cloud allowed | Yes |
| `performance` | Full cloud inference with PII stripped | Cloud allowed | Cloud allowed | Yes |

**Validation rules**:
- Value must be one of: `maximum`, `balanced`, `performance`
- Case-insensitive during parsing; stored lowercase
- Invalid value defaults to `maximum` with warning (FR-05)
- Absent key defaults to `maximum` with warning (FR-05)

### TierConfig (dataclass)

Loaded from `config.yml` at `privacy.tier` key. Captured once per operation.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tier` | `PrivacyTier` | `maximum` | Active privacy tier |
| `tier_source` | `str` | `"default"` | Where the value came from: `"config"`, `"default"`, or `"warning"` |
| `warning` | `str \| None` | `None` | Warning message if config was missing/invalid |

**Factory method**:
```
TierConfig.from_config(config: dict) -> TierConfig
```
- Reads `config.get("privacy", {}).get("tier")`
- Validates against known values
- Sets `tier_source` and `warning` appropriately

### ProviderLocation (enum)

Classification of a provider as local or cloud-based.

| Value | Meaning |
|-------|---------|
| `local` | Runs on localhost. Allowed on all tiers. |
| `cloud` | Runs on remote server. Blocked on Maximum; requires PII on Balanced/Performance. |

### ProviderLocationClassifier (function / static method)

Determines provider location from its base URL.

**Input**: Provider config dict (containing `api_base` or `host` field)
**Output**: `ProviderLocation`

**Logic**:
1. If provider config has explicit `local: true` → return `local`
2. If provider config has explicit `local: false` → return `cloud`
3. Parse `api_base` with `urllib.parse.urlparse()`
4. If `netloc` matches `localhost`, `127.0.0.1`, `[::1]` → return `local`
5. If the URL has no scheme and no netloc (Unix socket) → return `local`
6. Otherwise → return `cloud`

### TierRouter

Central enforcement point. Wraps Gateway methods.

**No persistent state** — stateless by design. Receives TierConfig at construction.

**Key methods**:
```
TierRouter(gateway: Gateway, config: TierConfig)
```

Wraps each Gateway method:
- `chat()` → enforces tier rules for LLM calls
- `embed()` → enforces tier rules for embedding calls

**Internal flow per call**:
1. Determine call type (known from which wrapper invoked)
2. Determine required provider location from current tier + call type
3. If required location is `cloud` and PII engine is unavailable → raise `PIIUnavailableError`
4. Filter available providers to those matching required location
5. If no matching providers → raise `NoMatchingProviderError` with suggestions
6. Pass filtered providers to Gateway for dispatch

**PII verification**:
- Before dispatching a cloud call on Balanced/Performance tier:
  - Call `PiiEngine.is_available()` (per-operation cached)
  - If unavailable → raise `PIIUnavailableError` (fail-closed)
  - Look up stripped text in per-operation cache. Cache key is SHA-256 of input text, or a caller-provided cache key (document ID or operation ID passed by the upstream pipeline).
  - If cache hit (PII stripping already performed for this input) → use cached result, proceed
  - If cache miss → raise error indicating PII stripping has not been performed yet. The router does not trigger stripping — the upstream pipeline must strip PII before invoking the router.
- **Cache lifecycle**: The per-operation cache is created at operation start and cleared at operation end (both success and failure). No cache data persists across operations.

### PrivacyTierReport (dataclass)

Attached to operation result. Provides transparency about data flow.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tier` | `PrivacyTier` | — | Tier used for the operation |
| `tier_label` | `str` | — | Human-readable tier description |
| `cloud_calls_made` | `int` | `0` | Number of cloud provider calls dispatched |
| `pii_entities_stripped` | `int \| None` | `None` | Count of PII entities redacted before cloud calls |
| `pii_stripping_warning` | `str \| None` | `None` | Warning if PII confidence was low |
| `tier_warning` | `str \| None` | `None` | Warning if tier was defaulted or changed |

**Display methods**:
- `progress_banner()` → formatted string for CLI progress output (e.g., "Privacy tier: MAXIMUM — all inference local")
- `report_footer()` → formatted string for final report

### PiiEngineReadiness

Not a separate entity — a boolean check exposed by the existing PiiEngine:
```
PiiEngine.is_available() -> bool
```
- Lightweight: attempts `analyze("test", language="en")` once per operation
- Caches result in a module-level or instance-level variable
- Returns `True` if analysis succeeds, `False` if spaCy model missing, OOM, or any error

## State Transitions

Tier state is simple: loaded once, stays constant for operation duration.

```
Config loaded → TierConfig created → TierRouter constructed →
  For each model call:
    Call type determined → Location filtered → PII checked (if cloud) →
      Gateway dispatched (or error raised)
```

No intermediate states. No runtime transition. No persistence.

## Relationships

```
TierConfig ─────────────► TierRouter
     │                        │
     │                        ├── wraps Gateway.chat()
     │                        ├── wraps Gateway.embed()
     │                        ├── TierRouter.classify_provider() (static method)
     │                        │      └── uses urllib.parse.urlparse() on provider config
     │                        │      └── returns ProviderLocation (local | cloud)
     │                        └── uses PiiEngine.is_available() before cloud dispatch
     │
     └──► PrivacyTierReport ───► Final CLI output

```
