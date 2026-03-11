"""Kiso error classes."""


class KisoError(Exception):
    """Base exception class for all Kiso errors."""


class KisoValueError(KisoError):
    """Raised when an invalid value is detected in Kiso configuration or execution."""


class KisoTimeoutError(KisoError):
    """Raised when a Kiso operation exceeds its allowed time limit."""
