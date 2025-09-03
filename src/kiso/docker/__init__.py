"""Docker software installation."""

from dataclasses import dataclass

__all__ = ("DATACLASS",)


@dataclass
class Docker:
    """Docker configuration."""

    #:
    labels: list[str]


#: Main class to represent Docker configuration as a dataclass
DATACLASS = Docker
