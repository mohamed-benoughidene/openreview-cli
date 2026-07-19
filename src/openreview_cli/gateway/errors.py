class GatewayError(Exception):
    pass


class SlotNotConfiguredError(GatewayError):
    pass


class AllProvidersFailedError(GatewayError):
    pass


class AuthError(GatewayError):
    def __init__(self, provider: str, message: str = "") -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"auth failed for {provider}: {message}")

    def __str__(self) -> str:
        return f"auth failed for {self.provider}: {self.message}"


class ModelNotFoundError(GatewayError):
    def __init__(self, provider: str, message: str = "") -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"model not found for {provider}: {message}")

    def __str__(self) -> str:
        return f"model not found for {self.provider}: {self.message}"


class CapabilityMismatchError(GatewayError):
    def __init__(self, provider: str, detail: str) -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(f"capability mismatch for {provider}: {detail}")

    def __str__(self) -> str:
        return f"capability mismatch for {self.provider}: {self.detail}"


class RateLimitError(GatewayError):
    def __init__(self, provider: str, message: str = "") -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"rate limit exceeded for {provider}: {message}")

    def __str__(self) -> str:
        return f"rate limit exceeded for {self.provider}: {self.message}"


class ConnectionError(GatewayError):
    def __init__(
        self,
        provider: str,
        message: str = "",
        timeout_kind: str | None = None,
    ) -> None:
        self.provider = provider
        self.message = message
        self.timeout_kind = timeout_kind
        suffix = f" [{timeout_kind}]" if timeout_kind else ""
        super().__init__(f"connection failed for {provider}{suffix}: {message}")

    def __str__(self) -> str:
        if self.timeout_kind:
            return f"connection failed for {self.provider} [{self.timeout_kind}]: {self.message}"
        return f"connection failed for {self.provider}: {self.message}"


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


# ── Custom Provider Registration Errors ──────────────────────────────────────


class ProviderNameCollisionError(GatewayError):
    """Raised when a custom provider name already exists in the registry."""

    def __init__(self, provider: str, message: str = "") -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"provider name collision for {provider}: {message}")

    def __str__(self) -> str:
        return f"provider name collision for {self.provider}: {self.message}"


class EnvKeyCollisionError(GatewayError):
    """Raised when a derived API key env var already exists in the registry."""

    def __init__(
        self,
        provider: str,
        env_key: str,
        existing: str = "",
        message: str = "",
    ):
        self.provider = provider
        self.env_key = env_key
        self.existing = existing
        self.message = message
        super().__init__(
            f"provider {provider} derives to env var {env_key} "
            f"already used by {existing or 'another provider'}"
        )

    def __str__(self) -> str:
        return (
            f"provider {self.provider} derives to env var {self.env_key} "
            f"already used by {self.existing or 'another provider'}"
        )


class EmptyMessagesError(GatewayError):
    pass
