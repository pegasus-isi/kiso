"""Objects to represent Kiso Pegasus workflow experiment configuration."""
# ruff: noqa: UP007, UP045

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

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
    variables: dict[str, Union[str, int, float]] = field(default_factory=dict)

    #:
    description: Optional[str] = None

    #:
    inputs: Optional[list[Location]] = None

    #:
    outputs: Optional[list[Location]] = None
