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
    """_summary_.

    _extended_summary_
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
        """__init__ _summary_.

        _extended_summary_

        :param experiment: Experiment configuration
        :type experiment: PegasusWorkflow
        :param index: Experiment index
        :type index: int
        :param variables: Globally defined variables, defaults to None
        :type variables: dict[str, str  |  int  |  float] | None, optional
        """
        self.index = index
        self.variables = copy.deepcopy(variables or {})

        # Experiment configuration
        self.experiment = experiment
        self.name = experiment.name
        self.scripts = experiment.scripts
        self.outputs = experiment.outputs or []
        self.poll_interval = const.POLL_INTERVAL
        self.timeout = const.WORKFLOW_TIMEOUT

    def check(self, config: Kiso, label_to_machines: Roles) -> None:
        """Check  summary_.

        _extended_summary_

        :param label_to_machines: _description_
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
        """__call__ _summary_.

        _extended_summary_

        :param wd: Experiment working directory
        :type wd: str
        :param remote_wd: Remote experiment working directory
        :type remote_wd: str
        :param resultdir: Results directory
        :type resultdir: str
        :param labels: All provisioned resources
        :type labels: Roles
        :param env: Environment context
        :type env: Environment
        """
        self.wd = wd
        self.remote_wd = remote_wd
        self.resultdir = resultdir
        self.labels = labels
        self.env = env

        self._run_scripts()
        self._fetch_outputs()

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

        :param instance: The specific instance number of the setup_script
        :type index: int
        :param index: The overall experiment index
        :type index: int
        :param setup_script: Configuration dictionary containing setup_script details
        :type setup_script: dict
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
                        utils.run_script(
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

        :param instance: Output instance index
        :type instance: int
        :param index: Experiment index in the environment configuration
        :type index: int
        :param output: Output file configuration dictionary
        :type output: dict
        :param env: Global environment configuration
        :type env: Environment
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
