"""Docker software installation."""

from .configuration import Docker
from .installer import DockerInstaller
from .schema import SCHEMA

__all__ = (
    "SCHEMA",
    "DATACLASS",
    "INSTALLER",
)

#: Main class to represent Docker configuration as a dataclass
DATACLASS = Docker

#: Main function to install Docker
INSTALLER = DockerInstaller
