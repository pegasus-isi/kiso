"""Main class to check HTCondor configuration andinstall HTCondor."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from .configuration import Ollama
from .schema import SCHEMA

from kiso import display, utils

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
        """__init__ _summary_.

        _extended_summary_

        :param config: Ollama configuration
        :type config: Ollama
        """
        self.config = config

    def check(self, label_to_machines: Roles) -> None:
        """Check if the Ollama configuration is valid."""
        log.debug(
            "Check labels referenced in ollama section are defined in the sites section"
        )
        self._check_ollama_labels(label_to_machines)

    def _check_ollama_labels(self, label_to_machines: Roles) -> None:
        """Check Apptainer labels in an experiment configuration.

        Validates that all Apptainer labels are defined.

        :param label_to_machines: Mapping of predefined labels
        :type label_to_machines: Roles
        :raises ValueError: If undefined labels are referenced or configuration files
        are missing
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
        """Install Ollama on specified labels in an experiment configuration.

        Installs Ollama on virtual machines and containers based on the provided
        configuration.
        Supports optional version specification and uses Ansible for VM installations.

        :param config: Configuration dictionary containing Ollama
        installation details
        :type config: Ollama
        :param env: Environment context for the installation
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
                        utils.run_script(
                            container,
                            Path(__file__).parent / "ollama.sh",
                            "--no-dry-run",
                        )
                    )
                    # To each node we add a flag to identify if Ollama is installed on
                    # the node
                    container.extra[self.HAS_SOFTWARE_KEY] = True

        display._render(console, results)
