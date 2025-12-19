"""Main class to check HTCondor configuration and install HTCondor."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from .configuration import Docker
from .schema import SCHEMA

from kiso import display, utils

if TYPE_CHECKING:
    from enoslib.objects import Roles
    from enoslib.task import Environment


log = logging.getLogger("kiso.software.docker")


console = Console()


class DockerInstaller:
    """Docker software installation."""

    #:
    schema: dict = SCHEMA

    #:
    config_type: type = Docker

    #:
    HAS_SOFTWARE_KEY: str = "has_docker"

    def __init__(self, config: Docker) -> None:
        """__init__ _summary_.

        _extended_summary_

        :param config: Docker configuration
        :type config: Docker
        """
        self.config = config

    def check(self, label_to_machines: Roles) -> None:
        """Check if the HTCondor configuration is valid."""
        if self.config is None:
            return

        log.debug("Check docker is not installed on Chameleon edge")
        self._check_docker_is_not_on_edge(label_to_machines)

    def _check_docker_is_not_on_edge(self, label_to_machines: Roles) -> None:
        """Check that Docker is not configured to run on Chameleon Edge devices.

        Validates that no Docker labels are assigned to Chameleon Edge resources,
        which is not supported. Raises a ValueError if such a configuration is detected.

        :param label_to_machines: Mapping of predefined labels
        :type label_to_machines: Roles
        :raises ValueError: If Docker labels are found on Chameleon Edge devices
        """
        labels = set(self.config.labels) if self.config.labels else set()
        if not labels:
            return

        machines: set = set()
        machines.update(_ for label in labels for _ in label_to_machines[label])

        if not machines:
            raise ValueError("No machines found to install Docker")

        docker_edge_machines = machines.intersection(
            label_to_machines["chameleon-edge"]
        )
        if docker_edge_machines:
            raise ValueError("Docker cannot be installed on Chameleon Edge devices")

    def __call__(self, env: Environment) -> None:
        """Install Docker on specified labels in an experiment configuration.

        Installs Docker on virtual machines and containers based on the provided
        configuration.
        Supports optional version specification and uses Ansible for VM installations.

        :param config: Configuration dictionary containing Docker
        installation details
        :type config: Docker
        :param env: Environment context for the installation
        :type env: Environment
        """
        if self.config is None:
            return

        log.debug("Install Docker")
        console.rule("[bold green]Installing Docker[/bold green]")

        labels = env["labels"]
        _labels = utils.resolve_labels(labels, self.config.labels)
        vms, containers = utils.split_labels(_labels, labels)
        if vms:
            results = utils.run_ansible([Path(__file__).parent / "main.yml"], roles=vms)
            for node in vms:
                # To each node we add a flag to identify if Docker is installed on
                # the node
                node.extra[self.HAS_SOFTWARE_KEY] = True

        if containers:
            raise RuntimeError(
                "Docker cannot be installed on containers, because Chameleon Edge does "
                "not allow setting privileged mode for containers"
            )

        display._render(console, results)
