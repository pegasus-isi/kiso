"""Ollama software installation."""

from .configuration import Ollama
from .installer import OllamaInstaller
from .schema import SCHEMA

__all__ = (
    "SCHEMA",
    "DATACLASS",
    "INSTALLER",
)

#: Main class to represent Ollama configuration as a dataclass
DATACLASS = list[Ollama]

#: Main function to install Ollama
INSTALLER = OllamaInstaller
