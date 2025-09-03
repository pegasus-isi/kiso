"""Apptainer software installation."""

from dataclasses import dataclass

__all__ = ("DATACLASS",)


@dataclass
class Apptainer:
    """Apptainer configuration."""

    #:
    labels: list[str]


#: Main class to represent Apptainer configuration as a dataclass
DATACLASS = Apptainer
