"""Unit tests for kiso.errors exception hierarchy."""

import pytest

from kiso.errors import KisoError, KisoTimeoutError, KisoValueError


def test_kiso_error_is_exception() -> None:
    assert issubclass(KisoError, Exception)


def test_kiso_value_error_is_kiso_error() -> None:
    assert issubclass(KisoValueError, KisoError)


def test_kiso_timeout_error_is_kiso_error() -> None:
    assert issubclass(KisoTimeoutError, KisoError)


def test_kiso_error_raise_and_catch() -> None:
    with pytest.raises(KisoError, match="boom"):
        raise KisoError("boom")


def test_kiso_value_error_raise_and_catch() -> None:
    with pytest.raises(KisoError):
        raise KisoValueError("bad value")


def test_kiso_timeout_error_raise_and_catch() -> None:
    with pytest.raises(KisoError):
        raise KisoTimeoutError("timed out")
