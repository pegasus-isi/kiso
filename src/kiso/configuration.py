"""_summary_.

_extended_summary_
"""

# ruff: noqa: UP007

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from kiso import constants as const


@dataclass
class Site:
    """Site configuration."""

    #:
    kind: str


@dataclass
class CondorDaemon:
    """Condor daemon configuration."""

    #:
    roles: list[str]

    #:
    config_file: Optional[str] = None


@dataclass
class Condor:
    """Condor configuration."""

    #:
    central_manager: Optional[CondorDaemon] = None


@dataclass
class Docker:
    """Docker configuration."""

    #:
    roles: list[str]


@dataclass
class Apptainer:
    """Apptainer configuration."""

    #:
    roles: list[str]


@dataclass
class Script:
    """Script configuration."""

    #:
    roles: list[str]

    #:
    script: str

    #:
    executable: str = "/bin/bash"


@dataclass
class Location:
    """Location configuration."""

    #:
    roles: list[str]

    #:
    src: str

    #:
    dst: str


@dataclass
class Experiment:
    """Experiment configuration."""

    #:
    kind: str

    #:
    name: str

    #:
    main: str

    #:
    submit_node_roles: list[str]

    #:
    variables: dict[str, Union[str, int, float]] = field(default_factory=dict)

    #:
    args: Optional[list[Union[str, int, float]]] = None

    #:
    setup: Optional[list[Script]] = None

    #:
    input_locations: Optional[list[Location]] = None

    #:
    post_scripts: Optional[list[Script]] = None

    #:
    result_locations: Optional[list[Location]] = None

    #:
    count: int = 1

    #:
    interval: int = const.POLL_INTERVAL

    #:
    timeout: int = const.WORKFLOW_TIMEOUT


@dataclass
class Kiso:
    """Kiso configuration."""

    #:
    name: str

    #:
    sites: list[Site]

    #:
    experiments: list[Experiment]

    #:
    variables: dict[str, Union[str, int, float]] = field(default_factory=dict)

    #:
    condor: Optional[Condor] = None

    #:
    docker: Optional[Docker] = None

    #:
    apptainer: Optional[Apptainer] = None
