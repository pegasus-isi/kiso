"""Unit tests for kiso.htcondor.installer.HTCondorInstaller."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import pytest
from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice
from enoslib.objects import Host, Roles

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

from kiso.htcondor.configuration import HTCondorDaemon
from kiso.htcondor.installer import HTCondorInstaller

# ---------------------------------------------------------------------------
# __init__ / check
# ---------------------------------------------------------------------------


def test_htcondor_init_stores_config() -> None:
    daemon = HTCondorDaemon(kind="central-manager", labels=["cm"])
    installer = HTCondorInstaller([daemon])
    assert installer.config == [daemon]


def test_htcondor_check_none_config_is_noop() -> None:
    HTCondorInstaller(None).check({})  # must not raise


def test_htcondor_check_valid_central_manager() -> None:
    daemon = HTCondorDaemon(kind="central-manager", labels=["cm"])
    installer = HTCondorInstaller([daemon])
    label_to_machines = defaultdict(set)
    label_to_machines["cm"].add("machine1")
    installer.check(label_to_machines)  # must not raise


def test_htcondor_check_undefined_label_raises() -> None:
    daemon = HTCondorDaemon(kind="execute", labels=["undefined"])
    installer = HTCondorInstaller([daemon])
    with pytest.raises(ValueError, match="No machines found"):
        installer.check(defaultdict(set))


def test_htcondor_check_missing_config_file_raises(tmp_path: Path) -> None:
    config_file = str(tmp_path / "nonexistent.cfg")
    daemon = HTCondorDaemon(kind="execute", labels=["node"], config_file=config_file)
    installer = HTCondorInstaller([daemon])
    label_to_machines = defaultdict(set)
    label_to_machines["node"].add("machine1")
    with pytest.raises(ValueError, match="Missing config files"):
        installer.check(label_to_machines)


def test_htcondor_check_existing_config_file_passes(tmp_path: Path) -> None:
    config_file = tmp_path / "condor.cfg"
    config_file.write_text("DAEMON_LIST = MASTER\n")
    daemon = HTCondorDaemon(
        kind="execute", labels=["node"], config_file=str(config_file)
    )
    installer = HTCondorInstaller([daemon])
    label_to_machines = defaultdict(set)
    label_to_machines["node"].add("machine1")
    installer.check(label_to_machines)  # must not raise


def test_htcondor_check_multiple_central_managers_raises() -> None:
    installer = HTCondorInstaller(
        [
            HTCondorDaemon(kind="central-manager", labels=["cm1"]),
            HTCondorDaemon(kind="central-manager", labels=["cm2"]),
        ]
    )
    label_to_machines = defaultdict(set)
    label_to_machines["cm1"].add("m1")
    label_to_machines["cm2"].add("m2")
    with pytest.raises(ValueError, match="Multiple central-manager"):
        installer.check(label_to_machines)


def test_htcondor_check_too_many_cm_machines_raises() -> None:
    installer = HTCondorInstaller(
        [HTCondorDaemon(kind="central-manager", labels=["cm"])]
    )
    label_to_machines = defaultdict(set)
    label_to_machines["cm"] = {"m1", "m2"}  # two machines for same CM label
    with pytest.raises(ValueError, match="Multiple central-manager machines"):
        installer.check(label_to_machines)


def test_htcondor_check_overlapping_execute_labels_raises() -> None:
    installer = HTCondorInstaller(
        [
            HTCondorDaemon(kind="execute", labels=["node"]),
            HTCondorDaemon(kind="execute", labels=["node"]),  # duplicate label
        ]
    )
    label_to_machines = defaultdict(set)
    label_to_machines["node"].add("m1")
    with pytest.raises(ValueError, match="[Ee]xecute nodes"):
        installer.check(label_to_machines)


def test_htcondor_check_non_overlapping_execute_labels_passes() -> None:
    installer = HTCondorInstaller(
        [
            HTCondorDaemon(kind="execute", labels=["node1"]),
            HTCondorDaemon(kind="execute", labels=["node2"]),
        ]
    )
    label_to_machines = defaultdict(set)
    label_to_machines["node1"].add("m1")
    label_to_machines["node2"].add("m2")
    installer.check(label_to_machines)  # must not raise


def test_htcondor_check_node_overlap_submit() -> None:
    installer = HTCondorInstaller(
        [
            HTCondorDaemon(kind="submit", labels=["sub"]),
            HTCondorDaemon(kind="submit", labels=["sub"]),
        ]
    )
    with pytest.raises(ValueError, match="[Ss]ubmit nodes"):
        installer._check_node_overlap("submit")


# ---------------------------------------------------------------------------
# __call__ — None config early-return
# ---------------------------------------------------------------------------


def test_htcondor_call_none_config_is_noop() -> None:
    HTCondorInstaller(None)({"labels": {}})  # must not raise


# ---------------------------------------------------------------------------
# __call__ — with infrastructure mocked
# ---------------------------------------------------------------------------


def test_htcondor_call_with_host_non_central_manager(mocker: MockerFixture) -> None:
    """HTCondorInstaller.__call__ with execute host runs ansible via executor."""
    daemon = HTCondorDaemon(kind="execute", labels=["worker"])
    installer = HTCondorInstaller([daemon])

    mock_host = mocker.MagicMock()
    mock_host.address = "10.0.0.1"
    mock_host.alias = "worker1"
    mock_host.extra = {"kiso_preferred_ip": "10.0.0.1"}
    mock_host.__class__ = Host

    mocker.patch.object(
        installer,
        "_get_label_daemon_machine_map",
        return_value={mock_host: {(0, "execute")}},
    )
    mocker.patch.object(installer, "_get_condor_config", return_value=([], {}))
    mocker.patch(
        "kiso.htcondor.installer.utils.get_pool_passwd_file",
        return_value="/fake/pool_passwd",
    )

    mock_future = mocker.MagicMock()
    mock_future.result.return_value = [mocker.MagicMock()]
    mock_executor = mocker.MagicMock()
    mock_executor.submit.return_value = mock_future
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_executor)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch(
        "kiso.htcondor.installer.get_process_pool_executor", return_value=mock_cm
    )

    mocker.patch(
        "kiso.htcondor.installer.utils.run_ansible", return_value=[mocker.MagicMock()]
    )
    mocker.patch("kiso.htcondor.installer.display._render")
    mocker.patch("kiso.htcondor.installer.console.rule")

    env = {"labels": mocker.MagicMock(), "is_public_ip_required": False}
    installer(env)

    assert mock_host.extra[installer.HAS_SOFTWARE_KEY] is True
    mock_executor.submit.assert_called_once()


def test_htcondor_call_with_central_manager_waits(mocker: MockerFixture) -> None:
    """Central-manager daemons are installed synchronously (line 263-265)."""
    daemon = HTCondorDaemon(kind="central-manager", labels=["cm"])
    installer = HTCondorInstaller([daemon])

    mock_host = mocker.MagicMock()
    mock_host.alias = "cm1"
    mock_host.extra = {"kiso_preferred_ip": "10.0.0.1"}
    mock_host.__class__ = Host

    mocker.patch.object(
        installer,
        "_get_label_daemon_machine_map",
        return_value={mock_host: {(0, "central-manager")}},
    )
    mocker.patch.object(installer, "_get_condor_config", return_value=([], {}))
    mocker.patch(
        "kiso.htcondor.installer.utils.get_pool_passwd_file",
        return_value="/fake/pool_passwd",
    )
    mocker.patch(
        "kiso.htcondor.installer.utils.resolve_labels", return_value=[mock_host]
    )

    mock_future = mocker.MagicMock()
    mock_future.result.return_value = [mocker.MagicMock()]
    mock_executor = mocker.MagicMock()
    mock_executor.submit.return_value = mock_future
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_executor)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch(
        "kiso.htcondor.installer.get_process_pool_executor", return_value=mock_cm
    )

    mocker.patch("kiso.htcondor.installer.display._render")
    mocker.patch("kiso.htcondor.installer.console.rule")

    env = {"labels": mocker.MagicMock(), "is_public_ip_required": False}
    installer(env)

    # future.result() called immediately for central-manager
    mock_future.result.assert_called_once()


def test_htcondor_call_with_chameleon_device_submits_edge_install(
    mocker: MockerFixture,
) -> None:
    """ChameleonDevice branch submits _install_condor_on_edge (lines 242-248)."""
    daemon = HTCondorDaemon(kind="execute", labels=["edge"])
    installer = HTCondorInstaller([daemon])

    mock_container = mocker.MagicMock(spec=ChameleonDevice)
    mock_container.address = "10.0.0.5"
    mock_container.extra = {"kiso_preferred_ip": "10.0.0.5"}

    mocker.patch.object(
        installer,
        "_get_label_daemon_machine_map",
        return_value={mock_container: {(0, "execute")}},
    )
    mocker.patch.object(installer, "_get_condor_config", return_value=([], {}))
    mocker.patch(
        "kiso.htcondor.installer.utils.get_pool_passwd_file",
        return_value="/fake/pool_passwd",
    )
    mocker.patch("kiso.htcondor.installer.utils.resolve_labels", return_value=[])

    mock_future = mocker.MagicMock()
    mock_future.result.return_value = [mocker.MagicMock()]
    mock_executor = mocker.MagicMock()
    mock_executor.submit.return_value = mock_future
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_executor)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch(
        "kiso.htcondor.installer.get_process_pool_executor", return_value=mock_cm
    )
    mocker.patch("kiso.htcondor.installer.display._render")
    mocker.patch("kiso.htcondor.installer.console.rule")

    env = {"labels": mocker.MagicMock(), "is_public_ip_required": False}
    installer(env)

    # executor.submit should be called with _install_condor_on_edge (not run_ansible)
    call_args = mock_executor.submit.call_args
    assert call_args[0][0] == installer._install_condor_on_edge
    assert mock_container.extra[installer.HAS_SOFTWARE_KEY] is True


# ---------------------------------------------------------------------------
# _get_label_daemon_machine_map
# ---------------------------------------------------------------------------


def test_htcondor_get_label_daemon_machine_map() -> None:
    daemon = HTCondorDaemon(kind="execute", labels=["worker"])
    installer = HTCondorInstaller([daemon])
    h = Host("vm1")
    h.extra = {}
    labels = Roles({"worker": [h]})

    result = installer._get_label_daemon_machine_map(installer.config, labels)
    assert h in result
    assert any(d[1] == "execute" for d in result[h])


def test_htcondor_get_label_daemon_machine_map_unknown_label() -> None:
    """Labels not in config are silently skipped."""
    daemon = HTCondorDaemon(kind="submit", labels=["sub"])
    installer = HTCondorInstaller([daemon])
    h = Host("vm1")
    h.extra = {}
    labels = Roles({"other": [h]})  # "other" not in config labels

    result = installer._get_label_daemon_machine_map(installer.config, labels)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# _cmp
# ---------------------------------------------------------------------------


def test_htcondor_cmp_central_manager() -> None:
    installer = HTCondorInstaller([])
    assert installer._cmp(("", {(0, "central-manager")})) == 0


def test_htcondor_cmp_personal() -> None:
    installer = HTCondorInstaller([])
    assert installer._cmp(("", {(0, "personal")})) == 1


def test_htcondor_cmp_execute() -> None:
    installer = HTCondorInstaller([])
    assert installer._cmp(("", {(0, "execute")})) == 2


def test_htcondor_cmp_submit() -> None:
    installer = HTCondorInstaller([])
    assert installer._cmp(("", {(0, "submit")})) == 3


def test_htcondor_cmp_empty_daemons() -> None:
    installer = HTCondorInstaller([])
    assert installer._cmp(("", set())) == 10


def test_htcondor_cmp_invalid_daemon_raises() -> None:
    installer = HTCondorInstaller([])
    with pytest.raises(ValueError, match="Daemon"):
        installer._cmp(("", {(0, "invalid-daemon")}))


# ---------------------------------------------------------------------------
# _get_condor_config
# ---------------------------------------------------------------------------


def test_htcondor_get_condor_config_execute() -> None:
    daemon = HTCondorDaemon(kind="execute", labels=["worker"])
    installer = HTCondorInstaller([daemon])
    h = Host("vm1")
    h.extra = {
        "kind": "vagrant",
        "is_central_manager": False,
        "is_submit": False,
        "kiso_preferred_ip": "10.0.0.1",
    }
    env = {"is_public_ip_required": False}

    config_lines, config_files = installer._get_condor_config(
        installer.config, {(0, "execute")}, "10.0.0.2", h, env
    )
    assert any("Execute" in line for line in config_lines)
    assert config_files == {}


def test_htcondor_get_condor_config_submit() -> None:
    daemon = HTCondorDaemon(kind="submit", labels=["sub"])
    installer = HTCondorInstaller([daemon])
    h = Host("vm1")
    h.extra = {
        "kind": "vagrant",
        "is_central_manager": False,
        "is_submit": True,
        "kiso_preferred_ip": "10.0.0.1",
    }
    env = {"is_public_ip_required": False}

    config_lines, config_files = installer._get_condor_config(
        installer.config, {(0, "submit")}, "10.0.0.2", h, env
    )
    assert any("Submit" in line for line in config_lines)


def test_htcondor_get_condor_config_personal() -> None:
    daemon = HTCondorDaemon(kind="personal", labels=["all"])
    installer = HTCondorInstaller([daemon])
    h = Host("vm1")
    h.extra = {
        "kind": "vagrant",
        "is_central_manager": False,
        "is_submit": False,
        "kiso_preferred_ip": "10.0.0.1",
    }
    env = {"is_public_ip_required": False}

    config_lines, _ = installer._get_condor_config(
        installer.config, {(0, "personal")}, None, h, env
    )
    assert any("CentralManager" in line for line in config_lines)


def test_htcondor_get_condor_config_with_config_file(tmp_path: Path) -> None:
    """config_file set on a daemon → config_files dict is populated (line 390)."""
    cfg = tmp_path / "condor.cfg"
    cfg.write_text("DAEMON_LIST = MASTER\n")
    daemon = HTCondorDaemon(kind="execute", labels=["worker"], config_file=str(cfg))
    installer = HTCondorInstaller([daemon])
    h = Host("vm1")
    h.extra = {
        "kind": "vagrant",
        "is_central_manager": False,
        "is_submit": False,
        "kiso_preferred_ip": "10.0.0.1",
    }
    env = {"is_public_ip_required": False}

    config_lines, config_files = installer._get_condor_config(
        installer.config, {(0, "execute")}, "10.0.0.2", h, env
    )
    assert "kiso-execute-config-file" in config_files


def test_htcondor_get_condor_config_tcp_forwarding_host() -> None:
    """TCP_FORWARDING_HOST is added when chameleon-edge + public ip + submit."""
    daemon = HTCondorDaemon(kind="submit", labels=["sub"])
    installer = HTCondorInstaller([daemon])
    h = Host("vm1")
    h.extra = {
        "kind": "chameleon-edge",
        "is_central_manager": False,
        "is_submit": True,
        "kiso_preferred_ip": "203.0.113.1",
    }
    env = {"is_public_ip_required": True}

    config_lines, _ = installer._get_condor_config(
        installer.config, {(0, "submit")}, "10.0.0.2", h, env
    )
    assert any("TCP_FORWARDING_HOST" in line for line in config_lines)


# ---------------------------------------------------------------------------
# _get_condor_daemon_labels
# ---------------------------------------------------------------------------


def test_htcondor_get_condor_daemon_labels_submit() -> None:
    """Submit kind hits the submit branch in _get_condor_daemon_labels."""
    installer = HTCondorInstaller([HTCondorDaemon(kind="submit", labels=["sub"])])
    _, submit_labels, _, _ = installer._get_condor_daemon_labels()
    assert "sub" in submit_labels


def test_htcondor_get_condor_daemon_labels_personal() -> None:
    """Personal kind hits the personal branch in _get_condor_daemon_labels."""
    installer = HTCondorInstaller([HTCondorDaemon(kind="personal", labels=["all"])])
    _, _, _, personal_labels = installer._get_condor_daemon_labels()
    assert "all" in personal_labels


# ---------------------------------------------------------------------------
# _is_public_ip_required
# ---------------------------------------------------------------------------


def test_htcondor_is_public_ip_required_true_multi_execute_sites() -> None:
    """Execute nodes on multiple sites → public IP required."""
    installer = HTCondorInstaller([])
    daemon_to_site = {
        "execute": {"site-a", "site-b"},
        "submit": set(),
        "central-manager": set(),
    }
    assert installer._is_public_ip_required(daemon_to_site) is True


def test_htcondor_is_public_ip_required_true_execute_and_submit_differ() -> None:
    """Execute and submit on different sites → public IP required."""
    installer = HTCondorInstaller([])
    daemon_to_site = {
        "execute": {"site-a"},
        "submit": {"site-b"},
        "central-manager": {"site-a"},
    }
    assert installer._is_public_ip_required(daemon_to_site) is True


def test_htcondor_is_public_ip_required_false_same_site() -> None:
    """All daemons on the same site → public IP not required."""
    installer = HTCondorInstaller([])
    daemon_to_site = {
        "execute": {"site-a"},
        "submit": {"site-a"},
        "central-manager": {"site-a"},
    }
    assert installer._is_public_ip_required(daemon_to_site) is False


# ---------------------------------------------------------------------------
# _map_daemon_to_sites
# ---------------------------------------------------------------------------


def test_htcondor_map_daemon_to_sites_flags_nodes() -> None:
    """_map_daemon_to_sites sets is_central_manager, is_execute on nodes."""
    installer = HTCondorInstaller(
        [
            HTCondorDaemon(kind="central-manager", labels=["cm"]),
            HTCondorDaemon(kind="execute", labels=["worker"]),
        ]
    )
    h_cm = Host("10.0.0.1")
    h_cm.extra = {"kind": "vagrant", "site": "vagrant"}
    h_worker = Host("10.0.0.2")
    h_worker.extra = {"kind": "vagrant", "site": "vagrant"}

    labels = Roles({"cm": [h_cm], "worker": [h_worker]})
    daemon_to_site = installer._map_daemon_to_sites(labels)

    assert h_cm.extra["is_central_manager"] is True
    assert h_worker.extra["is_execute"] is True
    assert "central-manager" in daemon_to_site
    assert "execute" in daemon_to_site


def test_htcondor_map_daemon_to_sites_with_submit() -> None:
    """_map_daemon_to_sites handles submit nodes."""
    installer = HTCondorInstaller([HTCondorDaemon(kind="submit", labels=["sub"])])
    h = Host("10.0.0.1")
    h.extra = {"kind": "vagrant", "site": "vagrant"}
    labels = Roles({"sub": [h]})

    daemon_to_site = installer._map_daemon_to_sites(labels)

    assert h.extra["is_submit"] is True
    assert "submit" in daemon_to_site


def test_htcondor_map_daemon_to_sites_fabric_node() -> None:
    """Nodes with kind=fabric use 'fabric' as the site label."""
    installer = HTCondorInstaller([HTCondorDaemon(kind="execute", labels=["compute"])])
    h = Host("10.0.0.1")
    h.extra = {"kind": "fabric", "site": "fabric-chi"}
    labels = Roles({"compute": [h]})

    daemon_to_site = installer._map_daemon_to_sites(labels)
    assert "fabric" in daemon_to_site["execute"]
