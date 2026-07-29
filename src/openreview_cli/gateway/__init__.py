"""AI Gateway — lazy package facade.

Names resolve on first attribute access (PEP 562) so importing the package
never pulls litellm. TUI safety is by construction, not convention.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openreview_cli.gateway.cost import CostTracker
    from openreview_cli.gateway.errors import (
        AllProvidersFailedError,
        AuthError,
        GatewayError,
        ModelNotFoundError,
        NoMatchingProviderError,
        PIIUnavailableError,
        SlotNotConfiguredError,
        TierRoutingError,
    )
    from openreview_cli.gateway.models import (
        CostRecord,
        ModelEntry,
        PrivacyTierReport,
        ProviderInfo,
    )
    from openreview_cli.gateway.registry import ModelRegistry
    from openreview_cli.gateway.router import Gateway
    from openreview_cli.gateway.tier_config import PrivacyTier, TierConfig
    from openreview_cli.gateway.tier_router import TierRouter
    from openreview_cli.gateway.tier_tracker import TierTracker
    from openreview_cli.gateway.wizard import gateway_setup

_LAZY: dict[str, str] = {
    "CostTracker": "openreview_cli.gateway.cost",
    "AllProvidersFailedError": "openreview_cli.gateway.errors",
    "AuthError": "openreview_cli.gateway.errors",
    "GatewayError": "openreview_cli.gateway.errors",
    "ModelNotFoundError": "openreview_cli.gateway.errors",
    "NoMatchingProviderError": "openreview_cli.gateway.errors",
    "PIIUnavailableError": "openreview_cli.gateway.errors",
    "SlotNotConfiguredError": "openreview_cli.gateway.errors",
    "TierRoutingError": "openreview_cli.gateway.errors",
    "CostRecord": "openreview_cli.gateway.models",
    "ModelEntry": "openreview_cli.gateway.models",
    "PrivacyTierReport": "openreview_cli.gateway.models",
    "ProviderInfo": "openreview_cli.gateway.models",
    "ModelRegistry": "openreview_cli.gateway.registry",
    "Gateway": "openreview_cli.gateway.router",
    "PrivacyTier": "openreview_cli.gateway.tier_config",
    "TierConfig": "openreview_cli.gateway.tier_config",
    "TierRouter": "openreview_cli.gateway.tier_router",
    "TierTracker": "openreview_cli.gateway.tier_tracker",
    "gateway_setup": "openreview_cli.gateway.wizard",
}

__all__ = [
    "AllProvidersFailedError",
    "AuthError",
    "CostRecord",
    "CostTracker",
    "Gateway",
    "GatewayError",
    "ModelEntry",
    "ModelNotFoundError",
    "ModelRegistry",
    "NoMatchingProviderError",
    "PIIUnavailableError",
    "PrivacyTier",
    "PrivacyTierReport",
    "ProviderInfo",
    "SlotNotConfiguredError",
    "TierConfig",
    "TierRouter",
    "TierRoutingError",
    "TierTracker",
    "gateway_setup",
]


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module = importlib.import_module(_LAZY[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
