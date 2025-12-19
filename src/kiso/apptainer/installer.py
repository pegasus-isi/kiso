"""Main class to check HTCondor configuration andinstall HTCondor."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from .configuration import Apptainer
from .schema import SCHEMA

from kiso import display, utils

if TYPE_CHECKING:
    from enoslib.objects import Roles
    from enoslib.task import Environment


log = logging.getLogger("kiso.software.apptainer")


console = Console()


class ApptainerInstaller:
    """Apptainer software installation."""

    #:
    schema: dict = SCHEMA

    #:
    config_type: type = Apptainer

    #:
    HAS_SOFTWARE_KEY: str = "has_apptainer"

    def __init__(self, config: Apptainer) -> None:
        """__init__ _summary_.

        _extended_summary_

        :param config: Apptainer configuration
        :type config: Apptainer
        """
        self.config = config

    def check(self, label_to_machines: Roles) -> None:
        """Check if the HTCondor configuration is valid."""
        if self.config is None:
            return

        log.debug(
            "Check labels referenced in apptainer section are defined in the sites "
            "section"
        )
        self._check_apptainer_labels(label_to_machines)

    def _check_apptainer_labels(self, label_to_machines: Roles) -> None:
        """Check Apptainer labels in an experiment configuration.

        Validates that all Apptainer labels are defined.

        :param label_to_machines: Mapping of predefined labels
        :type label_to_machines: Roles
        :raises ValueError: If undefined labels are referenced or configuration files
        are missing
        """
        labels = set(self.config.labels) if self.config.labels else set()
        if not labels:
            return

        machines: set = set()
        machines.update(_ for label in labels for _ in label_to_machines[label])

        if not machines:
            raise ValueError("No machines found to install Apptainer")

    def __call__(self, env: Environment) -> None:
        """Install Apptainer on specified labels in an experiment configuration.

        Installs Apptainer on virtual machines and containers based on the provided
        configuration. Supports optional version specification and uses Ansible for VM
        installations and a script for container installations.

        :param config: Configuration dictionary containing Apptainer
        installation details
        :type config: Apptainer
        :param env: Environment context for the installation
        :type env: Environment
        """
        if self.config is None:
            return

        log.debug("Install Apptainer")
        console.rule("[bold green]Installing Apptainer[/bold green]")

        labels = env["labels"]
        _labels = utils.resolve_labels(labels, self.config.labels)
        vms, containers = utils.split_labels(_labels, labels)
        results = []

        if vms:
            results.extend(
                utils.run_ansible([Path(__file__).parent / "main.yml"], roles=vms)
            )
            for node in vms:
                # To each node we add a flag to identify if Apptainer is installed on
                # the node
                node.extra[self.HAS_SOFTWARE_KEY] = True

        if containers:
            for container in containers:
                results.append(
                    utils.run_script(
                        container,
                        Path(__file__).parent / "apptainer.sh",
                        "--no-dry-run",
                    )
                )
                # To each node we add a flag to identify if Apptainer is installed on
                # the node
                container.extra[self.HAS_SOFTWARE_KEY] = True

        display._render(console, results)
