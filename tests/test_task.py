"""Unit tests for kiso.task helper functions."""

from __future__ import annotations

import copy
import sys
from collections import defaultdict
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from enoslib.objects import Host, Roles
from jsonschema.exceptions import ValidationError

from kiso import task
from kiso.configuration import Deployment, Kiso, Software
from kiso.docker.configuration import Docker
from kiso.errors import KisoError
from kiso.htcondor.configuration import HTCondorDaemon
from kiso.objects import Script
from kiso.shell.configuration import ShellConfiguration
from kiso.task import (
    _check_deployed_software,
    _check_experiments,
    _check_software,
    _deduplicate_hosts,
    _extend_labels,
    _generate_etc_hosts,
    _get_defined_machines,
    _get_region_name,
    _install_deployed_software,
    _install_software,
    _replace_labels_key_with_roles_key,
    _show_rysnc_warning,
    check_provisioned,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kiso(**kwargs: object) -> Kiso:
    defaults: dict[str, Any] = {
        "name": "test",
        "sites": [],
        "experiments": [],
        "deployment": None,
        "software": None,
    }
    defaults.update(kwargs)
    return Kiso(**defaults)


class _FakeHost:
    def __init__(self, address: str) -> None:
        self.address = address
        self.extra: dict = {}


# ---------------------------------------------------------------------------
# _replace_labels_key_with_roles_key
# ---------------------------------------------------------------------------


def test_replace_labels_replaces_machine_labels() -> None:
    config = {
        "sites": [
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [{"labels": ["compute"], "number": 1}],
                    "networks": [],
                },
            }
        ]
    }
    result = _replace_labels_key_with_roles_key(config)
    machine = result["sites"][0]["resources"]["machines"][0]
    assert "roles" in machine
    assert "labels" not in machine
    assert machine["roles"] == ["compute"]


def test_replace_labels_replaces_network_labels() -> None:
    config = {
        "sites": [
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [{"labels": ["a"], "number": 1}],
                    "networks": [{"labels": ["net1"], "cidr": "10.0.0.0/24"}],
                },
            }
        ]
    }
    result = _replace_labels_key_with_roles_key(config)
    network = result["sites"][0]["resources"]["networks"][0]
    assert "roles" in network
    assert "labels" not in network


def test_replace_labels_skips_string_networks() -> None:
    config = {
        "sites": [
            {
                "resources": {
                    "machines": [{"labels": ["a"]}],
                    "networks": ["eth0"],
                },
            }
        ]
    }
    result = _replace_labels_key_with_roles_key(config)
    assert result["sites"][0]["resources"]["networks"][0] == "eth0"


def test_replace_labels_does_not_mutate_original() -> None:
    config = {
        "sites": [
            {
                "resources": {
                    "machines": [{"labels": ["a"]}],
                    "networks": [],
                },
            }
        ]
    }
    original = copy.deepcopy(config)
    _replace_labels_key_with_roles_key(config)
    assert config == original


# ---------------------------------------------------------------------------
# _get_defined_machines
# ---------------------------------------------------------------------------


def test_get_defined_machines_basic() -> None:
    kiso_config = _make_kiso(
        sites=[
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [{"labels": ["compute"], "number": 2}],
                    "networks": [],
                },
            }
        ]
    )
    result = _get_defined_machines(kiso_config)
    assert "compute" in result
    assert len(result["compute"]) == 2


def test_get_defined_machines_adds_kiso_labels() -> None:
    kiso_config = _make_kiso(
        sites=[
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [{"labels": ["compute"], "number": 1}],
                    "networks": [],
                },
            }
        ]
    )
    result = _get_defined_machines(kiso_config)
    assert "kiso.compute.1" in result


def test_get_defined_machines_kind_in_result() -> None:
    kiso_config = _make_kiso(
        sites=[
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [{"labels": ["compute"], "number": 1}],
                    "networks": [],
                },
            }
        ]
    )
    result = _get_defined_machines(kiso_config)
    assert "vagrant" in result


def test_get_defined_machines_multiple_vagrant_sites_raises() -> None:
    kiso_config = _make_kiso(
        sites=[
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [{"labels": ["a"], "number": 1}],
                    "networks": [],
                },
            },
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [{"labels": ["b"], "number": 1}],
                    "networks": [],
                },
            },
        ]
    )
    with pytest.raises(ValueError, match="Multiple vagrant"):
        _get_defined_machines(kiso_config)


def test_get_defined_machines_default_number_is_one() -> None:
    kiso_config = _make_kiso(
        sites=[
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [{"labels": ["compute"]}],  # no "number" key
                    "networks": [],
                },
            }
        ]
    )
    result = _get_defined_machines(kiso_config)
    assert len(result["compute"]) == 1


# ---------------------------------------------------------------------------
# check_provisioned
# ---------------------------------------------------------------------------


def test_check_provisioned_raises_if_no_providers() -> None:
    @check_provisioned
    def dummy(_config: object, **_kwargs: object) -> str:
        return "ok"

    with pytest.raises(KisoError):
        dummy(None, env={})


def test_check_provisioned_raises_if_no_env() -> None:
    @check_provisioned
    def dummy(_config: object, **_kwargs: object) -> str:
        return "ok"

    with pytest.raises(KisoError):
        dummy(None)


def test_check_provisioned_passes_with_providers() -> None:
    @check_provisioned
    def dummy(_config: object, **_kwargs: object) -> str:
        return "passed"

    result = dummy(None, env={"providers": ["something"]})
    assert result == "passed"


# ---------------------------------------------------------------------------
# _check_software / _check_deployed_software (early-exit on None)
# ---------------------------------------------------------------------------


def test_check_software_none_returns() -> None:
    _check_software(None, {})  # must not raise


def test_check_software_with_docker_config() -> None:
    software = Software(docker=Docker(labels=["compute"]), apptainer=None, ollama=None)
    label_to_machines = defaultdict(set)
    label_to_machines["compute"].add("vm1")
    label_to_machines["chameleon-edge"] = set()
    _check_software(software, label_to_machines)  # must not raise


def test_check_software_with_invalid_docker_raises() -> None:
    software = Software(docker=Docker(labels=["missing"]), apptainer=None, ollama=None)
    with pytest.raises(ValueError, match="No machines found"):
        _check_software(software, defaultdict(set))


def test_check_deployed_software_none_returns() -> None:
    _check_deployed_software(None, {})  # must not raise


def test_check_deployed_software_with_htcondor_config() -> None:
    deployment = Deployment(htcondor=[HTCondorDaemon(kind="execute", labels=["node"])])
    label_to_machines = defaultdict(set)
    label_to_machines["node"].add("vm1")
    _check_deployed_software(deployment, label_to_machines)  # must not raise


def test_check_deployed_software_with_invalid_htcondor_raises() -> None:
    deployment = Deployment(
        htcondor=[HTCondorDaemon(kind="execute", labels=["missing"])]
    )
    with pytest.raises(ValueError, match="No machines found"):
        _check_deployed_software(deployment, defaultdict(set))


# ---------------------------------------------------------------------------
# _check_experiments
# ---------------------------------------------------------------------------


def test_check_experiments_empty_list() -> None:
    kiso_config = _make_kiso()
    _check_experiments(kiso_config, {})  # must not raise


def test_check_experiments_valid_shell() -> None:
    script = Script(labels=["compute"], script="echo hello")
    exp = ShellConfiguration(kind="shell", name="test", scripts=[script])
    kiso_config = _make_kiso(experiments=[exp])
    label_to_machines = {"compute": {"machine1"}}
    _check_experiments(kiso_config, label_to_machines)  # must not raise


def test_check_experiments_undefined_label_raises() -> None:
    script = Script(labels=["undefined"], script="echo hi")
    exp = ShellConfiguration(kind="shell", name="test", scripts=[script])
    kiso_config = _make_kiso(experiments=[exp])
    with pytest.raises(ValueError, match="Undefined labels"):
        _check_experiments(kiso_config, {})


# ---------------------------------------------------------------------------
# _get_region_name
# ---------------------------------------------------------------------------


def test_get_region_name_found(tmp_path: Path) -> None:
    rc_file = tmp_path / "openrc.sh"
    rc_file.write_text('export OS_REGION_NAME="CHI@UC"\n')
    assert _get_region_name(str(rc_file)) == "CHI@UC"


def test_get_region_name_single_quotes(tmp_path: Path) -> None:
    rc_file = tmp_path / "openrc.sh"
    rc_file.write_text("export OS_REGION_NAME='CHI@TACC'\n")
    assert _get_region_name(str(rc_file)) == "CHI@TACC"


def test_get_region_name_not_found_raises(tmp_path: Path) -> None:
    rc_file = tmp_path / "openrc.sh"
    rc_file.write_text("export OS_PROJECT_NAME=my-project\n")
    with pytest.raises(ValueError, match="Unable to get region name"):
        _get_region_name(str(rc_file))


# ---------------------------------------------------------------------------
# _generate_etc_hosts
# ---------------------------------------------------------------------------


def test_generate_etc_hosts_single_host() -> None:
    host = _FakeHost("10.0.0.1")
    env = {"labels": {"compute": [host]}}
    result = _generate_etc_hosts(env)
    assert "10.0.0.1" in result
    assert "compute" in result
    assert "# Kiso: Start" in result
    assert "# Kiso: End" in result


def test_generate_etc_hosts_uses_preferred_ip() -> None:
    host = _FakeHost("10.0.0.1")
    host.extra["kiso_preferred_ip"] = "1.2.3.4"
    env = {"labels": {"compute": [host]}}
    result = _generate_etc_hosts(env)
    assert "1.2.3.4" in result
    assert "10.0.0.1" not in result


def test_generate_etc_hosts_skips_multi_machine_labels() -> None:
    h1 = _FakeHost("10.0.0.1")
    h2 = _FakeHost("10.0.0.2")
    env = {"labels": {"compute": [h1, h2]}}  # 2 machines → skipped
    result = _generate_etc_hosts(env)
    assert "10.0.0.1" not in result
    assert "10.0.0.2" not in result


# ---------------------------------------------------------------------------
# _install_software
# ---------------------------------------------------------------------------


def test_install_software_none_is_noop() -> None:
    config = _make_kiso()  # software=None
    _install_software(config, {})  # must not raise


def test_install_software_invokes_installer(mocker: MockerFixture) -> None:
    docker_config = Docker(labels=["compute"])
    software = Software(docker=docker_config, apptainer=None, ollama=None)
    config = _make_kiso(software=software)

    mock_instance = mocker.MagicMock()
    mock_cls = mocker.MagicMock(return_value=mock_instance)
    mocker.patch("kiso.task.utils.get_software", return_value=mock_cls)

    env: dict[str, Any] = {"labels": {}}
    _install_software(config, env)
    mock_cls.assert_called_once_with(docker_config)
    mock_instance.assert_called_once_with(env)


# ---------------------------------------------------------------------------
# _install_deployed_software
# ---------------------------------------------------------------------------


def test_install_deployed_software_none_is_noop() -> None:
    config = _make_kiso()  # deployment=None
    _install_deployed_software(config, {})  # must not raise


def test_install_deployed_software_with_none_htcondor_skips() -> None:
    """When deployment.htcondor is None, continue is hit (line 986)."""
    config = _make_kiso(deployment=Deployment(htcondor=None))
    _install_deployed_software(config, {})  # must not raise


def test_install_deployed_software_invokes_installer(mocker: MockerFixture) -> None:
    daemon = HTCondorDaemon(kind="central-manager", labels=["cm"])
    deployment = Deployment(htcondor=[daemon])
    config = _make_kiso(deployment=deployment)

    mock_instance = mocker.MagicMock()
    mock_cls = mocker.MagicMock(return_value=mock_instance)
    mocker.patch("kiso.task.utils.get_deployment", return_value=mock_cls)

    env: dict[str, Any] = {"labels": {}}
    _install_deployed_software(config, env)
    mock_cls.assert_called_once_with([daemon])
    mock_instance.assert_called_once_with(env)


# ---------------------------------------------------------------------------
# _deduplicate_hosts
# ---------------------------------------------------------------------------


def test_deduplicate_hosts_noop_when_no_duplicates() -> None:
    h1, h2 = Host("vm1"), Host("vm2")
    labels = Roles({"a": [h1], "b": [h2]})
    _deduplicate_hosts(labels)  # must not raise


def test_deduplicate_hosts_deduplicates_same_object() -> None:
    h = Host("vm1")
    labels = Roles({"a": [h], "b": [h]})
    _deduplicate_hosts(labels)
    # After dedup, each group should still contain the canonical instance
    assert h in labels["a"]
    assert h in labels["b"]


# ---------------------------------------------------------------------------
# _check_deployed_software with None htcondor (line 296 coverage)
# ---------------------------------------------------------------------------


def test_check_deployed_software_with_none_htcondor() -> None:
    deployment = Deployment(htcondor=None)
    _check_deployed_software(deployment, {})  # config is None → continue → no raise


# ---------------------------------------------------------------------------
# _check_experiments with None experiments (line 317 coverage)
# ---------------------------------------------------------------------------


def test_check_experiments_none_experiments() -> None:
    config_mock = MagicMock()
    config_mock.experiments = None
    _check_experiments(config_mock, {})  # experiments is None → early return


# ---------------------------------------------------------------------------
# validate_config with a dict (covers lines 98-99)
# ---------------------------------------------------------------------------


def test_validate_config_schema_error_logs_and_raises() -> None:
    """validate_config logs validation errors and re-raises ValidationError."""
    # name=42 (integer) fails the 'string' type requirement, triggering iter_errors
    invalid_config = {
        "name": 42,
        "sites": [
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [{"labels": ["c"], "flavour": "small", "number": 1}],
                    "networks": [],
                },
            }
        ],
        "experiments": [],
    }
    with pytest.raises(ValidationError):
        task.check(invalid_config)


# ---------------------------------------------------------------------------
# _extend_labels
# ---------------------------------------------------------------------------


def test_extend_labels_single_host() -> None:
    """_extend_labels adds kiso.<label>.<index> entries for each node."""
    h = Host("10.0.0.1")
    labels = Roles({"compute": [h]})
    _extend_labels(labels)

    assert "kiso.compute.1" in labels
    assert h in labels["kiso.compute.1"]


def test_extend_labels_multiple_hosts() -> None:
    """Multiple hosts get unique indexed kiso labels."""
    h1, h2 = Host("10.0.0.1"), Host("10.0.0.2")
    labels = Roles({"worker": [h1, h2]})
    _extend_labels(labels)

    assert "kiso.worker.1" in labels
    assert "kiso.worker.2" in labels


# ---------------------------------------------------------------------------
# _show_rysnc_warning
# ---------------------------------------------------------------------------


def test_show_rsync_warning_fabric_site_no_rsync(mocker: MockerFixture) -> None:
    """With fabric site and no rsync found, the break is hit and warning is skipped."""
    mocker.patch("kiso.task.shutil.which", return_value=None)
    mock_print = mocker.patch("kiso.task.console.print")

    _show_rysnc_warning([{"kind": "fabric"}])

    mock_print.assert_not_called()


def test_show_rsync_warning_fabric_mac_default_rsync(mocker: MockerFixture) -> None:
    """On macOS with the default rsync, the warning is printed (lines 587, 591-594)."""
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/rsync")
    mock_print = mocker.patch("kiso.task.console.print")
    mocker.patch.object(sys, "platform", "darwin")

    _show_rysnc_warning([{"kind": "fabric"}])

    assert mock_print.call_count >= 2  # Markdown header + message


# ---------------------------------------------------------------------------
# ssh
# ---------------------------------------------------------------------------

# Bypass @enostask so tests can pass env as a plain dict.
_ssh = task.ssh.__wrapped__


def _make_ssh_env(*hosts: Host) -> dict:
    """Build a minimal env dict for ssh unit tests."""
    labels: Roles = Roles()
    for host in hosts:
        labels[host.alias] = [host]
    _extend_labels(labels)
    return {"providers": [object()], "labels": labels}


def _make_host(
    alias: str,
    address: str = "10.0.0.1",
    user: str = "ubuntu",
    port: int = 22,
    keyfile: str | None = None,
) -> Host:
    return Host(address, alias=alias, user=user, port=port, keyfile=keyfile)


def test_ssh_no_executable_raises(mocker: MockerFixture) -> None:
    mocker.patch("kiso.task.shutil.which", return_value=None)
    with pytest.raises(KisoError, match="Unable to locate SSH"):
        _ssh("worker1", env=_make_ssh_env(_make_host("worker1")))


def test_ssh_unknown_alias_raises(mocker: MockerFixture) -> None:
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")
    with pytest.raises(KisoError, match="not found"):
        _ssh("ghost", env=_make_ssh_env(_make_host("worker1")))


def test_ssh_by_host_alias(mocker: MockerFixture) -> None:
    host = _make_host("worker1", address="10.0.0.1", user="ubuntu")
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("worker1", env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert "ubuntu@10.0.0.1" in cmd


def test_ssh_by_kiso_label(mocker: MockerFixture) -> None:
    host = _make_host("worker1", address="10.0.0.2", user="ubuntu")
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("kiso.worker1.1", env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert "ubuntu@10.0.0.2" in cmd


def test_ssh_tty_adds_dash_t(mocker: MockerFixture) -> None:
    host = _make_host("worker1")
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("worker1", tty=True, env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert "-t" in cmd


def test_ssh_no_tty_omits_dash_t(mocker: MockerFixture) -> None:
    host = _make_host("worker1")
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("worker1", tty=False, env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert "-t" not in cmd


def test_ssh_command_appended(mocker: MockerFixture) -> None:
    host = _make_host("worker1")
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("worker1", command="hostname", env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert cmd[-1] == "hostname"


def test_ssh_extra_args_appended(mocker: MockerFixture) -> None:
    host = _make_host("worker1")
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("worker1", extra_ssh_args=["-L", "8080:localhost:80"], env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert "-L" in cmd
    assert "8080:localhost:80" in cmd


def test_ssh_nonstandard_port(mocker: MockerFixture) -> None:
    host = _make_host("worker1", port=2222)
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("worker1", env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert "-p" in cmd
    assert "2222" in cmd


def test_ssh_standard_port_omitted(mocker: MockerFixture) -> None:
    host = _make_host("worker1", port=22)
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("worker1", env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert "-p" not in cmd


def test_ssh_keyfile_added(mocker: MockerFixture) -> None:
    host = _make_host("worker1", keyfile="/home/user/.ssh/id_rsa")
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("worker1", env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert "-i" in cmd
    assert "/home/user/.ssh/id_rsa" in cmd


def test_ssh_user_prefix_overrides_node_user(mocker: MockerFixture) -> None:
    host = _make_host("worker1", user="ubuntu")
    mock_execvp = mocker.patch("kiso.task.os.execvp")
    mocker.patch("kiso.task.shutil.which", return_value="/usr/bin/ssh")

    _ssh("root@worker1", env=_make_ssh_env(host))

    cmd = mock_execvp.call_args[0][1]
    assert "root@10.0.0.1" in cmd
    assert "ubuntu@" not in " ".join(cmd)


def test_validate_config_accepts_dict_config() -> None:
    """validate_config wrapper handles dict input without a file path."""
    # A fully valid config (same as test-1.yml) passed as a dict
    valid_config = {
        "name": "test-experiment",
        "sites": [
            {
                "kind": "vagrant",
                "resources": {
                    "machines": [
                        {"labels": ["compute"], "flavour": "small", "number": 1}
                    ],
                    "networks": [{"cidr": "192.168.42.0/24", "labels": ["net1"]}],
                },
            }
        ],
        "experiments": [
            {
                "kind": "shell",
                "name": "test-shell",
                "scripts": [{"labels": ["compute"], "script": "echo hello"}],
            }
        ],
    }
    with patch("kiso.task.en.check"):
        # Should not raise — dict path hits lines 98-99
        task.check(valid_config)
