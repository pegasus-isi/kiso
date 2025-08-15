"""Main Kiso task implementations."""

# ruff: noqa: ARG001
from __future__ import annotations

import copy
import json
import logging
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from functools import wraps
from ipaddress import IPv4Interface, IPv6Interface, ip_address
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

import enoslib as en
import yaml
from dacite import Config, from_dict
from enoslib.objects import DefaultNetwork, Host, Networks, Roles
from enoslib.task import Environment, enostask
from jsonschema_pyref import ValidationError, validate
from rich.console import Console

import kiso.constants as const
from kiso import display, edge, utils
from kiso.errors import KisoError
from kiso.log import get_process_pool_executor
from kiso.schema import SCHEMA
from kiso.version import __version__

if TYPE_CHECKING:
    from os import PathLike

    from enoslib.api import CommandResult
    from enoslib.infra.provider import Provider


T = TypeVar("T")

PROVIDER_MAP: dict[str, tuple[Callable[[dict], Any], Callable[..., Any]]] = {}

log = logging.getLogger("kiso")

console = Console()

if hasattr(en, "Vagrant"):
    log.debug("Vagrant provider is available")
    PROVIDER_MAP["vagrant"] = (en.VagrantConf.from_dictionary, en.Vagrant)
if hasattr(en, "CBM"):
    log.debug("Chameleon Bare Metal provider is available")
    from enoslib.infra.enos_openstack.utils import source_credentials_from_rc_file

    PROVIDER_MAP["chameleon"] = (en.CBMConf.from_dictionary, en.CBM)
if hasattr(en, "ChameleonEdge"):
    log.debug("Chameleon Edge provider is available")
    from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice

    PROVIDER_MAP["chameleon-edge"] = (
        en.ChameleonEdgeConf.from_dictionary,
        en.ChameleonEdge,
    )
if hasattr(en, "Fabric"):
    log.debug("FABRIC provider is available")
    PROVIDER_MAP["fabric"] = (en.FabricConf.from_dictionary, en.Fabric)


def validate_config(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to validate the experiment configuration against a predefined schema.

    Validates the experiment configuration by checking it against the Kiso experiment
    configuration schema. Supports configuration passed as a dictionary or a file path.

    :param func: The function to be decorated, which will receive the experiment
    configuration
    :type func: Callable[..., T]
    :return: A wrapped function that validates the configuration before executing the
    original function
    :rtype: Callable[..., T]
    :raises ValidationError: if the configuration is invalid
    """

    @wraps(func)
    def wrapper(experiment_config: PathLike | dict, *args: Any, **kwargs: Any) -> T:  # noqa: ANN401
        log.debug("Check Kiso experiment configuration")
        if isinstance(experiment_config, dict):
            config = experiment_config
            wd = Path.cwd().resolve()
        else:
            wd = Path(experiment_config).parent.resolve()
            with Path(experiment_config).open() as _experiment_config:
                config = yaml.safe_load(_experiment_config)

        try:
            validate(config, SCHEMA)
        except ValidationError:
            log.exception("Invalid Kiso experiment config <%s>", experiment_config)
            raise

        log.debug("Kiso experiment configuration is valid")
        return func(config, *args, wd=wd, **kwargs)

    return wrapper


@validate_config
def check(experiment_config: dict[str, Any], **kwargs: dict) -> None:
    """Check the experiment configuration for various validation criteria.

    This function performs multiple validation checks on the experiment configuration,
    including:
    - Verifying vagrant site constraints
    - Validating role definitions
    - Checking docker and Condor configurations
    - Ensuring proper node configurations
    - Validating input file locations
    - Performing EnOSlib platform checks

    :param experiment_config: The experiment configuration dictionary
    :type experiment_config: dict[str, Any]
    :param kwargs: Additional keyword arguments
    :type kwargs: dict
    """
    console.rule("[bold green]Check experiment configuration[/bold green]")
    log.debug("Check only one vagrant site is present in the experiment")
    role_to_machines: dict[str, set] = _get_defined_roles(experiment_config)

    if "docker" in experiment_config:
        log.debug("Check docker is not installed on Chameleon edge")
        _check_docker_is_not_on_edge(experiment_config)

    log.debug(
        "Check roles referenced in condor section are defined in the sites section"
    )
    _check_condor_roles(experiment_config, role_to_machines)

    log.debug("Check there is only one central-manager")
    _check_central_manager_cardinality(experiment_config, role_to_machines)

    log.debug("Check execute node configurations doesn't overlap")
    _check_exec_node_overlap(experiment_config)

    log.debug("Check worker nodes configurations doesn't overlap")
    _check_worker_node_overlap(experiment_config)

    log.debug(
        "Check roles referenced in experiments section are defined in the sites section"
    )
    _check_undefined_roles(experiment_config, role_to_machines)

    log.debug("Check for missing files in inputs")
    _check_missing_input_files(experiment_config)

    log.debug(
        "Check submit-node-roles specified in the experiment are valid submit "
        "nodes as per the Condor configuration"
    )
    _check_submit_roles_are_submit_nodes(experiment_config, role_to_machines)

    log.debug("Check EnOSlib")
    en.MOTD = en.INFO = ""
    en.check(platform_filter=["Vagrant", "Fabric", "Chameleon", "ChameleonEdge"])


def _get_defined_roles(experiment_config: dict[str, Any]) -> dict[str, set]:
    """Get the defined roles from the experiment configuration.

    Extracts and counts roles defined in the sites section of the experiment
    configuration. Validates that only one Vagrant site is present and generates
    additional role variants.

    :param experiment_config: Configuration dictionary containing site and resource
    definitions
    :type experiment_config: dict[str, Any]
    :raises ValueError: If multiple Vagrant sites are detected
    :return: A counter of defined roles with their counts
    :rtype: dict[str, set]
    """
    vagrant_sites = 0
    def_roles: Counter = Counter()
    role_to_machines: dict[str, set] = defaultdict(set)

    for site_index, site in enumerate(experiment_config["sites"]):
        if site["kind"] == "vagrant":
            vagrant_sites += 1

        for machine_index, machine in enumerate(site["resources"]["machines"]):
            def_roles.update({site["kind"]: machine.get("number", 1)})

            for role in machine["roles"]:
                def_roles.update({role: machine.get("number", 1)})

            for index in range(machine.get("number", 1)):
                machine_key = f"site-{site_index}-machine-{machine_index}-index-{index}"
                role_to_machines[site["kind"]].add(machine_key)

                for role in machine["roles"]:
                    role_to_machines[role].add(machine_key)

    else:
        if vagrant_sites > 1:
            raise ValueError("Multiple vagrant sites are not supported")

        extra_roles = {}
        for role, count in def_roles.items():
            machines = list(role_to_machines[role])
            for index in range(1, count + 1):
                extra_roles[f"kiso.{role}.{index}"] = 1
                role_to_machines[f"kiso.{role}.{index}"].add(machines[index - 1])

    return role_to_machines


def _check_docker_is_not_on_edge(experiment_config: dict[str, Any]) -> None:
    """Check that Docker is not configured to run on Chameleon Edge devices.

    Validates that no Docker roles are assigned to Chameleon Edge resources,
    which is not supported. Raises a ValueError if such a configuration is detected.

    :param experiment_config: Experiment configuration dictionary
    :type experiment_config: dict[str, Any]
    :raises ValueError: If Docker roles are found on Chameleon Edge devices
    """
    docker_roles = set(experiment_config.get("docker", []))
    edge_roles = set()

    if not docker_roles:
        return

    for site in experiment_config["sites"]:
        if site["kind"] != "chameleon-edge":
            continue

        for machine in site["resources"]["machines"]:
            edge_roles.update(machine["roles"])

    docker_edge_roles = docker_roles.intersection(edge_roles)

    if docker_edge_roles:
        raise ValueError(
            "Docker cannot be installed on Chameleon Edge devices", docker_edge_roles
        )


def _check_condor_roles(
    experiment_config: dict[str, Any], role_to_machines: dict[str, set]
) -> None:
    """Check Condor roles and configuration files in an experiment configuration.

    Validates that all Condor roles are defined and all referenced configuration files
    exist.

    :param experiment_config: Dictionary containing Condor configuration for an
    experiment
    :type experiment_config: dict[str, Any]
    :param role_to_machines: Mapping of predefined roles
    :type role_to_machines: dict[str, set]
    :raises ValueError: If undefined roles are referenced or configuration files are
    missing
    """
    unrole_to_machines = defaultdict(set)
    missing_config_files = []
    for condor, nodes in experiment_config.get("condor", {}).items():
        for node, roles in nodes.items():
            if node.endswith("-file"):
                if not Path(roles).exists():
                    missing_config_files.append((condor, node, roles))

                continue

            unrole_to_machines[condor].update(
                [role for role in roles if role not in role_to_machines]
            )

            if not unrole_to_machines[condor]:
                del unrole_to_machines[condor]
    else:
        if unrole_to_machines:
            raise ValueError(
                "Undefined roles referenced in condor section", unrole_to_machines
            )

        if missing_config_files:
            raise ValueError(
                "Missing config files referenced in condor section",
                missing_config_files,
            )


def _check_central_manager_cardinality(
    experiment_config: dict[str, Any], role_to_machines: dict[str, set]
) -> None:
    """Check the cardinality of Condor central manager nodes in an experiment configuration.

    Validates that only one machine is assigned the central-manager role.

    :param experiment_config: Dictionary containing Condor configuration for an
    experiment
    :type experiment_config: dict[str, Any]
    :param role_to_machines: Mapping of predefined roles
    :type role_to_machines: dict[str, set]
    :raises ValueError: If more than one machine is assigned the central-manager role
    """  # noqa: E501
    central_manager = experiment_config.get("condor", {}).get("central-manager", None)
    if central_manager:
        for role in central_manager["roles"]:
            if len(role_to_machines[role]) > 1:
                raise ValueError("Multiple central-manager machines are not supported")


def _check_exec_node_overlap(experiment_config: dict[str, Any]) -> None:
    """Check for overlapping roles in Condor execute nodes.

    Validates that no two execute nodes in the experiment configuration
    have overlapping role assignments, which could cause configuration conflicts.

    :param experiment_config: Dictionary containing Condor node configuration
    :type experiment_config: dict[str, Any]
    :raises ValueError: If execute nodes have roles that intersect
    """
    for i, nodes_i in experiment_config.get("condor", {}).items():
        if not i.startswith("execute"):
            continue

        for j, nodes_j in experiment_config["condor"].items():
            if not j.startswith("execute") or i == j:
                continue

            if set(nodes_i["roles"]).intersection(set(nodes_j["roles"])):
                raise ValueError(
                    f"Execute nodes <{i}> and <{j}> have overlapping roles"
                )


def _check_worker_node_overlap(experiment_config: dict[str, Any]) -> None:
    """Check for overlapping roles in Condor submit nodes.

    Validates that no two submit nodes in the experiment configuration
    have overlapping role assignments, which could cause configuration conflicts.

    :param experiment_config: Dictionary containing Condor node configuration
    :type experiment_config: dict[str, Any]
    :raises ValueError: If submit nodes have roles that intersect
    """
    for i, nodes_i in experiment_config.get("condor", {}).items():
        if not i.startswith("submit"):
            continue

        for j, nodes_j in experiment_config["condor"].items():
            if not j.startswith("submit") or i == j:
                continue

            if set(nodes_i["roles"]).intersection(set(nodes_j["roles"])):
                raise ValueError(f"Submit nodes <{i}> and <{j}> have overlapping roles")


def _check_undefined_roles(
    experiment_config: dict[str, Any], role_to_machines: dict[str, set]
) -> None:
    """Check for undefined roles in experiment configuration.

    Validates that all roles referenced in experiment setup, input locations,
    and result locations are defined in the experiment configuration.

    :param experiment_config: Complete experiment configuration dictionary
    :type experiment_config: dict[str, Any]
    :param role_to_machines: Mapping of predefined roles in the configuration
    :type role_to_machines: dict[str, set]
    :raises ValueError: If any undefined roles are found in the experiment configuration
    """
    unrole_to_machines = defaultdict(set)
    for experiment in experiment_config["experiments"]:
        for index, setup in enumerate(experiment.get("setup", [])):
            unrole_to_machines[experiment["name"]].update(
                [
                    (f"setup[{index}]", role)
                    for role in setup["roles"]
                    if role not in role_to_machines
                ]
            )

        for index, location in enumerate(experiment.get("inputs", [])):
            unrole_to_machines[experiment["name"]].update(
                [
                    (f"inputs[{index}]", role)
                    for role in location["roles"]
                    if role not in role_to_machines
                ]
            )

        for index, location in enumerate(experiment.get("outputs", [])):
            unrole_to_machines[experiment["name"]].update(
                [
                    (f"outputs[{index}]", role)
                    for role in location["roles"]
                    if role not in role_to_machines
                ]
            )
        for index, setup in enumerate(experiment.get("post-scripts", [])):
            unrole_to_machines[experiment["name"]].update(
                [
                    (f"post-scripts[{index}]", role)
                    for role in setup["roles"]
                    if role not in role_to_machines
                ]
            )

        if not unrole_to_machines[experiment["name"]]:
            del unrole_to_machines[experiment["name"]]
    else:
        if unrole_to_machines:
            raise ValueError(
                "Undefined roles referenced in experiments section", unrole_to_machines
            )


def _check_missing_input_files(experiment_config: dict[str, Any]) -> None:
    """Check for missing input files in experiment configurations.

    Validates the existence of input files specified in experiment configurations.
    Raises a ValueError with details of any missing input files and their associated
    experiments.

    :param experiment_config: Configuration dictionary containing experiment details
    :type experiment_config: dict[str, Any]
    :raises ValueError: If any specified input files do not exist
    """
    missing_files = []
    for experiment in experiment_config["experiments"]:
        for location in experiment.get("inputs", []):
            src = Path(location["src"])
            if not src.exists():
                missing_files.append((experiment["name"], src))

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


def _check_submit_roles_are_submit_nodes(
    experiment_config: dict[str, Any], role_to_machines: dict[str, set]
) -> None:
    """Check for missing input files in experiment configurations.

    Validates the existence of input files specified in experiment configurations.
    Raises a ValueError with details of any missing input files and their associated
    experiments.

    :param experiment_config: Configuration dictionary containing experiment details
    :type experiment_config: dict[str, Any]
    :raises ValueError: If any specified input files do not exist
    """
    submit_node_roles = set()
    submit_nodes = set()
    for i, nodes_i in experiment_config.get("condor", {}).items():
        if not (
            i[0] == "s"  # submit
            or i[0] == "p"  # personal
        ):
            continue

        submit_node_roles.update(nodes_i["roles"])
        for role in nodes_i["roles"]:
            submit_nodes.update(role_to_machines[role])

    for experiment in experiment_config["experiments"]:
        for role in experiment["submit-node-roles"]:
            if role_to_machines[role].intersection(submit_nodes):
                break
        else:
            raise ValueError(
                f"Experiment <{experiment['name']}>'s submit-node-roles do not map to "
                f"any submit node(s) {submit_node_roles}"
            )


@validate_config
@enostask(new=True, symlink=False)
def up(
    experiment_config: dict[str, Any],
    force: bool = False,
    env: Environment = None,
    **kwargs: Any,  # noqa: ANN401
) -> None:
    """Create and set up resources for running an experiment.

    Initializes the experiment environment, sets up working directories, and prepares
    infrastructure by initializing sites, installing Docker, Apptainer, and Condor
    across specified roles.

    :param experiment_config: Configuration dictionary defining experiment parameters
    :type experiment_config: dict[str, Any]
    :param force: Force recreation of resources, defaults to False
    :type force: bool, optional
    :param env: Optional environment context for the experiment, defaults to None
    :type env: Environment, optional
    """
    console.rule(
        "[bold green]Create and set up resources for the experiments[/bold green]"
    )
    env["version"] = __version__
    env["wd"] = str(kwargs.get("wd", Path.cwd()))
    env["remote_wd"] = str(Path("~kiso") / Path(env["wd"]).name)

    _init_sites(experiment_config, env, force)
    _install_commons(env)
    _install_docker(experiment_config, env)
    _install_apptainer(experiment_config, env)
    _install_condor(experiment_config, env)


def _init_sites(
    experiment_config: dict[str, Any], env: Environment, force: bool = False
) -> tuple[list[Provider], Roles, Networks]:
    """Initialize sites for an experiment.

    Initializes and configures sites from the experiment configuration using parallel
    processing.
    Performs the following key tasks:
    - Initializes providers for each site concurrently
    - Aggregates roles and networks from initialized sites
    - Extends roles with daemon-to-site mappings
    - Determines public IP requirements
    - Associates floating IPs and selects preferred IPs for nodes

    :param experiment_config: Configuration dictionary containing site definitions
    :type experiment_config: dict[str, Any]
    :param env: Environment context for the experiment
    :type env: Environment
    :param force: Force recreation of resources, defaults to False
    :type force: bool, optional
    :return: A tuple of providers, roles, and networks for the experiment
    :rtype: tuple[list[Provider], Roles, Networks]
    """
    log.debug("Initializing sites")

    providers = []
    roles = Roles()
    networks = Networks()

    with get_process_pool_executor() as executor:
        futures = [
            executor.submit(_init_site, site_index, site, force)
            for site_index, site in enumerate(experiment_config["sites"])
        ]

        for future in futures:
            provider, _roles, _networks = future.result()

            providers.append(provider)
            roles.extend(_roles)
            networks.extend(_networks)

    daemon_to_site = _extend_roles(experiment_config, roles)
    is_public_ip_required = _is_public_ip_required(daemon_to_site)
    env["is_public_ip_required"] = is_public_ip_required

    for node in roles.all():
        # TODO(mayani): Remove the floating ip assignment code after it has been
        # implemented into the EnOSlib ChameleonEdge provider
        _associate_floating_ip(node, is_public_ip_required)

        ip = _get_best_ip(
            node,
            is_public_ip_required
            and (node.extra["is_submit"] or node.extra["is_central_manager"]),
        )
        node.extra["kiso_preferred_ip"] = ip

    providers = en.Providers(providers)
    env["providers"] = providers
    env["roles"] = roles
    env["networks"] = networks

    return providers, roles, networks


def _init_site(
    index: int, site: dict[Any, Any], force: bool = False
) -> tuple[Provider, Roles, Networks]:
    """Initialize a site for provisioning resources.

    Configures and initializes a site based on its provider type, handling specific
    requirements for different cloud providers like Chameleon. Performs the following
    key tasks:
    - Validates the site's provider type
    - Configures exposed ports for containers
    - Initializes provider resources and networks
    - Adds metadata to nodes about their provisioning context
    - Handles region-specific configurations

    :param index: The index of the site in the configuration
    :type index: int
    :param site: Site configuration dictionary
    :type site: dict[Any, Any]
    :param force: Force recreation of resources, defaults to False
    :type force: bool, optional
    :raises TypeError: If an invalid site provider type is specified
    :return: A tuple containing the provider, roles, and networks for the site
    :rtype: tuple[Provider, Roles, Networks]
    """
    kind = site["kind"]
    if kind not in PROVIDER_MAP:
        raise TypeError(f"Invalid site.type <{kind}> for site <{index}>")

    # There is no firewall on ChameleonEdge containers, but to reach HTCondor
    # daemons the port(s) still need to be exposed
    if kind == "chameleon-edge":
        for container in site["resources"]["machines"]:
            container = container["container"]
            exposed_ports = set(container.get("exposed_ports", []))
            exposed_ports.add(str(const.HTCONDOR_PORT))
            # exposed_ports.add(str(const.SSHD_PORT))
            container["exposed_ports"] = list(exposed_ports)

    conf = PROVIDER_MAP[kind][0](site)
    provider = PROVIDER_MAP[kind][1](conf)

    _roles, _networks = provider.init(force_deploy=force)
    _deduplicate_hosts(_roles)
    _roles[kind] = _roles.all()
    _networks[kind] = _networks.all()

    # For Chameleon site, the region name is important as each region will act like
    # a different site
    region_name = kind
    if kind.startswith("chameleon"):
        region_name = _get_region_name(site["rc_file"])
        _roles[region_name] = _roles.all()
        _networks[region_name] = _networks.all()

    # To each node we add a tag to identify what site/region it was provisioned on
    for node in _roles.all():
        # ChameleonDevice object does not have an attribute named extra
        if kind == "chameleon-edge":
            attr = "extra"
            setattr(node, attr, {})
        elif kind == "chameleon":
            # Used to copy this file to Chameleon VMs, so we cna use the Openstack
            # client to get a floating IP
            node.extra["rc_file"] = str(Path(conf.rc_file).resolve())

        node.extra["kind"] = kind
        node.extra["site"] = region_name

    if kind != "chameleon-edge":
        _roles = en.sync_info(_roles, _networks)
    else:
        # Because zunclient.v1.containers.Container is not pickleable
        provider.client.concrete_resources = []

    return provider, _roles, _networks


def _deduplicate_hosts(roles: Roles) -> None:
    """Deduplicate_hosts _summary_.

    _extended_summary_

    :param roles: _description_
    :type roles: Roles
    """
    dedup = {}
    for _, nodes in roles.items():
        update = set()
        for node in nodes:
            if node not in dedup:
                dedup[node] = node
            else:
                update.add(dedup[node])

        for node in update:
            nodes.remove(node)

        nodes.extend(update)


def _get_region_name(rc_file: str) -> str | None:
    """Extract the OpenStack region name from a given RC file.

    Parses the provided RC file to find the OS_REGION_NAME environment variable
    and returns its value. Raises a ValueError if the region name cannot be found.

    :param rc_file: Path to the OpenStack RC file containing environment variables
    :type rc_file: str
    :raises ValueError: If OS_REGION_NAME is not found in the RC file
    :return: The name of the OpenStack region
    :rtype: str | None
    """
    region_name = None
    with Path(rc_file).open() as env_file:
        for env_var in env_file:
            if "OS_REGION_NAME" in env_var:
                parts = env_var.split("=")
                region_name = parts[1].strip("\n\"'")
                break
        else:
            raise ValueError(f"Unable to get region name from the rc_file <{rc_file}>")

    return region_name


def _extend_roles(experiment_config: dict[str, Any], roles: Roles) -> dict[str, set]:
    """Extend roles for an experiment configuration by adding unique roles and flags to nodes.

    Processes the given roles and experiment configuration to:
    - Create unique roles for each node based on their original role
    - Add flags to nodes indicating their HTCondor daemon types (central manager,
    submit, execute, personal)
    - Add flags for container technologies (Docker, Apptainer)
    - Track the sites where different HTCondor daemon types are located

    :param experiment_config: Configuration dictionary for the experiment
    :type experiment_config: dict[str, Any]
    :param roles: Dictionary of roles and their associated nodes
    :type roles: Roles
    :return: A mapping of HTCondor daemon types to their sites
    :rtype: dict[str, set]
    """  # noqa: E501
    extra: dict[str, set] = defaultdict(set)
    daemon_to_site = defaultdict(set)
    central_manager_roles, submit_roles, execute_roles, personal_roles = (
        _get_condor_daemon_roles(experiment_config)
    )
    docker_roles = set()
    if "docker" in experiment_config:
        docker_roles = experiment_config["docker"]["roles"]

    apptainer_roles = set()
    if "apptainer" in experiment_config:
        apptainer_roles = experiment_config["apptainer"]["roles"]

    for role, nodes in roles.items():
        is_central_manager = role in central_manager_roles
        is_submit = role in submit_roles
        is_execute = role in execute_roles
        is_personal = role in personal_roles
        is_docker = role in docker_roles
        is_apptainer = role in apptainer_roles
        for index, node in enumerate(nodes, 1):
            # EnOSlib resources.machines.number can be greater than 1, so we add the
            # host with a new unique role of the form kiso.<role>.<index>
            _role = f"kiso.{role}.{index}"
            extra[_role].add(node)

            # To each node we add flags to identify what HTCondor daemons will run on
            # the node
            node.extra["is_central_manager"] = (
                node.extra.get("is_central_manager", False) or is_central_manager
            )
            node.extra["is_submit"] = node.extra.get("is_submit", False) or is_submit
            node.extra["is_execute"] = node.extra.get("is_execute", False) or is_execute
            node.extra["is_personal"] = (
                node.extra.get("is_personal", False) or is_personal
            )

            # To each node we add a flag to identify if Docker is installed on the node
            node.extra["is_docker"] = node.extra.get("is_docker", False) or is_docker

            # To each node we add a flag to identify if Apptainer is installed on
            # the node
            node.extra["is_apptainer"] = (
                node.extra.get("is_apptainer", False) or is_apptainer
            )

            site = [node.extra["site"]]
            if is_execute:
                daemon_to_site["execute"].update(site)
            if is_submit:
                daemon_to_site["submit"].update(site)
            if is_central_manager:
                daemon_to_site["central-manager"].update(site)

    roles.update(extra)

    return daemon_to_site


def _is_public_ip_required(daemon_to_site: dict[str, set]) -> bool:
    """Determine if a public IP address is required for the HTCondor cluster configuration.

    Checks if public IP addresses are needed based on the distribution of HTCondor
    daemons
    across different sites. A public IP is required under the following conditions:
    - Execute nodes are spread across multiple sites
    - Submit nodes are spread across multiple sites
    - Execute and submit nodes are on different sites
    - Submit nodes are on a different site from the central manager

    :param daemon_to_site: A dictionary mapping HTCondor daemon types to their sites
    :type daemon_to_site: dict[str, set]
    :return: True if a public IP is required, False otherwise
    :rtype: bool
    """  # noqa: E501
    is_public_ip_required = False
    central_manager = daemon_to_site["central-manager"]
    submit = daemon_to_site["submit"]
    execute = daemon_to_site["execute"]

    # A public IP is required if,
    # 1. If execute nodes are on multiple sites
    # 2. If submit nodes are on multiple sites
    # 3. If all execute nodes and submit nodes are on one site, but not the same one
    # 4. If submit nodes are on one site, but not the same one as the central manager
    if (central_manager or submit or execute) and (
        len(execute) > 1
        or len(submit) > 1
        or execute != submit
        or submit - central_manager
    ):
        is_public_ip_required = True

    return is_public_ip_required


def _associate_floating_ip(
    node: Host | ChameleonDevice, is_public_ip_required: bool = False
) -> None:
    """Associate a floating IP address to a node based on specific conditions.

    Determines whether to assign a floating IP to a node depending on its role and type.
    Supports different cloud providers and testbed types with specific IP assignment
    strategies.

    :param node: The node to potentially assign a floating IP to
    :type node: Host | ChameleonDevice
    :param is_public_ip_required: Flag indicating if a public IP is needed, defaults
    to False
    :type is_public_ip_required: bool, optional
    :raises NotImplementedError: If floating IP assignment is not supported for a
    specific testbed
    :raises KisoError: If assigning a public IP is unsupported
    :raises ValueError: If an unsupported site type is encountered
    """
    if is_public_ip_required and (
        node.extra["is_central_manager"] or node.extra["is_submit"]
    ):
        kind = node.extra["kind"]
        if kind == "chameleon":
            _associate_floating_ip_chameleon(node)
        elif kind == "chameleon-edge":
            _associate_floating_ip_edge(node)
        elif kind == "fabric":
            raise NotImplementedError(
                "Assigning floating IP for FABRIC testbed hasn't been implemented yet"
            )
        elif kind == "vagrant":
            raise KisoError("Assigning public IPs to Vagrant VMs is not supported")
        else:
            raise ValueError(f"Unknown site type {kind}", kind)


def _associate_floating_ip_chameleon(node: Host) -> None:
    """Associate a floating IP address with a Chameleon node.

    Retrieves or creates a floating IP for a Chameleon node using the OpenStack CLI.
    Handles cases where a node may already have a floating IP or requires a new one.
    Logs debug information during the IP association process.

    :param node: The Chameleon node to associate a floating IP with
    :type node: Host
    :raises ValueError: If the OpenStack CLI is not found or the server cannot be
    located
    """
    with source_credentials_from_rc_file(node.extra["rc_file"]):
        ip = None
        cli = shutil.which("openstack")
        if cli is None:
            raise ValueError("Could not locate the openstack client")

        try:
            cli = str(cli)

            log.debug("Get the Chameleon node's id")
            # Get the node information so we can extract the server id
            server = subprocess.run(  # noqa: S603
                [cli, "server", "show", node.alias, "-f", "json"],
                capture_output=True,
                check=True,
            )
            _server = json.loads(server.stdout.decode("utf-8"))

            log.debug("Check if the node already has a floating IP")
            # Determine if the node has a floating IP
            for _, addresses in _server["addresses"].items():
                for address in addresses:
                    if not ip_address(address).is_private:
                        ip = address

            if ip is None:
                log.debug("Check for any unused floating ips")
                # Check for any unused floating ip
                all_floating_ips = subprocess.run(  # noqa: S603
                    [cli, "floating", "ip", "list", "-f", "json"],
                    capture_output=True,
                    check=True,
                )
                _floating_ips = json.loads(all_floating_ips.stdout.decode("utf-8"))
                for floating_ip in _floating_ips:
                    # If an unused floating ip is available, use it
                    if (
                        floating_ip["Fixed IP Address"] is None
                        and floating_ip["Port"] is None
                    ):
                        _floating_ip = {"name": floating_ip["Floating IP Address"]}
                else:
                    log.debug("Request a new floating ip")
                    # Request a new floating ip
                    floating_ip = subprocess.run(  # noqa: S603
                        [cli, "floating", "ip", "create", "public", "-f", "json"],
                        capture_output=True,
                        check=True,
                    )
                    _floating_ip = json.loads(floating_ip.stdout.decode("utf-8"))

                log.debug("Associate the floating ip with the node")
                # Associate the floating ip with the node
                _associate_floating_ip = subprocess.run(  # noqa: S603
                    [
                        cli,
                        "server",
                        "add",
                        "floating",
                        "ip",
                        _server["id"],
                        _floating_ip["name"],
                    ],
                    capture_output=True,
                    check=True,
                )
                ip = _floating_ip["name"]
                log.debug(
                    "Floating IP <%s> associated with the node <%s>, status <%d>",
                    ip,
                    node.alias,
                    _associate_floating_ip,
                )

                floating_ips = node.extra.get("floating-ips", [])
                floating_ips.append(ip)
                node.extra["floating-ips"] = floating_ips
                log.debug("Floating IPs <%s>", floating_ips)
        except Exception as e:
            raise ValueError(f"Server <{node.alias}> not found") from e


def _associate_floating_ip_edge(node: ChameleonDevice) -> None:
    """Associate a floating IP address with a Chameleon Edge device.

    Attempts to retrieve an existing floating IP from /etc/floating-ip. If no IP is
    found, a new floating IP is associated with the device and saved to
    /etc/floating-ip.

    :param node: The Chameleon device to associate a floating IP with
    :type node: ChameleonDevice
    :raises: Potential exceptions from associate_floating_ip() method
    """
    # TODO(mayani): Handle error raised when user exceeds the floating IP usage
    # TODO(mayani): Handle error raised when IP can't be assigned as all are used up
    # Chameleon Edge API does not have a method to get the associated floating
    # IP, if one was already associated with the container
    status = edge._execute(node, "cat /etc/floating-ip")
    if status.rc == 0:
        log.debug("Floating IP already associated with the device")
        ip = status.stdout.strip()
    else:
        ip = node.associate_floating_ip()
        edge._execute(node, f"echo {ip} > /etc/floating-ip")

    log.debug("Floating IP associated with the device %s", ip)
    floating_ips = node.extra.get("floating-ips", [])
    floating_ips.append(ip)
    node.extra["floating-ips"] = floating_ips


def _get_best_ip(
    machine: Host | ChameleonDevice, is_public_ip_required: bool = False
) -> str:
    """Get the best IP address for a given machine.

    Selects an IP address based on priority, filtering out multicast, reserved,
    loopback, and link-local addresses. Supports both Host and ChameleonDevice
    types. Optionally enforces returning a public IP address.

    :param machine: The machine to get an IP address for
    :type machine: Host | ChameleonDevice
    :param is_public_ip_required: Whether a public IP is required, defaults to False
    :type is_public_ip_required: bool, optional
    :return: The selected IP address as a string
    :rtype: str
    :raises ValueError: If a public IP is required but not available
    """
    addresses = []
    # Vagrant Host
    # net_devices={
    #   NetDevice(
    #       name='eth1',
    #       addresses={
    #           IPAddress(
    #               network=None,
    #               ip=IPv6Interface('fe80::a00:27ff:fe6f:87e4/64')),
    #           IPAddress(
    #               network=<enoslib.infra.enos_vagrant.provider.VagrantNetwork ..,
    #               ip=IPv4Interface('172.16.255.243/24'))
    #   ..
    #   )
    # }
    #
    # Chameleon Host
    # net_devices={
    #   NetDevice(
    #     name='eno12419',
    #     addresses=set()),
    #   NetDevice(
    #     name='enp161s0f1',
    #     addresses=set()),
    #   NetDevice(
    #     name='enp161s0f0',
    #     addresses={
    #         IPAddress(
    #             network=<enoslib.infra.enos_openstack.objects.OSNetwork ..>,
    #             ip=IPv4Interface('10.52.3.205/22')
    #         ),
    #         IPAddress(
    #             network=None,
    #             ip=IPv6Interface('fe80::3680:dff:feed:50f4/64'))}
    #         ),
    #   NetDevice(
    #     name='eno8403',
    #     addresses=set()
    #   ),
    #   NetDevice(
    #     name='lo',
    #     addresses={
    #         IPAddress(network=None, ip=IPv4Interface('127.0.0.1/8')),
    #         IPAddress(network=None, ip=IPv6Interface('::1/128'))}),
    #   NetDevice(
    #     name='eno8303',
    #     addresses=set()
    #   ),
    #   NetDevice(
    #     name='eno12399',
    #     addresses=set()
    #   ),
    #   NetDevice(
    #     name='eno12429',
    #     addresses=set()
    #   ),
    #   NetDevice(
    #     name='eno12409',
    #     addresses=set()
    #   )
    # )
    # Chameleon Edge Host
    # Fabric Host
    if isinstance(machine, Host):
        for net_device in machine.net_devices:
            for address in net_device.addresses:
                if isinstance(address.network, DefaultNetwork) and isinstance(
                    address.ip, (IPv4Interface, IPv6Interface)
                ):
                    ip = address.ip.ip
                    if (
                        ip.is_multicast
                        or ip.is_reserved
                        or ip.is_loopback
                        or ip.is_link_local
                    ):
                        continue

                    priority = 1 if ip.is_private else 0
                    addresses.append((address.ip.ip, priority))
    else:
        address = ip_address(machine.address)
        priority = 1 if address.is_private else 0
        addresses.append((address, priority))

    for address in machine.extra.get("floating-ips", []):
        ip = ip_address(address)
        if ip.is_multicast or ip.is_reserved or ip.is_loopback or ip.is_link_local:
            continue

        priority = 1 if ip.is_private else 0
        addresses.append((ip, priority))

    addresses = sorted(addresses, key=lambda v: v[1])
    preferred_ip, priority = addresses[0]
    if is_public_ip_required is True and priority == 1:
        # TODO(mayani): We should not use gateway IP as it could be the same for
        # multiple VMs. Here we should just raise an error
        preferred_ip = machine.extra.get("gateway")
        if preferred_ip is None:
            raise ValueError(
                f"Machine <{machine.name}> does not have a public IP address"
            )

        preferred_ip = ip_address(preferred_ip)

    return str(preferred_ip)


def _get_condor_daemon_roles(
    experiment_config: dict[str, Any],
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Get roles for different Condor daemon types from an experiment configuration.

    Parses the Condor configuration to extract roles for central manager, submit,
    execute, and personal daemon types. Validates daemon types and raises an error for
    invalid types.

    :param experiment_config: Dictionary containing Condor cluster configuration
    :type experiment_config: dict[str, Any]
    :raises ValueError: If an invalid Condor daemon type is encountered
    :return: Tuple of role sets for central manager, submit, execute, and personal
    daemons
    :rtype: tuple[set[str], set[str], set[str], set[str]]
    """
    condor_cluster = experiment_config.get("condor")
    central_manager_roles = set()
    submit_roles = set()
    execute_roles = set()
    personal_roles = set()

    if condor_cluster:
        for daemon, nodes in condor_cluster.items():
            if daemon[0] == "c":  # central-manager
                central_manager_roles.update(nodes["roles"])
            elif daemon[0] == "s":  # submit
                submit_roles.update(nodes["roles"])
            elif daemon[0] == "e":  # execute
                execute_roles.update(nodes["roles"])
            elif daemon[0] == "p":  # personal
                personal_roles.update(nodes["roles"])
            else:
                raise ValueError(f"Invalid condor daemon <{daemon}> in configuration")

    return central_manager_roles, submit_roles, execute_roles, personal_roles


def _install_commons(env: Environment) -> None:
    """Install components needed to run a Kiso experiment.

    1. Disable SELinux on EL-based systems.
    2. Disable Firewall.
    3. Install dependencies, like sudo, curl, etc.
    4. Create a kiso group and a user.
    5. Allow passwordless sudo for kiso.
    6. Copy .ssh dir to ~kiso/.ssh dir.

    :param env: Environment context for the installation
    :type env: Environment
    """
    log.debug("Install Commons")
    console.rule("[bold green]Installing Commons[/bold green]")

    roles = env["roles"]
    # Special case here. Do not pass (roles, roles) to split_roles. Since the Roles
    # object is like a dictionary, so roles - roles["<key>"] and roles & roles["<key>"]
    # doesn't work.
    vms, containers = utils.split_roles(roles.all(), roles)
    results = []

    if vms:
        results.extend(
            utils.run_ansible(
                [Path(__file__).parent / "commons/main.yml"],
                roles=vms,
            )
        )

    if containers:
        for container in containers:
            results.append(
                utils.run_script(
                    container,
                    Path(__file__).parent / "commons/init.sh",
                    "--no-dry-run",
                )
            )

    display.commons(console, results)


def _install_docker(experiment_config: dict[str, Any], env: Environment) -> None:
    """Install Docker on specified roles in an experiment configuration.

    Installs Docker on virtual machines and containers based on the provided
    configuration.
    Supports optional version specification and uses Ansible for VM installations.

    :param experiment_config: Configuration dictionary containing Docker installation
    details
    :type experiment_config: dict[str, Any]
    :param env: Environment context for the installation
    :type env: Environment
    """
    config = experiment_config.get("docker")
    if config is None:
        return

    log.debug("Install Docker")
    console.rule("[bold green]Installing Docker[/bold green]")

    roles = env["roles"]
    _roles = utils.resolve_roles(roles, config["roles"])
    vms, containers = utils.split_roles(_roles, roles)
    if vms:
        results = utils.run_ansible(
            [Path(__file__).parent / "docker/main.yml"], roles=vms
        )

    if containers:
        raise RuntimeError(
            "Docker cannot be installed on containers, because Chameleon Edge does "
            "not allow setting privileged mode for containers"
        )

    display.docker(console, results)


def _install_apptainer(experiment_config: dict[str, Any], env: Environment) -> None:
    """Install Apptainer on specified roles in an experiment configuration.

    Installs Apptainer on virtual machines and containers based on the provided
    configuration. Supports optional version specification and uses Ansible for VM
    installations and a script for container installations.

    :param experiment_config: Configuration dictionary containing Apptainer installation
    details
    :type experiment_config: dict[str, Any]
    :param env: Environment context for the installation
    :type env: Environment
    """
    config = experiment_config.get("apptainer")
    if config is None:
        return

    log.debug("Install Apptainer")
    console.rule("[bold green]Installing Apptainer[/bold green]")

    roles = env["roles"]
    _roles = utils.resolve_roles(roles, config["roles"])
    vms, containers = utils.split_roles(_roles, roles)
    results = []

    if vms:
        results.extend(
            utils.run_ansible([Path(__file__).parent / "apptainer/main.yml"], roles=vms)
        )

    if containers:
        for container in containers:
            results.append(
                utils.run_script(
                    container,
                    Path(__file__).parent / "apptainer/apptainer.sh",
                    "--no-dry-run",
                )
            )

    display.apptainer(console, results)


def _install_condor(experiment_config: dict[str, Any], env: Environment) -> None:
    """Install HTCondor on machines based on experiment configuration and roles.

    Configures and installs HTCondor daemons across different machines in an experiment,
    handling central manager, personal, submit, and execute daemon types. Uses parallel
    execution to install HTCondor on multiple machines simultaneously.

    :param experiment_config: Configuration dictionary containing HTCondor deployment
    details
    :type experiment_config: dict[str, Any]
    :param env: Environment configuration for the experiment
    :type env: Environment
    """
    condor_config = experiment_config.get("condor")
    if condor_config is None:
        return

    log.debug("Install HTCondor")
    console.rule("[bold green]Installing HTCondor[/bold green]")

    roles = env["roles"]
    _condor_host = (
        next(
            iter(utils.resolve_roles(roles, condor_config["central-manager"]["roles"]))
        )
        if "central-manager" in condor_config
        else None
    )
    condor_host_ip = _condor_host.extra["kiso_preferred_ip"] if _condor_host else None
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
        machine_to_daemons = _get_role_daemon_machine_map(condor_config, roles)
        for machine, daemons in machine_to_daemons.items():
            log.debug(
                "Install HTCondor Daemons <%s> on Machine <%s>",
                daemons,
                machine.address
                if isinstance(machine, ChameleonDevice)
                else machine.alias,
            )
            htcondor_config, config_files = _get_condor_config(
                condor_config, daemons, condor_host_ip, machine, env
            )

            extra_vars = dict(extra_vars)
            extra_vars["htcondor_daemons"] = daemons
            extra_vars["htcondor_config"] = htcondor_config
            extra_vars["config_files"] = config_files

            if isinstance(machine, ChameleonDevice):
                future = executor.submit(
                    _install_condor_on_edge, machine, htcondor_config, extra_vars
                )
            else:
                future = executor.submit(
                    utils.run_ansible,
                    [Path(__file__).parent / "htcondor/main.yml"],
                    roles=machine,
                    extra_vars=extra_vars,
                )

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

        display.condor(console, results)


def _get_role_daemon_machine_map(
    condor_config: dict, roles: Roles
) -> dict[ChameleonDevice | Host, set]:
    """Get a mapping of roles, daemons, and machines from the HTCondor configuration.

    _extended_summary_

    :param condor_config: _description_
    :type condor_config: dict
    :param roles: _description_
    :type roles: Roles
    :return: _description_
    :rtype: dict[ChameleonDevice | Host, set]
    """
    role_to_daemons: dict[str, set] = defaultdict(set)
    machine_to_daemons: dict[ChameleonDevice | Host, set] = defaultdict(set)

    for daemon, nodes in condor_config.items():
        for role in nodes["roles"]:
            role_to_daemons[role].add(daemon)

    for role, machines in roles.items():
        if role in role_to_daemons:
            for machine in machines:
                machine_to_daemons[machine].update(role_to_daemons[role])

    # Sort on daemons so that the HTCondor central-manager is installed first
    return dict(sorted(machine_to_daemons.items(), key=_cmp))


def _cmp(item: tuple[str, set]) -> int:
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
        if daemon[0] == "c":  # central-manager
            rv = min(rv, 0)
            break
        if daemon[0] == "p":  # personal
            rv = min(rv, 1)
        elif daemon[0] == "e":  # execute
            rv = min(rv, 2)
        elif daemon[0] == "s":  # submit
            rv = min(rv, 3)
        else:
            raise ValueError(f"Daemon <{daemon}> is not valid")

    return rv


def _get_condor_config(
    condor_config: dict,
    daemons: set[str],
    condor_host_ip: str | None,
    machine: Host | ChameleonDevice,
    env: Environment,
) -> tuple[list[str], dict[str, str]]:
    """Get HTCondor configuration for a specific machine and set of daemons.

    Generates HTCondor configuration based on the specified daemons, machine type,
    and environment requirements. Handles configuration for different daemon roles
    (personal, central manager, submit, execute) and special networking scenarios.

    :param condor_config: Configuration dictionary for HTCondor
    :type condor_config: dict
    :param daemons: Set of daemon types to configure
    :type daemons: set[str]
    :param condor_host_ip: IP address of the Condor host
    :type condor_host_ip: str | None
    :param machine: Machine (Host or ChameleonDevice) being configured
    :type machine: Host | ChameleonDevice
    :param env: Environment configuration
    :type env: Environment
    :return: A tuple containing HTCondor configuration lines and additional config files
    :rtype: tuple[list[str], dict[str, str]]
    """
    is_public_ip_required = env["is_public_ip_required"]

    htcondor_config = [
        f"CONDOR_HOST = {condor_host_ip}",
        f"TRUST_DOMAIN = {const.TRUST_DOMAIN}",
    ]
    config_files = {}
    for daemon in daemons:
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

        if "config-file" in condor_config[daemon]:
            config_files[f"kiso-{daemon}-config-file"] = str(
                Path(condor_config[daemon]["config-file"]).resolve()
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
    machine: ChameleonDevice, htcondor_config: list[str], extra_vars: dict
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
            Path(__file__).parent / "htcondor/htcondor.sh",
            "--no-dry-run",
        )
    )

    results.append(
        utils.run_script(
            machine,
            Path(__file__).parent / "htcondor/pegasus.sh",
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
        # User may change the experiment configuration and rerun the up command, so we
        # remove old configuration files before configuring HTCondor
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
                    f"mv {config_root}/{Path(config_file).name} {config_root}/{fname}",
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
            f"mv {sec_password_directory}/{Path(extra_vars['pool_passwd_file']).name} "
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


@validate_config
@enostask()
def run(
    experiment_config: dict[str, Any],
    force: bool = False,
    env: Environment = None,
    **kwargs: Any,  # noqa: ANN401
) -> None:
    """Run the defined experiments.

    Executes a series of experiments by performing the following steps:
    - Copies experiment directory to remote roles
    - Copies input files for each experiment
    - Runs setup scripts
    - Executes experiment workflows
    - Runs post-scripts
    - Copies output files

    :param experiment_config: Configuration dictionary containing experiment details
    :type experiment_config: dict[str, Any]
    :param force: Force rerunning of experiments, defaults to False
    :type force: bool, optional
    :param env: Environment configuration containing providers, roles, and networks
    :type env: Environment, optional
    :param kwargs: Additional keyword arguments
    :type kwargs: dict
    """
    log.debug("Run Kiso experiments")
    console.rule("[bold green]Run experiments[/bold green]")

    experiments = experiment_config["experiments"]
    variables = copy.deepcopy(experiment_config.get("variables", {}))
    env.setdefault("experiments", {})
    if force is True:
        env["experiments"] = {}

    _copy_experiment_dir(env)
    for experiment_index, experiment in enumerate(experiments):
        env["experiments"].setdefault(experiment_index, {})
        _run_experiments(experiment_index, experiment, variables, env)


def _copy_experiment_dir(env: Environment) -> None:
    """Copy experiment directory to remote roles.

    Copies the experiment directory from the local working directory to the remote
    working directory for specified submit node roles. Supports copying to both virtual
    machines and containers.

    :param env: Environment configuration containing roles and working directory
    information
    :type env: Environment
    :raises Exception: If directory copy fails for any role
    """
    log.debug("Copy experiment directory to remote nodes")
    console.print("Copying experiment directory to remote nodes")

    roles = env["roles"]
    # Special case here. Do not pass (roles, roles) to split_roles. Since the Roles
    # object is like a dictionary, so roles - roles["<key>"] and roles & roles["<key>"]
    # doesn't work.
    vms, containers = utils.split_roles(roles.all(), roles)

    try:
        kiso_state = env["experiments"]
        if kiso_state.get("copy-experiment-directory") == const.STATUS_OK:
            return
        kiso_state["copy-experiment-directory"] = const.STATUS_STARTED
        src = Path(env["wd"])
        dst = Path(env["remote_wd"]).parent
        if vms:
            with utils.actions(roles=vms, run_as=const.KISO_USER, strategy="free") as p:
                p.copy(
                    src=str(src),
                    dest=str(dst),
                    mode="preserve",
                    task_name="Copy experiment dir",
                )
        if containers:
            for container in containers:
                edge.upload(container, src, dst, user=const.KISO_USER)
    except Exception:
        kiso_state["copy-experiment-directory"] = const.STATUS_FAILED
        raise
    else:
        kiso_state["copy-experiment-directory"] = const.STATUS_OK


def _run_experiments(
    index: int, experiment: dict, variables: dict, env: Environment
) -> None:
    """Run multiple workflow instances for a specific experiment.

    Generates and executes workflows for each instance of an experiment.

    :param index: The overall experiment index
    :type index: int
    :param experiment: Configuration dictionary for the experiment
    :type experiment: dict
    :param env: Environment context containing workflow and execution details
    :type env: Environment
    """
    # Get the `kind` of experiment
    kind = experiment["kind"]

    # Locate the EntryPoint for the runner `kind` of experiment and load it
    runner_cfg = utils.get_runner(kind)

    # Runner's DATACLASS attribute points to a :py:class:`dataclasses.dataclass` that
    # defines the experiment configuration schema for the `kind` of experiment
    data_cls = runner_cfg.DATACLASS

    # Convert the JSON configuration to a :py:class:`dataclasses.dataclass`
    runner_obj = from_dict(data_cls, experiment, Config(convert_key=_to_snake_case))

    # Instantiate the runner class. The runner class to use is defined in the
    # runner's `RUNNER` attribute
    runner = runner_cfg.RUNNER(
        runner_obj,
        index,
        env["wd"],  # Local experiment working directory
        env["remote_wd"],  # Remote experiment working directory
        env["resultdir"],  # Local results directory
        env["roles"],  # Provisioned resources
        env["experiments"][index],  # Store to maintain the state of the experiment
        console=console,  # Console object to output experiment progress
        log=logging.getLogger("kiso.wf.pegasus"),  # Logger object to use
        variables=variables,  # Variables defined globally for the experiment
    )

    # Run the experiment
    runner()


def _to_snake_case(key: str) -> str:
    return "-".join(key.split("_"))


@validate_config
@enostask()
def down(
    experiment_config: dict[str, Any], env: Environment = None, **kwargs: dict
) -> None:
    """Destroy the resources provisioned for the experiments.

    This function is responsible for tearing down and cleaning up resources
    associated with an experiment configuration using the specified providers.

    :param experiment_config: Configuration dictionary for the experiment
    :type experiment_config: dict[str, Any]
    :param env: Environment object containing provider information
    :type env: Environment, optional
    :param kwargs: Additional keyword arguments
    :type kwargs: dict
    """
    log.debug("Destroy the resources provisioned for the experiments")
    console.rule(
        "[bold green]Destroy resources created for the experiments[/bold green]"
    )

    if "providers" not in env:
        log.debug("No providers found, skipping")
        console.rule(
            "No providers found. Either resources were not provisioned or the output "
            "directory was removed"
        )
        return

    providers = env["providers"]
    providers.destroy()
