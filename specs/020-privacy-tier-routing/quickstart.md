# Quickstart Validation Guide: Privacy Tier Routing

**Feature**: `020-privacy-tier-routing` — three privacy tiers controlling how data travels during model inference.

**Prerequisites**:
- Python 3.12, `uv` installed, `uv sync` completed
- Existing AI Gateway implementation (`src/openreview_cli/gateway/`)
- Existing PII Stripping Engine (`src/openreview_cli/pii/`)
- Configuration loader (`src/openreview_cli/config/`)
- Review pipeline (single-party review, `src/openreview_cli/review/`)

**Artifacts referenced**:
- Data model: `specs/020-privacy-tier-routing/data-model.md`
- Interface contracts: `specs/020-privacy-tier-routing/contracts/`

---

## Validation Scenario 1: TierRouter Rejects Cloud Call on Maximum Tier

**Purpose**: Verify that Maximum tier blocks cloud provider calls.

**Setup**:
1. Create a `TierConfig` with `PrivacyTier.MAXIMUM`
2. Create a mock Gateway with both local and cloud providers configured
3. Create a `TierRouter(gateway, config)`

**Action**: Call `router.chat()` with model parameters that would route to a cloud provider.

**Expected outcome**:
- `router.chat()` raises `NoMatchingProviderError`
- Error message includes "Maximum privacy tier" and "local provider"
- No call reaches the mock Gateway's cloud provider

**Run**:
```bash
# Comamnd placeholder — implementation tests will live in:
# tests/unit/test_tier_router.py::test_maximum_tier_rejects_cloud_call
uv run pytest tests/unit/test_tier_router.py::test_maximum_tier_rejects_cloud_call -v
```

---

## Validation Scenario 2: Balanced Tier Routes Embeddings to Local, LLM to Cloud

**Purpose**: Verify that Balanced tier routes by call type correctly.

**Setup**:
1. `TierConfig` with `PrivacyTier.BALANCED`
2. Mock Gateway with both local and cloud providers
3. Document text with seeded PII

**Action**: Call `router.embed()` then `router.chat()`.

**Expected outcome**:
- `router.embed()` routes to a local provider only
- `router.chat()` routes to a cloud provider
- `router.chat()` input receives PII-stripped text (verified via mock capture)
- Raw PII values do not appear in cloud call input

**Run**:
```bash
uv run pytest tests/unit/test_tier_router.py::test_balanced_tier_routing -v
```

---

## Validation Scenario 3: PII Engine Failure Blocks Cloud Call

**Purpose**: Verify fail-closed behavior when PII is unavailable.

**Setup**:
1. `TierConfig` with `PrivacyTier.BALANCED`
2. Mock Gateway with cloud provider
3. Mock `PiiEngine.is_available()` returns `False`

**Action**: Call `router.chat()`.

**Expected outcome**:
- `router.chat()` raises `PIIUnavailableError`
- Error message includes "PII" and at least two actionable suggestions
- No HTTP request to any cloud provider URL
- No document text appears in the error message

**Run**:
```bash
uv run pytest tests/unit/test_tier_router.py::test_pii_failure_blocks_cloud_call -v
```

---

## Validation Scenario 4: Performance Tier Routes Everything to Cloud

**Purpose**: Verify Performance tier routes all calls to cloud providers with PII stripping.

**Setup**:
1. `TierConfig` with `PrivacyTier.PERFORMANCE`
2. Mock Gateway with both local and cloud providers
3. Document with seeded PII

**Action**: Call `router.embed()` and `router.chat()`.

**Expected outcome**:
- Both calls route to cloud providers
- All call inputs have PII stripped

**Run**:
```bash
uv run pytest tests/unit/test_tier_router.py::test_performance_tier_routing -v
```

---

## Validation Scenario 5: Missing Tier Config Defaults to Maximum

**Purpose**: Verify safe default when `privacy.tier` is absent.

**Setup**:
1. `TierConfig.from_config({})` (empty config)

**Action**: Call `TierConfig.from_config()`.

**Expected outcome**:
- Returns `TierConfig(tier=PrivacyTier.MAXIMUM, tier_source="default", warning=...)`
- Warning message explains the default
- Same behaviour for `from_config({"privacy": {}})` and `from_config({"privacy": {"tier": "invalid"}})`

**Run**:
```bash
uv run pytest tests/unit/test_tier_config.py::test_missing_config_defaults_to_maximum -v
uv run pytest tests/unit/test_tier_config.py::test_invalid_tier_defaults_to_maximum -v
```

---

## Validation Scenario 6: Provider Classification by URL

**Purpose**: Verify local vs cloud classification.

**Setup**: Call `TierRouter.classify_provider()` (static method on TierRouter) with various provider configs.

**Expected outcome**:
- `http://localhost:11434` → `LOCAL`
- `https://api.openai.com/v1` → `CLOUD`
- `{"local": true, "api_base": "http://192.168.1.100:11434"}` → `LOCAL`
- `{}` → `CLOUD`

**Run**:
```bash
uv run pytest tests/unit/test_tier_router.py -v
```

---

## Integration: Full Pipeline with Privacy Tiers

**Purpose**: End-to-end verification through the review pipeline.

**Setup**:
1. Temporary config file per tier (see `tests/fixtures/config_tier_*.yml`)
2. Test document with seeded PII (existing PII test fixtures)
3. Mock providers (both local and cloud) configured

**Action**: Run the review pipeline with each tier.

**Expected outcome**:
- Maximum: zero external HTTP requests; output shows "MAXIMUM" banner
- Balanced: embeddings local, LLM cloud; output shows "BALANCED" banner
- Performance: all cloud; output shows "PERFORMANCE" banner
- All outputs include tier summary in final report

**Run**:
```bash
uv run pytest tests/integration/test_privacy_tier.py -v
```

---

## Validation Checklist

- [ ] Unit tests pass for all tier routing scenarios
- [ ] Unit tests pass for provider classification
- [ ] Unit tests pass for config parsing (missing/invalid values)
- [ ] Integration tests verify zero external calls on Maximum tier
- [ ] Integration tests verify PII stripping before cloud calls
- [ ] Integration tests verify fail-closed on PII engine failure
- [ ] Integration tests verify tier visibility in output
- [ ] Pre-commit hooks pass (`ruff`, `ruff-format`, `mypy`, pytest-fast)
- [ ] Memory test passes (<100 MB peak, NLP model exempted)
