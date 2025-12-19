"""Objects to represent Kiso experiment configuration."""

# ruff: noqa: UP007, UP045

from __future__ import annotations

import contextlib
from dataclasses import field, make_dataclass
from importlib.metadata import entry_points
from typing import Any, Optional, Union, _SpecialForm

from kiso import constants as const

with contextlib.suppress(ImportError):
    from importlib.metadata import EntryPoints


def _get_experiment_kinds() -> _SpecialForm:
    kinds = _get_kinds(const.KISO_EXPERIMENT_ENTRY_POINT_GROUP)
    return Union[tuple(kind[1] for kind in kinds)]


def _get_software_type() -> type:
    kinds = _get_kinds(const.KISO_SOFTWARE_ENTRY_POINT_GROUP)
    return make_dataclass("Software", [(kind[0], Optional[kind[1]]) for kind in kinds])


def _get_deployment_type() -> type:
    kinds = _get_kinds(const.KISO_DEPLOYMENT_ENTRY_POINT_GROUP)
    return make_dataclass(
        "Deployment", [(kind[0], Optional[kind[1]]) for kind in kinds]
    )


def _get_kinds(kind: str) -> set:
    all_eps: dict | EntryPoints = entry_points()
    if isinstance(all_eps, dict):
        all_eps = all_eps.get(kind, [])
    else:
        all_eps = all_eps.select(group=kind)

    kinds = set()
    for ep in all_eps:
        kinds.add((ep.name, ep.load().config_type))

    return kinds


Deployment = _get_deployment_type()


Software = _get_software_type()


ExperimentTypes = _get_experiment_kinds()


Kiso = make_dataclass(
    "Kiso",
    [
        ("name", str),
        ("sites", list[dict[str, Any]]),
        (
            "experiments",
            list[ExperimentTypes],  # type: ignore[valid-type]
        ),  # Dynamically constructed type
        ("deployment", Optional[Deployment]),  # Dynamically constructed type
        ("software", Optional[Software]),  # Dynamically constructed type
        ("variables", dict[str, Union[str, int, float]], field(default_factory=dict)),
    ],
)
