"""Main class to check HTCondor configuration andinstall HTCondor."""

from __future__ import annotations

import itertools
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

import enoslib as en
from enoslib.objects import Roles
from rich.console import Console

from .configuration import HTCondorDaemon
from .schema import SCHEMA

import kiso.constants as const
from kiso import display, edge, utils
from kiso.log import get_process_pool_executor

if TYPE_CHECKING:
    from enoslib.api import CommandResult
    from enoslib.objects import Host, Roles
    from enoslib.task import Environment


log = logging.getLogger("kiso.deployment.htcondor")


console = Console()


if hasattr(en, "ChameleonEdge"):
    from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice
else:
    ChameleonDevice = utils.undefined


class HTCondorInstaller:
    """HTCondor software deployment."""

    #:
    schema: dict = SCHEMA

    #:
    config_type: type = list[HTCondorDaemon]

    #:
    HAS_SOFTWARE_KEY: str = "has_htcondor"

    def __init__(self, config: list[HTCondorDaemon]) -> None:
        """__init__ _summary_.

        _extended_summary_

        :param config: HTCondor configuration
        :type config: list[HTCondorDaemon]
        """
        self.config = config

    def check(self, label_to_machines: Roles) -> None:
        """Check if the HTCondor configuration is valid."""
        if self.config is None:
            return

        log.debug(
            "Check labels referenced in HTCondor section are defined in the sites "
            "section"
        )
        self._check_condor_labels(label_to_machines)

        log.debug("Check there is only one central-manager")
        self._check_central_manager_cardinality(label_to_machines)

        log.debug("Check execute node configurations doesn't overlap")
        self._check_node_overlap("execute")

        log.debug("Check submit nodes configurations doesn't overlap")
        self._check_node_overlap("submit")

        log.debug("Check personal nodes configurations doesn't overlap")
        self._check_node_overlap("personal")

    def _check_condor_labels(self, label_to_machines: Roles) -> None:
        """Check HTCondor labels and configuration files in an experiment configuration.

        Validates that all HTCondor labels are defined and all referenced configuration
        files exist.

        :param label_to_machines: Mapping of predefined labels
        :type label_to_machines: Roles
        :raises ValueError: If undefined labels are referenced or configuration files
        are missing
        """
        unlabel_to_machines: dict[int, list[str]] = defaultdict(list)
        missing_config_files = []
        for index, daemon_config in enumerate(self.config):
            kind = daemon_config.kind
            labels = daemon_config.labels
            config_file = daemon_config.config_file

            if config_file and not Path(config_file).exists():
                missing_config_files.append((index, kind, config_file))
                continue

            machines: set = set()
            machines.update(_ for label in labels for _ in label_to_machines[label])

            if not machines:
                unlabel_to_machines[index] = labels
        else:
            if unlabel_to_machines:
                raise ValueError(
                    "No machines found to install HTCondor configuration section",
                    unlabel_to_machines,
                )

            if missing_config_files:
                raise ValueError(
                    "Missing config files referenced in HTCondor section",
                    missing_config_files,
                )

    def _check_central_manager_cardinality(self, label_to_machines: Roles) -> None:
        """Check the cardinality of HTCondor central manager nodes in an experiment configuration.

        Validates that only one machine is assigned the central-manager label.

        :param label_to_machines: Mapping of predefined labels
        :type label_to_machines: Roles
        :raises ValueError: If more than one machine is assigned the central-manager label
        """  # noqa: E501
        central_manager = [
            daemon_config
            for daemon_config in self.config or []
            if daemon_config.kind[0] == "c"
        ]

        if len(central_manager) > 1:
            raise ValueError(
                "Multiple central-manager configurations are not supported"
            )

        if central_manager:
            for label in central_manager[0].labels:
                if len(label_to_machines[label]) > 1:
                    raise ValueError(
                        "Multiple central-manager machines are not supported"
                    )

    def _check_node_overlap(self, kind: str) -> None:
        """Check for overlapping labels in HTCondor nodes.

        Validates that no two nodes in the experiment configuration
        have overlapping label assignments, which could cause configuration conflicts.

        :param kind: Kind of node overlap to check
        :type kind: str
        :raises ValueError: If nodes have labels that intersect
        """
        condor_config = self.config
        for i, j in itertools.product(
            range(len(condor_config)), range(len(condor_config))
        ):
            kind_i = condor_config[i].kind
            labels_i = set(condor_config[i].labels)

            kind_j = condor_config[j].kind
            labels_j = set(condor_config[j].labels)

            if i == j or kind_i[0] != kind[0] or kind_j[0] != kind[0]:
                continue

            if labels_i.intersection(labels_j):
                raise ValueError(
                    f"{kind.capitalize()} nodes <{i}> and <{j}> have overlapping labels"
                )

    def __call__(self, env: Environment) -> None:
        """Install HTCondor on machines based on experiment configuration and labels.

        Configures and installs HTCondor daemons across different machines in an
        experiment, handling central manager, personal, submit, and execute daemon
        types. Uses parallel execution to install HTCondor on multiple machines
        simultaneously.

        :param config: Configuration dictionary containing HTCondor deployment
        details
        :type config: list[HTCondorDaemon]
        :param env: Environment configuration for the experiment
        :type env: Environment
        """
        if self.config is None:
            return

        log.debug("Install HTCondor")
        console.rule("[bold green]Installing HTCondor[/bold green]")

        labels = env["labels"]
        _condor_hosts = [c for c in self.config if c.kind[0] == "c"]
        _condor_host = (
            next(iter(utils.resolve_labels(labels, _condor_hosts[0].labels)))
            if _condor_hosts
            else None
        )
        condor_host_ip = (
            _condor_host.extra["kiso_preferred_ip"] if _condor_host else None
        )
        extra_vars: dict = {
            "condor_host": condor_host_ip,
            "trust_domain": const.TRUST_DOMAIN,
            "token_identity": f"condor_pool@{const.TRUST_DOMAIN}",
            "pool_passwd_file": utils.get_pool_passwd_file(),
        }

        if condor_host_ip is not None:
            log.debug("HTCondor Central Manager IP <%s>", condor_host_ip)

        with get_process_pool_executor() as executor:
            results = []
            futures = []
            machine_to_daemons = self._get_label_daemon_machine_map(self.config, labels)
            for machine, daemons in machine_to_daemons.items():
                log.debug(
                    "Install HTCondor Daemons <%s> on Machine <%s>",
                    daemons,
                    machine.address
                    if isinstance(machine, ChameleonDevice)
                    else machine.alias,
                )
                htcondor_config, config_files = self._get_condor_config(
                    self.config, daemons, condor_host_ip, machine, env
                )

                extra_vars = dict(extra_vars)
                extra_vars["htcondor_daemons"] = daemons
                extra_vars["htcondor_config"] = htcondor_config
                extra_vars["config_files"] = config_files

                if isinstance(machine, ChameleonDevice):
                    future = executor.submit(
                        self._install_condor_on_edge,
                        machine,
                        htcondor_config,
                        extra_vars,
                    )
                else:
                    future = executor.submit(
                        utils.run_ansible,
                        [Path(__file__).parent / "main.yml"],
                        roles=machine,
                        extra_vars=extra_vars,
                    )

                # To each node we add a flag to identify if HTCondor is installed on
                # the node
                machine.extra[self.HAS_SOFTWARE_KEY] = True

                # Wait for HTCondor Central Manager to be installed and started before
                # installing in on any other machine
                if "central-manager" in daemons:
                    result = future.result()
                    results.append(result[-1])
                else:
                    futures.append(future)

            # We need to wait for HTCondor to be installed on the remaining machines,
            # because even though the ProcessPoolExecutor does not exit the context
            # until all running futures have finished, the code gets stuck if we don't
            # invoke result() on the futures
            for future in futures:
                result = future.result()
                results.append(result[-1])

            display._render(console, results)

    def _get_label_daemon_machine_map(
        self, condor_config: list, labels: Roles
    ) -> dict[ChameleonDevice | Host, set]:
        """Get mapping of labels, daemons, and machines from the HTCondor configuration.

        _extended_summary_

        :param condor_config: _description_
        :type condor_config: list
        :param labels: _description_
        :type labels: Roles
        :return: _description_
        :rtype: dict[ChameleonDevice | Host, set]
        """
        label_to_daemons: Roles = defaultdict(set)
        machine_to_daemons: dict[ChameleonDevice | Host, set] = defaultdict(set)

        for index, config in enumerate(condor_config):
            kind = config.kind
            _labels = config.labels
            for label in _labels:
                label_to_daemons[label].add((index, kind))

        for label, machines in labels.items():
            if label in label_to_daemons:
                for machine in machines:
                    machine_to_daemons[machine].update(label_to_daemons[label])

        # Sort on daemons so that the HTCondor central-manager is installed first
        return dict(sorted(machine_to_daemons.items(), key=self._cmp))

    def _cmp(self, item: tuple[str, set]) -> int:
        """Cmp _summary_.

        _extended_summary_

        :param item: _description_
        :type item: tuple[str, set]
        :raises ValueError: _description_
        :return: _description_
        :rtype: int
        """
        rv = 10
        for daemon in item[1]:
            if daemon[1][0] == "c":  # central-manager
                rv = min(rv, 0)
                break
            if daemon[1][0] == "p":  # personal
                rv = min(rv, 1)
            elif daemon[1][0] == "e":  # execute
                rv = min(rv, 2)
            elif daemon[1][0] == "s":  # submit
                rv = min(rv, 3)
            else:
                raise ValueError(f"Daemon <{daemon[1]}> is not valid")

        return rv

    def _get_condor_config(
        self,
        config: list,
        daemons: set[tuple[int, str]],
        condor_host_ip: str | None,
        machine: Host | ChameleonDevice,
        env: Environment,
    ) -> tuple[list[str], dict[str, str]]:
        """Get HTCondor configuration for a specific machine and set of daemons.

        Generates HTCondor configuration based on the specified daemons, machine type,
        and environment requirements. Handles configuration for different daemon labels
        (personal, central manager, submit, execute) and special networking scenarios.

        :param config: Configuration dictionary for HTCondor
        :type config: list
        :param daemons: Set of daemon types to configure
        :type daemons: set[str]
        :param condor_host_ip: IP address of the HTCondor host
        :type condor_host_ip: str | None
        :param machine: Machine (Host or ChameleonDevice) being configured
        :type machine: Host | ChameleonDevice
        :param env: Environment configuration
        :type env: Environment
        :return: A tuple containing HTCondor configuration lines and additional config
        files
        :rtype: tuple[list[str], dict[str, str]]
        """
        is_public_ip_required = env["is_public_ip_required"]

        htcondor_config = [
            f"CONDOR_HOST = {condor_host_ip}",
            f"TRUST_DOMAIN = {const.TRUST_DOMAIN}",
        ]
        config_files = {}
        for index, daemon in daemons:
            if daemon[0] == "p":  # personal
                htcondor_config = [
                    "CONDOR_HOST = $(IP_ADDRESS)",
                    "use ROLE: CentralManager",
                    "use ROLE: Submit",
                    "use ROLE: Execute",
                ]
            else:
                _daemon = re.sub(r"[-\d]", "", daemon.title())
                htcondor_config.append(f"use ROLE: {_daemon}")

                # Execute nodes without public IPs need these configuration
                if _daemon[0] == "E":  # Execute
                    htcondor_config.append("USE_CCB = True")
                    htcondor_config.append("CCB_ADDRESS = $(CONDOR_HOST)")

            if config[index].config_file:
                config_files[f"kiso-{daemon}-config-file"] = str(
                    Path(config[index].config_file).resolve()
                )

        if (
            is_public_ip_required is True
            and machine.extra["kind"] == "chameleon-edge"
            and (
                machine.extra["is_central_manager"] is True
                or machine.extra["is_submit"] is True
            )
        ):
            # In a multi site setup, when the central manager and/or submit daemon
            # run on Chameleon Edge containers, they would require
            # a public IP. The public IP is acquired as a floating IP, so the IP is not
            # visible in the output of the ifconfig command. For some reason, HTCondor
            # tries to connect on the floating ip to a port, that is not 9618, and
            # hence it can't register itself. To bypass this, we add TCP_FORWARDING_HOST
            # (https://htcondor.readthedocs.io/en/latest/admin-manual/configuration-macros.html#TCP_FORWARDING_HOST)
            htcondor_config.append(
                f"TCP_FORWARDING_HOST = {machine.extra['kiso_preferred_ip']}"
            )
        else:
            # Vagrant VMs with VirtualBox use NAT networking, and each VM is isolated
            # from the other, so all VMs get the same IP address. So we add HTCondor's
            # NETWORK_INTERFACE (https://htcondor.readthedocs.io/en/latest/admin-manual/configuration-macros.html#NETWORK_INTERFACE),
            # configuration to the Vagrant VMs to ensure they can communicate
            htcondor_config.append(
                f"NETWORK_INTERFACE = {machine.extra['kiso_preferred_ip']}"
            )

        return htcondor_config, config_files

    def _install_condor_on_edge(  # noqa: C901
        self, machine: ChameleonDevice, htcondor_config: list[str], extra_vars: dict
    ) -> list[CommandResult]:
        """Install and configure HTCondor on a Chameleon Edge machine.

        This function performs the following tasks:
        - Runs initialization, HTCondor, and Pegasus installation scripts
        - Manages configuration files for HTCondor
        - Sets up security credentials (pool password and token)
        - Restarts the HTCondor service

        :param machine: The Chameleon device to install HTCondor on
        :type machine: ChameleonDevice
        :param htcondor_config: List of HTCondor configuration settings
        :type htcondor_config: list[str]
        :param extra_vars: Additional configuration variables for HTCondor installation
        :type extra_vars: dict
        :return: _description_
        :rtype: list[CommandResult]
        """
        results = []
        results.append(
            utils.run_script(
                machine,
                Path(__file__).parent / "htcondor.sh",
                "--no-dry-run",
            )
        )

        results.append(
            utils.run_script(
                machine,
                Path(__file__).parent / "pegasus.sh",
                "--no-dry-run",
            )
        )
        if results[-1].rc != 0:
            return results

        config_root = edge._execute(machine, "condor_config_val CONFIG_ROOT")
        results.append(config_root)
        if results[-1].rc != 0:
            return results
        config_root = config_root.stdout
        config_root = f"{config_root}/config.d"

        config_files = extra_vars.get("config_files")
        if config_files:
            # User may change the experiment configuration and rerun the up command, so
            # we remove old configuration files before configuring HTCondor
            results.append(
                edge._execute(machine, f"rm -rf  {config_root}/kiso-*-config-file")
            )
            if results[-1].rc != 0:
                return results

            for fname, config_file in config_files.items():
                edge._upload_file(machine, config_file, f"{config_root}")
                results.append(
                    edge._execute(
                        machine,
                        f"mv {config_root}/{Path(config_file).name} "
                        f"{config_root}/{fname}",
                    )
                )
                if results[-1].rc != 0:
                    return results
            results.append(
                edge._execute(
                    machine,
                    f"chown root:root {config_root}/* ; chmod 644 {config_root}/*",
                )
            )
            if results[-1].rc != 0:
                return results

        for daemon in extra_vars.get("htcondor_daemons", set()):
            if daemon == "personal":
                return results

        sec_password_directory = edge._execute(
            machine, "condor_config_val SEC_PASSWORD_DIRECTORY"
        )
        results.append(sec_password_directory)
        if results[-1].rc != 0:
            return results
        sec_password_directory = sec_password_directory.stdout

        sec_token_system_directory = edge._execute(
            machine, "condor_config_val SEC_TOKEN_SYSTEM_DIRECTORY"
        )
        results.append(sec_token_system_directory)
        if results[-1].rc != 0:
            return results
        sec_token_system_directory = sec_token_system_directory.stdout

        NL = "\n"
        DOLLAR = "\\$"
        results.append(
            edge._execute(
                machine,
                f"""cat > "{config_root}/01-kiso" << EOF
{NL.join(htcondor_config).replace("$", DOLLAR)}
EOF
""",
            )
        )
        if results[-1].rc != 0:
            return results

        edge._upload_file(
            machine, extra_vars["pool_passwd_file"], f"{sec_password_directory}/"
        )
        results.append(
            edge._execute(
                machine,
                f"mv {sec_password_directory}/"
                f"{Path(extra_vars['pool_passwd_file']).name} "
                f"{sec_password_directory}/POOL",
            )
        )
        if results[-1].rc != 0:
            return results

        results.append(
            edge._execute(
                machine,
                f"chown root:root {sec_password_directory}/POOL ; "
                f"chmod 600 {sec_password_directory}/POOL ; "
                f"rm -f {config_root}/00-minicondor",
            )
        )
        if results[-1].rc != 0:
            return results

        results.append(
            edge._execute(
                machine,
                "condor_token_create -key POOL "
                f"-identity {extra_vars['token_identity']} "
                f"-file {sec_token_system_directory}/POOL.token",
            )
        )
        if results[-1].rc != 0:
            return results

        # Restart HTCondor
        # machine.execute(
        #     "sh -c 'ps aux | grep condor | grep -v condor | awk \\'{print $2}\\' | "
        #     "xargs kill -9'"
        # )
        # machine.execute("condor_master")
        results.append(edge._execute(machine, "condor_restart"))

        return results
