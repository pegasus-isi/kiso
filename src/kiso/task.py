"""Main Kiso task implementations."""

# ruff: noqa: ARG001
from __future__ import annotations

import copy
import io
import logging
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from dataclasses import fields
from functools import wraps
from ipaddress import IPv4Address, IPv4Interface, IPv6Address, IPv6Interface, ip_address
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

import enoslib as en
import yaml
from dacite import from_dict
from enoslib.objects import DefaultNetwork, Host, Networks, Roles
from enoslib.task import Environment, enostask
from jsonschema.validators import validator_for
from jsonschema_pyref import RefResolver, ValidationError
from rich.console import Console

import kiso.constants as const
from kiso import display, edge, utils
from kiso.configuration import Deployment, Kiso, Software
from kiso.errors import KisoError
from kiso.ip import associate_floating_ip
from kiso.log import get_process_pool_executor
from kiso.schema import SCHEMA
from kiso.version import __version__

if TYPE_CHECKING:
    from os import PathLike

    from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice
    from enoslib.infra.provider import Provider

    from kiso.configuration import ExperimentTypes


T = TypeVar("T")

PROVIDER_MAP: dict[str, tuple[Callable[[dict], Any], Callable[..., Any]]] = {}

log = logging.getLogger("kiso")

console = Console()

has_fabric = False

if hasattr(en, "Vagrant"):
    log.debug("Vagrant provider is available")
    PROVIDER_MAP["vagrant"] = (en.VagrantConf.from_dictionary, en.Vagrant)
if hasattr(en, "CBM"):
    log.debug("Chameleon Bare Metal provider is available")

    PROVIDER_MAP["chameleon"] = (en.CBMConf.from_dictionary, en.CBM)
if hasattr(en, "ChameleonEdge"):
    log.debug("Chameleon Edge provider is available")

    PROVIDER_MAP["chameleon-edge"] = (
        en.ChameleonEdgeConf.from_dictionary,
        en.ChameleonEdge,
    )
if hasattr(en, "Fabric"):
    log.debug("FABRIC provider is available")
    from enoslib.infra.enos_fabric.configuration import Fabnetv6NetworkConfiguration

    PROVIDER_MAP["fabric"] = (en.FabricConf.from_dictionary, en.Fabric)
    has_fabric = True


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
            validator_cls = validator_for(SCHEMA)
            validator = validator_cls(SCHEMA, resolver=RefResolver.from_schema(SCHEMA))
            errors = []
            for error in validator.iter_errors(
                _replace_labels_key_with_roles_key(config)
            ):
                log.error(error)
                errors.append(error)
            if errors:
                raise ValidationError("JSON Schema Validation Error", errors)

            # Convert the JSON configuration to a :py:class:`dataclasses.dataclass`
            kiso_config = from_dict(Kiso, config)

            console.rule("[bold green]Check experiment configuration[/bold green]")
            log.debug("Check only one vagrant site is present in the experiment")
            label_to_machines: Roles = _get_defined_machines(kiso_config)

            _check_software(kiso_config.software, label_to_machines)
            _check_deployed_software(kiso_config.deployment, label_to_machines)
            _check_experiments(kiso_config, label_to_machines)
        except ValidationError:
            log.exception("Invalid Kiso experiment config <%s>", experiment_config)
            raise

        log.debug("Kiso experiment configuration is valid")
        return func(kiso_config, *args, wd=wd, **kwargs)

    return wrapper


def check_provisioned(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to check that the resources were provisioned.

    :param func: The function to be decorated, which will receive the experiment
    configuration
    :type func: Callable[..., T]
    :return: A wrapped function that validates the configuration before executing the
    original function
    :rtype: Callable[..., T]
    """

    @wraps(func)
    def wrapper(experiment_config: Kiso, *args: Any, **kwargs: Any) -> T:  # noqa: ANN401
        is_provisioned = False
        env = kwargs.get("env")
        if env and env.get("providers"):
            is_provisioned = True

        if is_provisioned is False:
            raise KisoError(
                "No providers found, resources were not provisioned. "
                "Suggestion: Run `kiso up` first."
            )

        return func(experiment_config, *args, **kwargs)

    return wrapper


def _replace_labels_key_with_roles_key(experiment_config: Kiso | dict) -> dict:
    """Replace labels with roles in the experiment configuration."""
    experiment_config = copy.deepcopy(experiment_config)
    sites = (
        experiment_config["sites"]
        if isinstance(experiment_config, dict)
        else experiment_config.sites
    )
    for site in sites:
        for machine in site["resources"]["machines"]:
            machine["roles"] = machine["labels"]
            del machine["labels"]

        for network in site["resources"].get("networks", []):
            if isinstance(network, str):
                continue

            network["roles"] = network["labels"]
            del network["labels"]

    return experiment_config


@validate_config
def check(experiment_config: Kiso, **kwargs: dict) -> None:
    """Check the experiment configuration for various validation criteria.

    This function performs multiple validation checks on the experiment configuration,
    including:
    - Verifying vagrant site constraints
    - Validating label definitions
    - Checking docker and HTCondor configurations
    - Ensuring proper node configurations
    - Validating input file locations
    - Performing EnOSlib platform checks

    :param experiment_config: The experiment configuration dictionary
    :type experiment_config: Kiso
    :param kwargs: Additional keyword arguments
    :type kwargs: dict
    """
    log.debug("Check EnOSlib")
    en.MOTD = en.INFO = ""
    en.check(platform_filter=["Vagrant", "Fabric", "Chameleon", "ChameleonEdge"])


def _get_defined_machines(experiment_config: Kiso) -> Roles:
    """Get the defined machines from the experiment configuration.

    Extracts and counts labels defined in the sites section of the experiment
    configuration. Validates that only one Vagrant site is present and generates
    additional label variants.

    :param experiment_config: Configuration dictionary containing site and resource
    definitions
    :type experiment_config: Kiso
    :raises ValueError: If multiple Vagrant sites are detected
    :return: A counter of defined labels with their counts
    :rtype: Roles
    """
    vagrant_sites = 0
    def_labels: Counter = Counter()
    label_to_machines: Roles = defaultdict(set)

    for site_index, site in enumerate(experiment_config.sites):
        if site["kind"] == "vagrant":
            vagrant_sites += 1

        for machine_index, machine in enumerate(site["resources"]["machines"]):
            def_labels.update({site["kind"]: machine.get("number", 1)})

            for label in machine["labels"]:
                def_labels.update({label: machine.get("number", 1)})

            for index in range(machine.get("number", 1)):
                machine_key = Host(
                    f"site-{site_index}-machine-{machine_index}-index-{index}"
                )
                label_to_machines[site["kind"]].add(machine_key)

                for label in machine["labels"]:
                    label_to_machines[label].add(machine_key)

    else:
        if vagrant_sites > 1:
            raise ValueError("Multiple vagrant sites are not supported")

        extra_labels = {}
        for label, count in def_labels.items():
            machines = list(label_to_machines[label])
            for index in range(1, count + 1):
                extra_labels[f"kiso.{label}.{index}"] = 1
                label_to_machines[f"kiso.{label}.{index}"].add(machines[index - 1])

    return label_to_machines


def _check_software(softwares: Software, label_to_machines: dict[str, set]) -> None:
    """Check software configuration."""
    if softwares is None:
        return

    for software in fields(Software):
        config = getattr(softwares, software.name, None)
        if config is None:
            continue

        # Get the `name` of the software
        name = software.name

        # Locate the EntryPoint for the software `name` and load it
        cls = utils.get_software(name)

        # Instantiate the installer class.
        obj = cls(
            config  # Software configuration
        )
        obj.check(label_to_machines)


def _check_deployed_software(
    deployments: Deployment, label_to_machines: dict[str, set]
) -> None:
    """Check software deployment configuration."""
    if deployments is None:
        return

    for deployment in fields(Deployment):
        config = getattr(deployments, deployment.name, None)
        if config is None:
            continue

        # Get the `name` of the software
        name = deployment.name

        # Locate the EntryPoint for the software `name` and load it
        cls = utils.get_deployment(name)

        # Instantiate the installer class.
        obj = cls(
            config  # Deployment configuration
        )
        obj.check(label_to_machines)


def _check_experiments(
    experiment_config: Kiso, label_to_machines: dict[str, set]
) -> None:
    """Check software deployment configuration."""
    experiments = experiment_config.experiments
    if experiments is None:
        return

    variables = copy.deepcopy(experiment_config.variables, {})
    for index, experiment in enumerate(experiments):
        # Get the `kind` of experiment
        kind = experiment.kind

        # Locate the EntryPoint for the runner `kind` of experiment and load it
        cls = utils.get_runner(kind)

        # Instantiate the runner class.
        runner = cls(
            experiment,
            index,
            variables=variables,  # Variables defined globally for the experiment
        )

        runner.check(experiment_config, label_to_machines)


@validate_config
@enostask(new=True, symlink=False)
def up(
    experiment_config: Kiso,
    force: bool = False,
    env: Environment = None,
    **kwargs: Any,  # noqa: ANN401
) -> None:
    """Create and set up resources for running an experiment.

    Initializes the experiment environment, sets up working directories, and prepares
    infrastructure by initializing sites, installing Docker, Apptainer, and HTCondor
    across specified labels.

    :param experiment_config: Configuration dictionary defining experiment parameters
    :type experiment_config: Kiso
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

    experiment_config = _replace_labels_key_with_roles_key(experiment_config)

    _init_sites(experiment_config, env, force)
    _install_commons(env)
    _install_software(experiment_config, env)
    _install_deployed_software(experiment_config, env)


def _init_sites(
    experiment_config: Kiso, env: Environment, force: bool = False
) -> tuple[list[Provider], Roles, Networks]:
    """Initialize sites for an experiment.

    Initializes and configures sites from the experiment configuration using parallel
    processing.
    Performs the following key tasks:
    - Initializes providers for each site concurrently
    - Aggregates labels and networks from initialized sites
    - Extends labels with daemon-to-site mappings
    - Determines public IP requirements
    - Associates floating IPs and selects preferred IPs for nodes

    :param experiment_config: Configuration dictionary containing site definitions
    :type experiment_config: Kiso
    :param env: Environment context for the experiment
    :type env: Environment
    :param force: Force recreation of resources, defaults to False
    :type force: bool, optional
    :return: A tuple of providers, labels, and networks for the experiment
    :rtype: tuple[list[Provider], Roles, Networks]
    """
    log.debug("Initializing sites")

    providers = []
    labels = Roles()
    networks = Networks()

    with get_process_pool_executor() as executor:
        futures = [
            executor.submit(_init_site, site_index, site, force)
            for site_index, site in enumerate(experiment_config.sites)
        ]

        for future in futures:
            provider, _labels, _networks = future.result()

            providers.append(provider)
            labels.extend(_labels)
            networks.extend(_networks)

    providers = en.Providers(providers)
    env["providers"] = providers
    env["labels"] = labels
    env["networks"] = networks

    daemon_to_site = _extend_labels(experiment_config, labels)

    # TODO(mayani): Kiso should not have to detect and associate public IPs with nodes
    # Kiso should not be aware if a software or deployment requires public IPs, it
    # should be handled by the installer of the software or deployment or throw an
    # error requiring the user to provision IPs during provisioning
    if experiment_config.deployment and experiment_config.deployment.htcondor:
        is_public_ip_required = _is_public_ip_required(daemon_to_site)
        env["is_public_ip_required"] = is_public_ip_required

        for node in labels.all():
            preferred_ip, priority = None, 1000
            addresses = _get_ips(node)
            if addresses:
                # Priority is,
                # 0 for a public IPv4 address
                # 1 for a public IPv6 address
                # 2 for a private IPv4 address
                # 3 for a private IPv6 address
                preferred_ip, priority = addresses[0]
                log.debug(
                    "Preferred IP <%s> with priority <%d>", preferred_ip, priority
                )

            if (
                is_public_ip_required
                and priority > 1
                and (node.extra["is_central_manager"] or node.extra["is_submit"])
            ):
                preferred_ip = associate_floating_ip(node)

            node.extra["kiso_preferred_ip"] = str(preferred_ip)

    return providers, labels, networks


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
    :return: A tuple containing the provider, labels, and networks for the site
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

    _labels, _networks = provider.init(force_deploy=force)
    _deduplicate_hosts(_labels)
    _labels[kind] = _labels.all()
    _networks[kind] = _networks.all()

    # For Chameleon site, the region name is important as each region will act like
    # a different site
    region_name = kind
    if kind.startswith("chameleon"):
        region_name = _get_region_name(site["rc_file"])
        _labels[region_name] = _labels.all()
        _networks[region_name] = _networks.all()

    # To each node we add a tag to identify what site/region it was provisioned on
    for node in _labels.all():
        # ChameleonDevice object does not have an attribute named extra
        if kind == "chameleon-edge":
            attr = "extra"
            setattr(node, attr, {})
        elif kind == "chameleon" or kind == "fabric":
            # Used to copy this file to Chameleon VMs, so we cna use the Openstack
            # client to get a floating IP
            node.extra["rc_file"] = str(Path(conf.rc_file).resolve())

        node.extra["kind"] = kind
        node.extra.setdefault("site", region_name)
        if kind == "fabric":
            _labels[f"fabric.{node.extra['site']}"] += [node]

    if kind != "chameleon-edge":
        _labels = en.sync_info(_labels, _networks)
    else:
        # Because zunclient.v1.containers.Container is not pickleable
        provider.client.concrete_resources = []

    return provider, _labels, _networks


def _deduplicate_hosts(labels: Roles) -> None:
    """Deduplicate_hosts _summary_.

    _extended_summary_

    :param labels: _description_
    :type labels: Roles
    """
    dedup = {}
    for _, nodes in labels.items():
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


def _extend_labels(experiment_config: Kiso, labels: Roles) -> dict[str, set]:
    """Extend labels for an experiment configuration by adding unique labels and flags to nodes.

    Processes the given labels and experiment configuration to:
    - Create unique labels for each node based on their original label
    - Add flags to nodes indicating their HTCondor daemon types (central manager,
    submit, execute, personal)
    - Add flags for container technologies (Docker, Apptainer)
    - Track the sites where different HTCondor daemon types are located

    :param experiment_config: Configuration dictionary for the experiment
    :type experiment_config: Kiso
    :param labels: Dictionary of labels and their associated nodes
    :type labels: Roles
    :return: A mapping of HTCondor daemon types to their sites
    :rtype: dict[str, set]
    """  # noqa: E501
    extra: dict[str, set] = defaultdict(set)
    daemon_to_site = defaultdict(set)
    central_manager_labels, submit_labels, execute_labels, personal_labels = (
        _get_condor_daemon_labels(experiment_config)
    )

    for label, nodes in labels.items():
        is_central_manager = label in central_manager_labels
        is_submit = label in submit_labels
        is_execute = label in execute_labels
        is_personal = label in personal_labels
        for index, node in enumerate(nodes, 1):
            # EnOSlib resources.machines.number can be greater than 1, so we add the
            # host with a new unique label of the form kiso.<label>.<index>
            _label = f"kiso.{label}.{index}"
            extra[_label].add(node)

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

            site = [node.extra["site"]]
            if is_execute:
                daemon_to_site["execute"].update(site)
            if is_submit:
                daemon_to_site["submit"].update(site)
            if is_central_manager:
                daemon_to_site["central-manager"].update(site)

    labels.update(extra)

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


def _get_ips(
    machine: Host | ChameleonDevice, is_public_ip_required: bool = False
) -> list[tuple[IPv4Address | IPv6Address, int]]:
    """Get the IP addresses for a given machine.

    Selects an IP address based on priority, filtering out multicast, reserved,
    loopback, and link-local addresses. Supports both Host and ChameleonDevice
    types. Optionally enforces returning a public IP address.

    :param machine: The machine to get an IP address for
    :type machine: Host | ChameleonDevice
    :param is_public_ip_required: Whether a public IP is required, defaults to False
    :type is_public_ip_required: bool, optional
    :return: List of tuples of an IP address and it's priority.
        Priority is 0 for a public IPv4 address, 1 for a public IPv6 address,
        2 for a private IPv4 address, and 3 for a private IPv6 address.
    :rtype: list[tuple[IPv4Address | IPv6Address, int]]
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
    #     name='lo',
    #     addresses={
    #         IPAddress(network=None, ip=IPv4Interface('127.0.0.1/8')),
    #         IPAddress(network=None, ip=IPv6Interface('::1/128'))}),
    #   NetDevice(
    #     name='eno8303',
    #     addresses=set()
    #   )
    # )
    # Chameleon Edge Host
    # Fabric Host
    # 1 for Management, 1 for add_fabnet, and 1 for loopback
    # net_devices={
    #   NetDevice(
    #     name="lo",
    #     addresses={
    #         IPAddress(network=None, ip=IPv4Interface("127.0.0.1/8")),
    #         IPAddress(network=None, ip=IPv6Interface("::1/128")),
    #     },
    #   ),
    #   NetDevice(
    #     name="eth0",
    #     addresses={
    #         IPAddress(network=None, ip=IPv4Interface("10.20.4.136/23")),
    #         IPAddress(network=None, ip=IPv6Interface("fe80::f816:3eff:fecd:a657/64")),
    #     },
    #   ),
    #   NetDevice(
    #     name="eth1",
    #     addresses={
    #         IPAddress(network=None, ip=IPv4Interface("10.134.142.2/24")),
    #         IPAddress(network=None, ip=IPv6Interface("fe80::8117:f69:a883:76c5/64")),
    #     },
    #   ),
    # }
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

                    # FABRIC uses the same IPRange (2602:FCFB::/36) for both IPv6
                    # and IPv6External networks, so we check if the IPv6 address
                    # assigned by FABRIC is public or private.
                    is_private = ip.is_private or (
                        has_fabric
                        and isinstance(
                            address.network.config, Fabnetv6NetworkConfiguration
                        )
                    )
                    # Prioritize public over private IPs and prioritize IPv4 over IPv6
                    priority = (
                        (2 if is_private else 0)
                        if isinstance(address.ip, IPv4Interface)
                        else (3 if is_private else 1)
                    )

                    addresses.append((address.ip.ip, priority))
    else:
        address = ip_address(machine.address)
        priority = 1 if address.is_private else 0
        addresses.append((address, priority))

    for address in machine.extra.get("floating-ips", []):
        ip = ip_address(address)
        if ip.is_multicast or ip.is_reserved or ip.is_loopback or ip.is_link_local:
            continue

        # Prioritize public over private IPs and prioritize IPv4 over IPv6
        priority = (
            (2 if is_private else 0)
            if isinstance(address.ip, IPv4Address)
            else (3 if is_private else 1)
        )
        addresses.append((ip, priority))

    addresses = sorted(addresses, key=lambda v: v[1])
    log.debug("Addresses <%s>", addresses)

    return addresses
    preferred_ip, priority = addresses[0]
    log.debug("Preferred IP <%s> with priority <%d>", preferred_ip, priority)

    if is_public_ip_required is True and priority > 1:
        # TODO(mayani): We should not use gateway IP as it could be the same for
        # multiple VMs. Here we should just raise an error
        preferred_ip = machine.extra.get("gateway")
        if preferred_ip is None:
            raise ValueError(
                f"Machine <{machine.name}> does not have a public IP address"
            )

        preferred_ip = ip_address(preferred_ip)

    return str(preferred_ip)


def _get_condor_daemon_labels(
    experiment_config: Kiso,
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Get labels for different HTCondor daemon types from an experiment configuration.

    Parses the HTCondor configuration to extract labels for central manager, submit,
    execute, and personal daemon types. Validates daemon types and raises an error for
    invalid types.

    :param experiment_config: Dictionary containing HTCondor cluster configuration
    :type experiment_config: Kiso
    :raises ValueError: If an invalid HTCondor daemon type is encountered
    :return: Tuple of label sets for central manager, submit, execute, and personal
    daemons
    :rtype: tuple[set[str], set[str], set[str], set[str]]
    """
    condor_cluster = (
        experiment_config.deployment and experiment_config.deployment.htcondor
    )
    central_manager_labels = set()
    submit_labels = set()
    execute_labels = set()
    personal_labels = set()

    if condor_cluster:
        for config in condor_cluster:
            if config.kind[0] == "c":  # central-manager
                central_manager_labels.update(config.labels)
            elif config.kind[0] == "s":  # submit
                submit_labels.update(config.labels)
            elif config.kind[0] == "e":  # execute
                execute_labels.update(config.labels)
            elif config.kind[0] == "p":  # personal
                personal_labels.update(config.labels)
            else:
                raise ValueError(
                    f"Invalid HTCondor daemon <{config.kind}> in configuration"
                )

    return central_manager_labels, submit_labels, execute_labels, personal_labels


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

    labels = env["labels"]
    # Special case here. Do not pass (labels, labels) to split_labels. Since the Roles
    # object is like a dictionary, so labels - labels["<key>"] and
    # labels & labels["<key>"] doesn't work.
    vms, containers = utils.split_labels(labels.all(), labels)
    results = []
    etc_hosts_content = _generate_etc_hosts(env)
    log.debug("/etc/hosts content <%s>", etc_hosts_content)

    if vms:
        results.extend(
            utils.run_ansible(
                [Path(__file__).parent / "commons/main.yml"],
                roles=vms,
                extra_vars={"etc_hosts_content": etc_hosts_content},
            )
        )

    if containers:
        for container in containers:
            results.append(
                utils.run_script(
                    container,
                    Path(__file__).parent / "commons/init.sh",
                    "--hosts",
                    etc_hosts_content,
                    "--no-dry-run",
                )
            )

    display.commons(console, results)


def _generate_etc_hosts(env: Environment) -> str:
    """Generate /etc/hosts file for the experiment."""
    labels = env["labels"]
    content = io.StringIO()

    host_to_labels: dict[str, set[str]] = defaultdict(set)
    for label, machines in labels.items():
        if len(machines) == 1:
            host_to_labels[
                machines[0].extra.get("kiso_preferred_ip", machines[0].address)
            ].add(label)

    content.write("# Kiso: Start\n")
    for address, labels in host_to_labels.items():
        content.write(f"{address} {' '.join(labels)}\n")
    content.write("# Kiso: End\n")

    return content.getvalue()


def _install_software(experiment_config: Kiso, env: Environment) -> None:
    """Install software on specified labels in an experiment configuration."""
    softwares = experiment_config.software
    if softwares is None:
        return

    for software in fields(Software):
        config = getattr(softwares, software.name, None)
        if config is None:
            continue

        # Get the `name` of the software
        name = software.name

        # Locate the EntryPoint for the software `name` and load it
        cls = utils.get_software(name)

        # Instantiate the installer class.
        obj = cls(
            config  # Software configuration
        )
        obj(env)


def _install_deployed_software(experiment_config: Kiso, env: Environment) -> None:
    """Install software for deployments on specified labels in an experiment configuration."""  # noqa: E501
    deployments = experiment_config.deployment
    if deployments is None:
        return

    for deployment in fields(Deployment):
        config = getattr(deployments, deployment.name, None)
        if config is None:
            continue

        # Get the `name` of the deployment
        name = deployment.name

        # Locate the EntryPoint for the software `name` and load it
        cls = utils.get_deployment(name)

        # Instantiate the installer class.
        obj = cls(
            config  # Deployment configuration
        )
        obj(env)


@validate_config
@enostask()
@check_provisioned
def run(
    experiment_config: Kiso,
    force: bool = False,
    env: Environment = None,
    **kwargs: Any,  # noqa: ANN401
) -> None:
    """Run the defined experiments.

    Executes a series of experiments by performing the following steps:
    - Copies experiment directory to remote labels
    - Executes experiment

    :param experiment_config: Configuration dictionary containing experiment details
    :type experiment_config: Kiso
    :param force: Force rerunning of experiments, defaults to False
    :type force: bool, optional
    :param env: Environment configuration containing providers, labels, and networks
    :type env: Environment, optional
    :param kwargs: Additional keyword arguments
    :type kwargs: dict
    """
    log.debug("Run Kiso experiments")
    console.rule("[bold green]Run experiments[/bold green]")

    experiments = experiment_config.experiments
    variables = copy.deepcopy(experiment_config.variables, {})
    env.setdefault("experiments", {})
    if force is True:
        env["experiments"] = {}

    _copy_experiment_dir(env)
    for experiment_index, experiment in enumerate(experiments):
        env["experiments"].setdefault(experiment_index, {})
        _run_experiments(experiment_index, experiment, variables, env)


def _copy_experiment_dir(env: Environment) -> None:
    """Copy experiment directory to remote labels.

    Copies the experiment directory from the local working directory to the remote
    working directory for specified submit node labels. Supports copying to both virtual
    machines and containers.

    :param env: Environment configuration containing labels and working directory
    information
    :type env: Environment
    :raises Exception: If directory copy fails for any label
    """
    log.debug("Copy experiment directory to remote nodes")
    console.print("Copying experiment directory to remote nodes")

    labels = env["labels"]
    # Special case here. Do not pass (labels, labels) to split_labels. Since the Roles
    # object is like a dictionary, so labels - labels["<key>"] and
    # labels & labels["<key>"] doesn't work.
    vms, containers = utils.split_labels(labels.all(), labels)

    try:
        kiso_state = env["experiments"]
        if kiso_state.get("copy-experiment-directory") == const.STATUS_OK:
            return
        kiso_state["copy-experiment-directory"] = const.STATUS_STARTED
        src = Path(env["wd"])
        dst = Path(env["remote_wd"]).parent
        if vms:
            with utils.actions(roles=vms, strategy="free") as p:
                # macOS's rsync does not work as expected when the host
                # has an IPv6 address and a gateway host is used in between. So we
                # create a temp SSH config file with the Host and HostName directives
                # and use it to run rsync
                tmpfile = tempfile.NamedTemporaryFile(delete=False)  # noqa: SIM115
                p.copy(
                    dest=f"{tmpfile.name}-{{{{ansible_host}}}}",
                    content="""
Host pegasusvm
    HostName {{ansible_host}}
""",
                    delegate_to="localhost",
                )
                p.shell(
                    f"rsync -auzv -e 'ssh -F {tmpfile.name}-{{{{ansible_host}}}} "
                    "{{ansible_ssh_common_args}} "
                    "{% if ansible_port is defined %}-p {{ansible_port}} "
                    "{% endif %}{% if ansible_ssh_private_key_file is defined %}-i "
                    "{{ansible_ssh_private_key_file}}' {% endif %}"
                    f"{src} kiso@pegasusvm:{dst}",
                    delegate_to="localhost",
                    task_name="Copy experiment dir",
                )
                p.file(
                    path=f"{tmpfile.name}-{{{{ansible_host}}}}",
                    state="absent",
                    delegate_to="localhost",
                )
                tmpfile.close()
        if containers:
            for container in containers:
                edge.upload(container, src, dst, user=const.KISO_USER)
    except Exception:
        kiso_state["copy-experiment-directory"] = const.STATUS_FAILED
        raise
    else:
        kiso_state["copy-experiment-directory"] = const.STATUS_OK


def _run_experiments(
    index: int, experiment: ExperimentTypes, variables: dict, env: Environment
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
    kind = experiment.kind

    # Locate the EntryPoint for the runner `kind` of experiment and load it
    cls = utils.get_runner(kind)

    # Instantiate the runner class. The runner class to use is defined in the
    # runner's `RUNNER` attribute
    runner = cls(
        experiment,
        index,
        variables=variables,  # Variables defined globally for the experiment
    )

    # Run the experiment
    runner(
        env["wd"],  # Local experiment working directory
        env["remote_wd"],  # Remote experiment working directory
        env["resultdir"],  # Local results directory
        env["labels"],  # Provisioned resources
        env["experiments"][index],  # Store to maintain the state of the experiment
    )


@validate_config
@enostask()
@check_provisioned
def down(experiment_config: Kiso, env: Environment = None, **kwargs: dict) -> None:
    """Destroy the resources provisioned for the experiments.

    This function is responsible for tearing down and cleaning up resources
    associated with an experiment configuration using the specified providers.

    :param experiment_config: Configuration dictionary for the experiment
    :type experiment_config: Kiso
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

    vagrant_dir = Path(env["wd"]) / ".vagrant"
    vagrant_file = Path(env["wd"]) / "Vagrantfile"
    providers = env["providers"]
    del env["providers"]

    for provider in providers.providers:
        if isinstance(provider, en.Vagrant) and vagrant_dir.exists():
            ssh_add = shutil.which("ssh-add")
            if ssh_add:
                for key in vagrant_dir.glob("**/private_key"):
                    result = subprocess.run([ssh_add, "-d", str(key)])  # noqa: S603
                    if result.returncode != 0:
                        log.debug("Failed to remove SSH key <%s> from ssh-agent", key)

    providers.destroy()
    if vagrant_dir.exists():
        shutil.rmtree(vagrant_dir)
    if vagrant_file.exists():
        vagrant_file.unlink()
