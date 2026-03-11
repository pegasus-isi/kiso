"""Main class to check Apptainer configuration and install Apptainer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from .configuration import Apptainer
from .schema import SCHEMA

from kiso import display, edge, utils

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
        """Initialize the ApptainerInstaller with the given configuration.

        :param config: Apptainer configuration, or None to disable Apptainer
            installation
        :type config: Apptainer
        """
        self.config = config

    def check(self, label_to_machines: Roles) -> None:
        """Check if the Apptainer configuration is valid."""
        if self.config is None:
            return

        log.debug(
            "Check labels referenced in apptainer section are defined in the sites "
            "section"
        )
        self._check_apptainer_labels(label_to_machines)

    def _check_apptainer_labels(self, label_to_machines: Roles) -> None:
        """Check that all Apptainer labels resolve to at least one machine.

        :param label_to_machines: Mapping of predefined labels to machines
        :type label_to_machines: Roles
        :raises ValueError: If no machines are found for the configured labels
        """
        labels = set(self.config.labels) if self.config.labels else set()
        if not labels:
            return

        machines: set = set()
        machines.update(_ for label in labels for _ in label_to_machines[label])

        if not machines:
            raise ValueError("No machines found to install Apptainer")

    def __call__(self, env: Environment) -> None:
        """Install Apptainer on the nodes specified in the configuration.

        Uses Ansible for VM installations and a shell script for Chameleon Edge
        container installations.

        :param env: Environment context containing label-to-host mappings
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
                    edge.run_script(
                        container,
                        Path(__file__).parent / "apptainer.sh",
                        "--no-dry-run",
                        timeout=-1,
                    )
                )
                # To each node we add a flag to identify if Apptainer is installed on
                # the node
                container.extra[self.HAS_SOFTWARE_KEY] = True

        display._render(console, results)
