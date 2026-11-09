"""Exceptions for OVapi Client."""


class OvapiError(Exception):
    """Base exception for all OVapi client errors."""


class OvapiConnectionError(OvapiError):
    """Raised when connecting to OVapi fails."""


class OvapiStopNotFoundError(OvapiError):
    """Raised when the specified TimingPointCode (TPC) is not found."""


class OvapiParseError(OvapiError):
    """Raised when parsing OVapi response data fails."""
