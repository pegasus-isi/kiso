"""Unit tests for kiso.shell.runner.ShellRunner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from kiso import constants as const
from kiso.configuration import Kiso
from kiso.objects import Location, Script
from kiso.pegasus.configuration import PegasusConfiguration
from kiso.shell.configuration import ShellConfiguration
from kiso.shell.runner import ShellRunner

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


def _make_runner(
    scripts: list[Script] | None = None,
    inputs: list[Location] | None = None,
    outputs: list[Location] | None = None,
    variables: dict[str, Any] | None = None,
    index: int = 0,
) -> tuple[ShellRunner, ShellConfiguration]:
    scripts = scripts or [Script(labels=["compute"], script="echo hello")]
    exp = ShellConfiguration(
        kind="shell",
        name="test-exp",
        scripts=scripts,
        inputs=inputs,
        outputs=outputs,
    )
    runner = ShellRunner(exp, index, variables=variables)
    return runner, exp


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_stores_name_and_index() -> None:
    runner, _ = _make_runner(index=2)
    assert runner.name == "test-exp"
    assert runner.index == 2


def test_init_stores_scripts() -> None:
    scripts = [
        Script(labels=["a"], script="echo a"),
        Script(labels=["b"], script="echo b"),
    ]
    runner, _ = _make_runner(scripts=scripts)
    assert runner.scripts == scripts


def test_init_defaults_empty_inputs_outputs() -> None:
    runner, _ = _make_runner()
    assert runner.inputs == []
    assert runner.outputs == []


def test_init_stores_inputs_and_outputs() -> None:
    inputs = [Location(labels=["a"], src="/local/f", dst="/remote/")]
    outputs = [Location(labels=["a"], src="/remote/out", dst="/local/")]
    runner, _ = _make_runner(inputs=inputs, outputs=outputs)
    assert runner.inputs == inputs
    assert runner.outputs == outputs


def test_init_copies_variables() -> None:
    vars_in = {"x": 1}
    runner, _ = _make_runner(variables=vars_in)
    assert runner.variables == vars_in
    # Deep copy — mutating original should not affect runner
    vars_in["y"] = 2
    assert "y" not in runner.variables


def test_init_none_variables_defaults_to_empty() -> None:
    runner, _ = _make_runner(variables=None)
    assert runner.variables == {}


def test_schema_and_config_type_class_attributes() -> None:
    assert ShellRunner.kind == "shell"
    assert ShellRunner.config_type is ShellConfiguration


# ---------------------------------------------------------------------------
# check / _check_undefined_labels
# ---------------------------------------------------------------------------


def test_check_passes_when_labels_defined() -> None:
    runner, exp = _make_runner()
    kiso_config = _make_kiso(experiments=[exp])
    runner.check(kiso_config, {"compute": {"machine1"}})  # must not raise


def test_check_raises_for_undefined_script_label() -> None:
    runner, exp = _make_runner(scripts=[Script(labels=["missing"], script="echo hi")])
    kiso_config = _make_kiso(experiments=[exp])
    with pytest.raises(ValueError, match="Undefined labels"):
        runner.check(kiso_config, {})


def test_check_raises_for_undefined_output_label() -> None:
    scripts = [Script(labels=["compute"], script="echo ok")]
    outputs = [Location(labels=["missing"], src="/remote/out", dst="/local/")]
    runner, exp = _make_runner(scripts=scripts, outputs=outputs)
    kiso_config = _make_kiso(experiments=[exp])
    with pytest.raises(ValueError, match="Undefined labels"):
        runner.check(kiso_config, {"compute": {"m1"}})


def test_check_skips_non_shell_experiments() -> None:
    """Labels in non-shell experiments are not validated by ShellRunner."""
    runner, exp = _make_runner(scripts=[Script(labels=["compute"], script="echo ok")])
    # Only the current experiment is in the list
    kiso_config = _make_kiso(experiments=[exp])
    runner.check(kiso_config, {"compute": {"m1"}})  # no raise


def test_check_undefined_labels_continue_on_non_shell_kind() -> None:
    """Non-shell experiments trigger the continue branch (line 116 in runner.py)."""
    shell_script = Script(labels=["compute"], script="echo ok")
    shell_exp = ShellConfiguration(kind="shell", name="shell", scripts=[shell_script])
    pegasus_exp = PegasusConfiguration(
        kind="pegasus", name="wf", main="wf.py", submit_node_labels=["compute"]
    )
    runner, _ = _make_runner(scripts=[shell_script])
    # pegasus_exp is first → kind != "shell" → triggers continue branch
    kiso_config = _make_kiso(experiments=[pegasus_exp, shell_exp])
    runner._check_undefined_labels(kiso_config, {"compute": {"m1"}})  # no raise


# ---------------------------------------------------------------------------
# _copy_inputs / _run_scripts / _fetch_outputs — early-exit on empty lists
# ---------------------------------------------------------------------------


def test_copy_inputs_empty_returns_immediately() -> None:
    runner, _ = _make_runner(inputs=[])
    runner.env = {}
    runner.labels = {}
    runner._copy_inputs()  # must not raise or call infrastructure


def test_run_scripts_empty_returns_immediately() -> None:
    runner, _ = _make_runner()
    runner.scripts = []  # override: empty list triggers early return
    runner.env = {}
    runner.labels = {}
    runner._run_scripts()  # must not raise


def test_fetch_outputs_empty_returns_immediately() -> None:
    runner, _ = _make_runner(outputs=[])
    runner.env = {}
    runner.labels = {}
    runner._fetch_outputs()  # must not raise


# ---------------------------------------------------------------------------
# __call__ — orchestration
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _copy_inputs / _run_scripts / _fetch_outputs — non-empty lists
# ---------------------------------------------------------------------------


def test_copy_inputs_non_empty_calls_copy_input(mocker: MockerFixture) -> None:
    inputs = [Location(labels=["compute"], src="/some/file", dst="/remote/")]
    runner, _ = _make_runner(inputs=inputs)
    runner.env = {}
    runner.labels = {}
    mock_copy = mocker.patch.object(runner, "_copy_input", return_value=[])
    runner._copy_inputs()
    mock_copy.assert_called_once_with(0, inputs[0])
    assert "copy-input" in runner.env


def test_run_scripts_non_empty_calls_run_script(mocker: MockerFixture) -> None:
    script = Script(labels=["compute"], script="echo hi")
    runner, _ = _make_runner(scripts=[script])
    runner.env = {}
    runner.labels = {}
    mock_run = mocker.patch.object(runner, "_run_script", return_value=[])
    runner._run_scripts()
    mock_run.assert_called_once_with(0, script)
    assert "run-script" in runner.env


def test_fetch_outputs_non_empty_calls_fetch_output(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    outputs = [Location(labels=["compute"], src="/remote/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.env = {}
    runner.labels = {}
    runner.remote_wd = "/remote"
    runner.index = 0
    mock_fetch = mocker.patch.object(runner, "_fetch_output", return_value=[])
    runner._fetch_outputs()
    mock_fetch.assert_called_once_with(0, outputs[0])
    assert "fetch-output" in runner.env


# ---------------------------------------------------------------------------
# _copy_input — internal paths
# ---------------------------------------------------------------------------


def _mock_roles(
    mocker: MockerFixture, vms_truthy: bool = False, containers_truthy: bool = False
) -> tuple[Any, Any]:
    """Patch resolve_labels and split_labels in shell runner."""
    mock_roles = mocker.MagicMock()
    mocker.patch("kiso.shell.runner.utils.resolve_labels", return_value=mock_roles)
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: vms_truthy
    mock_containers = mocker.MagicMock()
    mock_containers.__bool__ = lambda _: containers_truthy
    mocker.patch(
        "kiso.shell.runner.utils.split_labels",
        return_value=(mock_vms, mock_containers),
    )
    return mock_vms, mock_containers


def test_copy_input_already_ok_returns_empty(mocker: MockerFixture) -> None:
    inputs = [Location(labels=["compute"], src="/nonexistent", dst="/remote/")]
    runner, _ = _make_runner(inputs=inputs)
    runner.labels = mocker.MagicMock()
    _mock_roles(mocker)
    runner.env = {"copy-input": {0: const.STATUS_OK}}
    result = runner._copy_input(0, inputs[0])
    assert result == []


def test_copy_input_src_not_exists_returns_empty(mocker: MockerFixture) -> None:
    inputs = [Location(labels=["compute"], src="/nonexistent/path", dst="/remote/")]
    runner, _ = _make_runner(inputs=inputs)
    runner.labels = mocker.MagicMock()
    _mock_roles(mocker)
    runner.env = {}
    result = runner._copy_input(0, inputs[0])
    assert result == []


def test_copy_input_with_containers_uses_edge(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    src = tmp_path / "data.txt"
    src.write_text("hello")
    inputs = [Location(labels=["compute"], src=str(src), dst=str(tmp_path))]
    runner, _ = _make_runner(inputs=inputs)
    runner.labels = mocker.MagicMock()

    mock_container = mocker.MagicMock()
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False
    mocker.patch(
        "kiso.shell.runner.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.shell.runner.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mock_upload = mocker.patch(
        "kiso.shell.runner.edge.upload", return_value=mocker.MagicMock()
    )

    runner.env = {}
    results = runner._copy_input(0, inputs[0])
    assert len(results) == 1
    mock_upload.assert_called_once()


def test_copy_input_with_vms_uses_actions(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    src = tmp_path / "data.txt"
    src.write_text("hello")
    inputs = [Location(labels=["compute"], src=str(src), dst=str(tmp_path))]
    runner, _ = _make_runner(inputs=inputs)
    runner.labels = mocker.MagicMock()
    mock_vms, _ = _mock_roles(mocker, vms_truthy=True)

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.shell.runner.utils.actions", return_value=mock_cm)

    runner.env = {}
    results = runner._copy_input(0, inputs[0])
    assert len(results) == 1
    mock_p.copy.assert_called_once()


# ---------------------------------------------------------------------------
# _run_script — internal paths
# ---------------------------------------------------------------------------


def test_run_script_already_ok_returns_empty(mocker: MockerFixture) -> None:
    script = Script(labels=["compute"], script="echo hello")
    runner, _ = _make_runner(scripts=[script])
    runner.labels = mocker.MagicMock()
    _mock_roles(mocker)
    runner.env = {"run-script": {0: const.STATUS_OK}}
    result = runner._run_script(0, script)
    assert result == []


def test_run_script_with_containers_uses_run_script(mocker: MockerFixture) -> None:
    script = Script(labels=["compute"], script="echo hello")
    runner, _ = _make_runner(scripts=[script])
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"

    mock_container = mocker.MagicMock()
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False
    mocker.patch(
        "kiso.shell.runner.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.shell.runner.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mock_run_script = mocker.patch(
        "kiso.shell.runner.edge.run_script", return_value=mocker.MagicMock()
    )

    runner.env = {}
    results = runner._run_script(0, script)
    assert len(results) == 1
    mock_run_script.assert_called_once()


def test_run_script_with_vms_uses_actions(mocker: MockerFixture) -> None:
    script = Script(labels=["compute"], script="echo hello")
    runner, _ = _make_runner(scripts=[script])
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"
    _mock_roles(mocker, vms_truthy=True)

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.shell.runner.utils.actions", return_value=mock_cm)

    runner.env = {}
    results = runner._run_script(0, script)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# _fetch_output — internal paths
# ---------------------------------------------------------------------------


def test_fetch_output_already_ok_returns_empty(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    outputs = [Location(labels=["compute"], src="/remote/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"
    _mock_roles(mocker)
    runner.env = {"fetch-output": {0: const.STATUS_OK}}
    result = runner._fetch_output(0, outputs[0])
    assert result == []


def test_fetch_output_relative_src_prepends_remote_wd(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    outputs = [Location(labels=["compute"], src="relative/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote/wd"
    _mock_roles(mocker)
    runner.env = {}
    result = runner._fetch_output(0, outputs[0])
    assert result == []


def test_fetch_output_creates_missing_dst_dir(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    new_dst = tmp_path / "new_results_dir"
    outputs = [Location(labels=["compute"], src="/remote/out", dst=str(new_dst))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"
    _mock_roles(mocker)
    runner.env = {}
    runner._fetch_output(0, outputs[0])
    assert new_dst.exists()


def test_fetch_output_with_vms_uses_actions(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    outputs = [Location(labels=["compute"], src="/remote/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"
    _mock_roles(mocker, vms_truthy=True)

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.shell.runner.utils.actions", return_value=mock_cm)

    runner.env = {}
    results = runner._fetch_output(0, outputs[0])
    assert len(results) == 1


def test_fetch_output_with_containers_uses_edge(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    outputs = [Location(labels=["compute"], src="/remote/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"

    mock_container = mocker.MagicMock()
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False
    mocker.patch(
        "kiso.shell.runner.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.shell.runner.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mock_download = mocker.patch(
        "kiso.shell.runner.edge.download", return_value=mocker.MagicMock()
    )

    runner.env = {}
    results = runner._fetch_output(0, outputs[0])
    assert len(results) == 1
    mock_download.assert_called_once()


def test_call_sets_attributes_and_calls_steps(mocker: MockerFixture) -> None:
    runner, _ = _make_runner()
    cp = mocker.patch.object(runner, "_copy_inputs")
    run = mocker.patch.object(runner, "_run_scripts")
    fetch = mocker.patch.object(runner, "_fetch_outputs")

    runner("/wd", "/remote", "/results", {}, {})

    assert runner.wd == "/wd"
    assert runner.remote_wd == "/remote"
    assert runner.resultdir == "/results"
    cp.assert_called_once()
    run.assert_called_once()
    fetch.assert_called_once()
