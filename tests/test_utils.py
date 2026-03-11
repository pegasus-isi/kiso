"""Unit tests for kiso.utils utility functions."""

import re
import stat
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from kiso import constants as const
from kiso import utils
from kiso.utils import (
    experiment_state,
    get_deployment,
    get_pool_passwd_file,
    get_random_string,
    get_runner,
    get_software,
    resolve_labels,
    split_labels,
)

# ---------------------------------------------------------------------------
# get_random_string
# ---------------------------------------------------------------------------


def test_default_length() -> None:
    assert len(get_random_string()) == 64


def test_custom_length() -> None:
    assert len(get_random_string(32)) == 32


def test_charset_alphanumeric() -> None:
    result = get_random_string(200)
    assert re.fullmatch(r"[a-zA-Z0-9]+", result) is not None


def test_zero_length_raises() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        get_random_string(0)


def test_negative_length_raises() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        get_random_string(-1)


def test_uniqueness() -> None:
    assert get_random_string() != get_random_string()


# ---------------------------------------------------------------------------
# get_pool_passwd_file
# ---------------------------------------------------------------------------


def test_creates_file_with_correct_perms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = get_pool_passwd_file()
    p = Path(result)
    assert p.exists()
    assert stat.S_IMODE(p.stat().st_mode) == 0o600


def test_existing_valid_perms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    # Create it first
    first = get_pool_passwd_file()
    # Should not raise on second call
    second = get_pool_passwd_file()
    assert first == second


def test_existing_wrong_perms_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    # Create the file with correct perms first, then chmod to wrong perms
    get_pool_passwd_file()
    pool_passwd = Path(tmp_path / ".kiso" / "pool_passwd")
    pool_passwd.chmod(0o644)
    with pytest.raises(ValueError, match="permissions 0600"):
        get_pool_passwd_file()


# ---------------------------------------------------------------------------
# experiment_state
# ---------------------------------------------------------------------------


def test_initial_status_is_started() -> None:
    env: dict = {}
    with experiment_state(env, "step") as state:
        assert state.status == const.STATUS_STARTED


def test_success_sets_ok() -> None:
    env: dict = {}
    with experiment_state(env, "step"):
        pass
    assert env["step"] == const.STATUS_OK


def test_exception_sets_failed() -> None:
    env: dict = {}
    with experiment_state(env, "step"):
        raise RuntimeError("oops")
    assert env["step"] == const.STATUS_FAILED


def test_exception_suppressed_by_default() -> None:
    env: dict = {}
    # on_error_continue=True by default — no exception should escape
    with experiment_state(env, "step"):
        raise RuntimeError("oops")
    # Reached here without propagation
    assert env["step"] == const.STATUS_FAILED


def test_exception_propagates_when_disabled() -> None:
    env: dict = {}
    with (
        pytest.raises(RuntimeError),
        experiment_state(env, "step", on_error_continue=False),
    ):
        raise RuntimeError("oops")
    assert env["step"] == const.STATUS_FAILED


def test_nested_key_path() -> None:
    env: dict = {}
    with experiment_state(env, "experiment", "run", "step"):
        pass
    assert env["experiment"]["run"]["step"] == const.STATUS_OK


def test_skip_if_already_ok() -> None:
    env: dict = {"step": const.STATUS_OK}
    with experiment_state(env, "step") as state:
        assert state.status == const.STATUS_OK


# ---------------------------------------------------------------------------
# get_runner / get_software / get_deployment — entry-point lookup
# ---------------------------------------------------------------------------


def test_get_runner_shell_returns_class() -> None:
    cls = get_runner("shell")
    assert cls is not None
    assert cls.kind == "shell"


def test_get_runner_nonexistent_raises() -> None:
    with pytest.raises(ValueError, match="<kiso.experiment>:does-not-exist>"):
        get_runner("does-not-exist")


def test_get_software_docker_returns_class() -> None:
    cls = get_software("docker")
    assert cls is not None


def test_get_software_nonexistent_raises() -> None:
    with pytest.raises(ValueError, match="<kiso.software>:does-not-exist>"):
        get_software("does-not-exist")


def test_get_deployment_htcondor_returns_class() -> None:
    cls = get_deployment("htcondor")
    assert cls is not None


def test_get_deployment_nonexistent_raises() -> None:
    with pytest.raises(ValueError, match="<kiso.deployment>:does-not-exist>"):
        get_deployment("does-not-exist")


# ---------------------------------------------------------------------------
# resolve_labels
# ---------------------------------------------------------------------------


def test_resolve_labels_empty_names_returns_labels() -> None:
    labels = MagicMock()
    result = resolve_labels(labels, [])
    assert result is labels


def test_resolve_labels_single_name() -> None:
    labels = MagicMock()
    expected = MagicMock()
    labels.__getitem__ = MagicMock(return_value=expected)
    result = resolve_labels(labels, ["compute"])
    assert result is expected
    labels.__getitem__.assert_called_with("compute")


def test_resolve_labels_multiple_names() -> None:
    role_a = MagicMock()
    role_b = MagicMock()
    union_result = MagicMock()
    role_a.__or__ = MagicMock(return_value=union_result)
    labels = MagicMock()
    labels.__getitem__ = MagicMock(side_effect=lambda k: {"a": role_a, "b": role_b}[k])
    result = resolve_labels(labels, ["a", "b"])
    assert result is union_result


# ---------------------------------------------------------------------------
# split_labels
# ---------------------------------------------------------------------------


def test_split_labels_returns_vms_and_containers() -> None:
    edge_hosts = MagicMock()
    vms_result = MagicMock()
    containers_result = MagicMock()

    split = MagicMock()
    split.__sub__ = MagicMock(return_value=vms_result)
    split.__and__ = MagicMock(return_value=containers_result)

    labels = MagicMock()
    labels.__getitem__ = MagicMock(return_value=edge_hosts)

    vms, containers = split_labels(split, labels)
    assert vms is vms_result
    assert containers is containers_result
    labels.__getitem__.assert_called_with("chameleon-edge")


# ---------------------------------------------------------------------------
# get_runner / get_software / get_deployment — ModuleNotFoundError → ValueError
# ---------------------------------------------------------------------------


def test_get_runner_module_not_found_raises_value_error(mocker: MockerFixture) -> None:
    mock_ep = mocker.MagicMock()
    mock_ep.load.side_effect = ModuleNotFoundError("boom")
    mocker.patch.object(utils, "_get_single", return_value=mock_ep)
    with pytest.raises(ValueError, match="No runner found"):
        utils.get_runner("shell")


def test_get_software_module_not_found_raises_value_error(
    mocker: MockerFixture,
) -> None:
    mock_ep = mocker.MagicMock()
    mock_ep.load.side_effect = ModuleNotFoundError("boom")
    mocker.patch.object(utils, "_get_single", return_value=mock_ep)
    with pytest.raises(ValueError, match="No software found"):
        utils.get_software("docker")


def test_get_deployment_module_not_found_raises_value_error(
    mocker: MockerFixture,
) -> None:
    mock_ep = mocker.MagicMock()
    mock_ep.load.side_effect = ModuleNotFoundError("boom")
    mocker.patch.object(utils, "_get_single", return_value=mock_ep)
    with pytest.raises(ValueError, match="No software found"):
        utils.get_deployment("htcondor")


# ---------------------------------------------------------------------------
# _get_single — .select() path (non-dict entry_points)
# ---------------------------------------------------------------------------


def test_get_single_uses_select_when_entry_points_not_dict(
    mocker: MockerFixture,
) -> None:
    # Simulate a non-dict EntryPoints object (Python 3.12+ style)
    mock_ep = mocker.MagicMock()
    mock_ep.name = "shell"

    mock_eps = mocker.MagicMock()
    mock_eps.select = mocker.MagicMock(return_value=[mock_ep])
    # Make isinstance(all_eps, dict) return False by using a non-dict object
    mocker.patch("kiso.utils.entry_points", return_value=mock_eps)

    result = utils._get_single("kiso.experiment", "shell")
    assert result is mock_ep
    mock_eps.select.assert_called_once_with(group="kiso.experiment")
