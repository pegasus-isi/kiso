"""Kiso Shell experiment runner plugin."""

from kiso.shell.configuration import ShellConfiguration
from kiso.shell.runner import ShellRunner
from kiso.shell.schema import SCHEMA

__all__ = (
    "SCHEMA",
    "DATACLASS",
    "RUNNER",
)


#: Main class to represent Pegasus workflow experiment configuration as a dataclass
DATACLASS = ShellConfiguration


#: Main class to run Pegasus workflow experiments
RUNNER = ShellRunner
