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
