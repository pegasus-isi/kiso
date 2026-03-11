"""Unit tests for kiso.docker.installer.DockerInstaller."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import pytest

from kiso.docker.configuration import Docker
from kiso.docker.installer import DockerInstaller

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_docker_init_stores_config() -> None:
    docker = Docker(labels=["compute"])
    installer = DockerInstaller(docker)
    assert installer.config is docker


def test_docker_check_none_config_is_noop() -> None:
    DockerInstaller(None).check({})  # must not raise


def test_docker_check_empty_labels_is_noop() -> None:
    installer = DockerInstaller(Docker(labels=[]))
    installer.check(defaultdict(set))  # must not raise (labels set is empty)


def test_docker_check_no_machines_raises() -> None:
    installer = DockerInstaller(Docker(labels=["undefined"]))
    with pytest.raises(ValueError, match="No machines found"):
        installer.check(defaultdict(set))


def test_docker_check_valid_vm_machines_passes() -> None:
    installer = DockerInstaller(Docker(labels=["compute"]))
    label_to_machines = defaultdict(set)
    label_to_machines["compute"].add("vm1")
    label_to_machines["chameleon-edge"] = set()
    installer.check(label_to_machines)  # must not raise


def test_docker_check_edge_machines_raises() -> None:
    installer = DockerInstaller(Docker(labels=["edge"]))
    label_to_machines = defaultdict(set)
    label_to_machines["edge"].add("edge_device")
    label_to_machines["chameleon-edge"].add("edge_device")
    with pytest.raises(ValueError, match="Chameleon Edge"):
        installer.check(label_to_machines)


def test_docker_call_none_config_is_noop() -> None:
    DockerInstaller(None)({"labels": {}})  # must not raise


def test_docker_call_with_vms_runs_ansible(mocker: MockerFixture) -> None:
    """DockerInstaller.__call__ with vms truthy installs via ansible (lines 99-118)."""
    installer = DockerInstaller(Docker(labels=["compute"]))

    mock_host = mocker.MagicMock()
    mock_host.extra = {}
    mock_vms = [mock_host]
    mock_containers = mocker.MagicMock()
    mock_containers.__bool__ = lambda _: False

    mocker.patch(
        "kiso.docker.installer.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.docker.installer.utils.split_labels",
        return_value=(mock_vms, mock_containers),
    )
    mocker.patch("kiso.docker.installer.utils.run_ansible", return_value=[])
    mocker.patch("kiso.docker.installer.display._render")
    mocker.patch("kiso.docker.installer.console.rule")

    installer({"labels": mocker.MagicMock()})
    assert mock_host.extra[installer.HAS_SOFTWARE_KEY] is True


def test_docker_call_with_containers_raises(mocker: MockerFixture) -> None:
    """DockerInstaller raises RuntimeError when containers are found (line 112-116)."""
    installer = DockerInstaller(Docker(labels=["edge"]))

    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False
    mock_container = mocker.MagicMock()

    mocker.patch(
        "kiso.docker.installer.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.docker.installer.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mocker.patch("kiso.docker.installer.console.rule")

    with pytest.raises(RuntimeError, match="Docker cannot be installed on containers"):
        installer({"labels": mocker.MagicMock()})
