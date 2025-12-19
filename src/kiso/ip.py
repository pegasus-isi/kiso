"""Assign public IPs to nodes."""

# ruff: noqa: ARG001
from __future__ import annotations

import inspect
import json
import logging
import shutil
import subprocess
from ipaddress import IPv4Address, IPv6Address, ip_address
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import enoslib as en

import kiso.constants as const
from kiso import edge
from kiso.errors import KisoError

if TYPE_CHECKING:
    from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice
    from enoslib.objects import Host

log = logging.getLogger("kiso")

if hasattr(en, "CBM"):
    log.debug("Chameleon Bare Metal provider is available")
    from enoslib.infra.enos_openstack.utils import source_credentials_from_rc_file
if hasattr(en, "Fabric"):
    log.debug("FABRIC provider is available")
    from enoslib.infra.enos_fabric.constants import FABNETV4EXT, NIC_BASIC
    from enoslib.infra.enos_fabric.utils import (
        source_credentials_from_rc_file as source_fabric_credentials_from_rc_file,
    )
    from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager


def associate_floating_ip(node: Host | ChameleonDevice) -> IPv4Address | IPv6Address:
    """Associate a floating IP address to a node based on specific conditions.

    Determines whether to assign a floating IP to a node depending on its label and
    type. Supports different cloud providers and testbed types with specific IP
    assignment strategies.

    :param node: The node to potentially assign a floating IP to
    :type node: Host | ChameleonDevice
    :return: The associated floating IP address
    :rtype: IPv4Address | IPv6Address
    :raises NotImplementedError: If floating IP assignment is not supported for a
    specific testbed
    :raises KisoError: If assigning a public IP is unsupported
    :raises ValueError: If an unsupported site type is encountered
    """
    kind = node.extra["kind"]
    if kind not in IP_PROVIDER_MAP:
        raise ValueError(f"Unknown site type {kind}", kind)

    return IP_PROVIDER_MAP[kind](node)


def _associate_floating_ip_vagrant(node: Host) -> IPv4Address | IPv6Address:
    """Associate a floating IP address with a Vagrant node."""
    raise KisoError("Assigning public IPs to Vagrant VMs is not supported")


def _associate_floating_ip_chameleon(node: Host) -> IPv4Address | IPv6Address:
    """Associate a floating IP address with a Chameleon node.

    Retrieves or creates a floating IP for a Chameleon node using the OpenStack CLI.
    Handles cases where a node may already have a floating IP or requires a new one.
    Logs debug information during the IP association process.

    :param node: The Chameleon node to associate a floating IP with
    :type node: Host
    :return: The associated floating IP address
    :rtype: IPv4Address | IPv6Address
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

        return ip_address(ip)


def _associate_floating_ip_chameleon_edge(
    node: ChameleonDevice,
) -> IPv4Address | IPv6Address:
    """Associate a floating IP address with a Chameleon Edge device.

    Attempts to retrieve an existing floating IP from /etc/floating-ip. If no IP is
    found, a new floating IP is associated with the device and saved to
    /etc/floating-ip.

    :param node: The Chameleon device to associate a floating IP with
    :type node: ChameleonDevice
    :return: The associated floating IP address
    :rtype: IPv4Address | IPv6Address
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

    return ip_address(ip)


def _associate_floating_ip_fabric(node: Host) -> IPv4Address | IPv6Address:
    """Associate a floating IP address with a Chameleon node.

    Retrieves or creates a floating IP for a Chameleon node using the OpenStack CLI.
    Handles cases where a node may already have a floating IP or requires a new one.
    Logs debug information during the IP association process.

    :param node: The Chameleon node to associate a floating IP with
    :type node: Host
    :return: The associated floating IP address
    :rtype: IPv4Address | IPv6Address
    :raises ValueError: If the OpenStack CLI is not found or the server cannot be
    located
    """
    with source_fabric_credentials_from_rc_file(node.extra["rc_file"]):
        try:
            fablib = fablib_manager(log_propagate=True)
            fabric_slice = fablib.get_slice(name=node.extra["slice"])
            fabric_node = fabric_slice.get_node(name=node.extra["name"])
            stdout, _stderr = fabric_node.execute("cat /etc/floating-ip")
            if len(stdout.strip()):
                log.debug("Floating IP already associated with the device")
                ip = stdout.strip()
            else:
                # Create an L3 network for the public IP
                network_name = f"kiso-public-network-{node.extra['site']}"
                network = fabric_slice.get_network(name=network_name)
                if not network:
                    log.debug(
                        "Adding IPv4Ext L3 Network to FABRIC node <%s>",
                        fabric_node.get_management_ip(),
                    )
                    network = fabric_slice.add_l3network(
                        name=network_name, type="IPv4Ext"
                    )

                # Create a NIC for the public IP
                nic_name = "kiso-public-nic"
                try:
                    component = fabric_node.get_component(name=nic_name)
                except Exception:
                    log.debug(
                        "Adding NIC_Basic component to FABRIC node <%s>",
                        node.extra["name"],
                    )
                    component = fabric_node.add_component(
                        model=NIC_BASIC, name=nic_name
                    )
                finally:
                    interface = component.get_interfaces()[0]
                    network.add_interface(interface)

                # Submit needed for the changes to take effect
                fabric_slice.submit()

                # Make an IP publicly routable
                fabric_slice = fablib.get_slice(name=node.extra["slice"])
                network = fabric_slice.get_network(name=network_name)
                ip = network.get_available_ips()
                network.make_ip_publicly_routable(ipv4=[str(ip[0])])

                # Submit needed for the changes to take effect
                fabric_slice.submit()

                fabric_slice = fablib.get_slice(name=node.extra["slice"])
                fabric_node = fabric_slice.get_node(name=node.extra["name"])
                interface = fabric_node.get_interface(network_name=network_name)
                os_ifname = interface.get_physical_os_interface_name()
                network = fabric_slice.get_network(name=network_name)
                gateway = network.get_gateway()
                subnet = network.get_subnet()
                prefix_len = subnet.prefixlen

                ip = network.get_public_ips()[-1]
                interface.ip_addr_add(addr=ip, subnet=subnet)
                scripts_dir = Path(inspect.getfile(en.Fabric)).parent / "scripts"
                fabric_node.upload_directory(str(scripts_dir), const.TMP_DIR)
                cmd = (
                    f"cd /tmp/{scripts_dir.name} ; chmod +x *.sh ; "
                    f"sudo ./main.sh -t {FABNETV4EXT} -I {os_ifname} "
                    f"-A {ip}/{prefix_len} -G {gateway}"
                )
                log.debug(
                    "Executing command <%s> on node <%s>", cmd, node.extra["name"]
                )
                fabric_node.execute(cmd)
                fabric_node.execute(f"echo {ip} | sudo tee /etc/floating-ip")

            log.debug("Floating IP associated with the device %s", ip)
            floating_ips = node.extra.get("floating-ips", [])
            floating_ips.append(ip)
            node.extra["floating-ips"] = floating_ips

        except Exception as e:
            raise ValueError(
                f"Error occurred assigning public IP to FABRIC node <{node.alias}>"
            ) from e

        return ip_address(ip)


IP_PROVIDER_MAP: dict[str, Callable[[Host], IPv4Address | IPv6Address]] = {
    "chameleon": _associate_floating_ip_chameleon,
    "chameleon-edge": _associate_floating_ip_chameleon_edge,
    "fabric": _associate_floating_ip_fabric,
    "vagrant": _associate_floating_ip_vagrant,
}
