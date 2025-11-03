"""Objects to represent Kiso HTCondor deployment configuration."""

# ruff: noqa: UP045
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HTCondorDaemon:
    """HTCondor daemon configuration."""

    #:
    kind: str

    #:
    labels: list[str]

    #:
    config_file: Optional[str] = None
