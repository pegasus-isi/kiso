"""Common Kiso objects."""

from dataclasses import dataclass


@dataclass
class Script:
    """Script configuration."""

    #: Labels identifying the target resources to run the script on.
    labels: list[str]

    #: The script content to be executed.
    script: str

    #: The executable (shebang) used to run the script.
    executable: str = "/bin/bash"


@dataclass
class Location:
    """Location configuration for file upload or download."""

    #: Labels identifying the target resources for the file transfer.
    labels: list[str]

    #: Source file path.
    src: str

    #: Destination directory path.
    dst: str
