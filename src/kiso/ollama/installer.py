"""Main class to check Ollama configuration and install Ollama."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from .configuration import Ollama
from .schema import SCHEMA

from kiso import display, edge, utils

if TYPE_CHECKING:
    from enoslib.objects import Roles
    from enoslib.task import Environment


log = logging.getLogger("kiso.software.ollama")


console = Console()


class OllamaInstaller:
    """Ollama software installation."""

    #:
    schema: dict = SCHEMA

    #:
    config_type: type = list[Ollama]

    #:
    HAS_SOFTWARE_KEY: str = "has_ollama"

    def __init__(
        self,
        config: list[Ollama],
    ) -> None:
        """Initialize the OllamaInstaller with the given configuration.

        :param config: List of Ollama configurations, or None to disable installation
        :type config: list[Ollama]
        """
        self.config = config

    def check(self, label_to_machines: Roles) -> None:
        """Check if the Ollama configuration is valid."""
        log.debug(
            "Check labels referenced in ollama section are defined in the sites section"
        )
        self._check_ollama_labels(label_to_machines)

    def _check_ollama_labels(self, label_to_machines: Roles) -> None:
        """Check that all Ollama labels resolve to at least one machine.

        :param label_to_machines: Mapping of predefined labels to machines
        :type label_to_machines: Roles
        :raises ValueError: If no machines are found for any configured Ollama section
        """
        if not self.config:
            return

        for index, section in enumerate(self.config):
            labels = set(section.labels) if section.labels else set()
            machines: set = set()
            machines.update(_ for label in labels for _ in label_to_machines[label])

            if not machines:
                raise ValueError(
                    f"No machines found to install Ollama for $.software.ollama.{index}"
                )

    def __call__(self, env: Environment) -> None:
        """Install Ollama on the nodes specified in each configuration section.

        Iterates over all Ollama configuration sections and installs Ollama on the
        matching nodes. Uses Ansible for VM installations and a shell script for
        Chameleon Edge container installations.

        :param env: Environment context containing label-to-host mappings
        :type env: Environment
        """
        if self.config is None:
            return

        log.debug("Install Ollama")
        console.rule("[bold green]Installing Ollama[/bold green]")
        results = []
        labels = env["labels"]
        for section in self.config:
            _labels = utils.resolve_labels(labels, section.labels)
            vms, containers = utils.split_labels(_labels, labels)
            if vms:
                extra_vars: dict = {
                    "models": section.models,
                }
                if section.environment:
                    extra_vars["config"] = section.environment

                results.extend(
                    utils.run_ansible(
                        [Path(__file__).parent / "main.yml"],
                        roles=vms,
                        extra_vars=extra_vars,
                    )
                )
                for node in vms:
                    # To each node we add a flag to identify if Ollama is installed on
                    # the node
                    node.extra[self.HAS_SOFTWARE_KEY] = True

            if containers:
                for container in containers:
                    results.append(
                        edge.run_script(
                            container,
                            Path(__file__).parent / "ollama.sh",
                            "--no-dry-run",
                            timeout=-1,
                        )
                    )
                    # To each node we add a flag to identify if Ollama is installed on
                    # the node
                    container.extra[self.HAS_SOFTWARE_KEY] = True

        display._render(console, results)
