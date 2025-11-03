"""Objects to represent Kiso Apptainer software configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Apptainer:
    """Apptainer configuration."""

    #:
    labels: list[str]
