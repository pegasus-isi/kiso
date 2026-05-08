"""Objects to represent Kiso HTCondor deployment configuration."""

# ruff: noqa: UP045
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(unsafe_hash=True)
class HTCondorDaemon:
    """HTCondor daemon configuration."""

    #:
    kind: str

    #:
    labels: list[str] = field(default_factory=list, hash=False)

    #:
    config_file: Optional[str] = None
