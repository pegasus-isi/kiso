"""Kiso utilities."""

from __future__ import annotations

import logging
import secrets
import string
from contextlib import ContextDecorator, suppress
from functools import partial, reduce
from importlib.metadata import EntryPoint, entry_points
from ipaddress import IPv4Address, IPv4Interface, IPv6Address, IPv6Interface, ip_address
from pathlib import Path
from typing import TYPE_CHECKING

import enoslib as en
from enoslib.objects import DefaultNetwork, Host, Roles
from enoslib.task import Environment

from kiso import constants as const

if TYPE_CHECKING:
    from types import TracebackType

    from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice
    from enoslib.objects import Roles
    from enoslib.task import Environment

with suppress(ImportError):
    from importlib.metadata import EntryPoints

has_fabric = False

log = logging.getLogger("kiso")

run_ansible = partial(en.run_ansible, on_error_continue=True)

actions = partial(en.actions, on_error_continue=True)

undefined = type("undefined", (), {})


if hasattr(en, "Fabric"):
    from enoslib.infra.enos_fabric.configuration import Fabnetv6NetworkConfiguration

    has_fabric = True


def resolve_labels(labels: Roles, label_names: list[str]) -> Roles:
    """Resolve and combine labels based on provided label names.

    Filters or combines labels from a given Roles object based on the specified label
    names. If no label names are provided, returns the original labels. If multiple
    label names are given, merges the corresponding labels using a logical OR
    operation.

    :param labels: Collection of labels to resolve from
    :type labels: Roles
    :param label_names: List of label names to filter or combine
    :type label_names: list[str]
    :return: Resolved labels matching the specified label names
    :rtype: Roles
    """
    if not label_names:
        return labels

    return (
        labels[label_names[0]]
        if len(label_names) == 1
        else reduce(
            lambda a, b: (
                labels[a] | labels[b]
                if isinstance(a, str)
                else a | labels[b]
                if isinstance(b, str)
                else b
            ),
            label_names,
        )
    )


def get_pool_passwd_file() -> str:
    """Get the path to a pool password file, creating it if it doesn't exist.

    Creates a secure password file in the user's home directory with restricted
    permissions.
    If the file already exists, it validates the file permissions.

    :return: Absolute path to the pool password file
    :rtype: str
    :raises ValueError: If the existing file does not have the required 0600 permissions
    """
    pool_passwd_file = Path("~/.kiso/pool_passwd").expanduser()

    if not pool_passwd_file.exists():
        pool_passwd_file.parent.mkdir(parents=True, exist_ok=True)
        with pool_passwd_file.open("w") as f:
            f.write(get_random_string())
        pool_passwd_file.chmod(0o600)
    else:
        if pool_passwd_file.stat().st_mode & 0o777 != 0o600:
            raise ValueError(f"File <{pool_passwd_file}> must have permissions 0600")

    return str(pool_passwd_file)


def get_random_string(length: int = 64) -> str:
    """Generate a cryptographically secure random string.

    Generates a random string of specified length using ASCII letters and digits.

    :param length: Length of the random string to generate, defaults to 64
    :type length: int, optional
    :raises ValueError: If length is not a positive integer
    :return: Randomly generated string
    :rtype: str
    """
    if length <= 0:
        raise ValueError("Length must be a positive integer")

    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def split_labels(split: Roles, labels: Roles) -> tuple[Roles, Roles]:
    """Split a set of labels into virtual machines and containers.

    Separates the input labels into two groups: non-edge virtual machines and edge
    containers.

    :param split: The complete set of labels to be split
    :type split: Roles
    :param labels: The reference label set containing the chameleon-edge label
    :type labels: Roles
    :return: A tuple containing (non-edge VMs, edge containers)
    :rtype: tuple[Roles, Roles]
    """
    vms = split - labels["chameleon-edge"]
    containers = split & labels["chameleon-edge"]

    return vms, containers


def get_runner(kind: str) -> EntryPoint:
    """Retrieve and load a workflow runner class by its kind.

    Searches the ``kiso.experiment`` entry-point group for an entry point whose
    name matches ``kind`` and returns the loaded class.

    :param kind: The name of the workflow runner entry point to retrieve
    :type kind: str
    :return: The loaded runner class registered under the given kind
    :rtype: type
    :raises ValueError: If no entry point with the given kind is found or the
        module cannot be imported
    """  # noqa: E501
    runner = _get_single(const.KISO_EXPERIMENT_ENTRY_POINT_GROUP, kind)
    try:
        return runner.load()
    except ModuleNotFoundError as e:
        raise ValueError(f"No runner found for kind {kind}") from e


def get_software(name: str) -> EntryPoint:
    """Retrieve and load a software installer class by its name.

    Searches the ``kiso.software`` entry-point group for an entry point whose
    name matches ``name`` and returns the loaded class.

    :param name: The name of the software installer entry point to retrieve
    :type name: str
    :return: The loaded installer class registered under the given name
    :rtype: type
    :raises ValueError: If no entry point with the given name is found or the
        module cannot be imported
    """  # noqa: E501
    software = _get_single(const.KISO_SOFTWARE_ENTRY_POINT_GROUP, name)
    try:
        return software.load()
    except ModuleNotFoundError as e:
        raise ValueError(f"No software found for kind {name}") from e


def get_deployment(name: str) -> EntryPoint:
    """Retrieve and load a deployment installer class by its name.

    Searches the ``kiso.deployment`` entry-point group for an entry point whose
    name matches ``name`` and returns the loaded class.

    :param name: The name of the deployment installer entry point to retrieve
    :type name: str
    :return: The loaded installer class registered under the given name
    :rtype: type
    :raises ValueError: If no entry point with the given name is found or the
        module cannot be imported
    """  # noqa: E501
    software = _get_single(const.KISO_DEPLOYMENT_ENTRY_POINT_GROUP, name)
    try:
        return software.load()
    except ModuleNotFoundError as e:
        raise ValueError(f"No software found for kind {name}") from e


def _get_single(group: str, name: str) -> EntryPoint:
    """Retrieve a single entry point from a specified group by its name.

    Searches through all registered entry points in a given group and returns
    the entry point that matches the specified name.

    :param group: The entry point group to search within
    :type group: str
    :param name: The name of the specific entry point to retrieve
    :type name: str
    :return: The matching entry point
    :rtype: EntryPoint
    :raises ValueError: If no entry point with the given name is found in the group
    """
    all_eps: dict | EntryPoints = entry_points()
    if isinstance(all_eps, dict):
        all_eps = all_eps.get(group, [])
    else:
        all_eps = all_eps.select(group=group)

    for ep in all_eps:
        if ep.name == name:
            return ep

    raise ValueError(f"No such entrypoint <{group}>:{name}> found")


def get_ips(
    machine: Host | ChameleonDevice,
) -> list[tuple[IPv4Address | IPv6Address, int]]:
    """Get the IP addresses for a given machine.

    Selects an IP address based on priority, filtering out multicast, reserved,
    loopback, and link-local addresses. Supports both Host and ChameleonDevice
    types. Optionally enforces returning a public IP address.

    :param machine: The machine to get an IP address for
    :type machine: Host | ChameleonDevice
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


class experiment_state(ContextDecorator):
    """Context manager and decorator for tracking the state of an experiment step.

    Stores a status value in a nested environment dictionary under the provided
    key path. On entry the key is initialised to ``STATUS_STARTED`` (unless it
    already has a value). On exit the key is updated to ``STATUS_OK`` or
    ``STATUS_FAILED`` depending on whether an exception was raised.

    Can be used either as a ``with`` block or as a function decorator.
    """

    def __init__(
        self, env: Environment, *args: str | int, on_error_continue: bool = True
    ) -> None:
        """Initialise the context manager.

        Traverses ``env`` using all but the last element of ``args`` as nested
        keys, creating intermediate dicts as needed. The last element of
        ``args`` is used as the state key on enter/exit.

        :param env: The EnOSlib task environment used to persist step state
        :type env: Environment
        :param args: Key path into ``env``; intermediate keys are created
            automatically, the final key stores the status value
        :type args: str | int
        :param on_error_continue: When ``True`` exceptions are suppressed on
            exit (default). Set to ``False`` to let exceptions propagate.
        :type on_error_continue: bool, optional
        """
        self.env = env
        self.arg = args[-1]
        self.status = None
        self.on_error_continue = on_error_continue

        for index, arg in enumerate(args):
            if index == len(args) - 1:
                break

            if arg not in self.env:
                self.env[arg] = {}

            self.env = self.env[arg]

    def __enter__(self) -> experiment_state:
        """Enter the context, initialising the state key to ``STATUS_STARTED``.

        If the key already exists in the environment its current value is
        preserved in ``self.status`` so callers can detect a previously
        successful run and skip re-execution.

        :return: This ``experiment_state`` instance
        :rtype: experiment_state
        """
        self.status = self.env.setdefault(self.arg, const.STATUS_STARTED)
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Exit the context, set the final status, and optionally suppress exceptions.

        Sets the state key to ``STATUS_OK`` when no exception occurred, or
        ``STATUS_FAILED`` when an exception was raised. Returns ``True`` to
        suppress the exception when ``on_error_continue`` is ``True``.

        :param exc_type: Exception type, or ``None`` if no exception was raised
        :type exc_type: type | None
        :param exc_val: Exception instance, or ``None`` if no exception was raised
        :type exc_val: BaseException | None
        :param exc_tb: Traceback, or ``None`` if no exception was raised
        :type exc_tb: TracebackType | None
        :return: ``True`` to suppress exceptions when ``on_error_continue`` is
            ``True``, otherwise ``None`` to propagate them
        :rtype: bool | None
        """
        self.status = self.env[self.arg] = (
            const.STATUS_OK if exc_type is None else const.STATUS_FAILED
        )

        if self.on_error_continue is True:
            return True  # Suppress exceptions

        return None  # Do not suppress exceptions
