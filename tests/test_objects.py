"""Unit tests for kiso.objects dataclasses."""

from kiso.objects import Location, Script


def test_script_required_fields() -> None:
    s = Script(labels=["compute"], script="echo hello")
    assert s.labels == ["compute"]
    assert s.script == "echo hello"


def test_script_default_executable() -> None:
    s = Script(labels=[], script="echo hi")
    assert s.executable == "/bin/bash"


def test_script_custom_executable() -> None:
    s = Script(labels=["compute"], script="echo hi", executable="/bin/sh")
    assert s.executable == "/bin/sh"


def test_location_required_fields() -> None:
    loc = Location(labels=["compute"], src="/local/file.txt", dst="/remote/dir/")
    assert loc.labels == ["compute"]
    assert loc.src == "/local/file.txt"
    assert loc.dst == "/remote/dir/"
