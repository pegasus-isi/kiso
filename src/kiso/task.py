"""_summary_.

_extended_summary_
"""

# ruff: noqa: ARG001
from __future__ import annotations

import json
import logging
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import wraps
from ipaddress import IPv4Interface, IPv6Interface, ip_address
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

import enoslib as en
import yaml
from enoslib.objects import DefaultNetwork, Host, Networks, Roles
from enoslib.task import Environment, enostask
from jsonschema_pyref import ValidationError, validate

import kiso.constants as const
from kiso import utils
from kiso.log import get_process_pool_executor
from kiso.schema import SCHEMA
from kiso.utils import PegasusWorkflowProgress
from kiso.version import __version__

if TYPE_CHECKING:
    from os import PathLike

    from enoslib.api import CommandResult
    from enoslib.infra.provider import Provider


T = TypeVar("T")

PROVIDER_MAP: dict[str, tuple[Callable[[dict], Any], Callable[..., Any]]] = {}

log = logging.getLogger("kiso")

if hasattr(en, "Vagrant"):
    PROVIDER_MAP["vagrant"] = (en.VagrantConf.from_dictionary, en.Vagrant)
if hasattr(en, "CBM"):
    from enoslib.infra.enos_openstack.utils import source_credentials_from_rc_file
    from zunclient.common.apiclient.exceptions import GatewayTimeout

    PROVIDER_MAP["chameleon"] = (en.CBMConf.from_dictionary, en.CBM)
if hasattr(en, "ChameleonEdge"):
    from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice
    from zunclient.common.apiclient.exceptions import GatewayTimeout

    PROVIDER_MAP["chameleon-edge"] = (
        en.ChameleonEdgeConf.from_dictionary,
        en.ChameleonEdge,
    )
if hasattr(en, "Fabric"):
    PROVIDER_MAP["fabric"] = (en.FabricConf.from_dictionary, en.Fabric)


# TODO(mayani): Change the output en.config._set("ansible_stdout", "noop")


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
    def wrapper(experiment_config: PathLike | dict, *args: tuple, **kwargs: dict) -> T:
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
def check(experiment_config: dict, **kwargs: dict) -> None:
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
    :type experiment_config: dict
    :param kwargs: Additional keyword arguments
    :type kwargs: dict
    """
    log.debug("Check only one vagrant site is present in the experiment")
    def_roles: Counter = _get_defined_roles(experiment_config)

    log.debug(
        "Check roles referenced in experiments section are defined in the sites section"
    )
    _check_undefined_roles(experiment_config, def_roles)

    if "docker" in experiment_config:
        log.debug("Check docker is not installed on Chameleon edge")
        _check_docker_is_not_on_edge(experiment_config)

    log.debug(
        "Check roles referenced in condor section are defined in the sites section"
    )
    _check_condor_roles(experiment_config, def_roles)

    log.debug("Check there is only one central-manager")
    _check_central_manager_cardinality(experiment_config, def_roles)

    log.debug("Check execute node configurations doesn't overlap")
    _check_exec_node_overlap(experiment_config)

    log.debug("Check worker nodes configurations doesn't overlap")
    _check_worker_node_overlap(experiment_config)

    log.debug("Check for missing files in inputs")
    _check_missing_input_files(experiment_config)

    log.debug(
        "Check submut-node-roles specified in the experiment are valid submit "
        "nodes as per the Condor configuration"
    )
    _check_submit_roles_are_submit_nodes(experiment_config)

    log.debug("Check EnOSlib")
    en.MOTD = en.INFO = ""
    en.check(platform_filter=["Vagrant", "Fabric", "Chameleon", "ChameleonEdge"])


def _get_defined_roles(experiment_config: dict) -> Counter:
    """Get the defined roles from the experiment configuration.

    Extracts and counts roles defined in the sites section of the experiment
    configuration. Validates that only one Vagrant site is present and generates
    additional role variants.

    :param experiment_config: Configuration dictionary containing site and resource
    definitions
    :type experiment_config: dict
    :raises ValueError: If multiple Vagrant sites are detected
    :return: A counter of defined roles with their counts
    :rtype: Counter
    """
    vagrant_sites = 0
    def_roles: Counter = Counter()

    for site in experiment_config["sites"]:
        if site["kind"] == "vagrant":
            vagrant_sites += 1

        for machine in site["resources"]["machines"]:
            for role in machine["roles"]:
                def_roles.update({role: machine.get("number", 1)})
                def_roles.update({site["kind"]: machine.get("number", 1)})
    else:
        if vagrant_sites > 1:
            raise ValueError("Multiple vagrant sites are not supported")

        extra_roles = {}
        for role, count in def_roles.items():
            for index in range(1, count + 1):
                extra_roles[f"kiso.{role}.{index}"] = 1
        def_roles.update(extra_roles)

    return def_roles


def _check_undefined_roles(experiment_config: dict, def_roles: Counter) -> None:
    """Check for undefined roles in experiment configuration.

    Validates that all roles referenced in experiment setup, input locations,
    and result locations are defined in the experiment configuration.

    :param experiment_config: Complete experiment configuration dictionary
    :type experiment_config: dict
    :param def_roles: Counter of predefined roles in the configuration
    :type def_roles: Counter
    :raises ValueError: If any undefined roles are found in the experiment configuration
    """
    undef_roles = defaultdict(set)
    for experiment in experiment_config["experiments"]:
        for index, setup in enumerate(experiment.get("setup", {})):
            undef_roles[experiment["name"]].update(
                [
                    (f"setup[{index}]", role)
                    for role in setup["roles"]
                    if role not in def_roles
                ]
            )

        for location in experiment.get("inputs", []):
            undef_roles[experiment["name"]].update(
                [
                    ("inputs", role)
                    for role in location["roles"]
                    if role not in def_roles
                ]
            )

        for location in experiment.get("outputs", []):
            undef_roles[experiment["name"]].update(
                [
                    ("outputs", role)
                    for role in location["roles"]
                    if role not in def_roles
                ]
            )

        if not undef_roles[experiment["name"]]:
            del undef_roles[experiment["name"]]
    else:
        if undef_roles:
            raise ValueError(
                "Undefined roles referenced in experiments section", undef_roles
            )


def _check_docker_is_not_on_edge(experiment_config: dict) -> None:
    """Check that Docker is not configured to run on Chameleon Edge devices.

    Validates that no Docker roles are assigned to Chameleon Edge resources,
    which is not supported. Raises a ValueError if such a configuration is detected.

    :param experiment_config: Experiment configuration dictionary
    :type experiment_config: dict
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


def _check_condor_roles(experiment_config: dict, def_roles: Counter) -> None:
    """Check Condor roles and configuration files in an experiment configuration.

    Validates that all Condor roles are defined and all referenced configuration files
    exist.

    :param experiment_config: Dictionary containing Condor configuration for an
    experiment
    :type experiment_config: dict
    :param def_roles: Counter of predefined roles
    :type def_roles: Counter
    :raises ValueError: If undefined roles are referenced or configuration files are
    missing
    """
    undef_roles = defaultdict(set)
    missing_config_files = []
    for condor, nodes in experiment_config.get("condor", {}).items():
        for node, roles in nodes.items():
            if node.endswith("-file"):
                if not Path(roles).exists():
                    missing_config_files.append((condor, node, roles))

                continue

            undef_roles[condor].update(
                [role for role in roles if role not in def_roles]
            )

            if not undef_roles[condor]:
                del undef_roles[condor]
    else:
        if undef_roles:
            raise ValueError(
                "Undefined roles referenced in condor section", undef_roles
            )

        if missing_config_files:
            raise ValueError(
                "Missing config files referenced in condor section",
                missing_config_files,
            )


def _check_central_manager_cardinality(
    experiment_config: dict, def_roles: Counter
) -> None:
    """Check the cardinality of Condor central manager nodes in an experiment configuration.

    Validates that only one machine is assigned the central-manager role.

    :param experiment_config: Dictionary containing Condor configuration for an
    experiment
    :type experiment_config: dict
    :param def_roles: Counter of predefined roles
    :type def_roles: Counter
    :raises ValueError: If more than one machine is assigned the central-manager role
    """  # noqa: E501
    central_manager = experiment_config.get("condor", {}).get("central-manager", None)
    if central_manager:
        for role in central_manager["roles"]:
            if def_roles[role] > 1:
                raise ValueError("Multiple central-manager machines are not supported")


def _check_exec_node_overlap(experiment_config: dict) -> None:
    """Check for overlapping roles in Condor execute nodes.

    Validates that no two execute nodes in the experiment configuration
    have overlapping role assignments, which could cause configuration conflicts.

    :param experiment_config: Dictionary containing Condor node configuration
    :type experiment_config: dict
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


def _check_worker_node_overlap(experiment_config: dict) -> None:
    """Check for overlapping roles in Condor submit nodes.

    Validates that no two submit nodes in the experiment configuration
    have overlapping role assignments, which could cause configuration conflicts.

    :param experiment_config: Dictionary containing Condor node configuration
    :type experiment_config: dict
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


def _check_missing_input_files(experiment_config: dict) -> None:
    """Check for missing input files in experiment configurations.

    Validates the existence of input files specified in experiment configurations.
    Raises a ValueError with details of any missing input files and their associated
    experiments.

    :param experiment_config: Configuration dictionary containing experiment details
    :type experiment_config: dict
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


def _check_submit_roles_are_submit_nodes(experiment_config: dict) -> None:
    """Check for missing input files in experiment configurations.

    Validates the existence of input files specified in experiment configurations.
    Raises a ValueError with details of any missing input files and their associated
    experiments.

    :param experiment_config: Configuration dictionary containing experiment details
    :type experiment_config: dict
    :raises ValueError: If any specified input files do not exist
    """
    submit_nodes = set()
    for i, nodes_i in experiment_config.get("condor", {}).items():
        if not (
            i[0] == "s"  # submit
            or i[0] == "p"  # personal
        ):
            continue
        submit_nodes.update(nodes_i["roles"])

    for experiment in experiment_config["experiments"]:
        submit_roles = set(experiment["submit-node-roles"])
        if not submit_roles.intersection(submit_nodes):
            raise ValueError(
                f"Experiment <{experiment['name']}>'s submit-node-roles do not map to "
                f"any submit node(s) {submit_nodes}"
            )


@validate_config
@enostask(new=True, symlink=False)
def up(
    experiment_config: dict,
    env: Environment = None,
    **kwargs: dict,
) -> None:
    """Create and set up resources for running an experiment.

    Initializes the experiment environment, sets up working directories, and prepares
    infrastructure by initializing sites, installing Docker, Apptainer, and Condor
    across specified roles.

    :param experiment_config: Configuration dictionary defining experiment parameters
    :type experiment_config: dict
    :param env: Optional environment context for the experiment, defaults to None
    :type env: Environment, optional
    :param kwargs: Additional keyword arguments, including working directory
    specification
    :type kwargs: dict
    """
    env["version"] = __version__
    env["wd"] = str(kwargs.get("wd", Path.cwd()))
    env["remote_wd"] = str(Path("~kiso") / Path(env["wd"]).name)

    _providers, _roles, _networks = _init_sites(experiment_config, env)
    _install_docker(experiment_config, env)
    _install_apptainer(experiment_config, env)
    _install_condor(experiment_config, env)


def _init_sites(
    experiment_config: dict, env: Environment
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
    :type experiment_config: dict
    :param env: Environment context for the experiment
    :type env: Environment
    :return: A tuple of providers, roles, and networks for the experiment
    :rtype: tuple[list[Provider], Roles, Networks]
    """
    log.debug("Initializing sites")

    providers = []
    roles = Roles()
    networks = Networks()

    with get_process_pool_executor() as executor:
        futures = [
            executor.submit(_init_site, site_index, site)
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


def _init_site(index: int, site: dict) -> tuple[Provider, Roles, Networks]:
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
    :type site: dict
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
            container["exposed_ports"] = list(exposed_ports)

    conf = PROVIDER_MAP[kind][0](site)
    provider = PROVIDER_MAP[kind][1](conf)

    _roles, _networks = provider.init()
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
            node.extra["rc_file"] = str(Path(conf.rc_file).expanduser().resolve())

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


def _extend_roles(experiment_config: dict, roles: Roles) -> dict[str, set]:
    """Extend roles for an experiment configuration by adding unique roles and flags to nodes.

    Processes the given roles and experiment configuration to:
    - Create unique roles for each node based on their original role
    - Add flags to nodes indicating their HTCondor daemon types (central manager,
    submit, execute, personal)
    - Add flags for container technologies (Docker, Apptainer)
    - Track the sites where different HTCondor daemon types are located

    :param experiment_config: Configuration dictionary for the experiment
    :type experiment_config: dict
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
            raise ValueError("Assigning public IPs to Vagrant VMs is not supported")
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
                # print(server, floating_ip, associate_floating_ip.returncode)

                floating_ips = node.extra.get("floating-ips", [])
                floating_ips.append(ip)
                node.extra["floating-ips"] = floating_ips
                # print("@" * 10, floating_ips)
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
    status = node.execute("cat /etc/floating-ip")
    if status["exit_code"] == 0:
        log.debug("Floating IP already associated with the device")
        ip = status["output"].strip()
    else:
        ip = node.associate_floating_ip()
        node.execute(f"sh -c 'echo {ip} > /etc/floating-ip'")

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
    experiment_config: dict,
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Get roles for different Condor daemon types from an experiment configuration.

    Parses the Condor configuration to extract roles for central manager, submit,
    execute, and personal daemon types. Validates daemon types and raises an error for
    invalid types.

    :param experiment_config: Dictionary containing Condor cluster configuration
    :type experiment_config: dict
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


def _install_docker(experiment_config: dict, env: Environment) -> None:
    """Install Docker on specified roles in an experiment configuration.

    Installs Docker on virtual machines and containers based on the provided
    configuration.
    Supports optional version specification and uses Ansible for VM installations.

    :param experiment_config: Configuration dictionary containing Docker installation
    details
    :type experiment_config: dict
    :param env: Environment context for the installation
    :type env: Environment
    """
    log.debug("Install Docker")

    config = experiment_config.get("docker")
    if config is None:
        return

    roles = env["roles"]
    agents = roles[config["roles"][0]]
    for role in enumerate(config["roles"]):
        agents = agents | roles[role]

    vms, containers = utils.split_roles(agents, roles)

    if vms:
        utils.run_ansible(
            [Path(__file__).parent / "docker/main.yml"],
            roles=vms,
            on_error_continue=True,
        )

    if containers:
        raise RuntimeError(
            "Docker cannot be installed on containers, because Chameleon Edge does "
            "not allow setting privileged mode for containers"
        )


def _install_apptainer(experiment_config: dict, env: Environment) -> None:
    """Install Apptainer on specified roles in an experiment configuration.

    Installs Apptainer on virtual machines and containers based on the provided
    configuration. Supports optional version specification and uses Ansible for VM
    installations and a script for container installations.

    :param experiment_config: Configuration dictionary containing Apptainer installation
    details
    :type experiment_config: dict
    :param env: Environment context for the installation
    :type env: Environment
    """
    log.debug("Install Apptainer")

    config = experiment_config.get("apptainer")
    if config is None:
        return

    roles = env["roles"]
    agents = roles[config["roles"][0]]
    for role in enumerate(config["roles"]):
        agents = agents | roles[role]

    vms, containers = utils.split_roles(agents, roles)

    if vms:
        utils.run_ansible(
            [Path(__file__).parent / "apptainer/main.yml"],
            roles=vms,
            on_error_continue=True,
        )

    if containers:
        for container in containers:
            _run_script(
                container,
                Path(__file__).parent / "apptainer/apptainer.sh",
                "--no-dry-run",
            )


def _run_script(
    container: ChameleonDevice,
    script: Path,
    *args: str,
    workdir: str | None = None,
    user: str | None = None,
    poll_interval: int = const.POLL_INTERVAL,
) -> dict:
    """Run a script on a container with specified parameters.

    Uploads a script to a container, sets appropriate permissions, executes it, and
    handles cleanup.

    :param container: The target container device for script execution
    :type container: ChameleonDevice
    :param script: Path to the script to be executed
    :type script: Path
    :param args: Optional additional arguments to pass to the script
    :type args: str
    :param workdir: Working directory for script execution, defaults to system
    temporary directory
    :type workdir: str | None, optional
    :param user: User to execute the script as, defaults to root
    :type user: str | None, optional
    :param poll_interval: Interval between script execution status checks
    :type poll_interval: int, optional
    :return: _description_
    :rtype: dict
    """
    workdir = shlex.quote(str(utils.expanduser(container, workdir or const.TMP_DIR)))
    _user = shlex.quote(user or const.ROOT_USER)

    with (
        tempfile.NamedTemporaryFile(mode="w") as file,
        script.open() as script_file,
    ):
        file.write(script_file.read())
        file.seek(0)

        remote_script = f"{workdir}/{Path(file.name).name}"
        container.upload(file.name, workdir)  # noqa: S108
        container.execute(f"chmod +x {remote_script}")
        container.execute(f"chown {_user}:{_user} {remote_script}")

        status = _wait_for_script(
            container,
            remote_script,
            *args,
            user=user,
            workdir=workdir,
            poll_interval=poll_interval,
        )
        print("--", script, remote_script, status)

        container.execute(f"rm -f {remote_script}")
        return status


def _wait_for_script(
    container: ChameleonDevice,
    command: str | Path,
    *args: str,
    workdir: str | None = None,
    user: str | None = None,
    poll_interval: int = const.POLL_INTERVAL,
) -> dict:
    """Wait for a script to complete execution on a container and return its status.

    Executes a command in a specified container, optionally as a specific user, and
    tracks its execution status by creating temporary log and done files. Polls for
    script completion and returns the execution result.

    :param container: The container device where the script will be executed
    :type container: ChameleonDevice
    :param command: The script or command to execute
    :type command: str | Path
    :param args: Additional arguments to pass to the command
    :type args: str
    :param workdir: Working directory for script execution, defaults to temporary
    directory
    :type workdir: str | None, optional
    :param user: User to execute the script as, defaults to None
    :type user: str | None, optional
    :param poll_interval: Interval between status checks, defaults to system poll
    interval
    :type poll_interval: int, optional
    :return: Dictionary containing script execution status and output
    :rtype: dict
    """
    command = str(command) if isinstance(command, Path) else command
    workdir = shlex.quote(str(utils.expanduser(container, workdir or const.TMP_DIR)))
    user = shlex.quote(user) if user else None
    poll_interval = poll_interval or const.POLL_INTERVAL

    status_file = f"{const.TMP_DIR}/{utils.get_random_string(length=5)}"
    cmd = []
    if workdir:
        cmd.extend(["cd", shlex.quote(workdir), ";"])
    cmd.append(command)
    if args:
        cmd.extend([shlex.quote(arg) for arg in args])
    cmd.extend([">", f"{status_file}.log", "2>&1"])
    cmd.extend([";", "echo", "$?", ">", f"{status_file}.done"])

    wrapped_cmd = [] if user is None else ["sudo", "-u", user]
    wrapped_cmd.extend(["sh", "-c", shlex.quote(" ".join(cmd))])
    print(wrapped_cmd)

    status = container.execute(" ".join(wrapped_cmd))
    if status["exit_code"] is None:
        while True:
            status_code = container.execute(f"cat {status_file}.done")
            if status_code["exit_code"] == 0:
                status = container.execute(f"cat {status_file}.log")
                status["exit_code"] = int(status_code["output"].strip())
                break
            time.sleep(poll_interval)
    else:
        status["output"] = container.execute(f"cat {status_file}.log")["output"].strip()

    container.execute(f"rm -f {status_file}.log {status_file}.done")

    return status


def _install_condor(experiment_config: dict, env: Environment) -> None:
    """Install HTCondor on machines based on experiment configuration and roles.

    Configures and installs HTCondor daemons across different machines in an experiment,
    handling central manager, personal, submit, and execute daemon types. Uses parallel
    execution to install HTCondor on multiple machines simultaneously.

    :param experiment_config: Configuration dictionary containing HTCondor deployment
    details
    :type experiment_config: dict
    :param env: Environment configuration for the experiment
    :type env: Environment
    """
    log.debug("Install HTCondor")

    condor_config = experiment_config.get("condor")
    if condor_config is None:
        return

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
    # print("Condor Host", _condor_host)
    with get_process_pool_executor() as executor:
        futures = []
        machine_to_daemons = _get_role_daemon_machine_map(condor_config, roles)
        for machine, daemons in machine_to_daemons.items():
            # print(
            #     machine.address
            #     if isinstance(machine, ChameleonDevice)
            #     else machine.alias,
            #     daemons,
            # )
            htcondor_config, config_files = _get_condor_config(
                condor_config, daemons, condor_host_ip, machine, env
            )

            extra_vars = dict(extra_vars)
            extra_vars["htcondor_daemons"] = daemons
            extra_vars["htcondor_config"] = htcondor_config
            extra_vars["config_files"] = config_files

            # print(machine, daemons, extra_vars)
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
                    on_error_continue=True,
                )

            # Wait for HTCondor Central Manager to be installed and started before
            # installing in on any other machine
            if "central-manager" in daemons:
                future.result()
            else:
                futures.append(future)

        # We need to wait for HTCondor to be installed on the remaining machines,
        # because even though the ProcessPoolExecutor does not exit the context
        # until all running futures have finished, the code gets stuck if we don't
        # invoke result() on the futures
        for future in futures:
            future.result()


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


def _install_condor_on_edge(
    machine: ChameleonDevice, htcondor_config: list[str], extra_vars: dict
) -> None:
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
    """
    _run_script(
        machine,
        Path(__file__).parent / "htcondor/init.sh",
        "--no-dry-run",
    )
    _run_script(
        machine,
        Path(__file__).parent / "htcondor/htcondor.sh",
        "--no-dry-run",
    )
    _run_script(
        machine,
        Path(__file__).parent / "htcondor/pegasus.sh",
        "--no-dry-run",
    )

    config_root = machine.execute("condor_config_val CONFIG_ROOT")["output"].strip()
    config_root = f"{config_root}/config.d"

    config_files = extra_vars.get("config_files")
    if config_files:
        # User may change the experiment configuration and rerun the up command, so we
        # remove old configuration files before configuring HTCondor
        machine.execute(f"rm -rf  {config_root}/kiso-*-config-file")

        for fname, config_file in config_files.items():
            machine.upload(config_file, f"{config_root}")
            machine.execute(
                f"mv {config_root}/{Path(config_file).name} {config_root}/{fname}"
            )
        machine.execute(
            f"sh -c 'chown root:root {config_root}/* ; chmod 644 {config_root}/*'"
        )

    for daemon in extra_vars.get("htcondor_daemons", set()):
        if daemon == "personal":
            return

    sec_password_directory = machine.execute(
        "condor_config_val SEC_PASSWORD_DIRECTORY"
    )["output"].strip()

    sec_token_system_directory = machine.execute(
        "condor_config_val SEC_TOKEN_SYSTEM_DIRECTORY"
    )["output"].strip()

    NL = "\n"
    DOLLAR = "\\$"
    machine.execute(f"""sh -c 'cat > "{config_root}/01-kiso" << EOF
{NL.join(htcondor_config).replace("$", DOLLAR)}
EOF
'""")

    machine.upload(extra_vars["pool_passwd_file"], f"{sec_password_directory}/")
    machine.execute(
        f"mv {sec_password_directory}/{Path(extra_vars['pool_passwd_file']).name} "
        f"{sec_password_directory}/POOL"
    )
    machine.execute(
        f"sh -c 'chown root:root {sec_password_directory}/POOL ; "
        f"chmod 600 {sec_password_directory}/POOL ; "
        f"rm -f {config_root}/00-minicondor'"
    )

    machine.execute(
        "condor_token_create -key POOL "
        f"-identity {extra_vars['token_identity']} "
        f"-file {sec_token_system_directory}/POOL.token"
    )

    # TODO(mayani): Restart HTCondor
    # machine.execute(
    #     "sh -c 'ps aux | grep condor | grep -v condor | awk \\'{print $2}\\' | "
    #     "xargs kill -9'"
    # )
    # machine.execute("condor_master")
    machine.execute("condor_restart")


@validate_config
@enostask()
def run(
    experiment_config: dict,
    env: Environment = None,
    **kwargs: dict,
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
    :type experiment_config: dict
    :param env: Environment configuration containing providers, roles, and networks
    :type env: Environment, optional
    :param kwargs: Additional keyword arguments
    :type kwargs: dict
    """
    log.debug("Run Kiso experiments")

    experiments = experiment_config["experiments"]
    env["experiments"] = {}
    _copy_experiment_dir(experiments, env)
    for experiment_index, experiment in enumerate(experiments):
        env["experiments"][experiment_index] = {}
        _copy_inputs(experiment_index, experiment, env)
        _run_setup_scripts(experiment_index, experiment, env)
        _run_experiments(experiment_index, experiment, env)
        _run_post_scripts(experiment_index, experiment, env)
        _fetch_outputs(experiment_index, experiment, env)


def _copy_experiment_dir(experiments: dict, env: Environment) -> None:
    """Copy experiment directory to remote roles.

    Copies the experiment directory from the local working directory to the remote
    working directory for specified submit node roles. Supports copying to both virtual
    machines and containers.

    :param experiments: List of experiments with optional submit node roles
    :type experiments: dict
    :param env: Environment configuration containing roles and working directory
    information
    :type env: Environment
    :raises Exception: If directory copy fails for any role
    """
    roles = env["roles"]
    # Special case here. Do not pass (roles, roles) to split_roles. Since the Roles
    # object is like a dictionary, so roles - roles["<key>"] and roles & roles["<key>"]
    # doesn't work.
    vms, containers = utils.split_roles(roles.all(), roles)

    try:
        env["experiments"]["copy-experiment-directory"] = "STARTED"
        src = Path(env["wd"])
        dst = Path(env["remote_wd"]).parent
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
                    task_name="Copy experiment dir",
                )
        if containers:
            for container in containers:
                _upload_files(container, src, dst, user=const.KISO_USER)
    except Exception:
        env["experiments"]["copy-experiment-directory"] = "FAILED"
        raise
    else:
        env["experiments"]["copy-experiment-directory"] = "DONE"


def _upload_files(
    container: ChameleonDevice,
    src: Path,
    dst: Path,
    user: str | None = None,
) -> None:
    """Upload files or directories to a Chameleon container with robust handling of file and directory uploads.

    Handles file and directory uploads to a Chameleon container, with support for:
    - Checking source file/directory existence
    - Resolving destination paths
    - Uploading individual files or entire directory structures
    - Setting ownership of uploaded files/directories
    - Handling potential upload timeouts for large files/directories

    :param container: The Chameleon container device to upload files to
    :type container: ChameleonDevice
    :param src: Source path of file or directory to upload
    :type src: Path
    :param dst: Destination path on the container
    :type dst: Path
    :param user: User to set as owner of uploaded files (defaults to root)
    :type user: str | None, optional
    :raises ValueError: If source does not exist or destination is invalid
    """  # noqa: E501
    user = shlex.quote(user or const.ROOT_USER)

    # Check the source exists locally
    if not src.exists():
        raise ValueError(f"Source {src} doesn't exist", src)

    # The upload method of the Chameleon Edge API requires the destination to be a
    # directory. Also, it does not resolve destinations with a ~, i.e., ~kiso is not
    # resolved to /home/kiso, so we need to check directory exists and resolve it
    log.debug("Check destination <%s> exists and is a directory", dst)
    dst = Path(utils.expanduser(container, dst))
    cmd = f"cd {shlex.quote(str(dst))} && pwd"
    is_dir = container.execute(f"sh -c {shlex.quote(cmd)}")
    if is_dir["exit_code"] != 0:
        raise ValueError(
            f"Destination {dst} is either not a directory or can't be accessed", dst
        )
    dst = Path(is_dir["output"].strip())
    log.debug("Resolved destination directory is <%s>", dst)

    # TODO(mayani): Handle timeout while uploading large files
    # If the source is a file we can directly upload it
    if src.is_file():
        container.upload(str(src), dest=str(dst))
        cmd = f"chown {user}:{user} {shlex.quote(str(dst / src.name))}"
        container.execute(f"sh -c {shlex.quote(cmd)}")
        return

    try:
        container.upload(str(src), str(dst))
    except (Exception, GatewayTimeout):
        log.debug("Failed to upload file <%s> to <%s>", src, dst, exc_info=True)
        # If the source is a directory, create a destination directory with the
        # same name
        cmd = f"mkdir -p {shlex.quote(str(dst / src.name))}"
        log.debug("Create directory <%s> on edge", dst / src.name)
        container.execute(f"sh -c {shlex.quote(cmd)}")

        # TODO(mayani): Handle timeout while uploading large files
        # The Chameleon Edge API's upload method times out after ~60 seconds.
        # Uploading  an entire directory is more likely to time out and there is no
        # work around for this. To minimize the chances of time outs, we walk over the
        # source directory. We create directories as necessary and upload files one at
        # a time. If the file is itself too large and the method times out, then there
        # is no work around for it
        for file in Path(src).rglob("**"):
            _dst = dst / file.relative_to(src.parent)
            if file.is_dir():
                cmd = f"mkdir -p {shlex.quote(str(_dst))}"
                log.debug("Create directory <%s> on edge", _dst)
                container.execute(f"sh -c {shlex.quote(cmd)}")
            elif file.is_file():
                log.debug("Upload file <%s> to <%s>", file, _dst.parent)
                try:
                    container.upload(str(file), dest=str(_dst.parent))
                except GatewayTimeout:
                    log.error("Uploading of <%s> timed out", file)
                    ...

    # Change the ownership fo the uploaded directory to be owned by the specified user
    cmd = f"chown -R {user}:{user} {shlex.quote(str(dst))}"
    container.execute(f"sh -c {shlex.quote(cmd)}")


def _copy_inputs(index: int, experiment: dict, env: Environment) -> None:
    """Copy input files to specified destinations across virtual machines and containers.

    Iterates through input locations defined in the experiment configuration, resolving
    roles and copying files to their destination. Supports copying to both virtual
    machines and containers while tracking the status of each copy operation.

    :param index: The overall experiment index
    :type index: int
    :param experiment: Configuration dictionary containing experiment details
    :type experiment: dict
    :param env: Environment context with roles and execution settings
    :type env: Environment
    :raises Exception: If any input file copy operation fails
    """  # noqa: E501
    name = experiment["name"]
    roles = env["roles"]
    inputs = experiment.get("inputs", [])

    log.debug("Starting to copy inputs to the destination for <%s:%d>", name, index)

    env["experiments"][index]["copy-inputs"] = "STARTED"
    env["experiments"][index]["copy-input"] = {}
    for _index, location in enumerate(inputs):
        _roles = utils.resolve_roles(roles, location["roles"])
        vms, containers = utils.split_roles(_roles, roles)
        src = Path(location["src"])
        dst = Path(location["dst"])
        try:
            env["experiments"][index]["copy-input"][_index] = "STARTED"
            if not src.exists():
                log.debug("Input file <%s> does not exist, skipping copy", src)
                continue
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
                        task_name=f"Copy input file {_index}",
                    )
            if containers:
                for container in containers:
                    _upload_files(container, src, dst, user=const.KISO_USER)
        except Exception:
            env["experiments"][index]["copy-input"][_index] = "FAILED"
            raise
        else:
            env["experiments"][index]["copy-input"][_index] = "DONE"

    env["experiments"][index]["copy-inputs"] = "DONE"


def _run_setup_scripts(index: int, experiment: dict, env: Environment) -> None:
    """Run setup scripts for an experiment across specified roles.

    Executes setup scripts defined in the experiment configuration on virtual machines
    and containers. Handles script preparation, copying, and execution while tracking
    the status of each script run.

    :param index: The overall experiment index
    :type index: int
    :param experiment: Configuration dictionary containing experiment details
    :type experiment: dict
    :param env: Environment context with roles and execution settings
    :type env: Environment
    """
    name = experiment["name"]
    roles = env["roles"]
    setup_scripts = experiment.get("setup", [])

    log.debug("Starting to run setup scripts for <%s:%d>", name, index)

    env["experiments"][index]["run-setup-scripts"] = "STARTED"
    env["experiments"][index]["run-setup-script"] = {}
    for _index, setup_script in enumerate(setup_scripts):
        _roles = utils.resolve_roles(roles, setup_script["roles"])
        vms, containers = utils.split_roles(_roles, roles)
        executable = setup_script.get("executable", "/bin/bash")
        try:
            env["experiments"][index]["run-setup-script"][_index] = "STARTED"
            with tempfile.NamedTemporaryFile() as script:
                dst = str(Path(const.TMP_DIR) / Path(script.name).name)

                script.write(
                    f"#!{setup_script.get('executable', '/bin/bash')}\n".encode()
                )
                script.write(setup_script["script"].encode())
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
                            task_name=f"Copy script {_index}",
                        )
                        p.shell(f"{executable} {dst}", chdir=env["remote_wd"])
                        p.shell(f"rm -rf {dst}", chdir=env["remote_wd"])
                if containers:
                    for container in containers:
                        _run_script(
                            container,
                            Path(script.name),
                            user=const.KISO_USER,
                            workdir=env["remote_wd"],
                        )
        except Exception:
            env["experiments"][index]["run-setup-script"][_index] = "FAILED"
            raise
        else:
            env["experiments"][index]["run-setup-script"][_index] = "DONE"

    env["experiments"][index]["run-setup-scripts"] = "DONE"


def _run_experiments(index: int, experiment: dict, env: Environment) -> None:
    """Run multiple workflow instances for a specific experiment.

    Generates and executes workflows for each instance of an experiment.

    :param index: The overall experiment index
    :type index: int
    :param experiment: Configuration dictionary for the experiment
    :type experiment: dict
    :param env: Environment context containing workflow and execution details
    :type env: Environment
    """
    count = experiment["count"]

    env["experiments"][index]["submit-dir"] = {}
    for instance in range(count):
        _run_experiment(instance, index, experiment, env)


def _run_experiment(
    instance: int, index: int, experiment: dict, env: Environment
) -> None:
    """Run a complete workflow for a specific experiment instance.

    Executes workflow generation and then waits for workflow completion.

    :param instance: The specific instance number of the experiment
    :type instance: int
    :param index: The overall experiment index
    :type index: int
    :param experiment: Configuration dictionary for the experiment
    :type experiment: dict
    :param env: Environment context containing workflow and execution details
    :type env: Environment
    """
    _generate_workflow(instance, index, experiment, env)
    _wait_for_workflow(instance, index, experiment, env)
    _fetch_submit_dir(instance, index, experiment, env)


def _generate_workflow(
    instance: int, index: int, experiment: dict, env: Environment
) -> None:
    """Generate a Pegasus workflow for a specific experiment instance.

    Generates a workflow by executing the main script on a specified VM or container,
    capturing the submit directory for later tracking and management.

    :param instance: The specific instance number of the experiment
    :type instance: int
    :param index: The overall experiment index
    :type index: int
    :param experiment: Configuration dictionary for the experiment
    :type experiment: dict
    :param env: Environment context containing workflow and execution details
    :type env: Environment
    :raises Exception: If workflow generation fails at any point
    """
    name = experiment["name"]
    main = experiment["main"]
    args = experiment.get("args", [])
    roles = env["roles"]
    _roles = utils.resolve_roles(roles, experiment["submit-node-roles"])
    vms, containers = utils.split_roles(_roles, roles)

    log.debug("Generate workflow for <%s:%d:%d>", name, index, instance)
    try:
        env["experiments"][index]["workflow-generate"] = "STARTED"
        ts = datetime.now(timezone.utc)
        with tempfile.NamedTemporaryFile() as script:
            dst = Path(env["remote_wd"]) / Path(script.name).name
            script.write(main.encode())
            script.seek(0)

            if vms:
                vm = vms[0]
                with utils.actions(
                    roles=vm, run_as=const.KISO_USER, on_error_continue=True
                ) as p:
                    p.copy(
                        src=script.name,
                        dest=str(dst.parent),
                        mode="preserve",
                        task_name="Copy main script",
                    )
                    p.shell(
                        f"/bin/bash {dst} {' '.join([shlex.quote(_) for _ in args])}",
                        chdir=str(dst.parent),
                        task_name="Generate workflow",
                    )
                    p.shell(f"rm -rf {dst}", chdir=str(dst.parent))
                submit_dir = _get_submit_dir(p.results[1], vm, ts)
            elif containers:
                container = containers[0]
                status = _run_script(
                    container,
                    Path(script.name),
                    *args,
                    user=const.KISO_USER,
                    workdir=str(dst.parent),
                )
                submit_dir = _get_submit_dir(status, container, ts)
    except Exception:
        env["experiments"][index]["workflow-generate"] = "FAILED"
        raise
    else:
        env["experiments"][index]["submit-dir"][instance] = submit_dir
        env["experiments"][index]["workflow-generate"] = "DONE"


def _get_submit_dir(
    result: CommandResult | dict, machine: Host | ChameleonDevice, ts: datetime
) -> Path:
    """Get the submit directory for a Pegasus workflow.

    Determines the submit directory for a Pegasus workflow based on command results,
    handling different machine types and extraction methods. Attempts to locate the
    submit directory through log parsing, command output, or database query.

    :param result: Command execution result containing workflow information
    :type result: CommandResult | dict
    :param machine: Machine or device where the workflow was submitted
    :type machine: Host | ChameleonDevice
    :param ts: Timestamp of workflow submission
    :type ts: datetime
    :return: Path to the workflow submit directory
    :rtype: Path
    :raises ValueError: If workflow submit directory cannot be determined or workflow
    fails
    """
    if isinstance(result, dict):
        ec = result["exit_code"]
        output1 = result["output"]
    else:
        ec = result.rc
        output1 = f"""{result.stdout}
{result.stderr}
"""

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
                _exec_pegasus_run(machine, submit_dir)
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
            result = en.run_command(
                cmd, roles=machine, run_as=const.KISO_USER, on_error_continue=True
            )[0]

            ec = -1 if result.status == "FAILED" else 0
            output2 = f"""{result.payload["stdout"]}
{result.payload["stderr"]}
"""
        else:
            result = machine.execute(
                f"sudo -u {const.KISO_USER} sh -c {shlex.quote(cmd)}"
            )
            ec = result["exit_code"]
            output2 = result["output"]

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


def _exec_pegasus_run(machine: Host | ChameleonDevice, submit_dir: str | Path) -> None:
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
        with utils.actions(
            roles=machine, run_as=const.KISO_USER, on_error_continue=True
        ) as p:
            p.shell(f"pegasus-run {submit_dir}", task_name="Run workflow")
        submit_dir = _get_submit_dir(p.results[0], machine, datetime.fromtimestamp(0))
    else:
        status = _wait_for_script(
            machine, "pegasus-run", str(submit_dir), user=const.KISO_USER
        )
        submit_dir = _get_submit_dir(status, machine, datetime.fromtimestamp(0))


def _wait_for_workflow(
    instance: int, index: int, experiment: dict, env: Environment
) -> None:
    """Wait for a Pegasus workflow to complete for a specific experiment instance.

    Monitors the workflow status for a given experiment, tracking its progress and
    handling potential failures. Updates the experiment environment with the workflow's
    current state.

    :param instance: The specific instance number of the experiment
    :type instance: int
    :param index: The index of the experiment in the environment
    :type index: int
    :param experiment: Configuration dictionary for the experiment
    :type experiment: dict
    :param env: The environment context containing experiment details
    :type env: Environment
    :raises: Propagates any exceptions encountered during workflow monitoring
    """
    name = experiment["name"]
    roles = env["roles"]
    poll_interval = experiment.get("poll-interval", const.POLL_INTERVAL)
    timeout = experiment.get("timeout", const.WORKFLOW_TIMEOUT)

    _roles = utils.resolve_roles(roles, experiment["submit-node-roles"])
    vms, containers = utils.split_roles(_roles, roles)

    log.debug("Wait for workflow to finish for <%s:%d:%d>", name, index, instance)
    try:
        env["experiments"][index]["wait-workflow"] = "STARTED"
        submit_dir = env["experiments"][index]["submit-dir"][instance]
        _wait_for_workflow_2(
            vms[0] if vms else containers[0],
            submit_dir,
            poll_interval=poll_interval,
            timeout=timeout,
        )
        _exec_pegasus_statistics(vms[0] if vms else containers[0], submit_dir)
    except Exception:
        env["experiments"][index]["wait-workflow"] = "FAILED"
        raise
    else:
        env["experiments"][index]["wait-workflow"] = "DONE"


def _wait_for_workflow_2(
    machine: Host | ChameleonDevice,
    submit_dir: str | Path,
    poll_interval: int = const.POLL_INTERVAL,
    timeout: int = const.WORKFLOW_TIMEOUT,
) -> None:
    """Wait for a Pegasus workflow to complete on a given machine.

    Polls the workflow status periodically and checks for completion. Supports both Host
    and ChameleonDevice machine types. Handles workflow timeout by stopping the workflow
    if it exceeds the specified time limit.

    :param machine: The machine running the Pegasus workflow
    :type machine: Host | ChameleonDevice
    :param submit_dir: Directory containing the Pegasus workflow submit information
    :type submit_dir: str | Path
    :param poll_interval: Time between status checks, defaults to const.POLL_INTERVAL
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
        task = progress.add_task("Task", total=100)
        if isinstance(machine, Host):
            task = progress.add_task("Task", total=100)
            while True:
                logging.getLogger("enoslib.api").disabled = True
                with utils.actions(
                    roles=machine, run_as=const.KISO_USER, on_error_continue=True
                ) as p:
                    p.shell(status_cmd, task_name="Wait for workflow")
                    p.shell(f"cat {done_file}")

                logging.getLogger("enoslib.api").disabled = False
                pegasus_status = p.results[0]
                monitord_status = p.results[1]

                _render_status(task, progress, pegasus_status)

                if monitord_status.status == "OK":
                    break

                time.sleep(poll_interval)
                end_time = time.time()
                if timeout != -1 and end_time - start_time > timeout:
                    # Workflow ran for too long
                    log.debug("Workflow did not finish within the timeout")

                    # Stop the workflow
                    _exec_pegasus_remove(machine, submit_dir)

                    break
        else:
            while True:
                pegasus_status = _wait_for_script(
                    machine,
                    "pegasus-status",
                    "--jsonrv",
                    str(submit_dir),
                    user=const.KISO_USER,
                )

                _render_status(task, progress, pegasus_status)

                monitord_status = _wait_for_script(
                    machine, f"cat {done_file}", user=const.KISO_USER
                )
                if monitord_status["exit_code"] == 0:
                    break

                time.sleep(poll_interval)
                end_time = time.time()
                if timeout != -1 and end_time - start_time > timeout:
                    # Workflow ran for too long
                    log.debug("Workflow did not finish within the timeout")

                    # Stop the workflow
                    _exec_pegasus_remove(machine, submit_dir)

                    break


def _render_status(
    task: int, progress: PegasusWorkflowProgress, status: CommandResult | dict
) -> None:
    """Render the status of a Pegasus workflow command execution.

    Parses and prints the output of a Pegasus workflow command result,
    handling both CommandResult and dictionary input types.

    :param task: _description_
    :type task: int
    :param progress: _description_
    :type progress: PegasusWorkflowProgress
    :param status: The command execution result to render
    :type status: CommandResult or dict
    """
    if isinstance(status, dict):
        if status["exit_code"] == 0:
            output = json.loads(status["output"])
    else:
        if status.status == "OK":
            output = json.loads(status.payload["stdout"])

    progress.update(task, advance=1)
    progress.update_table(output)


def _exec_pegasus_remove(
    machine: Host | ChameleonDevice, submit_dir: str | Path
) -> None:
    """Remove a Pegasus workflow from the specified submit directory.

    Stops and removes a running Pegasus workflow on either a Host or ChameleonDevice
    machine.
    Supports execution through different mechanisms based on the machine type.

    :param machine: The machine hosting the Pegasus workflow to be removed
    :type machine: Host | ChameleonDevice
    :param submit_dir: Directory containing the Pegasus workflow submit information
    :type submit_dir: str | Path
    """
    if isinstance(machine, Host):
        with utils.actions(
            roles=machine, run_as=const.KISO_USER, on_error_continue=True
        ) as p:
            p.shell(f"pegasus-remove {submit_dir}", task_name="Remove workflow")
        # p.results[0]
    else:
        _wait_for_script(
            machine, "pegasus-remove", str(submit_dir), user=const.KISO_USER
        )


def _exec_pegasus_statistics(
    machine: Host | ChameleonDevice, submit_dir: str | Path
) -> None:
    """Execute Pegasus workflow statistics computation.

    Computes workflow statistics for a given submit directory using pegasus-statistics.
    Supports execution on both Host and ChameleonDevice machine types.

    :param machine: The machine on which to run pegasus-statistics
    :type machine: Host | ChameleonDevice
    :param submit_dir: Directory containing the Pegasus workflow submit information
    :type submit_dir: str | Path
    """
    if isinstance(machine, Host):
        with utils.actions(
            roles=machine, run_as=const.KISO_USER, on_error_continue=True
        ) as p:
            p.shell(
                f"pegasus-statistics -s all {submit_dir}",
                task_name="Compute workflow statistics",
            )
    else:
        _wait_for_script(
            machine,
            "pegasus-statistics",
            "-s",
            "all",
            str(submit_dir),
            user=const.KISO_USER,
        )


def _fetch_submit_dir(
    instance: int, index: int, experiment: dict, env: Environment
) -> None:
    """Copy output files from remote machines and containers to a local destination.

    Iterates through specified result locations, resolves target roles, and fetches
    output files from VMs and containers to a local destination directory.

    :param instance: Experiment index in the environment configuration
    :type instance: int
    :param index: Experiment index in the environment configuration
    :type index: int
    :param experiment: Experiment configuration dictionary
    :type experiment: dict
    :param env: Global environment configuration
    :type env: Environment
    """
    name = experiment["name"]
    roles = env["roles"]

    log.debug("Starting to copy submit dir to the destination for <%s:%d>", name, index)

    _roles = utils.resolve_roles(roles, experiment["submit-node-roles"])
    vms, containers = utils.split_roles(_roles, roles)

    src = Path(env["experiments"][index]["submit-dir"][instance])
    dst = Path(env["resultdir"]) / experiment["name"] / f"instance-{instance}"
    dst.mkdir(parents=True, exist_ok=True)
    if vms:
        with utils.actions(
            roles=vms[0], run_as=const.KISO_USER, on_error_continue=True
        ) as p:
            p.synchronize(
                mode="pull",
                src=str(src),
                dest=str(dst),
                use_ssh_args=True,
                task_name=f"Fetch submit dir {instance}",
            )
    if containers:
        _download_files(containers[0], src, dst)


def _run_post_scripts(index: int, experiment: dict, env: Environment) -> None:
    """Run post-execution scripts for an experiment.

    Executes post-scripts defined in the experiment configuration across specified
    roles, supporting both virtual machines and containers. Handles script
    copying, execution, and tracking of script run status.

    :param index: Index of the experiment in the environment configuration
    :type index: int
    :param experiment: Experiment configuration dictionary containing post-script
    details
    :type experiment: dict
    :param env: Global environment configuration
    :type env: Environment
    :raises: Exception if any post-script fails during execution
    """
    name = experiment["name"]
    roles = env["roles"]
    post_scripts = experiment.get("post-scripts", [])

    log.debug("Starting to run post scripts for <%s:%d>", name, index)

    env["experiments"][index]["run-post-scripts"] = "STARTED"
    env["experiments"][index]["run-post-script"] = {}
    for _index, post_script in enumerate(post_scripts):
        _roles = utils.resolve_roles(roles, post_script["roles"])
        vms, containers = utils.split_roles(_roles, roles)
        executable = post_script.get("executable", "/bin/bash")
        try:
            env["experiments"][index]["run-post-script"][_index] = "STARTED"
            with tempfile.NamedTemporaryFile() as script:
                dst = str(Path(const.TMP_DIR) / Path(script.name).name)

                script.write(
                    f"#!{post_script.get('executable', '/bin/bash')}\n".encode()
                )
                script.write(post_script["script"].encode())
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
                            task_name=f"Copy script {_index}",
                        )
                        p.shell(f"{executable} {dst}", chdir=env["remote_wd"])
                        p.shell(f"rm -rf {dst}", chdir=env["remote_wd"])
                if containers:
                    for container in containers:
                        _run_script(
                            container,
                            Path(script.name),
                            user=const.KISO_USER,
                            workdir=env["remote_wd"],
                        )
        except Exception:
            env["experiments"][index]["run-post-script"][_index] = "FAILED"
            raise
        else:
            env["experiments"][index]["run-post-script"][_index] = "DONE"

    env["experiments"][index]["run-post-scripts"] = "DONE"


def _download_files(
    container: ChameleonDevice,
    src: Path,
    dst: Path,
) -> None:
    """Upload files or directories to a Chameleon container with robust handling of file and directory uploads.

    Handles file and directory uploads to a Chameleon container, with support for:
    - Checking source file/directory existence
    - Resolving destination paths
    - Uploading individual files or entire directory structures
    - Setting ownership of uploaded files/directories
    - Handling potential upload timeouts for large files/directories

    :param container: The Chameleon container device to upload files to
    :type container: ChameleonDevice
    :param src: Source path of file or directory to upload
    :type src: Path
    :param dst: Destination path on the container
    :type dst: Path
    :raises ValueError: If source does not exist or destination is invalid
    """  # noqa: E501
    # The upload method of the Chameleon Edge API requires the source to be a
    # directory. Also, it does not resolve destinations with a ~, i.e., ~kiso is not
    # resolved to /home/kiso, so we need to check directory exists and resolve it
    log.debug("Check source <%s> exists", src)
    src = Path(utils.expanduser(container, src))
    cmd = f"[ -d {shlex.quote(str(src))} ]"
    status = container.execute(f"sh -c {shlex.quote(cmd)}")
    if status["exit_code"] != 0:
        raise ValueError(
            f"Source {src} either doesn't exist or isn't a directory on the edge", src
        )

    # Check the destination exists locally
    log.debug("Check destination <%s> exists and is a directory", dst)
    if dst.exists() and not dst.is_dir():
        raise ValueError(f"Destination {dst} must be a directory", dst)
    dst.mkdir(parents=True, exist_ok=True)

    try:
        container.download(str(src), str(dst))
    except GatewayTimeout:
        # TODO(mayani): Handle timeout
        log.error("Download of <%s> timed out", src)
        ...


def _fetch_outputs(index: int, experiment: dict, env: Environment) -> None:
    """Copy output files from remote machines and containers to a local destination.

    Iterates through specified result locations, resolves target roles, and fetches
    output files from VMs and containers to a local destination directory.

    :param index: Experiment index in the environment configuration
    :type index: int
    :param experiment: Experiment configuration dictionary
    :type experiment: dict
    :param env: Global environment configuration
    :type env: Environment
    """
    name = experiment["name"]
    roles = env["roles"]
    outputs = experiment.get("outputs", [])

    log.debug("Starting to copy outputs to the destination for <%s:%d>", name, index)

    env["experiments"][index]["fetch-output-locations"] = "STARTED"
    env["experiments"][index]["fetch-output"] = {}
    for _index, location in enumerate(outputs):
        _roles = utils.resolve_roles(roles, location["roles"])
        vms, containers = utils.split_roles(_roles, roles)
        dst = Path(location["dst"])
        if not dst.exists():
            log.debug("Destination directory <%s> does not exist, creating it", dst)
            dst.mkdir(parents=True)
        src = Path(location["src"])
        if not src.is_absolute() and location["src"][0] != "~":
            src = Path(env["remote_wd"]) / src

        try:
            env["experiments"][index]["fetch-output"][_index] = "STARTED"
            if vms:
                with utils.actions(
                    roles=vms, run_as=const.KISO_USER, on_error_continue=True
                ) as p:
                    p.synchronize(
                        mode="pull",
                        src=str(src),
                        dest=f"{dst}/",
                        use_ssh_args=True,
                        task_name=f"Fetch output file {_index}",
                    )
            if containers:
                for container in containers:
                    _download_files(container, src, dst)
        except Exception:
            env["experiments"][index]["fetch-output"][_index] = "FAILED"
            raise
        else:
            env["experiments"][index]["fetch-output"][_index] = "DONE"

    env["experiments"][index]["fetch-output-locations"] = "DONE"


@validate_config
@enostask()
def down(
    experiment_config: dict,
    env: Environment = None,
    **kwargs: dict,
) -> None:
    """Destroy the resources provisioned for the experiments.

    This function is responsible for tearing down and cleaning up resources
    associated with an experiment configuration using the specified providers.

    :param experiment_config: Configuration dictionary for the experiment
    :type experiment_config: dict
    :param env: Environment object containing provider information
    :type env: Environment, optional
    :param kwargs: Additional keyword arguments
    :type kwargs: dict
    """
    """Destroy the resources provisioned for the experiments."""
    log.debug("Loading Kiso experiment configuration")
    providers = env["providers"]
    providers.destroy()
