"""Unit tests for kiso.ollama.installer.OllamaInstaller."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import pytest

from kiso.ollama.configuration import Ollama
from kiso.ollama.installer import OllamaInstaller

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_ollama_init_stores_config() -> None:
    ollama = [Ollama(labels=["compute"], models=["llama3"], environment=None)]
    installer = OllamaInstaller(ollama)
    assert installer.config == ollama


def test_ollama_check_none_config_is_noop() -> None:
    OllamaInstaller(None).check({})  # must not raise


def test_ollama_check_empty_list_is_noop() -> None:
    OllamaInstaller([]).check(defaultdict(set))  # empty list → early return


def test_ollama_check_no_machines_raises() -> None:
    ollama = [Ollama(labels=["undefined"], models=["llama3"], environment=None)]
    installer = OllamaInstaller(ollama)
    with pytest.raises(ValueError, match="No machines found"):
        installer.check(defaultdict(set))


def test_ollama_check_with_machines_passes() -> None:
    ollama = [Ollama(labels=["compute"], models=["llama3"], environment=None)]
    installer = OllamaInstaller(ollama)
    label_to_machines = defaultdict(set)
    label_to_machines["compute"].add("vm1")
    installer.check(label_to_machines)  # must not raise


def test_ollama_check_empty_labels_raises() -> None:
    """Ollama section with empty labels set → no machines found."""
    ollama = [Ollama(labels=[], models=["llama3"], environment=None)]
    installer = OllamaInstaller(ollama)
    with pytest.raises(ValueError, match="No machines found"):
        installer.check(defaultdict(set))


def test_ollama_call_none_config_is_noop() -> None:
    OllamaInstaller(None)({"labels": {}})  # must not raise


def test_ollama_call_with_vms_runs_ansible(mocker: MockerFixture) -> None:
    """OllamaInstaller.__call__ with vms truthy installs via ansible (lines 98-138)."""
    ollama_cfg = [Ollama(labels=["compute"], models=["llama3"], environment=None)]
    installer = OllamaInstaller(ollama_cfg)

    mock_host = mocker.MagicMock()
    mock_host.extra = {}
    mock_vms = [mock_host]
    mock_containers = mocker.MagicMock()
    mock_containers.__bool__ = lambda _: False

    mocker.patch(
        "kiso.ollama.installer.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.ollama.installer.utils.split_labels",
        return_value=(mock_vms, mock_containers),
    )
    mocker.patch("kiso.ollama.installer.utils.run_ansible", return_value=[])
    mocker.patch("kiso.ollama.installer.display._render")
    mocker.patch("kiso.ollama.installer.console.rule")

    installer({"labels": mocker.MagicMock()})
    assert mock_host.extra[installer.HAS_SOFTWARE_KEY] is True


def test_ollama_call_with_vms_and_environment(mocker: MockerFixture) -> None:
    """OllamaInstaller passes environment to ansible extra_vars (line 110)."""
    ollama_cfg = [
        Ollama(labels=["compute"], models=["llama3"], environment={"GPU": "true"})
    ]
    installer = OllamaInstaller(ollama_cfg)

    mock_host = mocker.MagicMock()
    mock_host.extra = {}
    mock_containers = mocker.MagicMock()
    mock_containers.__bool__ = lambda _: False

    mocker.patch(
        "kiso.ollama.installer.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.ollama.installer.utils.split_labels",
        return_value=([mock_host], mock_containers),
    )
    mock_run_ansible = mocker.patch(
        "kiso.ollama.installer.utils.run_ansible", return_value=[]
    )
    mocker.patch("kiso.ollama.installer.display._render")
    mocker.patch("kiso.ollama.installer.console.rule")

    installer({"labels": mocker.MagicMock()})
    # Verify extra_vars includes config key
    call_kwargs = mock_run_ansible.call_args[1]
    assert "extra_vars" in call_kwargs
    assert "config" in call_kwargs["extra_vars"]


def test_ollama_call_with_containers_uses_run_script(mocker: MockerFixture) -> None:
    """OllamaInstaller uses run_script for containers (lines 124-136)."""
    ollama_cfg = [Ollama(labels=["edge"], models=["llama3"], environment=None)]
    installer = OllamaInstaller(ollama_cfg)

    mock_container = mocker.MagicMock()
    mock_container.extra = {}
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False

    mocker.patch(
        "kiso.ollama.installer.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.ollama.installer.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mock_run_script = mocker.patch(
        "kiso.ollama.installer.edge.run_script", return_value=mocker.MagicMock()
    )
    mocker.patch("kiso.ollama.installer.display._render")
    mocker.patch("kiso.ollama.installer.console.rule")

    installer({"labels": mocker.MagicMock()})
    mock_run_script.assert_called_once()
    assert mock_container.extra[installer.HAS_SOFTWARE_KEY] is True
