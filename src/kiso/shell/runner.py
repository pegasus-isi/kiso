"""Kiso Pegasus workflow runner implementation."""

from __future__ import annotations

import copy
import logging
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from enoslib.objects import Roles
from enoslib.task import Environment
from rich.console import Console

from .configuration import ShellConfiguration
from .schema import SCHEMA

import kiso.constants as const
from kiso import edge, utils
from kiso.shell import display
from kiso.utils import experiment_state

if TYPE_CHECKING:
    import enoslib as en
    from enoslib.api import CommandResult, CustomCommandResult
    from enoslib.objects import Environment, Roles

    if hasattr(en, "ChameleonEdge"):
        pass
    from kiso.configuration import Kiso
    from kiso.objects import Location, Script


console = Console()


log = logging.getLogger("kiso.experiment.shell")


class ShellRunner:
    """Runner that executes shell scripts directly on provisioned infrastructure.

    Handles input staging, sequential script execution, and result fetching
    for a single shell experiment entry in the Kiso configuration.
    """

    #:
    schema: dict = SCHEMA

    #:
    config_type: type = ShellConfiguration

    #:
    kind: str = "shell"

    def __init__(
        self,
        experiment: ShellConfiguration,
        index: int,
        variables: dict[str, str | int | float] | None = None,
    ) -> None:
        """Initialise the runner from a shell experiment configuration entry.

        :param experiment: Shell experiment configuration
        :type experiment: ShellConfiguration
        :param index: Zero-based position of this experiment in the experiments list
        :type index: int
        :param variables: Globally defined variables to merge with per-experiment
            variables, defaults to None
        :type variables: dict[str, str | int | float] | None, optional
        """
        self.index = index
        self.variables = copy.deepcopy(variables or {})

        # Experiment configuration
        self.experiment = experiment
        self.name = experiment.name
        self.scripts = experiment.scripts
        self.inputs = experiment.inputs or []
        self.outputs = experiment.outputs or []
        self.poll_interval = const.POLL_INTERVAL
        self.timeout = const.WORKFLOW_TIMEOUT

    def check(self, config: Kiso, label_to_machines: Roles) -> None:
        """Validate the shell experiment configuration against the overall Kiso config.

        Verifies that all labels referenced in the experiment's scripts and
        outputs are defined in the sites section.

        :param config: The complete Kiso experiment configuration
        :type config: Kiso
        :param label_to_machines: Mapping of defined labels to their machine sets
        :type label_to_machines: Roles
        """
        self._check_undefined_labels(config, label_to_machines)

    def _check_undefined_labels(
        self, experiment_config: Kiso, label_to_machines: dict[str, set]
    ) -> None:
        """Check for undefined labels in experiment configuration.

        Validates that all labels referenced in experiment setup, input locations,
        and result locations are defined in the experiment configuration.

        :param experiment_config: Complete experiment configuration dictionary
        :type experiment_config: Kiso
        :param label_to_machines: Mapping of predefined labels in the configuration
        :type label_to_machines: dict[str, set]
        :raises ValueError: If any undefined labels are found in the experiment
        configuration
        """
        unlabel_to_machines = defaultdict(set)
        for experiment in experiment_config.experiments:
            if experiment.kind != "shell":
                continue

            for index, script in enumerate(experiment.scripts or []):
                unlabel_to_machines[experiment.name].update(
                    [
                        (f"scripts[{index}]", label)
                        for label in script.labels
                        if label not in label_to_machines
                    ]
                )

            for index, location in enumerate(experiment.outputs or []):
                unlabel_to_machines[experiment.name].update(
                    [
                        (f"outputs[{index}]", label)
                        for label in location.labels
                        if label not in label_to_machines
                    ]
                )

            if not unlabel_to_machines[experiment.name]:
                del unlabel_to_machines[experiment.name]
        else:
            if unlabel_to_machines:
                raise ValueError(
                    "Undefined labels referenced in experiments section",
                    unlabel_to_machines,
                )

    def __call__(
        self, wd: str, remote_wd: str, resultdir: str, labels: Roles, env: Environment
    ) -> None:
        """Execute the shell experiment: copy inputs, run scripts, fetch outputs.

        :param wd: Local experiment working directory
        :type wd: str
        :param remote_wd: Remote working directory on provisioned resources
        :type remote_wd: str
        :param resultdir: Local directory where experiment results are collected
        :type resultdir: str
        :param labels: All provisioned resources keyed by label
        :type labels: Roles
        :param env: EnOSlib task environment used to persist step state
        :type env: Environment
        """
        self.wd = wd
        self.remote_wd = remote_wd
        self.resultdir = resultdir
        self.labels = labels
        self.env = env

        self._copy_inputs()
        self._run_scripts()
        self._fetch_outputs()

    def _copy_inputs(self) -> None:
        """Copy input files to specified destinations across virtual machines and containers.

        Iterates through input locations defined in the experiment configuration, resolving
        labels and copying files to their destination. Supports copying to both virtual
        machines and containers while tracking the status of each copy operation.
        """  # noqa: E501
        name = self.name
        inputs = self.inputs
        if not inputs:
            return

        log.debug("Copy inputs to the destination for <%s:%d>", name, self.index)
        console.print(rf"\[{name}] Copying inputs to the destination")

        self.env.setdefault("copy-input", {})
        results = []
        for instance, location in enumerate(inputs):
            result = self._copy_input(instance, location)
            results.append((instance, location, result))

        display.inputs(console, results)

    def _copy_input(
        self, instance: int, input: Location
    ) -> list[CommandResult | CustomCommandResult]:
        """Copy input file to specified destination on virtual machines and containers.

        Resolving labels and copying files to their destination. Supports copying to
        both virtual machines and containers while tracking the status of each copy
        operation.

        :param instance: Zero-based index of this input in the inputs list
        :type instance: int
        :param input: Input file location configuration
        :type input: Location
        :return: List of CommandResult or CustomCommandResult objects
        :rtype: list[CommandResult | CustomCommandResult]
        """
        results: list[CommandResult | CustomCommandResult] = []
        labels = self.labels
        _labels = utils.resolve_labels(labels, input.labels)
        vms, containers = utils.split_labels(_labels, labels)
        src = Path(input.src)
        dst = Path(input.dst)

        kiso_state_key = "copy-input"
        with experiment_state(self.env, kiso_state_key, instance) as state:
            if state.status == const.STATUS_OK:
                return results

            if not src.exists():
                log.debug("Input file <%s> does not exist, skipping copy", src)
                return results
            if vms:
                with utils.actions(
                    roles=vms,
                    run_as=const.KISO_USER,
                    on_error_continue=True,
                    strategy="free",
                ) as p:
                    p.copy(
                        src=str(src),
                        dest=str(dst),
                        mode="preserve",
                        task_name=f"Copy input file {instance}",
                    )
                results.extend(p.results)
            if containers:
                for container in containers:
                    results.append(
                        edge.upload(container, src, dst, user=const.KISO_USER)
                    )

        return results

    def _run_scripts(self) -> None:
        """Run scripts for an experiment across specified labels.

        Executes scripts defined in the experiment configuration on virtual
        machines and containers. Handles script preparation, copying, and execution
        while tracking the status of each script to run.
        """
        name = self.name
        scripts = self.scripts
        if not scripts:
            return

        log.debug("Run scripts for <%s:%d>", name, self.index)
        console.rule(
            f"[bold green]Experiment {self.index + 1}: {self.name}[/bold green]"
        )

        self.env.setdefault("run-script", {})
        results = []
        for instance, script in enumerate(scripts):
            result = self._run_script(instance, script)
            results.append((instance, script, result))

        display.scripts(console, results)

    def _run_script(
        self, instance: int, setup_script: Script
    ) -> list[CommandResult | CustomCommandResult]:
        """Run scripts for an experiment across specified labels.

        Executes scripts defined in the experiment configuration on virtual
        machines and containers. Handles script preparation, copying, and execution
        while tracking the status of each script run.

        :param instance: Zero-based index of this script in the scripts list
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
                    roles=vms,
                    run_as=const.KISO_USER,
                    on_error_continue=True,
                    strategy="free",
                ) as p:
                    p.copy(
                        src=script.name,
                        dest=dst,
                        mode="preserve",
                        task_name=f"Copy script {instance}",
                    )
                    p.shell(f"{executable} {dst}", chdir=self.remote_wd)
                    p.shell(f"rm -rf {dst}", chdir=self.remote_wd)
                results.extend(p.results)
            if containers:
                for container in containers:
                    results.append(
                        edge.run_script(
                            container,
                            Path(script.name),
                            user=const.KISO_USER,
                            workdir=self.remote_wd,
                        )
                    )

        return results

    def _fetch_outputs(self) -> None:
        """Copy output files from remote machines and containers to a local destination.

        Iterates through specified outputs, resolves target labels, and fetches
        output files from VMs and containers to a local destination directory.
        """
        name = self.name
        outputs = self.outputs
        if not outputs:
            return

        log.debug("Copy outputs to the destination for <%s:%d>", name, self.index)
        console.print(rf"\[{name}-{self.index}] Copying outputs to the destination")

        self.env.setdefault("fetch-output", {})
        results = []
        for _index, location in enumerate(outputs):
            result = self._fetch_output(_index, location)
            results.append((_index, location, result))

        display.outputs(console, results)

    def _fetch_output(
        self, instance: int, output: Location
    ) -> list[CommandResult | CustomCommandResult]:
        """Copy output file from remote machines and containers to a local destination.

        Resolves target labels, and fetches output files from VMs and containers to a
        local destination directory.

        :param instance: Zero-based index of this output in the outputs list
        :type instance: int
        :param output: Output file location configuration
        :type output: Location
        :return: List of CommandResult or CustomCommandResult objects
        :rtype: list[CommandResult | CustomCommandResult]
        """
        results: list[CommandResult | CustomCommandResult] = []
        labels = self.labels
        _labels = utils.resolve_labels(labels, output.labels)
        vms, containers = utils.split_labels(_labels, labels)

        src = Path(output.src)
        if not src.is_absolute() and output.src[0] != "~":
            src = Path(self.remote_wd) / src

        dst = Path(output.dst)
        if not dst.exists():
            log.debug("Destination directory <%s> does not exist, creating it", dst)
            dst.mkdir(parents=True)

        kiso_state_key = "fetch-output"
        with experiment_state(self.env, kiso_state_key, instance) as state:
            if state.status == const.STATUS_OK:
                return results

            if vms:
                with utils.actions(roles=vms, run_as=const.KISO_USER) as p:
                    p.synchronize(
                        mode="pull",
                        src=str(src),
                        dest=f"{dst}/",
                        use_ssh_args=True,
                        task_name=f"Fetch output file {instance}",
                    )
                results.extend(p.results)
            if containers:
                for container in containers:
                    results.append(edge.download(container, src, dst))

        return results
