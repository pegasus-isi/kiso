"""HTCondor software installation."""

# ruff: noqa: UP045
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ("DATACLASS",)


@dataclass
class HTCondorDaemon:
    """HTCondor daemon configuration."""

    #:
    kind: str

    #:
    labels: list[str]

    #:
    config_file: Optional[str] = None


#: Main class to represent Docker configuration as a dataclass
DATACLASS = list[HTCondorDaemon]
