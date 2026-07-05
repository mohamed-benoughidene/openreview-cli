# Provider Classification API Contract

## Purpose

Determines whether a given provider configuration represents a local or cloud-based service. Used by TierRouter to filter providers by tier rules.

## Function Signature

```python
from openreview_cli.gateway.tier_router import TierRouter
from openreview_cli.gateway.models import ProviderLocation

def classify_provider(provider_config: dict) -> ProviderLocation:
    """Convenience wrapper around TierRouter.classify_provider()."""
    """
    Classifies a provider as local or cloud based on its configuration.

    Args:
        provider_config: A dictionary containing provider configuration.
            Expected keys (one or both):
            - 'api_base': str — base URL of the provider API
            - 'host': str — host address (alternative to api_base)
            - 'local': bool (optional) — explicit override flag

    Returns:
        ProviderLocation.LOCAL or ProviderLocation.CLOUD

    Never raises. Malformed URLs are classified as cloud.
    """
```

## Classification Rules (in order of precedence)

1. **Explicit override**: If `provider_config` contains key `local` with value `True` → return `LOCAL`. If `False` → return `CLOUD`.
2. **Unix socket**: If `api_base` starts with `unix://` or is a filesystem path (no `://`) → return `LOCAL`.
3. **localhost**: Parse URL with `urllib.parse.urlparse()`. If `netloc` (hostname) matches `localhost`, `127.0.0.1`, or `[::1]` → return `LOCAL`.
4. **Default**: All other URLs → return `CLOUD`.

## URL Parsing Details

```python
import urllib.parse

def _parse_provider_url(provider_config: dict) -> str | None:
    """Extract the URL to classify from provider config."""
    if 'api_base' in provider_config:
        return provider_config['api_base']
    if 'host' in provider_config:
        return provider_config['host']
    return None
```

Localhost pattern detection:

```python
_LOCALHOST_PATTERNS = frozenset({
    'localhost',
    '127.0.0.1',
    '[::1]',
    '0.0.0.0',
})

def _is_localhost(hostname: str) -> bool:
    return hostname in _LOCALHOST_PATTERNS
```

## Test Vectors

| Provider Config | Expected Classification | Reason |
|-----------------|------------------------|--------|
| `{"api_base": "http://localhost:11434"}` | LOCAL | localhost hostname |
| `{"api_base": "http://127.0.0.1:11434"}` | LOCAL | loopback IP |
| `{"api_base": "http://[::1]:11434"}` | LOCAL | IPv6 loopback |
| `{"api_base": "unix:///var/run/ollama.sock"}` | LOCAL | Unix socket |
| `{"host": "localhost:11434"}` | LOCAL | host field, localhost |
| `{"api_base": "https://api.openai.com/v1"}` | CLOUD | remote host |
| `{"api_base": "http://192.168.1.100:11434"}` | CLOUD | private IP but not localhost (requires explicit override) |
| `{"api_base": "http://ollama.lan:11434"}` | CLOUD | DNS name, non-localhost |
| `{"api_base": "http://localhost:11434", "local": false}` | CLOUD | explicit override wins |
| `{"api_base": "http://192.168.1.100:11434", "local": true}` | LOCAL | explicit override wins |
| `{}` | CLOUD | no URL to classify → default cloud |

## Usage in TierRouter

```python
from openreview_cli.gateway.tier_router import TierRouter

# Usage: TierRouter.classify_provider(provider_config)
def _filter_providers_by_location(
    providers: list[dict],
    required_location: ProviderLocation
) -> list[dict]:
    return [
        p for p in providers
        if classify_provider_location(p) == required_location
    ]
```
