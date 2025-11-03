"""Apptainer software installation."""

from .configuration import Apptainer
from .installer import ApptainerInstaller
from .schema import SCHEMA

__all__ = (
    "SCHEMA",
    "DATACLASS",
    "INSTALLER",
)


#: Main class to represent Apptainer configuration as a dataclass
DATACLASS = Apptainer

#: Main class to install Apptainer
INSTALLER = ApptainerInstaller
