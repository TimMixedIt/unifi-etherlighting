"""Safe, narrow exceptions for the controller adapter layer."""


class UniFiEtherlightingError(Exception):
    """Base error for this integration's controller boundary."""


class UniFiAuthenticationError(UniFiEtherlightingError):
    """The controller rejected the current authentication/session."""


class UniFiPermissionError(UniFiEtherlightingError):
    """The authenticated account lacks permission for an operation."""


class UniFiResponseError(UniFiEtherlightingError):
    """The controller returned an invalid or unsuccessful response."""


class UniFiTransportError(UniFiResponseError):
    """A transport failure occurred and a write may already have reached the controller."""

    def __init__(self, message: str, *, request_may_have_been_sent: bool) -> None:
        super().__init__(message)
        self.request_may_have_been_sent = request_may_have_been_sent


class UniFiSchemaError(UniFiResponseError):
    """A confirmed response no longer matches its captured schema."""


class CapabilityNotConfirmedError(UniFiEtherlightingError):
    """A write was requested for a capability that is not production-confirmed."""


class ReadPathNotConfirmedError(UniFiEtherlightingError):
    """No capture-confirmed read endpoint exists for the requested operation."""


class VerificationError(UniFiEtherlightingError):
    """Read-after-write verification did not preserve the expected state."""


class UnsupportedCompatibilityError(UniFiEtherlightingError):
    """The runtime controller/device tuple is not the exact confirmed tuple."""


class DeviceNotFoundError(UniFiEtherlightingError):
    """A selected Device was absent or not uniquely identifiable."""


class WriteBlockedError(UniFiEtherlightingError):
    """Further writes are blocked after an indeterminate result."""
