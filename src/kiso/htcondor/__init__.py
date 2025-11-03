"""HTCondor software installation."""

from .configuration import HTCondorDaemon
from .installer import HTCondorInstaller
from .schema import SCHEMA

__all__ = (
    "SCHEMA",
    "DATACLASS",
    "INSTALLER",
)


#: Main class to represent HTCondor deployment configuration as a dataclass
DATACLASS = list[HTCondorDaemon]


#: Main class to install HTCondor
INSTALLER = HTCondorInstaller
