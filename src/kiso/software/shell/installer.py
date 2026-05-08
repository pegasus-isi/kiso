"""Main class to check Shell software configuration and run shell scripts."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from .configuration import Script
from .schema import SCHEMA

from kiso import constants as const
from kiso import edge, utils
from kiso.software.shell import display
from kiso.utils import experiment_state

if TYPE_CHECKING:
    from enoslib.api import CommandResult, CustomCommandResult
    from enoslib.objects import Roles
    from enoslib.task import Environment


log = logging.getLogger("kiso.software.shell")


console = Console()


class ShellSoftwareInstaller:
    """Shell software installation."""

    #:
    schema: dict = SCHEMA

    #:
    config_type: type = list[Script]

    #:
    HAS_SOFTWARE_KEY: str = "has_shell"

    def __init__(self, config: list[Script]) -> None:
        """Initialize the ShellSoftwareInstaller with the given configuration.

        :param config: List of shell script configurations, or None to skip
        :type config: list[Script]
        """
        self.config = config

    def check(self, label_to_machines: Roles) -> None:
        """Check if the Shell configuration is valid."""
        log.debug(
            "Check labels referenced in shell section are defined in the sites section"
        )
        self._check_shell_labels(label_to_machines)

    def _check_shell_labels(self, label_to_machines: Roles) -> None:
        """Check that all shell script labels resolve to at least one machine.

        :param label_to_machines: Mapping of predefined labels to machines
        :type label_to_machines: Roles
        :raises ValueError: If no machines are found for any configured section
        """
        if not self.config:
            return

        for index, section in enumerate(self.config):
            labels = set(section.labels) if section.labels else set()
            machines: set = set()
            machines.update(_ for label in labels for _ in label_to_machines[label])

            if not machines:
                raise ValueError(
                    f"No machines found to run shell scripts for "
                    f"$.software.shell.{index}"
                )

    def __call__(self, env: Environment) -> None:
        """Run shell scripts on the nodes specified in each configuration section.

        :param env: Environment context containing label-to-host mappings
        :type env: Environment
        """
        if self.config is None:
            return

        self.labels = env["labels"]
        self.env = env

        self._run_scripts()

    def _run_scripts(self) -> None:
        """Run all shell software scripts across their target nodes.

        Executes each script section defined in the software configuration on virtual
        machines and containers. Handles script preparation, copying, and execution
        while tracking the status of each script to run.
        """
        scripts = self.config
        if not scripts:
            return

        log.debug("Run shell software scripts")
        console.rule("[bold green]Running Shell Software Scripts[/bold green]")

        self.env.setdefault("run-script", {})
        results = []
        for instance, script in enumerate(scripts):
            result = self._run_script(instance, script)
            results.append((instance, script, result))

        display.scripts(console, results)

    def _run_script(
        self, instance: int, setup_script: Script
    ) -> list[CommandResult | CustomCommandResult]:
        """Execute a single shell software script section on its target nodes.

        Copies the script to each target node and executes it. Supports both virtual
        machines (via Ansible actions) and Chameleon Edge containers (via edge
        run_script).

        :param instance: Zero-based index of this script section in the config list
        :type instance: int
        :param setup_script: Script configuration (labels, executable, and content)
        :type setup_script: Script
        :return: List of CommandResult or CustomCommandResult objects
        :rtype: list[CommandResult | CustomCommandResult]
        """
        results: list[CommandResult | CustomCommandResult] = []
        labels = self.labels
        _labels = utils.resolve_labels(labels, setup_script.labels)
        vms, containers = utils.split_labels(_labels, labels)
        executable = setup_script.executable

        kiso_state_key = "run-script"
        with (
            experiment_state(self.env, kiso_state_key, instance) as state,
            tempfile.NamedTemporaryFile() as script,
        ):
            if state.status == const.STATUS_OK:
                return results

            dst = str(Path(const.TMP_DIR) / Path(script.name).name)

            script.write(f"#!{executable}\n".encode())
            script.write(setup_script.script.encode())
            script.seek(0)

            if vms:
                with utils.actions(
                    roles=vms, run_as=const.KISO_USER, strategy="free"
                ) as p:
                    p.copy(
                        src=script.name,
                        dest=dst,
                        mode="preserve",
                        task_name=f"Copy script {instance}",
                    )
                    p.shell(f"{executable} {dst}", chdir=const.TMP_DIR)
                    p.shell(f"rm -rf {dst}", chdir=const.TMP_DIR)
                results.extend(p.results)

                for node in vms:
                    # To each node we add a flag to identify if Ollama is installed on
                    # the node
                    node.extra[self.HAS_SOFTWARE_KEY] = True

            if containers:
                for container in containers:
                    results.append(
                        edge.run_script(container, Path(script.name), timeout=-1)
                    )
                    # To each node we add a flag to identify if Ollama is installed on
                    # the node
                    container.extra[self.HAS_SOFTWARE_KEY] = True

        return results
