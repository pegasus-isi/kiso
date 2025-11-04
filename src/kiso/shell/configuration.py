"""Objects to represent Kiso Pegasus workflow experiment configuration."""
# ruff: noqa: UP007, UP045

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ShellConfiguration:
    """Shell Experiment configuration."""

    #:
    kind: str

    #:
    name: str

    #:
    description: str

    #:
    scripts: list[Script]

    #:
    outputs: Optional[list[Location]] = None


@dataclass
class Script:
    """Script configuration."""

    #:
    labels: list[str]

    #:
    script: str

    #:
    executable: str = "/bin/bash"


@dataclass
class Location:
    """Location configuration."""

    #:
    labels: list[str]

    #:
    src: str

    #:
    dst: str
