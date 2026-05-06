"""Kiso error classes."""


class KisoError(Exception):
    """Base exception class for all Kiso errors."""


class KisoValueError(KisoError, ValueError):
    """Raised when an invalid value is detected in Kiso configuration or execution."""


class KisoTimeoutError(KisoError, TimeoutError):
    """Raised when a Kiso operation exceeds its allowed time limit."""


class KisoCheckError(KisoError):
    """Raised when validation of experiment specification fails."""

    def __init__(self, message: str, errors: list[Exception]) -> None:
        """Initialize the exception with a list of errors.

        :param message: Error message
        :type message: str
        :param errors: List of validation errors
        :type errors: list[Exception]
        """
        super().__init__(message)
        self.errors = errors


class KisoUpError(KisoError):
    """Raised when provisioning fails during Kiso up operation."""

    def __init__(self, message: str, errors: dict[int, Exception]) -> None:
        """Initialize the exception with a dictionary of errors.

        :param message: Error message
        :type message: str
        :param errors: Dictionary of site index to error
        :type errors: dict[int, Exception]
        """
        super().__init__(message)
        self.errors = errors


class KisoDownError(KisoError):
    """Raised when deprovisioning fails during Kiso down operation."""
