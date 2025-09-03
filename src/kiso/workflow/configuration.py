"""Objects to represent Kiso Pegasus workflow experiment configuration."""
# ruff: noqa: UP007, UP045

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from kiso import constants as const


@dataclass
class PegasusWorkflow:
    """Experiment configuration."""

    #:
    kind: str

    #:
    name: str

    #:
    main: str

    #:
    submit_node_labels: list[str]

    #:
    variables: dict[str, Union[str, int, float]] = field(default_factory=dict)

    #:
    args: Optional[list[Union[str, int, float]]] = None

    #:
    setup: Optional[list[Script]] = None

    #:
    inputs: Optional[list[Location]] = None

    #:
    post_scripts: Optional[list[Script]] = None

    #:
    outputs: Optional[list[Location]] = None

    #:
    count: int = 1

    #:
    poll_interval: int = const.POLL_INTERVAL

    #:
    timeout: int = const.WORKFLOW_TIMEOUT


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
