"""Objects to represent Kiso Ollama software configuration."""

# ruff: noqa: UP007, UP045
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class Ollama:
    """Ollama configuration."""

    #:
    labels: list[str]

    #:
    models: list[str]

    #:
    environment: Optional[dict[str, Union[str, int, float]]]
