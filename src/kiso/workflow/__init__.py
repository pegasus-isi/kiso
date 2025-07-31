"""Kiso Pegasus workflow runner plugin."""

from kiso.workflow.configuration import PegasusWorkflow
from kiso.workflow.pegasus import PegasusWMS
from kiso.workflow.schema import SCHEMA

__all__ = (
    "SCHEMA",
    "DATACLASS",
    "RUNNER",
)


#: Main class to represent Pegasus workflow experiment configuration as a dataclass
DATACLASS = PegasusWorkflow


#: Main class to run Pegasus workflow experiments
RUNNER = PegasusWMS
