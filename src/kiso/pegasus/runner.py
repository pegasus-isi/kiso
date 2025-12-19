"""Kiso Pegasus workflow runner implementation."""

from __future__ import annotations

import copy
import json
import logging
import re
import shlex
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import enoslib as en
from enoslib.objects import Host, Roles
from enoslib.task import Environment
from rich.console import Console

from .configuration import PegasusConfiguration
from .schema import SCHEMA

import kiso.constants as const
from kiso import edge, utils
from kiso.errors import KisoTimeoutError, KisoValueError
from kiso.pegasus import display
from kiso.pegasus.display import PegasusWorkflowProgress
from kiso.utils import experiment_state

if TYPE_CHECKING:
    from enoslib.api import CommandResult, CustomCommandResult
    from enoslib.objects import Environment, Roles

    if hasattr(en, "ChameleonEdge"):
        from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice

    from kiso.configuration import Kiso
    from kiso.objects import Location, Script


log = logging.getLogger("kiso.experiment.pegasus")


console = Console()


class PegasusRunner:
    """_summary_.

    _extended_summary_
    """

    #:
    schema: dict = SCHEMA

    #:
    config_type: type = PegasusConfiguration

    #:
    kind: str = "pegasus"

    def __init__(
        self,
        experiment: PegasusConfiguration,
        index: int,
        variables: dict[str, str | int | float] | None = None,
    ) -> None:
        """__init__ _summary_.

        _extended_summary_

        :param experiment: Experiment configuration
        :type experiment: PegasusWorkflow
        :param index: Experiment index
        :type index: int
        :param console: Rich console object to output experiment progress,
        defaults to None
        :type console: Console | None, optional
        :param log: Logger to use, defaults to None
        :type log: logging.Logger | None, optional
        :param variables: Globally defined variables, defaults to None
        :type variables: dict[str, str  |  int  |  float] | None, optional
        """
        self.index = index
        self.variables = copy.deepcopy(variables or {})

        # Experiment configuration
        self.experiment = experiment
        self.name = experiment.name
        self.main = experiment.main
        self.submit_node_labels = experiment.submit_node_labels
        self.variables.update(experiment.variables or {})
        self.args = experiment.args or []
        self.setup = experiment.setup or []
        self.inputs = experiment.inputs or []
        self.post_scripts = experiment.post_scripts or []
        self.outputs = experiment.outputs or []
        self.count = experiment.count or 1
        self.poll_interval = experiment.poll_interval or const.POLL_INTERVAL
        self.timeout = experiment.timeout or const.WORKFLOW_TIMEOUT

    def check(self, config: Kiso, label_to_machines: Roles) -> None:
        """Check  summary_.

        _extended_summary_

        :param label_to_machines: _description_
        :type label_to_machines: Roles
        """
        if config.deployment and config.deployment.htcondor:
            log.debug(
                "Check submit_node_labels specified in the experiment are valid submit "
                "nodes as per the HTCondor configuration"
            )
            self._check_submit_labels_are_submit_nodes(config, label_to_machines)

        log.debug(
            "Check labels referenced in experiments section are defined in the sites "
            "section"
        )
        self._check_undefined_labels(config, label_to_machines)

        log.debug("Check for missing files in inputs")
        self._check_missing_input_files(config)

    def _check_submit_labels_are_submit_nodes(
        self, experiment_config: Kiso, label_to_machines: dict[str, set]
    ) -> None:
        """Check for missing input files in experiment configurations.

        Validates the existence of input files specified in experiment configurations.
        Raises a ValueError with details of any missing input files and their associated
        experiments.

        :param experiment_config: Configuration dictionary containing experiment details
        :type experiment_config: Kiso
        :raises ValueError: If any specified input files do not exist
        """
        submit_node_labels = set()
        submit_nodes = set()
        for daemon_config in experiment_config.deployment.htcondor or []:
            kind = daemon_config.kind
            labels = set(daemon_config.labels)
            if not (
                kind[0] == "s"  # submit
                or kind[0] == "p"  # personal
            ):
                continue

            submit_node_labels.update(labels)
            for label in labels:
                submit_nodes.update(label_to_machines[label])

        for experiment in experiment_config.experiments:
            if experiment.kind != "pegasus":
                continue

            for label in experiment.submit_node_labels:
                if label_to_machines[label].intersection(submit_nodes):
                    break
            else:
                raise ValueError(
                    f"Experiment <{experiment['name']}>'s submit_node_labels do not map"
                    f"to any submit node(s) {submit_node_labels}"
                )

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
            if experiment.kind != "pegasus":
                continue

            for index, setup in enumerate(experiment.setup or []):
                unlabel_to_machines[experiment.name].update(
                    [
                        (f"setup[{index}]", label)
                        for label in setup.labels
                        if label not in label_to_machines
                    ]
                )

            for index, location in enumerate(experiment.inputs or []):
                unlabel_to_machines[experiment.name].update(
                    [
                        (f"inputs[{index}]", label)
                        for label in location.labels
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
            for index, setup in enumerate(experiment.post_scripts or []):
                unlabel_to_machines[experiment.name].update(
                    [
                        (f"post_scripts[{index}]", label)
                        for label in setup.labels
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

    def _check_missing_input_files(self, experiment_config: Kiso) -> None:
        """Check for missing input files in experiment configurations.

        Validates the existence of input files specified in experiment configurations.
        Raises a ValueError with details of any missing input files and their associated
        experiments.

        :param experiment_config: Configuration dictionary containing experiment details
        :type experiment_config: Kiso
        :raises ValueError: If any specified input files do not exist
        """
        missing_files = []
        for experiment in experiment_config.experiments:
            if experiment.kind != "pegasus":
                continue

            for location in experiment.inputs or []:
                src = Path(location.src)
                if not src.exists():
                    missing_files.append((experiment.name, src))

        if missing_files:
            raise ValueError(
                "\n".join(
                    [
                        f"Input file <{src}> does not exist for experiment <{exp}>"
                        for exp, src in missing_files
                    ]
                ),
                missing_files,
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

        # Resolve labels
        self._labels = utils.resolve_labels(labels, self.submit_node_labels)
        self.vms, self.containers = utils.split_labels(self._labels, labels)

        for instance in range(self.count):
            self.env.setdefault(instance, {})
            self.env[instance].setdefault("workflow-generate", {})
            self.env[instance].setdefault("submit-dir", {})
            self.env[instance].setdefault("wait-workflow", {})
            self.env[instance].setdefault("fetch-submit-dir", {})

        self._copy_inputs()
        self._run_setup_scripts()

        for instance in range(self.count):
            self._run_experiment(instance)

        self._run_post_scripts()
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

        :param index: The overall experiment index
        :type index: int
        :param input: Input file configuration dictionary
        :type input: dict
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

    def _run_setup_scripts(self) -> None:
        """Run setup scripts for an experiment across specified labels.

        Executes setup scripts defined in the experiment configuration on virtual
        machines and containers. Handles script preparation, copying, and execution
        while tracking the status of each script run.
        """
        name = self.name
        setup_scripts = self.setup
        if not setup_scripts:
            return

        log.debug("Run setup scripts for <%s:%d>", name, self.index)
        console.print(rf"\[{name}] Running setup scripts")

        self.env.setdefault("run-setup-script", {})
        results = []
        for instance, setup_script in enumerate(setup_scripts):
            result = self._run_setup_script(instance, setup_script)
            results.append((instance, setup_script, result))

        display.setup_scripts(console, results)

    def _run_setup_script(
        self, instance: int, setup_script: Script
    ) -> list[CommandResult | CustomCommandResult]:
        """Run setup scripts for an experiment across specified labels.

        Executes setup scripts defined in the experiment configuration on virtual
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

        kiso_state_key = "run-setup-script"
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

    def _run_post_scripts(self) -> None:
        """Run post-execution scripts for an experiment.

        Executes post_scripts defined in the experiment configuration across specified
        labels, supporting both virtual machines and containers. Handles script
        copying, execution, and tracking of script run status.
        """
        name = self.name
        post_scripts = self.post_scripts
        if not post_scripts:
            return

        log.debug("Run post scripts for <%s:%d>", name, self.index)
        console.print(rf"\[{name}] Running post scripts")

        self.env.setdefault("run-post-script", {})
        results = []
        for instance, post_script in enumerate(post_scripts):
            result = self._run_post_script(instance, post_script)
            results.append((instance, post_script, result))

        display.post_scripts(console, results)

    def _run_post_script(
        self, instance: int, post_script: Script
    ) -> list[CommandResult | CustomCommandResult]:
        """Run post-execution scripts for an experiment.

        Executes post_scripts defined in the experiment configuration across specified
        labels, supporting both virtual machines and containers. Handles script
        copying, execution, and tracking of script run status.

        :param instance: Instance number of the post-script
        :type instance: int
        :param post_script: Post-execution script configuration dictionary
        :type post_script: dict
        :raises: Exception if any post-script fails during execution
        :return: List of CommandResult or CustomCommandResult objects
        :rtype: list[CommandResult | CustomCommandResult]
        """
        results: list[CommandResult | CustomCommandResult] = []
        labels = self.labels
        _labels = utils.resolve_labels(labels, post_script.labels)
        vms, containers = utils.split_labels(_labels, labels)
        executable = post_script.executable

        kiso_state_key = "run-post-script"
        with (
            experiment_state(self.env, kiso_state_key, instance) as state,
            tempfile.NamedTemporaryFile() as script,
        ):
            if state.status == const.STATUS_OK:
                return results

            dst = str(Path(const.TMP_DIR) / Path(script.name).name)

            script.write(f"#!{executable}\n".encode())
            script.write(post_script.script.encode())
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

    def _run_experiment(self, instance: int) -> None:
        """Run a complete workflow for a specific experiment instance.

        Executes workflow generation and then waits for workflow completion.

        :param instance: The specific instance number of the experiment
        :type instance: int
        """
        console.rule(
            "[bold green]Experiment: "
            f"{self.name} {instance + 1}/{self.count}[/bold green]"
        )
        try:
            results = self._generate_workflow(instance)
            display.generate_workflow(
                console, (instance, [results] if results is not None else [])
            )

            self._wait_for_workflow(instance)
        except KisoValueError as e:
            results = e.args[1]
            display.generate_workflow(
                console, (instance, [results] if results is not None else [])
            )

        self._fetch_submit_dir(instance)

    def _generate_workflow(
        self, instance: int
    ) -> CommandResult | CustomCommandResult | None:
        """Generate a Pegasus workflow for a specific experiment instance.

        Generates a workflow by executing the main script on a specified VM or
        container, capturing the submit directory for later tracking and management.

        :param instance: The specific instance number of the experiment
        :type instance: int
        :raises Exception: If workflow generation fails at any point
        :return: _description_
        :rtype: CommandResult | CustomCommandResult | None
        """
        index = self.index
        name = self.name
        main = self.main
        args = self.args
        vms = self.vms
        containers = self.containers
        bash = "/bin/bash"

        log.debug("Generate workflow for <%s:%d:%d>", name, index, instance)
        console.print(rf"\[{name}-{instance + 1}] Generating workflow")

        kiso_state_key = "workflow-generate"
        with (
            experiment_state(self.env, instance, kiso_state_key) as state,
            tempfile.NamedTemporaryFile() as script,
        ):
            if state.status == const.STATUS_OK:
                return None

            ts = datetime.now(timezone.utc)

            dst = Path(self.remote_wd) / Path(script.name).name
            script.write(main.encode())
            script.seek(0)

            if vms:
                vm = vms[0]
                with utils.actions(roles=vm, run_as=const.KISO_USER) as p:
                    p.copy(
                        src=script.name,
                        dest=str(dst.parent),
                        mode="preserve",
                        task_name="Copy main script",
                    )
                    p.shell(
                        f"{bash} {dst} {' '.join([shlex.quote(str(_)) for _ in args])}",
                        chdir=str(dst.parent),
                        task_name="Generate workflow",
                    )
                    p.shell(f"rm -rf {dst}", chdir=str(dst.parent))
                submit_dir = self._get_submit_dir(p.results[1], vm, ts)
            elif containers:
                container = containers[0]
                status = utils.run_script(
                    container,
                    Path(script.name),
                    *args,
                    user=const.KISO_USER,
                    workdir=str(dst.parent),
                )
                submit_dir = self._get_submit_dir(status, container, ts)

        if state.status == const.STATUS_OK:
            self.env[instance]["submit-dir"] = submit_dir
        else:
            raise KisoValueError(
                "Workflow generation failed", p.results[1] if vms else status
            )

        return p.results[1] if vms else status

    def pegasus_run(
        self, machine: Host | ChameleonDevice, submit_dir: str | Path
    ) -> None:
        """Execute a Pegasus workflow run on a given machine.

        Runs a Pegasus workflow on either a Host or ChameleonDevice, handling different
        execution strategies based on the machine type.

        :param machine: The machine or device to run the workflow on
        :type machine: Host or ChameleonDevice
        :param submit_dir: Directory where the workflow is submitted
        :type submit_dir: str or Path
        :raises: Potential exceptions from pegasus-run or workflow submission
        """
        if isinstance(machine, Host):
            with utils.actions(roles=machine, run_as=const.KISO_USER) as p:
                p.shell(f"pegasus-run {submit_dir}", task_name="Run workflow")
            submit_dir = self._get_submit_dir(
                p.results[0], machine, datetime.fromtimestamp(0)
            )
        else:
            status = self._pegasus_run(machine, Path(submit_dir), user=const.KISO_USER)
            submit_dir = self._get_submit_dir(
                status, machine, datetime.fromtimestamp(0)
            )

    def _pegasus_run(
        self, container: ChameleonDevice, submit_dir: Path, user: str
    ) -> CommandResult:
        """Run Pegasus workflow on a Chameleon device.

        This function runs a Pegasus workflow on a Chameleon device using the
        ChameleonEdge API.

        :param container: The Chameleon device to execute the command on
        :type container: ChameleonDevice
        :param submit_dir: Directory where the workflow is submitted
        :type submit_dir: str
        :param user: User to execute the command as, defaults to None
        :type user: str, optional
        :return: CommandResult containing execution status and output
        :rtype: CommandResult
        """
        cmd = ["pegasus-run", shlex.quote(str(submit_dir))]
        return edge._execute(container, " ".join(cmd), user=user)

    def _get_submit_dir(
        self, result: CommandResult, machine: Host | ChameleonDevice, ts: datetime
    ) -> Path:
        """Get the submit directory for a Pegasus workflow.

        Determines the submit directory for a Pegasus workflow based on command results,
        handling different machine types and extraction methods. Attempts to locate the
        submit directory through log parsing, command output, or database query.

        :param result: Command execution result containing workflow information
        :type result: CommandResult
        :param machine: Machine or device where the workflow was submitted
        :type machine: Host | ChameleonDevice
        :param ts: Timestamp of workflow submission
        :type ts: datetime
        :return: Path to the workflow submit directory
        :rtype: Path
        :raises ValueError: If workflow submit directory cannot be determined or
        workflow fails
        """
        ec = result.rc
        output1 = f"""{result.stdout}
    {result.stderr}
    """
        log.debug(
            "Generate workflow, status <%s> stdout <%s> stderr <%s>",
            result.rc,
            result.stdout,
            result.stderr,
        )
        if ec != 0:
            raise ValueError("Workflow generation failed", output1, ec)

        # Locate the submit dir from the logs,
        #   Workflow was planned, pegasus-run  <submit-dir>
        #   Workflow was run, pegasus-remove  <submit-dir>
        #   Workflow was planned and/or run with Python API, submit_dir: "<submit-dir>"
        matches = re.findall(
            r'.*(pegasus-run|pegasus-remove|submit_dir:)\s+"?(.*)"?.*', output1
        )
        if matches:
            submit_dir = matches[-1][-1]
            if matches[-1][0] == "pegasus-run":
                # Workflow was only planned
                try:
                    self.pegasus_run(machine, submit_dir)
                except Exception as e:
                    raise ValueError(
                        "Failed to run the workflow", e.args[0], submit_dir
                    ) from e
        else:
            # If the experiment's main script does not generate any logs
            cmd = f"""echo 'SELECT ws.state, w.submit_dir
    FROM    master_workflow w
            JOIN master_workflowstate ws ON w.wf_id = ws.wf_id
            JOIN (SELECT wf_id, max(timestamp) timestamp
                FROM   master_workflowstate
                WHERE timestamp >= {ts.timestamp()}
                GROUP  BY wf_id) t ON ws.wf_id = t.wf_id
                AND ws.timestamp = t.timestamp
    ;' | sqlite3 -list ~{const.KISO_USER}/.pegasus/workflow.db
    """  # noqa: S608

            if isinstance(machine, Host):
                result = en.run_command(cmd, roles=machine, run_as=const.KISO_USER)[0]

                ec = 1 if result.status == const.STATUS_FAILED else 0
                output2 = f"""{result.payload["stdout"]}
    {result.payload["stderr"]}
    """
            else:
                result = edge._execute(machine, cmd, user=const.KISO_USER)
                ec = result.rc
                output2 = result.stdout

            if ec != 0:
                raise ValueError("Could not identify the submit dir", output2, ec)

            workflow_state = output2.strip().splitlines()
            if len(workflow_state) == 0:
                raise ValueError("Could not identify the submit dir")

            workflow_state = workflow_state[-1].split("|")
            if workflow_state[0] != "WORKFLOW_STARTED":
                raise ValueError("Invalid workflow state", workflow_state)

            submit_dir = workflow_state[1]

        return Path(submit_dir)

    def _wait_for_workflow(self, instance: int) -> None:
        """Wait for a Pegasus workflow to complete for a specific experiment instance.

        Monitors the workflow status for a given experiment, tracking its progress and
        handling potential failures. Updates the experiment environment with the
        workflow's current state.

        :param instance: The specific instance number of the experiment
        :type instance: int
        :raises: Propagates any exceptions encountered during workflow monitoring
        """
        index = self.index
        name = self.name
        vms = self.vms
        containers = self.containers
        poll_interval = self.poll_interval
        timeout = self.timeout

        log.debug("Wait for workflow to finish for <%s:%d:%d>", name, index, instance)
        console.print(rf"\[{name}-{instance + 1}] Waiting for workflow to finish")

        kiso_state_key = "wait-workflow"
        with experiment_state(self.env, instance, kiso_state_key) as state:
            if state.status == const.STATUS_OK:
                return

            submit_dir = self.env[instance]["submit-dir"]
            try:
                self._wait_for_workflow_2(
                    vms[0] if vms else containers[0],
                    submit_dir,
                    poll_interval=poll_interval,
                    timeout=timeout,
                )
            except KisoTimeoutError:
                console.print(
                    f"Workflow did not finish within the timeout <{timeout}> seconds"
                )
                raise
            finally:
                log.debug(
                    "Compute Pegasus statistics for workflow <%s:%d:%d>",
                    name,
                    index,
                    instance,
                )
                console.print(rf"\[{name}-{instance + 1}] Computing Pegasus statistics")
                self.pegasus_statistics(vms[0] if vms else containers[0], submit_dir)

                console.print(rf"\[{name}-{instance + 1}] Running Pegasus analyzer")
                self.pegasus_analyzer(vms[0] if vms else containers[0], submit_dir)

    def _wait_for_workflow_2(
        self,
        machine: Host | ChameleonDevice,
        submit_dir: str | Path,
        poll_interval: int = const.POLL_INTERVAL,
        timeout: int = const.WORKFLOW_TIMEOUT,
    ) -> None:
        """Wait for a Pegasus workflow to complete on a given machine.

        Polls the workflow status periodically and checks for completion. Supports both
        Host and ChameleonDevice machine types. Handles workflow timeout by stopping
        the workflow if it exceeds the specified time limit.

        :param machine: The machine running the Pegasus workflow
        :type machine: Host | ChameleonDevice
        :param submit_dir: Directory containing the Pegasus workflow submit information
        :type submit_dir: str | Path
        :param poll_interval: Time between status checks, defaults to
        const.POLL_INTERVAL
        :type poll_interval: int, optional
        :param timeout: Maximum time to wait for workflow completion, defaults to
        const.WORKFLOW_TIMEOUT
        :type timeout: int, optional
        """
        status_cmd = f"pegasus-status --jsonrv {submit_dir}"
        done_file = Path(submit_dir) / "monitord.done"
        start_time = time.time()
        cols = {
            "Unready": "unready",
            "Ready": "ready",
            "Pre": "pre",
            "Queued": "queued",
            "Post": "post",
            "Succeeded": "succeeded",
            "Failed": "failed",
            "%": "percent_done",
            "Total": "total",
            "State": "state",
        }
        with PegasusWorkflowProgress(cols=cols) as progress:
            while timeout == -1 or time.time() - start_time <= timeout:
                if isinstance(machine, Host):
                    with utils.actions(roles=machine, run_as=const.KISO_USER) as p:
                        p.shell(status_cmd, task_name="Wait for workflow")
                        p.shell(f"cat {done_file}")

                    pegasus_status = p.results[0]
                    monitord_status = p.results[1]

                    self._render_status(progress, pegasus_status)

                    if monitord_status.status == const.STATUS_OK:
                        break
                else:
                    pegasus_status = self.pegasus_status(
                        machine, Path(submit_dir), user=const.KISO_USER
                    )

                    self._render_status(progress, pegasus_status)

                    monitord_status = edge._execute(
                        machine, f"cat {done_file}", user=const.KISO_USER
                    )
                    if monitord_status.rc == 0:
                        break

                time.sleep(poll_interval)
            else:
                # Workflow ran for too long
                log.debug("Workflow did not finish within the timeout <%d>", timeout)
                # Stop the workflow
                self.pegasus_remove(machine, submit_dir)
                raise KisoTimeoutError(
                    f"Workflow did not finish within the timeout <{timeout}> seconds",
                    timeout,
                )

    def _render_status(
        self, progress: PegasusWorkflowProgress, status: CommandResult
    ) -> None:
        """Render the status of a Pegasus workflow command execution.

        Parses and prints the output of a Pegasus workflow command result,
        handling both CommandResult and dictionary input types.

        :param progress: _description_
        :type progress: PegasusWorkflowProgress
        :param status: The command execution result to render
        :type status: CommandResult
        """
        if status.status != const.STATUS_OK:
            return

        output = json.loads(status.payload["stdout"])
        progress.update_table(output)

    def pegasus_status(
        self, container: ChameleonDevice, submit_dir: Path, user: str
    ) -> CommandResult:
        """Get status of a Pegasus workflow on a Chameleon device.

        This function gets the status of a Pegasus workflow on a Chameleon device
        using the ChameleonEdge API.

        :param container: The Chameleon device to execute the command on
        :type container: ChameleonDevice
        :param submit_dir: Directory where the workflow is submitted
        :type submit_dir: str
        :param user: User to execute the command as, defaults to None
        :type user: str, optional
        :return: CommandResult containing execution status and output
        :rtype: CommandResult
        """
        cmd = ["pegasus-status", "--jsonrv", shlex.quote(str(submit_dir))]
        return edge._execute(container, " ".join(cmd), user=user)

    def pegasus_remove(
        self, machine: Host | ChameleonDevice, submit_dir: str | Path
    ) -> CommandResult:
        """Remove a Pegasus workflow from the specified submit directory.

        Stops and removes a running Pegasus workflow on either a Host or ChameleonDevice
        machine.
        Supports execution through different mechanisms based on the machine type.

        :param machine: The machine hosting the Pegasus workflow to be removed
        :type machine: Host | ChameleonDevice
        :param submit_dir: Directory containing the Pegasus workflow submit information
        :type submit_dir: str | Path
        :return: CommandResult containing execution status and output
        :rtype: CommandResult
        """
        if isinstance(machine, Host):
            with utils.actions(roles=machine, run_as=const.KISO_USER) as p:
                p.shell(f"pegasus-remove {submit_dir}", task_name="Remove workflow")
            result = p.results[0]
        else:
            result = self._pegasus_remove(
                machine, Path(submit_dir), user=const.KISO_USER
            )

        return result

    def _pegasus_remove(
        self, container: ChameleonDevice, submit_dir: Path, user: str
    ) -> CommandResult:
        """Stop Pegasus workflow on a Chameleon device.

        This function stops a Pegasus workflow on a Chameleon device using
        the ChameleonEdge API.

        :param container: The Chameleon device to execute the command on
        :type container: ChameleonDevice
        :param submit_dir: Directory where the workflow is submitted
        :type submit_dir: str
        :param user: User to execute the command as, defaults to None
        :type user: str, optional
        :return: CommandResult containing execution status and output
        :rtype: CommandResult
        """
        cmd = ["pegasus-remove", shlex.quote(str(submit_dir))]
        return edge._execute(container, " ".join(cmd), user=user)

    def pegasus_statistics(
        self, machine: Host | ChameleonDevice, submit_dir: str | Path
    ) -> None:
        """Execute Pegasus workflow statistics computation.

        Computes workflow statistics for a given submit directory using
        pegasus-statistics. Supports execution on both Host and ChameleonDevice
        machine types.

        :param machine: The machine on which to run pegasus-statistics
        :type machine: Host | ChameleonDevice
        :param submit_dir: Directory containing the Pegasus workflow submit information
        :type submit_dir: str | Path
        """
        if isinstance(machine, Host):
            with utils.actions(roles=machine, run_as=const.KISO_USER) as p:
                p.shell(
                    f"pegasus-statistics -s all {submit_dir}",
                    task_name="Compute workflow statistics",
                )
        else:
            self._pegasus_statistics(machine, Path(submit_dir), user=const.KISO_USER)

    def _pegasus_statistics(
        self, container: ChameleonDevice, submit_dir: Path, user: str
    ) -> CommandResult:
        """Compute Pegasus workflow statistics on a Chameleon device.

        This function computes statistics for a Pegasus workflow on a Chameleon device
        using the ChameleonEdge API.

        :param container: The Chameleon device to execute the command on
        :type container: ChameleonDevice
        :param submit_dir: Directory where the workflow is submitted
        :type submit_dir: str
        :param user: User to execute the command as, defaults to None
        :type user: str, optional
        :return: CommandResult containing execution status and output
        :rtype: CommandResult
        """
        cmd = ["pegasus-statistics", "-s", "all", shlex.quote(str(submit_dir))]
        return edge._execute(container, " ".join(cmd), user=user)

    def pegasus_analyzer(
        self, machine: Host | ChameleonDevice, submit_dir: str | Path
    ) -> None:
        """Execute Pegasus workflow analyzer.

        Analyzes workflow using pegasus-analyzer. The analyzer is commonly run on
        workflow failures. Supports execution on both Host and ChameleonDevice machine
        types.

        :param machine: The machine on which to run pegasus-statistics
        :type machine: Host | ChameleonDevice
        :param submit_dir: Directory containing the Pegasus workflow submit information
        :type submit_dir: str | Path
        """
        if isinstance(machine, Host):
            with utils.actions(roles=machine, run_as=const.KISO_USER) as p:
                p.shell(
                    f"pegasus-analyzer {submit_dir} >{submit_dir}/analyzer.log",
                    task_name="Analyze workflow",
                )
        else:
            self._pegasus_analyzer(machine, Path(submit_dir), user=const.KISO_USER)

    def _pegasus_analyzer(
        self, container: ChameleonDevice, submit_dir: Path, user: str
    ) -> CommandResult:
        """Analyze a Pegasus workflow on a Chameleon device.

        This function analyzes a Pegasus workflow on a Chameleon device using the
        ChameleonEdge API. The analyzer is commonly run on workflow failures.

        :param container: The Chameleon device to execute the command on
        :type container: ChameleonDevice
        :param submit_dir: Directory where the workflow is submitted
        :type submit_dir: str
        :param user: User to execute the command as, defaults to None
        :type user: str, optional
        :return: CommandResult containing execution status and output
        :rtype: CommandResult
        """
        _submit_dir = shlex.quote(str(submit_dir))
        cmd = [
            "pegasus-analyzer",
            shlex.quote(str(submit_dir)),
            ">",
            f"{_submit_dir}/analyzer.log",
        ]
        return edge._execute(container, " ".join(cmd), user=user)

    def _fetch_submit_dir(self, instance: int) -> None:
        """Copy output files from remote machines and containers to a local destination.

        Iterates through specified result locations, resolves target labels, and fetches
        output files from VMs and containers to a local destination directory.

        :param instance: Experiment index in the environment configuration
        :type instance: int
        """
        index = self.index
        name = self.name
        vms = self.vms
        containers = self.containers
        log.debug(
            "Starting to copy submit dir to the destination for <%s:%d:%d>",
            name,
            index,
            instance,
        )
        console.print(
            rf"\[{name}-{instance + 1}] Copying submit dir to the destination"
        )
        kiso_state_key = "fetch-submit-dir"
        with experiment_state(self.env, instance, kiso_state_key) as state:
            if state.status == const.STATUS_OK:
                return

            src = Path(self.env[instance]["submit-dir"])
            dst = Path(self.resultdir) / self.name / f"instance-{instance}"
            dst.mkdir(parents=True, exist_ok=True)
            if vms:
                with utils.actions(roles=vms[0], run_as=const.KISO_USER) as p:
                    p.synchronize(
                        mode="pull",
                        src=str(src),
                        dest=str(dst),
                        use_ssh_args=True,
                        task_name=f"Fetch submit dir {instance}",
                    )
            if containers:
                (dst / src.name).mkdir(parents=True, exist_ok=True)
                edge.download(containers[0], src, dst / src.name)
