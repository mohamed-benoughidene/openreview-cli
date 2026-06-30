"""Config hash computation for PII config change detection.

Serializes PII config section to canonical JSON (sorted keys, no whitespace)
and returns SHA-256 hex digest.
"""

import hashlib
import json


def compute_config_hash(pii_config: dict[str, object]) -> str:
    canonical = json.dumps(pii_config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


__all__ = ["compute_config_hash"]
