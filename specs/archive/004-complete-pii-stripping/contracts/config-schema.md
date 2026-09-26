# Config Schema: PII Section

**Date**: 2026-06-30 | **Feature**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

## Overview

This contract defines the `pii` section of `config.yml` for controlling PII detection and stripping behavior. The PII section is optional; if absent, default values are used.

## Schema Definition

```yaml
# config.yml

pii:
  # PII detection confidence threshold (0.0 to 1.0)
  # Entities with confidence below this threshold are ignored
  # Default: 0.5
  threshold: 0.5

  # Enable/disable PII stripping globally
  # When false, all review commands process raw text (equivalent to --no-pii flag)
  # Default: true
  enabled: true

  # Retention period for encrypted PII mappings (in days)
  # After this period, mappings are eligible for automatic cleanup
  # Default: 30
  retention_days: 30

  # Enabled PII recognizers (list of recognizer names)
  # If empty or absent, all default recognizers are enabled
  # Default: all recognizers
  enabled_recognizers:
    - person
    - date
    - money
    - address
    - email
    - phone
    - organization
    - location
    - nationality
    - date_of_birth
    - passport_number
    - credit_card
    - social_security
    - driver_license
    - ip_address
    - url

  # Placeholder format template
  # {type} is replaced with entity type (e.g., PARTY_A, DATE, AMOUNT)
  # Default: "[{type}]"
  placeholder_format: "[{type}]"

  # Encryption settings
  encryption:
    # Algorithm for encrypting PII mappings
    # Only "fernet" is supported (authenticated symmetric encryption)
    # Default: "fernet"
    algorithm: fernet

    # Key derivation function for generating encryption keys
    # Only "hkdf" is supported (HMAC-based Key Derivation Function)
    # Default: "hkdf"
    key_derivation: hkdf
```

## Field Descriptions

### `threshold` (float, optional, default: 0.5)

PII detection confidence threshold. Entities with confidence below this value are ignored.

- **Range**: 0.0 to 1.0
- **Validation**: Must be a float in range [0.0, 1.0]
- **Behavior**:
  - Lower values (e.g., 0.3) → more aggressive detection, higher recall, lower precision
  - Higher values (e.g., 0.7) → more conservative detection, lower recall, higher precision
- **Override**: Can be overridden per-command with `--pii-threshold` CLI flag
- **Config Change Detection**: Changing this value invalidates cached PII results (triggers re-processing)

### `enabled` (bool, optional, default: true)

Global enable/disable for PII stripping.

- **Validation**: Must be a boolean
- **Behavior**:
  - `true` → PII stripping enabled (default for all review commands)
  - `false` → PII stripping disabled (equivalent to `--no-pii` flag for all commands)
- **Override**: Can be overridden per-command with `--no-pii` CLI flag
- **Warning**: When `false`, system logs warning: "PII stripping disabled globally via config.yml"

### `retention_days` (int, optional, default: 30)

Retention period for encrypted PII mappings (in days).

- **Range**: 1 to 365
- **Validation**: Must be a positive integer
- **Behavior**:
  - Encrypted mappings expire after `retention_days` from creation
  - Expired mappings are eligible for automatic cleanup via `openreview pii cleanup`
  - User can delete mappings manually before expiry via `openreview pii delete`
- **GDPR Compliance**: Aligns with data minimization principle (Article 5(1)(e))

### `enabled_recognizers` (list[str], optional, default: all)

List of enabled PII recognizer names.

- **Validation**: Each item must be a valid recognizer name (see list below)
- **Behavior**:
  - If absent or empty → all default recognizers enabled
  - If specified → only listed recognizers enabled
- **Config Change Detection**: Changing this list invalidates cached PII results
- **Supported Recognizers**:
  - `person` — Person names (e.g., "John Smith")
  - `date` — Dates (e.g., "2026-06-30", "June 30, 2026")
  - `money` — Monetary amounts (e.g., "$1,000", "€500")
  - `address` — Physical addresses (e.g., "123 Main St, City, State")
  - `email` — Email addresses (e.g., "user@example.com")
  - `phone` — Phone numbers (e.g., "+1-555-123-4567")
  - `organization` — Organization names (e.g., "Acme Corp")
  - `location` — Geographic locations (e.g., "New York", "France")
  - `nationality` — Nationalities (e.g., "American", "French")
  - `date_of_birth` — Dates of birth (specific pattern)
  - `passport_number` — Passport numbers (country-specific patterns)
  - `credit_card` — Credit card numbers (Luhn validation)
  - `social_security` — Social security numbers (US-specific)
  - `driver_license` — Driver's license numbers (US-specific)
  - `ip_address` — IP addresses (IPv4, IPv6)
  - `url` — URLs (e.g., "https://example.com")

### `placeholder_format` (str, optional, default: "[{type}]")

Template for PII placeholder strings.

- **Validation**: Must contain `{type}` placeholder
- **Behavior**:
  - `{type}` is replaced with entity type in uppercase (e.g., "PERSON" → "[PERSON]")
  - Example: `"<{type}>"` → "<PERSON>", "<DATE>"
  - Example: `"{{type}}"` → "{PERSON}", "{DATE}"
- **Use Case**: Customize placeholder format for readability or downstream processing

### `encryption.algorithm` (str, optional, default: "fernet")

Encryption algorithm for PII mappings.

- **Validation**: Must be "fernet" (only supported value)
- **Behavior**:
  - "fernet" → Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256)
  - Authenticated encryption (tamper-evident)
- **Future**: May support additional algorithms (e.g., "aes-256-gcm") in future versions

### `encryption.key_derivation` (str, optional, default: "hkdf")

Key derivation function for generating encryption keys.

- **Validation**: Must be "hkdf" (only supported value)
- **Behavior**:
  - "hkdf" → HMAC-based Key Derivation Function (RFC 5869)
  - Derives encryption key from document hash + salt
- **Future**: May support additional KDFs (e.g., "pbkdf2", "argon2") in future versions

---

## Validation Rules

1. **Type Checking**:
   - `threshold` must be a float
   - `enabled` must be a boolean
   - `retention_days` must be an integer
   - `enabled_recognizers` must be a list of strings
   - `placeholder_format` must be a string containing `{type}`
   - `encryption.algorithm` must be "fernet"
   - `encryption.key_derivation` must be "hkdf"

2. **Range Checking**:
   - `threshold` must be in [0.0, 1.0]
   - `retention_days` must be in [1, 365]

3. **Enum Checking**:
   - Each item in `enabled_recognizers` must be a valid recognizer name
   - `encryption.algorithm` must be "fernet"
   - `encryption.key_derivation` must be "hkdf"

4. **Dependency Checking**:
   - If `enabled` is false, `threshold` and `enabled_recognizers` are ignored
   - If `enabled_recognizers` is empty or absent, all default recognizers are used

---

## Default Values

If the `pii` section is absent from `config.yml`, the following defaults are used:

```yaml
pii:
  threshold: 0.5
  enabled: true
  retention_days: 30
  enabled_recognizers: []  # All recognizers enabled
  placeholder_format: "[{type}]"
  encryption:
    algorithm: fernet
    key_derivation: hkdf
```

---

## Config Hash Computation

The config hash is computed from the `pii` section to detect changes:

1. Serialize `pii` section to canonical JSON (sorted keys, no whitespace)
2. Compute SHA-256 hash of the JSON string
3. Store hash in `pii_cache` and `pii_audit_trail` tables

**Example**:

```python
import json
import hashlib

pii_config = {
    "threshold": 0.5,
    "enabled": True,
    "retention_days": 30,
    "enabled_recognizers": ["person", "date", "money"],
    "placeholder_format": "[{type}]",
    "encryption": {
        "algorithm": "fernet",
        "key_derivation": "hkdf"
    }
}

canonical_json = json.dumps(pii_config, sort_keys=True, separators=(',', ':'))
config_hash = hashlib.sha256(canonical_json.encode()).hexdigest()
```

**Behavior**:
- Any change to `pii` section → different `config_hash` → cached results invalidated
- Changing `threshold` from 0.5 to 0.7 → new `config_hash` → re-processing triggered
- Changing `enabled_recognizers` → new `config_hash` → re-processing triggered

---

## Example Configurations

### Minimal (all defaults)

```yaml
# config.yml
# No pii section → all defaults used
```

### Conservative (high threshold, few recognizers)

```yaml
pii:
  threshold: 0.7
  enabled_recognizers:
    - person
    - date
    - money
```

### Aggressive (low threshold, all recognizers)

```yaml
pii:
  threshold: 0.3
  enabled_recognizers: []  # All recognizers
```

### Disabled (no PII stripping)

```yaml
pii:
  enabled: false
```

### Short Retention (7 days)

```yaml
pii:
  retention_days: 7
```

---

## Migration from Previous Versions

### v1.0.0 → v1.1.0 (PII Integration)

No migration required. The `pii` section is optional; if absent, defaults are used.

### Future Migrations

If the `pii` schema changes in future versions:
1. Add version field to `pii` section (e.g., `version: 1`)
2. Implement migration logic in config loader
3. Warn user if old schema detected

---

## Integration with CLI

The `pii` section is loaded by the config loader (`src/openreview_cli/config/loader.py`) and passed to the PII engine (`src/openreview_cli/pii/engine.py`).

**CLI Override Priority**:
1. CLI flags (highest priority): `--no-pii`, `--pii-threshold`
2. Environment variables: `OPENREVIEW_PII_ENABLED`, `OPENREVIEW_PII_THRESHOLD`
3. `config.yml` `pii` section
4. Default values (lowest priority)

**Example**:

```bash
# CLI flag overrides config.yml
OPENREVIEW_PII_THRESHOLD=0.6 openreview precheck --pii-threshold 0.7 contract.pdf
# Result: threshold = 0.7 (CLI flag wins)
```
