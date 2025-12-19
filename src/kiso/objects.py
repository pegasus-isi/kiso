"""Common Kiso objects."""

from dataclasses import dataclass


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
