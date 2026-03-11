"""Unit tests for task.py standalone helper functions and schema.py helpers."""

from __future__ import annotations

from ipaddress import IPv4Interface, IPv6Interface
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import enoslib as en
import pytest
from enoslib.objects import DefaultNetwork, Host, IPAddress, NetDevice

from kiso import constants as const
from kiso import schema
from kiso.task import (
    _copy_experiment_dir,
    _install_commons,
    _run_experiments,
    down,
    run,
)
from kiso.utils import get_ips

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

# ---------------------------------------------------------------------------
# _get_ips — standalone function, no decorators
# ---------------------------------------------------------------------------


def test_get_ips_non_host_private_ip() -> None:
    """ChameleonDevice (non-Host) with private IP → priority 1."""
    machine = MagicMock()
    # Not an enoslib Host — isinstance(machine, Host) will be False
    machine.address = "192.168.1.1"
    machine.extra = {}
    # Ensure it's NOT an instance of Host
    assert not isinstance(machine, Host)

    result = get_ips(machine)
    assert len(result) == 1
    ip, priority = result[0]
    assert str(ip) == "192.168.1.1"
    assert priority == 2  # private


def test_get_ips_non_host_public_ip() -> None:
    """ChameleonDevice with public IP → priority 0."""
    machine = MagicMock()
    machine.address = "8.8.8.8"
    machine.extra = {}

    result = get_ips(machine)
    assert len(result) == 1
    ip, priority = result[0]
    assert str(ip) == "8.8.8.8"
    assert priority == 0  # public


def test_get_ips_host_with_default_network_ipv4() -> None:
    """Host with IPv4 address on DefaultNetwork → included in results."""
    nd = NetDevice("eth0")
    ipa = IPAddress(IPv4Interface("10.0.0.1/24"), network=DefaultNetwork("10.0.0.0/24"))
    nd.addresses.add(ipa)
    h = Host("10.0.0.1", net_devices={nd})
    h.extra = {}

    result = get_ips(h)
    assert len(result) == 1
    ip, priority = result[0]
    assert str(ip) == "10.0.0.1"
    assert priority == 2  # private IPv4


def test_get_ips_host_with_no_net_devices() -> None:
    """Host with empty net_devices → empty result."""
    h = Host("10.0.0.1")
    h.extra = {}

    result = get_ips(h)
    assert result == []


def test_get_ips_host_skips_loopback() -> None:
    """Host with loopback address → skipped."""
    nd = NetDevice("lo")
    ipa = IPAddress(IPv4Interface("127.0.0.1/8"), network=DefaultNetwork("127.0.0.0/8"))
    nd.addresses.add(ipa)
    h = Host("10.0.0.1", net_devices={nd})
    h.extra = {}

    result = get_ips(h)
    assert result == []


def test_get_ips_host_skips_link_local() -> None:
    """Host with link-local IPv6 address → skipped."""
    nd = NetDevice("eth0")
    ipa = IPAddress(IPv6Interface("fe80::1/64"), network=DefaultNetwork("fe80::/10"))
    nd.addresses.add(ipa)
    h = Host("10.0.0.1", net_devices={nd})
    h.extra = {}

    result = get_ips(h)
    assert result == []


def test_get_ips_host_with_no_default_network() -> None:
    """Host with address on non-DefaultNetwork → skipped."""
    nd = NetDevice("eth0")
    # network=None means no DefaultNetwork
    ipa = IPAddress(IPv4Interface("10.0.0.1/24"), network=None)
    nd.addresses.add(ipa)
    h = Host("10.0.0.1", net_devices={nd})
    h.extra = {}

    result = get_ips(h)
    assert result == []


def test_get_ips_non_host_no_floating_ips() -> None:
    """Machine with empty floating-ips → only address from machine.address."""
    machine = MagicMock()
    machine.address = "192.168.1.5"
    machine.extra = {"floating-ips": []}

    result = get_ips(machine)
    assert len(result) == 1


def test_get_ips_non_host_shared_address_space_ip() -> None:
    """ChameleonDevice with IP in 100.64.0.0/10 (shared address space) → priority 2."""
    machine = MagicMock()
    machine.address = "100.64.0.1"
    machine.extra = {}
    assert not isinstance(machine, Host)

    result = get_ips(machine)
    assert len(result) == 1
    ip, priority = result[0]
    assert str(ip) == "100.64.0.1"
    assert priority == 2  # treated as private


def test_get_ips_host_shared_address_space_ip(mocker: MockerFixture) -> None:
    """Host with IP in 100.64.0.0/10 (shared address space) → priority 2."""
    mocker.patch("kiso.utils.has_fabric", False)
    nd = NetDevice("eth0")
    ipa = IPAddress(
        IPv4Interface("100.100.0.1/10"), network=DefaultNetwork("100.64.0.0/10")
    )
    nd.addresses.add(ipa)
    h = Host("100.100.0.1", net_devices={nd})
    h.extra = {}

    result = get_ips(h)
    assert len(result) == 1
    ip, priority = result[0]
    assert str(ip) == "100.100.0.1"
    assert priority == 2  # treated as private


# ---------------------------------------------------------------------------
# _install_commons — standalone function
# ---------------------------------------------------------------------------


def test_install_commons_with_empty_labels(mocker: MockerFixture) -> None:
    """_install_commons with no vms or containers calls display.commons."""
    mock_labels = MagicMock()
    mock_labels.all.return_value = MagicMock()
    mock_vms = MagicMock()
    mock_vms.__bool__ = lambda _: False
    mock_containers = MagicMock()
    mock_containers.__bool__ = lambda _: False

    mocker.patch(
        "kiso.task.utils.split_labels", return_value=(mock_vms, mock_containers)
    )
    mocker.patch("kiso.task._generate_etc_hosts", return_value="")
    mock_render = mocker.patch("kiso.task.display.commons")
    mocker.patch("kiso.task.console.rule")

    env = {"labels": mock_labels}
    _install_commons(env)
    mock_render.assert_called_once()


def test_install_commons_with_vms_runs_ansible(mocker: MockerFixture) -> None:
    """_install_commons calls run_ansible when vms are present (lines 908-915)."""
    mock_labels = MagicMock()
    mock_labels.all.return_value = MagicMock()
    mock_vms = [MagicMock()]  # truthy list
    mock_containers = MagicMock()
    mock_containers.__bool__ = lambda _: False

    mocker.patch(
        "kiso.task.utils.split_labels", return_value=(mock_vms, mock_containers)
    )
    mocker.patch("kiso.task._generate_etc_hosts", return_value="127.0.0.1 host1")
    mock_ansible = mocker.patch("kiso.task.utils.run_ansible", return_value=[])
    mocker.patch("kiso.task.display.commons")
    mocker.patch("kiso.task.console.rule")

    env = {"labels": mock_labels}
    _install_commons(env)
    mock_ansible.assert_called_once()


def test_install_commons_with_containers_uses_run_script(mocker: MockerFixture) -> None:
    """_install_commons calls run_script for containers (lines 917-928)."""
    mock_container = MagicMock()
    mock_labels = MagicMock()
    mock_labels.all.return_value = MagicMock()
    mock_vms = MagicMock()
    mock_vms.__bool__ = lambda _: False

    mocker.patch(
        "kiso.task.utils.split_labels", return_value=(mock_vms, [mock_container])
    )
    mocker.patch("kiso.task._generate_etc_hosts", return_value="")
    mock_run_script = mocker.patch(
        "kiso.task.edge.run_script", return_value=MagicMock()
    )
    mocker.patch("kiso.task.display.commons")
    mocker.patch("kiso.task.console.rule")

    env = {"labels": mock_labels}
    _install_commons(env)
    mock_run_script.assert_called_once()


# ---------------------------------------------------------------------------
# _copy_experiment_dir — standalone function
# ---------------------------------------------------------------------------


def test_copy_experiment_dir_skips_when_already_ok(mocker: MockerFixture) -> None:
    """_copy_experiment_dir returns early when status is already OK (line 1063-1064)."""
    mock_labels = MagicMock()
    mock_labels.all.return_value = MagicMock()
    mock_vms = MagicMock()
    mock_vms.__bool__ = lambda _: False
    mock_containers = MagicMock()
    mock_containers.__bool__ = lambda _: False

    mocker.patch(
        "kiso.task.utils.split_labels", return_value=(mock_vms, mock_containers)
    )
    mocker.patch("kiso.task.console.print")

    env: dict[str, Any] = {
        "labels": mock_labels,
        "experiments": {"copy-experiment-directory": const.STATUS_OK},
        "wd": "/wd",
        "remote_wd": "/remote/wd",
    }
    _copy_experiment_dir(env)
    # Status should remain OK, no changes
    assert env["experiments"]["copy-experiment-directory"] == const.STATUS_OK


def test_copy_experiment_dir_sets_ok_on_success(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """_copy_experiment_dir sets STATUS_OK after successful copy (line 1106)."""
    mock_labels = MagicMock()
    mock_labels.all.return_value = MagicMock()
    mock_vms = MagicMock()
    mock_vms.__bool__ = lambda _: False
    mock_containers = MagicMock()
    mock_containers.__bool__ = lambda _: False

    mocker.patch(
        "kiso.task.utils.split_labels", return_value=(mock_vms, mock_containers)
    )
    mocker.patch("kiso.task.console.print")

    env: dict[str, Any] = {
        "labels": mock_labels,
        "experiments": {},
        "wd": str(tmp_path),
        "remote_wd": "/remote/wd",
    }
    _copy_experiment_dir(env)
    assert env["experiments"]["copy-experiment-directory"] == const.STATUS_OK


def test_copy_experiment_dir_sets_failed_on_exception(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """_copy_experiment_dir sets STATUS_FAILED on exception (lines 1102-1104)."""
    mock_labels = MagicMock()
    mock_labels.all.return_value = MagicMock()
    mock_vms = [MagicMock()]  # truthy

    mocker.patch("kiso.task.utils.split_labels", return_value=(mock_vms, []))
    mocker.patch("kiso.task.console.print")
    mocker.patch("kiso.task.utils.actions", side_effect=RuntimeError("copy failed"))

    env: dict[str, Any] = {
        "labels": mock_labels,
        "experiments": {},
        "wd": str(tmp_path),
        "remote_wd": "/remote/wd",
    }
    with pytest.raises(RuntimeError):
        _copy_experiment_dir(env)
    assert env["experiments"]["copy-experiment-directory"] == const.STATUS_FAILED


def test_copy_experiment_dir_with_containers_uses_edge(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """_copy_experiment_dir calls edge.upload for containers (lines 1099-1101)."""
    mock_container = MagicMock()
    mock_labels = MagicMock()
    mock_labels.all.return_value = MagicMock()
    mock_vms = MagicMock()
    mock_vms.__bool__ = lambda _: False

    mocker.patch(
        "kiso.task.utils.split_labels", return_value=(mock_vms, [mock_container])
    )
    mocker.patch("kiso.task.console.print")
    mock_upload = mocker.patch("kiso.task.edge.upload")

    env: dict[str, Any] = {
        "labels": mock_labels,
        "experiments": {},
        "wd": str(tmp_path),
        "remote_wd": "/remote/wd",
    }
    _copy_experiment_dir(env)
    mock_upload.assert_called_once()


def test_copy_experiment_dir_with_vms_uses_actions(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """_copy_experiment_dir calls utils.actions for vms (lines 1068-1098)."""
    mock_labels = MagicMock()
    mock_labels.all.return_value = MagicMock()
    mock_vms = [MagicMock()]  # truthy list

    mocker.patch("kiso.task.utils.split_labels", return_value=(mock_vms, []))
    mocker.patch("kiso.task.console.print")

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.task.utils.actions", return_value=mock_cm)
    mocker.patch("kiso.task.tempfile.NamedTemporaryFile", return_value=MagicMock())

    env: dict[str, Any] = {
        "labels": mock_labels,
        "experiments": {},
        "wd": str(tmp_path),
        "remote_wd": "/remote/wd",
    }
    _copy_experiment_dir(env)
    assert env["experiments"]["copy-experiment-directory"] == const.STATUS_OK


# ---------------------------------------------------------------------------
# _run_experiments — standalone function
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# schema.py — _get_experiment_kinds, _get_software_schemas, _get_deployment_schemas
#             all use the .select() path on modern Python (lines 232, 253, 274)
# ---------------------------------------------------------------------------


def test_schema_get_experiment_kinds_select_path(mocker: MockerFixture) -> None:
    """_get_experiment_kinds uses .select() when entry_points() is not a dict."""
    mock_ep = mocker.MagicMock()
    mock_ep.value = "kiso.shell.runner:ShellRunner"
    mock_ep.load.return_value = mocker.MagicMock(schema={"$$target": ""})
    mock_eps = mocker.MagicMock()
    mock_eps.select = mocker.MagicMock(return_value=[mock_ep])
    mocker.patch("kiso.schema.entry_points", return_value=mock_eps)

    result = schema._get_experiment_kinds()
    mock_eps.select.assert_called()
    assert isinstance(result, list)


def test_schema_get_software_schemas_select_path(mocker: MockerFixture) -> None:
    """_get_software_schemas uses .select() when entry_points() is not a dict."""
    mock_ep = mocker.MagicMock()
    mock_ep.name = "docker"
    mock_ep.value = "kiso.docker.installer:DockerInstaller"
    mock_ep.load.return_value = mocker.MagicMock(schema={"$$target": ""})
    mock_eps = mocker.MagicMock()
    mock_eps.select = mocker.MagicMock(return_value=[mock_ep])
    mocker.patch("kiso.schema.entry_points", return_value=mock_eps)

    result = schema._get_software_schemas()
    mock_eps.select.assert_called()
    assert isinstance(result, dict)


def test_schema_get_deployment_schemas_select_path(mocker: MockerFixture) -> None:
    """_get_deployment_schemas uses .select() when entry_points() is not a dict."""
    mock_ep = mocker.MagicMock()
    mock_ep.name = "htcondor"
    mock_ep.value = "kiso.htcondor.installer:HTCondorInstaller"
    mock_ep.load.return_value = mocker.MagicMock(schema={"$$target": ""})
    mock_eps = mocker.MagicMock()
    mock_eps.select = mocker.MagicMock(return_value=[mock_ep])
    mocker.patch("kiso.schema.entry_points", return_value=mock_eps)

    result = schema._get_deployment_schemas()
    mock_eps.select.assert_called()
    assert isinstance(result, dict)


def test_run_experiments_calls_runner(mocker: MockerFixture) -> None:
    """_run_experiments instantiates runner and calls it (lines 1124-1138)."""
    mock_experiment = MagicMock()
    mock_experiment.kind = "shell"

    mock_runner_instance = MagicMock()
    mock_runner_cls = MagicMock(return_value=mock_runner_instance)
    mocker.patch("kiso.task.utils.get_runner", return_value=mock_runner_cls)

    env = {
        "wd": "/wd",
        "remote_wd": "/remote",
        "resultdir": "/results",
        "labels": MagicMock(),
        "experiments": {0: {}},
    }
    _run_experiments(0, mock_experiment, {"x": 1}, env)

    mock_runner_cls.assert_called_once_with(mock_experiment, 0, variables={"x": 1})
    mock_runner_instance.assert_called_once()


# ---------------------------------------------------------------------------
# down() — decorated task function (bypass via __wrapped__)
# ---------------------------------------------------------------------------


def test_down_returns_early_when_no_providers(mocker: MockerFixture) -> None:
    """down() logs and returns early when 'providers' not in env (lines 1168-1174)."""
    raw_down = down.__wrapped__.__wrapped__.__wrapped__
    mocker.patch("kiso.task.console.rule")

    env = {"wd": "/fake/wd", "labels": {}}
    raw_down(MagicMock(), env=env)
    # Should return early, providers key should not be added
    assert "providers" not in env


def test_down_with_providers_calls_destroy(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """down() calls providers.destroy() when providers present (lines 1176-1202)."""
    raw_down = down.__wrapped__.__wrapped__.__wrapped__
    mocker.patch("kiso.task.console.rule")

    mock_providers = MagicMock()
    # Return a provider that doesn't match vagrant/chameleon so we skip inner branches
    mock_provider = MagicMock()
    mock_provider.__class__ = object  # type: ignore[assignment]  # not Vagrant or ChameleonEdge
    mock_providers.providers = [mock_provider]

    env = {
        "wd": str(tmp_path),
        "labels": {},
        "providers": mock_providers,
    }
    raw_down(MagicMock(), env=env)
    mock_providers.destroy.assert_called_once()
    # providers key removed from env
    assert "providers" not in env


def test_run_body_calls_copy_and_run_experiments(mocker: MockerFixture) -> None:
    """run() body calls _copy_experiment_dir and _run_experiments (lines 1025-1037)."""
    raw_run = run.__wrapped__.__wrapped__.__wrapped__
    mocker.patch("kiso.task.console.rule")
    mock_copy = mocker.patch("kiso.task._copy_experiment_dir")
    mock_run_exp = mocker.patch("kiso.task._run_experiments")

    mock_experiment = MagicMock()
    mock_config = MagicMock()
    mock_config.experiments = [mock_experiment]
    mock_config.variables = {}

    env = {"wd": "/wd", "labels": MagicMock()}
    raw_run(mock_config, env=env)

    mock_copy.assert_called_once_with(env)
    mock_run_exp.assert_called_once_with(0, mock_experiment, {}, env)


def test_run_body_with_force_clears_experiments(mocker: MockerFixture) -> None:
    """run() body with force=True clears experiments dict (line 1031-1032)."""
    raw_run = run.__wrapped__.__wrapped__.__wrapped__
    mocker.patch("kiso.task.console.rule")
    mocker.patch("kiso.task._copy_experiment_dir")
    mocker.patch("kiso.task._run_experiments")

    mock_config = MagicMock()
    mock_config.experiments = []
    mock_config.variables = {}

    env = {"wd": "/wd", "labels": MagicMock(), "experiments": {0: {"done": True}}}
    raw_run(mock_config, force=True, env=env)
    assert env["experiments"] == {}


def test_down_with_vagrant_provider_cleans_up(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """down() cleans up .vagrant dir when vagrant provider present (lines 1184-1190)."""
    if not hasattr(en, "Vagrant"):
        pytest.skip("Vagrant not available")

    raw_down = down.__wrapped__.__wrapped__.__wrapped__
    mocker.patch("kiso.task.console.rule")

    vagrant_dir = tmp_path / ".vagrant"
    vagrant_dir.mkdir()
    vagrant_file = tmp_path / "Vagrantfile"
    vagrant_file.write_text("# stub")

    mock_vagrant = MagicMock(spec=en.Vagrant)
    mock_providers = MagicMock()
    mock_providers.providers = [mock_vagrant]

    env = {
        "wd": str(tmp_path),
        "labels": {},
        "providers": mock_providers,
    }
    raw_down(MagicMock(), env=env)
    mock_providers.destroy.assert_called_once()
    # .vagrant dir and Vagrantfile removed
    assert not vagrant_dir.exists()
    assert not vagrant_file.exists()


def test_down_vagrant_ssh_key_removal(mocker: MockerFixture, tmp_path: Path) -> None:
    """down() calls ssh-add -d to remove vagrant SSH keys (lines 1186-1190)."""
    if not hasattr(en, "Vagrant"):
        pytest.skip("Vagrant not available")

    raw_down = down.__wrapped__.__wrapped__.__wrapped__
    mocker.patch("kiso.task.console.rule")

    # Create .vagrant dir with a private_key file
    vagrant_dir = tmp_path / ".vagrant"
    key_dir = vagrant_dir / "machines" / "default" / "virtualbox"
    key_dir.mkdir(parents=True)
    key_file = key_dir / "private_key"
    key_file.write_text("fake key")

    mock_vagrant = MagicMock(spec=en.Vagrant)
    mock_providers = MagicMock()
    mock_providers.providers = [mock_vagrant]

    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh-add")
    mock_subproc = mocker.patch(
        "kiso.task.subprocess.run",
        return_value=MagicMock(returncode=0),
    )

    env = {
        "wd": str(tmp_path),
        "labels": {},
        "providers": mock_providers,
    }
    raw_down(MagicMock(), env=env)
    # ssh-add -d was called for each private_key
    mock_subproc.assert_called_once()
