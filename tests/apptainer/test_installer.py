"""Unit tests for kiso.apptainer.installer.ApptainerInstaller."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import pytest

from kiso.apptainer.configuration import Apptainer
from kiso.apptainer.installer import ApptainerInstaller

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_apptainer_init_stores_config() -> None:
    apptainer = Apptainer(labels=["compute"])
    installer = ApptainerInstaller(apptainer)
    assert installer.config is apptainer


def test_apptainer_check_none_config_is_noop() -> None:
    ApptainerInstaller(None).check({})  # must not raise


def test_apptainer_check_empty_labels_is_noop() -> None:
    installer = ApptainerInstaller(Apptainer(labels=[]))
    installer.check(defaultdict(set))


def test_apptainer_check_no_machines_raises() -> None:
    installer = ApptainerInstaller(Apptainer(labels=["undefined"]))
    with pytest.raises(ValueError, match="No machines found"):
        installer.check(defaultdict(set))


def test_apptainer_check_with_machines_passes() -> None:
    installer = ApptainerInstaller(Apptainer(labels=["compute"]))
    label_to_machines = defaultdict(set)
    label_to_machines["compute"].add("vm1")
    installer.check(label_to_machines)  # must not raise


def test_apptainer_call_none_config_is_noop() -> None:
    ApptainerInstaller(None)({"labels": {}})  # must not raise


def test_apptainer_call_with_vms_runs_ansible(mocker: MockerFixture) -> None:
    """ApptainerInstaller.__call__ installs via ansible when vms are present."""
    installer = ApptainerInstaller(Apptainer(labels=["compute"]))

    mock_host = mocker.MagicMock()
    mock_host.extra = {}
    mock_vms = [mock_host]
    mock_containers = mocker.MagicMock()
    mock_containers.__bool__ = lambda _: False

    mocker.patch(
        "kiso.apptainer.installer.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.apptainer.installer.utils.split_labels",
        return_value=(mock_vms, mock_containers),
    )
    mocker.patch("kiso.apptainer.installer.utils.run_ansible", return_value=[])
    mocker.patch("kiso.apptainer.installer.display._render")
    mocker.patch("kiso.apptainer.installer.console.rule")

    installer({"labels": mocker.MagicMock()})
    assert mock_host.extra[installer.HAS_SOFTWARE_KEY] is True


def test_apptainer_call_with_containers_uses_run_script(mocker: MockerFixture) -> None:
    """ApptainerInstaller uses run_script for containers (lines 113-125)."""
    installer = ApptainerInstaller(Apptainer(labels=["edge"]))

    mock_container = mocker.MagicMock()
    mock_container.extra = {}
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False

    mocker.patch(
        "kiso.apptainer.installer.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.apptainer.installer.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mock_run_script = mocker.patch(
        "kiso.apptainer.installer.edge.run_script", return_value=mocker.MagicMock()
    )
    mocker.patch("kiso.apptainer.installer.display._render")
    mocker.patch("kiso.apptainer.installer.console.rule")

    installer({"labels": mocker.MagicMock()})
    mock_run_script.assert_called_once()
    assert mock_container.extra[installer.HAS_SOFTWARE_KEY] is True
