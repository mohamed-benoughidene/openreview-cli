# Spec 034 — Multi-Field Provider Credential Support

## Context

The recent AI Gateway update shipped a unified provider registry that models provider authentication via a single environment variable key.

Three major cloud providers cannot be expressed this way due to requiring multiple authentication fields simultaneously. Confirmed against litellm docs during the `033` provider-addition pass:

| Provider | Required credentials (per litellm docs) | Why single `env_key` fails |
|----------|------------------------------------------|----------------------------|
| **Azure OpenAI** | `AZURE_OPENAI_ENDPOINT` (URL) + deployment name + `AZURE_OPENAI_KEY` | Needs endpoint + deployment, not just a key |
| **AWS Bedrock** | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_REGION_NAME` | 3-field AWS credential set |
| **Google Vertex AI** | `VERTEXAI_PROJECT` + `VERTEXAI_LOCATION` + `GOOGLE_APPLICATION_CREDENTIALS` | project + region + service-account path |

Forcing them into a single-key pattern would either break resolution or silently misroute the call. This specification extends the credential handling so complex providers can be configured cleanly alongside single-key ones.

## Goal

A user can configure Azure / Bedrock / Vertex via the existing
wizard flow, with each credential field validated and surfaced in health checks, using only the existing provider support (no new dependency).

## Clarifications

### Session 2026-07-20
- Q: Where should credential values be stored? → A: Extend the secure local auth file (store a flat mapping of keys to values as a fallback).
- Q: Does base URL stay a top-level field? → A: Keep base URL as a top-level field.
- Q: How does the wizard collect multiple fields via CLI arguments? → A: Repeated flag arguments.
- Q: Should the wizard validate credential files? → A: Yes, validate existence, read access, and that the file is non-empty.
- Q: How are parameters mapped to the inference engine? → A: Via an explicit mapping attribute in the configuration model (see technical contract).

## Functional Requirements

- **FR-1:** The gateway configuration accepts an ordered list of credential fields per provider in addition to the legacy single key.
- **FR-2:** Single-key providers load **unchanged** — fully backward compatible, no regression.
- **FR-3:** When a provider is invoked, the gateway correctly maps each defined credential field to the underlying inference engine's required parameters.
- **FR-4:** The CLI providers list and the TUI health check report **per-field** configuration status; a provider is considered "configured" only when ALL required fields resolve successfully from the environment or fallback storage.
- **FR-5:** The interactive wizard and the CLI setup command collect N fields via repeated key-value flags, validating presence for each required field.
- **FR-6:** A complex provider entry loads successfully and is marked healthy only when its required credentials are set; a live integration call with those providers succeeds (verified with real keys during testing, skipped otherwise).
- **FR-7:** For providers requiring file-based credentials (e.g., Google), the CLI wizard MUST validate that the specified file exists on disk, is readable, and is non-empty before setup succeeds.
- **FR-8:** Multi-field credential values are securely persisted locally as a fallback to system environment variables, mirroring the privacy and persistence guarantees of single-key secrets.

## Constraints

- No new dependencies. litellm already supports all three providers;
  this is our config/credential model catching up.
- Single-key providers untouched; existing unit + integration suites
  stay green.
- `mypy --strict`, `ruff`, pre-commit all pass.
- Local-only CLI; no web server (per repo constitution).

## Out of Scope

- Defaulting these providers on vs. leaving them opt-in.
- Cost-tracking differences (Bedrock/Vertex billing ≠ per-token).
- Any change to the privacy-tier model.
- Adding the actual Azure/Bedrock/Vertex registry entries is a task
  that **depends on** this model change landing first.

## Success Criteria

1. `ProviderInfo` accepts `credentials: list[CredentialField]`; single-key
   providers unchanged and still load from `env_key` (FR-1, FR-2).
2. A new provider with `credentials` (e.g. a Bedrock entry) loads via
   `load_registry()` and reports healthy only when all required env vars
   are set (FR-4, FR-6).
3. `Gateway` maps each credential field to the correct litellm kwarg and
   makes a real call (FR-3, FR-6) — verified with a live test where
   creds exist, skipped otherwise.
4. TUI health check + CLI `gateway providers --json` show per-field
   status (FR-4).
5. mypy --strict, ruff, existing unit suite green; new unit + integration
   tests added per provider (FR-6).
