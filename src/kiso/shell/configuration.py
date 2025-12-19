"""Objects to represent Kiso Pegasus workflow experiment configuration."""
# ruff: noqa: UP007, UP045

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from kiso.objects import Location, Script  # noqa: TC001


@dataclass
class ShellConfiguration:
    """Shell Experiment configuration."""

    #:
    kind: str

    #:
    name: str

    #:
    scripts: list[Script]

    #:
    description: Optional[str] = None

    #:
    outputs: Optional[list[Location]] = None
