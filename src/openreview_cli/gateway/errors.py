class GatewayError(Exception):
    pass


class SlotNotConfiguredError(GatewayError):
    pass


class AllProvidersFailedError(GatewayError):
    pass


class AuthError(GatewayError):
    pass


class ModelNotFoundError(GatewayError):
    pass


# ── Privacy Tier Errors ─────────────────────────────────────────────────────


class TierRoutingError(GatewayError):
    """Base error for privacy tier routing failures."""

    pass


class PIIUnavailableError(TierRoutingError):
    """Raised when PII engine is unavailable and a cloud call requires it."""

    pass


class NoMatchingProviderError(TierRoutingError):
    """Raised when no provider matches the current tier's routing rules."""

    pass
