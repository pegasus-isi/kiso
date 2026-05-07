"""Objects to represent Kiso Docker software configuration."""

from dataclasses import dataclass


@dataclass
class Docker:
    """Docker configuration."""

    #:
    labels: list[str]
