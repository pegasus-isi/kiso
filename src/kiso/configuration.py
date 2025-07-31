"""Objects to represent Kiso experiment configuration."""

# ruff: noqa: UP007, UP045

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field, make_dataclass
from importlib.metadata import entry_points
from typing import Optional, Union, _SpecialForm

with contextlib.suppress(ImportError):
    from importlib.metadata import EntryPoints


@dataclass
class Site:
    """Site configuration."""

    #:
    kind: str


@dataclass
class Condor:
    """Condor configuration."""

    #:
    central_manager: Optional[CondorDaemon] = None


@dataclass
class CondorDaemon:
    """Condor daemon configuration."""

    #:
    roles: list[str]

    #:
    config_file: Optional[str] = None


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


def _get_experiment_kinds() -> _SpecialForm:
    all_eps: dict | EntryPoints = entry_points()
    if isinstance(all_eps, dict):
        all_eps = all_eps.get("kiso.wf", [])
    else:
        all_eps = all_eps.select(group="kiso.wf")

    kinds = []
    for ep in all_eps:
        kinds.append(ep.load().DATACLASS)

    return Union[tuple(kinds)]


Kiso = make_dataclass(
    "Kiso",
    [
        ("name", str),
        ("sites", list[Site]),
        (
            "experiments",
            list[_get_experiment_kinds()],  # type: ignore[misc]
        ),  # Dynamically constructed type
        ("variables", dict[str, Union[str, int, float]], field(default_factory=dict)),
        ("condor", Optional[Condor], field(default=None)),
        ("docker", Optional[Docker], field(default=None)),
        ("apptainer", Optional[Apptainer], field(default=None)),
    ],
)
