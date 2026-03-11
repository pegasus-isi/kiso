"""Unit tests for kiso.pegasus.runner.PegasusRunner."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from enoslib.objects import Host

from kiso import constants as const
from kiso.configuration import Deployment, Kiso
from kiso.errors import KisoTimeoutError, KisoValueError
from kiso.htcondor.configuration import HTCondorDaemon
from kiso.objects import Location, Script
from kiso.pegasus.configuration import PegasusConfiguration
from kiso.pegasus.runner import PegasusRunner
from kiso.shell.configuration import ShellConfiguration

if TYPE_CHECKING:
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


def _make_exp(**kwargs: object) -> PegasusConfiguration:
    defaults: dict[str, Any] = {
        "kind": "pegasus",
        "name": "wf",
        "main": "wf.py",
        "submit_node_labels": ["submit"],
    }
    defaults.update(kwargs)
    return PegasusConfiguration(**defaults)


def _make_runner(**kwargs: object) -> tuple[PegasusRunner, PegasusConfiguration]:
    exp = _make_exp(**kwargs)
    return PegasusRunner(exp, 0), exp


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_stores_basic_fields() -> None:
    runner, exp = _make_runner()
    assert runner.name == "wf"
    assert runner.index == 0
    assert runner.main == "wf.py"
    assert runner.submit_node_labels == ["submit"]


def test_init_defaults_empty_collections() -> None:
    runner, _ = _make_runner()
    assert runner.setup == []
    assert runner.inputs == []
    assert runner.outputs == []
    assert runner.post_scripts == []


def test_init_merges_variables() -> None:
    runner, _ = _make_runner(variables={"x": 1})
    assert runner.variables["x"] == 1


def test_init_copies_variables() -> None:
    global_vars = {"g": 10}
    runner = PegasusRunner(_make_exp(), 0, variables=global_vars)
    global_vars["h"] = 20
    assert "h" not in runner.variables


def test_init_count_defaults_to_one() -> None:
    runner, _ = _make_runner()
    assert runner.count == 1


def test_schema_and_config_type() -> None:
    assert PegasusRunner.kind == "pegasus"
    assert PegasusRunner.config_type is PegasusConfiguration


# ---------------------------------------------------------------------------
# check — no HTCondor, no inputs, no undefined labels
# ---------------------------------------------------------------------------


def test_check_passes_clean_config() -> None:
    runner, exp = _make_runner()
    kiso_config = _make_kiso(experiments=[exp])
    runner.check(kiso_config, {"submit": {"m1"}})  # must not raise


def test_check_skips_htcondor_check_when_no_deployment() -> None:
    runner, exp = _make_runner()
    kiso_config = _make_kiso(experiments=[exp], deployment=None)
    runner.check(kiso_config, {"submit": {"m1"}})  # no raise; no htcondor check


# ---------------------------------------------------------------------------
# _check_undefined_labels
# ---------------------------------------------------------------------------


def test_check_undefined_labels_passes_when_all_defined() -> None:
    setup = [Script(labels=["submit"], script="echo hi")]
    runner, exp = _make_runner(setup=setup)
    kiso_config = _make_kiso(experiments=[exp])
    runner._check_undefined_labels(kiso_config, {"submit": {"m1"}})


def test_check_undefined_labels_raises_for_missing_setup_label() -> None:
    setup = [Script(labels=["missing"], script="echo hi")]
    runner, exp = _make_runner(setup=setup)
    kiso_config = _make_kiso(experiments=[exp])
    with pytest.raises(ValueError, match="Undefined labels"):
        runner._check_undefined_labels(kiso_config, {})


def test_check_undefined_labels_raises_for_missing_input_label() -> None:
    inputs = [Location(labels=["missing"], src="/f", dst="/d")]
    runner, exp = _make_runner(inputs=inputs)
    kiso_config = _make_kiso(experiments=[exp])
    with pytest.raises(ValueError, match="Undefined labels"):
        runner._check_undefined_labels(kiso_config, {})


def test_check_undefined_labels_raises_for_missing_output_label() -> None:
    outputs = [Location(labels=["missing"], src="/r", dst="/l")]
    runner, exp = _make_runner(outputs=outputs)
    kiso_config = _make_kiso(experiments=[exp])
    with pytest.raises(ValueError, match="Undefined labels"):
        runner._check_undefined_labels(kiso_config, {})


def test_check_undefined_labels_raises_for_missing_post_script_label() -> None:
    post = [Script(labels=["missing"], script="echo hi")]
    runner, exp = _make_runner(post_scripts=post)
    kiso_config = _make_kiso(experiments=[exp])
    with pytest.raises(ValueError, match="Undefined labels"):
        runner._check_undefined_labels(kiso_config, {})


def test_check_undefined_labels_skips_non_pegasus_experiments() -> None:
    shell_exp = ShellConfiguration(
        kind="shell", name="sh", scripts=[Script(labels=["other"], script="echo ok")]
    )
    runner, exp = _make_runner()
    kiso_config = _make_kiso(experiments=[exp, shell_exp])
    # "other" not in label_to_machines, but only pegasus experiments are checked here
    runner._check_undefined_labels(kiso_config, {"submit": {"m1"}})  # no raise


# ---------------------------------------------------------------------------
# _check_missing_input_files
# ---------------------------------------------------------------------------


def test_check_missing_input_files_skips_non_pegasus_experiment() -> None:
    """Non-pegasus experiments use the continue branch in _check_missing_input_files."""
    shell_exp = ShellConfiguration(kind="shell", name="sh", scripts=[])
    runner, exp = _make_runner()
    kiso_config = _make_kiso(experiments=[shell_exp, exp])
    runner._check_missing_input_files(
        kiso_config
    )  # shell_exp kind != "pegasus" → continue


def test_check_missing_input_files_no_inputs() -> None:
    runner, exp = _make_runner()
    kiso_config = _make_kiso(experiments=[exp])
    runner._check_missing_input_files(kiso_config)  # no raise


def test_check_missing_input_files_existing_file_passes(tmp_path: Path) -> None:
    src = tmp_path / "data.txt"
    src.write_text("hello")
    inputs = [Location(labels=["submit"], src=str(src), dst="/remote/")]
    runner, exp = _make_runner(inputs=inputs)
    kiso_config = _make_kiso(experiments=[exp])
    runner._check_missing_input_files(kiso_config)  # no raise


def test_check_missing_input_files_missing_file_raises(tmp_path: Path) -> None:
    inputs = [
        Location(
            labels=["submit"], src=str(tmp_path / "nonexistent.txt"), dst="/remote/"
        )
    ]
    runner, exp = _make_runner(inputs=inputs)
    kiso_config = _make_kiso(experiments=[exp])
    with pytest.raises(ValueError, match="Input file"):
        runner._check_missing_input_files(kiso_config)


# ---------------------------------------------------------------------------
# __call__ — orchestration
# ---------------------------------------------------------------------------


def test_call_sets_attributes_and_calls_steps(mocker: MockerFixture) -> None:
    runner, _ = _make_runner()
    cp = mocker.patch.object(runner, "_copy_inputs")
    setup = mocker.patch.object(runner, "_run_setup_scripts")
    exp = mocker.patch.object(runner, "_run_experiment")
    post = mocker.patch.object(runner, "_run_post_scripts")
    fetch = mocker.patch.object(runner, "_fetch_outputs")

    mock_labels = mocker.MagicMock()
    mocker.patch("kiso.pegasus.runner.utils.resolve_labels", return_value=mock_labels)
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False
    mock_containers = mocker.MagicMock()
    mock_containers.__bool__ = lambda _: False
    mocker.patch(
        "kiso.pegasus.runner.utils.split_labels",
        return_value=(mock_vms, mock_containers),
    )

    runner("/wd", "/remote", "/results", mocker.MagicMock(), {})

    assert runner.wd == "/wd"
    assert runner.remote_wd == "/remote"
    assert runner.resultdir == "/results"
    cp.assert_called_once()
    setup.assert_called_once()
    exp.assert_called_once_with(0)
    post.assert_called_once()
    fetch.assert_called_once()


# ---------------------------------------------------------------------------
# _run_setup_scripts — empty early return
# ---------------------------------------------------------------------------


def test_run_setup_scripts_empty_returns_immediately() -> None:
    runner, _ = _make_runner()
    runner.setup = []
    runner.env = {}
    runner.labels = {}
    runner._run_setup_scripts()  # must not raise


# ---------------------------------------------------------------------------
# _copy_inputs — non-empty calls _copy_input
# ---------------------------------------------------------------------------


def test_copy_inputs_empty_returns_immediately() -> None:
    runner, _ = _make_runner(inputs=[])
    runner.env = {}
    runner.labels = {}
    runner._copy_inputs()  # early return when inputs empty


def test_copy_inputs_non_empty_calls_copy_input(mocker: MockerFixture) -> None:
    inputs = [Location(labels=["submit"], src="/some/file", dst="/remote/")]
    runner, _ = _make_runner(inputs=inputs)
    runner.env = {}
    runner.labels = {}
    mock_copy = mocker.patch.object(runner, "_copy_input", return_value=[])
    runner._copy_inputs()
    mock_copy.assert_called_once_with(0, inputs[0])
    assert "copy-input" in runner.env


# ---------------------------------------------------------------------------
# _check_submit_labels_are_submit_nodes
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# check — with htcondor deployment triggers submit-label check
# ---------------------------------------------------------------------------


def test_check_with_htcondor_calls_submit_label_check(mocker: MockerFixture) -> None:

    deployment = Deployment(htcondor=[HTCondorDaemon(kind="submit", labels=["submit"])])
    runner, exp = _make_runner()
    kiso_config = _make_kiso(experiments=[exp], deployment=deployment)
    mock_check = mocker.patch.object(runner, "_check_submit_labels_are_submit_nodes")
    runner.check(kiso_config, {"submit": {"m1"}})
    mock_check.assert_called_once()


# ---------------------------------------------------------------------------
# _check_submit_labels_are_submit_nodes — edge cases
# ---------------------------------------------------------------------------


def test_check_submit_labels_skips_non_pegasus_experiment() -> None:
    """Non-pegasus experiments trigger the continue branch (line 160)."""
    machine = object()
    deployment = Deployment(htcondor=[HTCondorDaemon(kind="submit", labels=["sub"])])
    shell_exp = ShellConfiguration(kind="shell", name="sh", scripts=[])
    kiso_config = _make_kiso(
        deployment=deployment,
        experiments=[shell_exp, _make_exp(submit_node_labels=["sub"])],
    )
    label_to_machines = {"sub": {machine}}
    runner, _ = _make_runner(submit_node_labels=["sub"])
    # shell_exp.kind != "pegasus" → continue (line 160)
    runner._check_submit_labels_are_submit_nodes(kiso_config, label_to_machines)


def test_check_submit_labels_skips_non_submit_daemon() -> None:
    """Central-manager daemon kind is skipped (continue branch, line 152)."""
    machine = object()
    deployment = Deployment(
        htcondor=[
            HTCondorDaemon(kind="central-manager", labels=["cm"]),
            HTCondorDaemon(kind="submit", labels=["sub"]),
        ]
    )
    kiso_config = _make_kiso(
        deployment=deployment,
        experiments=[_make_exp(submit_node_labels=["sub"])],
    )
    label_to_machines = {"cm": {machine}, "sub": {machine}}
    runner, _ = _make_runner(submit_node_labels=["sub"])
    runner._check_submit_labels_are_submit_nodes(
        kiso_config, label_to_machines
    )  # no raise


def test_check_submit_labels_raises_when_no_intersection() -> None:
    """Experiment submit labels don't intersect submit nodes → raises.

    Source-level bug: experiment['name'] raises TypeError instead of ValueError.
    """
    m1, m2 = object(), object()
    deployment = Deployment(htcondor=[HTCondorDaemon(kind="submit", labels=["sub"])])
    kiso_config = _make_kiso(
        deployment=deployment,
        experiments=[_make_exp(submit_node_labels=["exp-node"])],
    )
    label_to_machines = {"sub": {m1}, "exp-node": {m2}}
    runner, _ = _make_runner(submit_node_labels=["exp-node"])
    with pytest.raises((ValueError, TypeError)):
        runner._check_submit_labels_are_submit_nodes(kiso_config, label_to_machines)


# ---------------------------------------------------------------------------
# _run_setup_scripts — non-empty calls _run_setup_script
# ---------------------------------------------------------------------------


def test_run_setup_scripts_non_empty_calls_run_setup_script(
    mocker: MockerFixture,
) -> None:
    setup = [Script(labels=["submit"], script="echo hi")]
    runner, _ = _make_runner(setup=setup)
    runner.env = {}
    runner.labels = {}
    mock_run = mocker.patch.object(runner, "_run_setup_script", return_value=[])
    runner._run_setup_scripts()
    mock_run.assert_called_once_with(0, setup[0])
    assert "run-setup-script" in runner.env


# ---------------------------------------------------------------------------
# _copy_input — internal paths
# ---------------------------------------------------------------------------


def _mock_pegasus_roles(
    mocker: MockerFixture, vms_truthy: bool = False
) -> tuple[Any, Any]:
    """Patch resolve_labels and split_labels in pegasus runner."""
    mock_roles = mocker.MagicMock()
    mocker.patch("kiso.pegasus.runner.utils.resolve_labels", return_value=mock_roles)
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: vms_truthy
    mock_containers = mocker.MagicMock()
    mock_containers.__bool__ = lambda _: False
    mocker.patch(
        "kiso.pegasus.runner.utils.split_labels",
        return_value=(mock_vms, mock_containers),
    )
    return mock_vms, mock_containers


def test_pegasus_copy_input_already_ok_returns_empty(mocker: MockerFixture) -> None:
    inputs = [Location(labels=["submit"], src="/nonexistent", dst="/remote/")]
    runner, _ = _make_runner(inputs=inputs)
    runner.labels = mocker.MagicMock()
    _mock_pegasus_roles(mocker)
    runner.env = {"copy-input": {0: const.STATUS_OK}}
    result = runner._copy_input(0, inputs[0])
    assert result == []


def test_pegasus_copy_input_src_not_exists(mocker: MockerFixture) -> None:
    inputs = [Location(labels=["submit"], src="/nonexistent/path", dst="/remote/")]
    runner, _ = _make_runner(inputs=inputs)
    runner.labels = mocker.MagicMock()
    _mock_pegasus_roles(mocker)
    runner.env = {}
    result = runner._copy_input(0, inputs[0])
    assert result == []


# ---------------------------------------------------------------------------
# _copy_input — container path
# ---------------------------------------------------------------------------


def test_pegasus_copy_input_with_containers_uses_edge(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """_copy_input calls edge.upload when containers are truthy (lines 379-383)."""
    src = tmp_path / "data.txt"
    src.write_text("hello")
    inputs = [Location(labels=["submit"], src=str(src), dst=str(tmp_path))]
    runner, _ = _make_runner(inputs=inputs)
    runner.labels = mocker.MagicMock()

    mock_container = mocker.MagicMock()
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False
    mocker.patch(
        "kiso.pegasus.runner.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.pegasus.runner.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mock_upload = mocker.patch(
        "kiso.pegasus.runner.edge.upload", return_value=mocker.MagicMock()
    )

    runner.env = {}
    results = runner._copy_input(0, inputs[0])
    assert len(results) == 1
    mock_upload.assert_called_once()


# ---------------------------------------------------------------------------
# _run_post_scripts — empty early return and non-empty calls _run_post_script
# ---------------------------------------------------------------------------


def test_run_post_scripts_empty_returns_immediately() -> None:
    runner, _ = _make_runner()
    runner.post_scripts = []
    runner.env = {}
    runner.labels = {}
    runner._run_post_scripts()  # must not raise


def test_run_post_scripts_non_empty_calls_run_post_script(
    mocker: MockerFixture,
) -> None:
    post = [Script(labels=["submit"], script="echo hi")]
    runner, _ = _make_runner(post_scripts=post)
    runner.env = {}
    runner.labels = {}
    mock_run = mocker.patch.object(runner, "_run_post_script", return_value=[])
    mocker.patch("kiso.pegasus.runner.display.post_scripts")
    runner._run_post_scripts()
    mock_run.assert_called_once_with(0, post[0])


# ---------------------------------------------------------------------------
# _run_post_script — already-OK fast path and container path
# ---------------------------------------------------------------------------


def test_run_post_script_already_ok_returns_empty(mocker: MockerFixture) -> None:
    post_script = Script(labels=["submit"], script="echo hi")
    runner, _ = _make_runner(post_scripts=[post_script])
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"
    _mock_pegasus_roles(mocker)
    runner.env = {"run-post-script": {0: const.STATUS_OK}}
    result = runner._run_post_script(0, post_script)
    assert result == []


def test_run_post_script_with_containers_uses_run_script(mocker: MockerFixture) -> None:
    """_run_post_script calls egde.run_script for containers (lines 553-562)."""
    post_script = Script(labels=["submit"], script="echo hi")
    runner, _ = _make_runner(post_scripts=[post_script])
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"

    mock_container = mocker.MagicMock()
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False
    mocker.patch(
        "kiso.pegasus.runner.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.pegasus.runner.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mock_run_script = mocker.patch(
        "kiso.pegasus.runner.edge.run_script", return_value=mocker.MagicMock()
    )

    runner.env = {}
    results = runner._run_post_script(0, post_script)
    assert len(results) == 1
    mock_run_script.assert_called_once()


# ---------------------------------------------------------------------------
# _fetch_outputs — empty early return and non-empty calls _fetch_output
# ---------------------------------------------------------------------------


def test_pegasus_fetch_outputs_empty_returns_immediately() -> None:
    runner, _ = _make_runner(outputs=[])
    runner.env = {}
    runner.labels = {}
    runner._fetch_outputs()  # must not raise


def test_pegasus_fetch_outputs_non_empty_calls_fetch_output(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    outputs = [Location(labels=["submit"], src="/remote/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.env = {}
    runner.labels = {}
    runner.remote_wd = "/remote"
    mock_fetch = mocker.patch.object(runner, "_fetch_output", return_value=[])
    mocker.patch("kiso.pegasus.runner.display.outputs")
    runner._fetch_outputs()
    mock_fetch.assert_called_once_with(0, outputs[0])


# ---------------------------------------------------------------------------
# _fetch_output — already-OK, relative src, creates dst, container path
# ---------------------------------------------------------------------------


def test_pegasus_fetch_output_already_ok_returns_empty(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    outputs = [Location(labels=["submit"], src="/remote/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"
    _mock_pegasus_roles(mocker)
    runner.env = {"fetch-output": {0: const.STATUS_OK}}
    result = runner._fetch_output(0, outputs[0])
    assert result == []


def test_pegasus_fetch_output_relative_src_prepends_remote_wd(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    outputs = [Location(labels=["submit"], src="relative/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote/wd"
    _mock_pegasus_roles(mocker)
    runner.env = {}
    result = runner._fetch_output(0, outputs[0])
    assert result == []


def test_pegasus_fetch_output_creates_missing_dst_dir(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    new_dst = tmp_path / "new_results_dir"
    outputs = [Location(labels=["submit"], src="/remote/out", dst=str(new_dst))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"
    _mock_pegasus_roles(mocker)
    runner.env = {}
    runner._fetch_output(0, outputs[0])
    assert new_dst.exists()


def test_pegasus_fetch_output_with_vms_uses_actions(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    outputs = [Location(labels=["submit"], src="/remote/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"
    _mock_pegasus_roles(mocker, vms_truthy=True)

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)

    runner.env = {}
    results = runner._fetch_output(0, outputs[0])
    assert len(results) == 1


def test_pegasus_fetch_output_with_containers_uses_edge(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """_fetch_output calls edge.download for containers (lines 636-638)."""
    outputs = [Location(labels=["submit"], src="/remote/out", dst=str(tmp_path))]
    runner, _ = _make_runner(outputs=outputs)
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"

    mock_container = mocker.MagicMock()
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False
    mocker.patch(
        "kiso.pegasus.runner.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.pegasus.runner.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mock_download = mocker.patch(
        "kiso.pegasus.runner.edge.download", return_value=mocker.MagicMock()
    )

    runner.env = {}
    results = runner._fetch_output(0, outputs[0])
    assert len(results) == 1
    mock_download.assert_called_once()


# ---------------------------------------------------------------------------
# _run_experiment — orchestration with mocked sub-methods
# ---------------------------------------------------------------------------


def test_run_experiment_calls_generate_wait_fetch(mocker: MockerFixture) -> None:
    """_run_experiment calls the three workflow helper methods in sequence."""
    runner, _ = _make_runner()
    runner.env = {}
    runner.count = 2

    mock_gen = mocker.patch.object(runner, "_generate_workflow", return_value=None)
    mock_wait = mocker.patch.object(runner, "_wait_for_workflow")
    mock_fetch = mocker.patch.object(runner, "_fetch_submit_dir")
    mocker.patch("kiso.pegasus.runner.display.generate_workflow")
    mocker.patch("kiso.pegasus.runner.console.rule")

    runner._run_experiment(0)

    mock_gen.assert_called_once_with(0)
    mock_wait.assert_called_once_with(0)
    mock_fetch.assert_called_once_with(0)


def test_run_experiment_handles_kiso_value_error(mocker: MockerFixture) -> None:
    """_run_experiment catches KisoValueError and displays result (lines 661-665)."""
    runner, _ = _make_runner()
    runner.env = {}
    runner.count = 1

    mock_result = mocker.MagicMock()
    mocker.patch.object(
        runner,
        "_generate_workflow",
        side_effect=KisoValueError("fail", mock_result),
    )
    mock_fetch = mocker.patch.object(runner, "_fetch_submit_dir")
    mock_display = mocker.patch("kiso.pegasus.runner.display.generate_workflow")
    mocker.patch("kiso.pegasus.runner.console.rule")

    runner._run_experiment(0)  # must not raise

    mock_fetch.assert_called_once_with(0)
    mock_display.assert_called()


# ---------------------------------------------------------------------------
# _run_setup_script — vms path
# ---------------------------------------------------------------------------


def test_run_setup_script_containers_uses_run_script(mocker: MockerFixture) -> None:
    """_run_setup_script calls edge.run_script for containers (lines 464-473)."""
    setup_script = Script(labels=["submit"], script="echo hi")
    runner, _ = _make_runner(setup=[setup_script])
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"

    mock_container = mocker.MagicMock()
    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: False
    mocker.patch(
        "kiso.pegasus.runner.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.pegasus.runner.utils.split_labels",
        return_value=(mock_vms, [mock_container]),
    )
    mock_run_script = mocker.patch(
        "kiso.pegasus.runner.edge.run_script", return_value=mocker.MagicMock()
    )

    runner.env = {}
    results = runner._run_setup_script(0, setup_script)
    assert len(results) == 1
    mock_run_script.assert_called_once()


def test_run_setup_script_already_ok_returns_empty(mocker: MockerFixture) -> None:
    """_run_setup_script returns early when STATUS_OK (line 440)."""
    setup_script = Script(labels=["submit"], script="echo hi")
    runner, _ = _make_runner(setup=[setup_script])
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"
    _mock_pegasus_roles(mocker)
    runner.env = {"run-setup-script": {0: const.STATUS_OK}}
    result = runner._run_setup_script(0, setup_script)
    assert result == []


def test_run_setup_script_with_vms_uses_actions(mocker: MockerFixture) -> None:
    """_run_setup_script calls utils.actions when vms are truthy (lines 448-463)."""
    setup_script = Script(labels=["submit"], script="echo hi")
    runner, _ = _make_runner(
        setup=setup_script if isinstance(setup_script, list) else [setup_script]
    )
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"

    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: True
    mock_containers = mocker.MagicMock()
    mock_containers.__bool__ = lambda _: False
    mocker.patch(
        "kiso.pegasus.runner.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.pegasus.runner.utils.split_labels",
        return_value=(mock_vms, mock_containers),
    )

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)

    runner.env = {}
    results = runner._run_setup_script(0, setup_script)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# _run_post_script — vms path
# ---------------------------------------------------------------------------


def test_run_post_script_with_vms_uses_actions(mocker: MockerFixture) -> None:
    """_run_post_script calls utils.actions when vms are truthy (lines 537-552)."""
    post_script = Script(labels=["submit"], script="echo hi")
    runner, _ = _make_runner(post_scripts=[post_script])
    runner.labels = mocker.MagicMock()
    runner.remote_wd = "/remote"

    mock_vms = mocker.MagicMock()
    mock_vms.__bool__ = lambda _: True
    mock_containers = mocker.MagicMock()
    mock_containers.__bool__ = lambda _: False
    mocker.patch(
        "kiso.pegasus.runner.utils.resolve_labels", return_value=mocker.MagicMock()
    )
    mocker.patch(
        "kiso.pegasus.runner.utils.split_labels",
        return_value=(mock_vms, mock_containers),
    )

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)

    runner.env = {}
    results = runner._run_post_script(0, post_script)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# _copy_input — vms path
# ---------------------------------------------------------------------------


def test_pegasus_copy_input_with_vms_uses_actions(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """_copy_input calls utils.actions when vms are truthy (lines 366-378)."""
    src = tmp_path / "data.txt"
    src.write_text("hello")
    inputs = [Location(labels=["submit"], src=str(src), dst=str(tmp_path))]
    runner, _ = _make_runner(inputs=inputs)
    runner.labels = mocker.MagicMock()
    _mock_pegasus_roles(mocker, vms_truthy=True)

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)

    runner.env = {}
    results = runner._copy_input(0, inputs[0])
    assert len(results) == 1


# ---------------------------------------------------------------------------
# _get_submit_dir — various paths
# ---------------------------------------------------------------------------


def test_get_submit_dir_failure_raises_value_error(mocker: MockerFixture) -> None:
    """_get_submit_dir raises ValueError when ec != 0 (line 821)."""
    runner, _ = _make_runner()
    result = MagicMock()
    result.rc = 1
    result.stdout = "error output"
    result.stderr = "some error"
    machine = MagicMock()

    with pytest.raises(ValueError, match="Workflow generation failed"):
        runner._get_submit_dir(result, machine, mocker.MagicMock())


def test_get_submit_dir_with_submit_dir_pattern(mocker: MockerFixture) -> None:
    """_get_submit_dir parses submit_dir: pattern (lines 827-831)."""
    runner, _ = _make_runner()
    result = MagicMock()
    result.rc = 0
    result.stdout = "submit_dir: /home/kiso/run/wf"
    result.stderr = ""
    machine = MagicMock()

    path = runner._get_submit_dir(result, machine, mocker.MagicMock())
    assert str(path) == "/home/kiso/run/wf"


def test_get_submit_dir_with_pegasus_run_pattern(mocker: MockerFixture) -> None:
    """_get_submit_dir calls pegasus_run when pegasus-run found in output."""
    runner, _ = _make_runner()
    result = MagicMock()
    result.rc = 0
    result.stdout = "pegasus-run /home/kiso/run/wf"
    result.stderr = ""
    machine = MagicMock()
    mock_run = mocker.patch.object(runner, "pegasus_run")

    runner._get_submit_dir(result, machine, MagicMock())
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# _wait_for_workflow — already-OK fast path
# ---------------------------------------------------------------------------


def test_wait_for_workflow_already_ok(mocker: MockerFixture) -> None:
    """_wait_for_workflow returns early when STATUS_OK (lines 891-904)."""
    runner, _ = _make_runner()
    runner.vms = mocker.MagicMock()
    runner.containers = mocker.MagicMock()
    runner.poll_interval = 5
    runner.timeout = 60
    runner.env = {0: {"wait-workflow": const.STATUS_OK}}
    mocker.patch("kiso.pegasus.runner.console.print")

    runner._wait_for_workflow(0)  # must not raise


# ---------------------------------------------------------------------------
# _render_status
# ---------------------------------------------------------------------------


def test_render_status_non_ok_returns_immediately(mocker: MockerFixture) -> None:
    """_render_status returns early when status is not OK (lines 1022-1023)."""
    runner, _ = _make_runner()
    status = mocker.MagicMock()
    status.status = const.STATUS_FAILED
    progress = mocker.MagicMock()

    runner._render_status(progress, status)
    progress.update_table.assert_not_called()


def test_render_status_ok_parses_json(mocker: MockerFixture) -> None:
    """_render_status parses JSON output when status is OK (lines 1025-1026)."""
    runner, _ = _make_runner()
    output = {"State": "Running", "Total": 10}
    status = mocker.MagicMock()
    status.status = const.STATUS_OK
    status.payload = {"stdout": json.dumps(output)}
    progress = mocker.MagicMock()

    runner._render_status(progress, status)
    progress.update_table.assert_called_once_with(output)


# ---------------------------------------------------------------------------
# pegasus_remove, pegasus_statistics, pegasus_analyzer — Host path
# ---------------------------------------------------------------------------


def test_pegasus_remove_host_path(mocker: MockerFixture) -> None:
    """pegasus_remove with Host uses utils.actions (lines 1064-1067)."""
    runner, _ = _make_runner()
    h = Host("10.0.0.1")
    h.extra = {}

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)

    result = runner.pegasus_remove(h, "/submit/dir")
    assert result is mock_p.results[0]


def test_pegasus_statistics_host_path(mocker: MockerFixture) -> None:
    """pegasus_statistics with Host uses utils.actions (lines 1109-1114)."""
    runner, _ = _make_runner()
    h = Host("10.0.0.1")
    h.extra = {}

    mock_p = mocker.MagicMock()
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)

    runner.pegasus_statistics(h, "/submit/dir")  # must not raise


def test_pegasus_analyzer_host_path(mocker: MockerFixture) -> None:
    """pegasus_analyzer with Host uses utils.actions (lines 1152-1157)."""
    runner, _ = _make_runner()
    h = Host("10.0.0.1")
    h.extra = {}

    mock_p = mocker.MagicMock()
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)

    runner.pegasus_analyzer(h, "/submit/dir")  # must not raise


# ---------------------------------------------------------------------------
# _fetch_submit_dir — already-OK and containers path
# ---------------------------------------------------------------------------


def test_fetch_submit_dir_already_ok(mocker: MockerFixture, tmp_path: Path) -> None:
    """_fetch_submit_dir returns early when STATUS_OK (lines 1196-1212)."""
    runner, _ = _make_runner()
    runner.vms = []
    runner.containers = []
    runner.resultdir = str(tmp_path)
    runner.env = {0: {"fetch-submit-dir": const.STATUS_OK, "submit-dir": "/submit/dir"}}
    mocker.patch("kiso.pegasus.runner.console.print")

    runner._fetch_submit_dir(0)  # must not raise


def test_fetch_submit_dir_with_containers_uses_edge(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """_fetch_submit_dir calls edge.download for containers (lines 1226-1228)."""
    runner, _ = _make_runner()
    submit_dir = str(tmp_path / "wf")
    runner.vms = []
    runner.containers = [mocker.MagicMock()]
    runner.resultdir = str(tmp_path)
    runner.env = {0: {"submit-dir": submit_dir}}
    mocker.patch("kiso.pegasus.runner.console.print")

    mock_download = mocker.patch("kiso.pegasus.runner.edge.download")
    runner._fetch_submit_dir(0)
    mock_download.assert_called_once()


def test_fetch_submit_dir_with_vms_uses_actions(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """_fetch_submit_dir calls utils.actions for vms (lines 1218-1225)."""
    runner, _ = _make_runner()
    submit_dir = str(tmp_path / "wf")
    mock_vm = mocker.MagicMock()
    runner.vms = [mock_vm]
    runner.containers = []
    runner.resultdir = str(tmp_path)
    runner.env = {0: {"submit-dir": submit_dir}}
    mocker.patch("kiso.pegasus.runner.console.print")

    mock_p = mocker.MagicMock()
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)

    runner._fetch_submit_dir(0)  # must not raise


# ---------------------------------------------------------------------------
# pegasus_run — Host path
# ---------------------------------------------------------------------------


def test_get_submit_dir_no_match_host_queries_db(mocker: MockerFixture) -> None:
    """_get_submit_dir queries sqlite when no regex match and machine is Host."""
    runner, _ = _make_runner()
    result = MagicMock()
    result.rc = 0
    result.stdout = "no workflow info here"
    result.stderr = ""
    h = Host("10.0.0.1")
    h.extra = {}

    # Mock en.run_command to return a successful result with workflow state
    mock_cmd_result = MagicMock()
    mock_cmd_result.status = const.STATUS_OK
    mock_cmd_result.payload = {
        "stdout": "WORKFLOW_STARTED|/submit/dir\n",
        "stderr": "",
    }
    mocker.patch("kiso.pegasus.runner.en.run_command", return_value=[mock_cmd_result])

    path = runner._get_submit_dir(result, h, MagicMock())
    assert str(path) == "/submit/dir"


def test_get_submit_dir_no_match_host_cmd_fails(mocker: MockerFixture) -> None:
    """_get_submit_dir raises ValueError when sqlite query fails (line 866)."""
    runner, _ = _make_runner()
    result = MagicMock()
    result.rc = 0
    result.stdout = "no workflow info"
    result.stderr = ""
    h = Host("10.0.0.1")
    h.extra = {}

    mock_cmd_result = MagicMock()
    mock_cmd_result.status = const.STATUS_FAILED
    mock_cmd_result.payload = {"stdout": "", "stderr": "error"}
    mocker.patch("kiso.pegasus.runner.en.run_command", return_value=[mock_cmd_result])

    with pytest.raises(ValueError, match="Could not identify the submit dir"):
        runner._get_submit_dir(result, h, MagicMock())


def test_get_submit_dir_no_match_host_empty_state(mocker: MockerFixture) -> None:
    """_get_submit_dir raises ValueError when workflow_state is empty (line 870)."""
    runner, _ = _make_runner()
    result = MagicMock()
    result.rc = 0
    result.stdout = "no workflow info"
    result.stderr = ""
    h = Host("10.0.0.1")
    h.extra = {}

    mock_cmd_result = MagicMock()
    mock_cmd_result.status = const.STATUS_OK
    mock_cmd_result.payload = {"stdout": "   ", "stderr": ""}
    mocker.patch("kiso.pegasus.runner.en.run_command", return_value=[mock_cmd_result])

    with pytest.raises(ValueError, match="Could not identify the submit dir"):
        runner._get_submit_dir(result, h, MagicMock())


def test_get_submit_dir_no_match_host_invalid_state(mocker: MockerFixture) -> None:
    """_get_submit_dir raises ValueError when workflow state is not WORKFLOW_STARTED."""
    runner, _ = _make_runner()
    result = MagicMock()
    result.rc = 0
    result.stdout = "no match"
    result.stderr = ""
    h = Host("10.0.0.1")
    h.extra = {}

    mock_cmd_result = MagicMock()
    mock_cmd_result.status = const.STATUS_OK
    mock_cmd_result.payload = {"stdout": "WORKFLOW_FAILED|/submit/dir\n", "stderr": ""}
    mocker.patch("kiso.pegasus.runner.en.run_command", return_value=[mock_cmd_result])

    with pytest.raises(ValueError, match="Invalid workflow state"):
        runner._get_submit_dir(result, h, MagicMock())


# ---------------------------------------------------------------------------
# pegasus_remove, pegasus_statistics, pegasus_analyzer — container path
# ---------------------------------------------------------------------------


def test_pegasus_remove_container_path(mocker: MockerFixture) -> None:
    """pegasus_remove with non-Host uses _pegasus_remove (line 1069-1071)."""
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()
    # Not a Host → isinstance(machine, Host) = False
    mock_remove = mocker.patch.object(
        runner, "_pegasus_remove", return_value=mocker.MagicMock()
    )

    runner.pegasus_remove(mock_container, "/submit/dir")
    mock_remove.assert_called_once()


def test_pegasus_statistics_container_path(mocker: MockerFixture) -> None:
    """pegasus_statistics with non-Host uses _pegasus_statistics (line 1116)."""
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()
    mock_stats = mocker.patch.object(
        runner, "_pegasus_statistics", return_value=mocker.MagicMock()
    )

    runner.pegasus_statistics(mock_container, "/submit/dir")
    mock_stats.assert_called_once()


def test_pegasus_analyzer_container_path(mocker: MockerFixture) -> None:
    """pegasus_analyzer with non-Host uses _pegasus_analyzer (line 1159)."""
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()
    mock_analyze = mocker.patch.object(
        runner, "_pegasus_analyzer", return_value=mocker.MagicMock()
    )

    runner.pegasus_analyzer(mock_container, "/submit/dir")
    mock_analyze.assert_called_once()


def test_get_submit_dir_pegasus_run_pattern_fails(mocker: MockerFixture) -> None:
    """_get_submit_dir raises ValueError when pegasus_run fails (lines 836-838)."""
    runner, _ = _make_runner()
    result = MagicMock()
    result.rc = 0
    result.stdout = "pegasus-run /home/kiso/run/wf"
    result.stderr = ""
    machine = MagicMock()
    mocker.patch.object(runner, "pegasus_run", side_effect=Exception("run failed"))

    with pytest.raises(ValueError, match="Failed to run the workflow"):
        runner._get_submit_dir(result, machine, MagicMock())


def test_wait_for_workflow_calls_sub_methods(mocker: MockerFixture) -> None:
    """_wait_for_workflow calls _wait_for_workflow_2, pegasus_statistics, analyzer."""
    runner, _ = _make_runner()
    mock_vm = mocker.MagicMock()
    runner.vms = [mock_vm]
    runner.containers = []
    runner.poll_interval = 5
    runner.timeout = 60
    runner.env = {0: {"submit-dir": "/submit/dir"}}

    mock_wait2 = mocker.patch.object(runner, "_wait_for_workflow_2")
    mock_stats = mocker.patch.object(runner, "pegasus_statistics")
    mock_analyze = mocker.patch.object(runner, "pegasus_analyzer")
    mocker.patch("kiso.pegasus.runner.console.print")

    runner._wait_for_workflow(0)

    mock_wait2.assert_called_once()
    mock_stats.assert_called_once()
    mock_analyze.assert_called_once()


def test_pegasus_run_container_path(mocker: MockerFixture) -> None:
    """pegasus_run with non-Host uses _pegasus_run (lines 765-768)."""
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()

    mock_pr = mocker.patch.object(
        runner, "_pegasus_run", return_value=mocker.MagicMock()
    )
    mock_gsd = mocker.patch.object(
        runner, "_get_submit_dir", return_value=mocker.MagicMock()
    )

    runner.pegasus_run(mock_container, "/submit/dir")
    mock_pr.assert_called_once()
    mock_gsd.assert_called_once()


def test_pegasus_status_calls_edge_execute(mocker: MockerFixture) -> None:
    """pegasus_status calls edge._execute (lines 1045-1046)."""
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()
    mock_execute = mocker.patch(
        "kiso.pegasus.runner.edge._execute", return_value=mocker.MagicMock()
    )

    runner.pegasus_status(mock_container, "/submit/dir", user="kiso")
    mock_execute.assert_called_once()


def test_pegasus_remove_edge_execute(mocker: MockerFixture) -> None:
    """_pegasus_remove calls edge._execute (lines 1092-1093)."""
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()
    mock_execute = mocker.patch(
        "kiso.pegasus.runner.edge._execute", return_value=mocker.MagicMock()
    )

    runner._pegasus_remove(mock_container, "/submit/dir", user="kiso")
    mock_execute.assert_called_once()


def test_pegasus_statistics_edge_execute(mocker: MockerFixture) -> None:
    """_pegasus_statistics calls edge._execute (lines 1135-1136)."""
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()
    mock_execute = mocker.patch(
        "kiso.pegasus.runner.edge._execute", return_value=mocker.MagicMock()
    )

    runner._pegasus_statistics(mock_container, "/submit/dir", user="kiso")
    mock_execute.assert_called_once()


def test_pegasus_run_host_path(mocker: MockerFixture) -> None:
    """pegasus_run with Host uses utils.actions (lines 758-763)."""
    runner, _ = _make_runner()
    h = Host("10.0.0.1")
    h.extra = {}

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock()]
    mock_p.results[0].rc = 0
    mock_p.results[0].stdout = 'submit_dir: "/submit/dir"'
    mock_p.results[0].stderr = ""
    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)

    runner.pegasus_run(h, "/submit/dir")  # must not raise


def test_pegasus_run_edge_execute(mocker: MockerFixture) -> None:
    """_pegasus_run calls edge._execute (lines 787-788)."""
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()
    mock_execute = mocker.patch(
        "kiso.pegasus.runner.edge._execute", return_value=mocker.MagicMock()
    )

    runner._pegasus_run(mock_container, Path("/submit/dir"), user="kiso")
    mock_execute.assert_called_once()


def test_pegasus_analyzer_edge_execute(mocker: MockerFixture) -> None:
    """_pegasus_analyzer calls edge._execute (lines 1178-1185)."""
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()
    mock_execute = mocker.patch(
        "kiso.pegasus.runner.edge._execute", return_value=mocker.MagicMock()
    )

    runner._pegasus_analyzer(mock_container, Path("/submit/dir"), user="kiso")
    mock_execute.assert_called_once()


def test_wait_for_workflow_timeout_sets_failed(mocker: MockerFixture) -> None:
    """KisoTimeoutError in _wait_for_workflow sets STATUS_FAILED (lines 914-918).

    experiment_state suppresses the exception (on_error_continue=True default)
    but STATUS_FAILED is recorded in env.
    """
    runner, _ = _make_runner()
    mock_vm = mocker.MagicMock()
    runner.vms = [mock_vm]
    runner.containers = []
    runner.poll_interval = 5
    runner.timeout = 60
    runner.env = {0: {"submit-dir": "/submit/dir"}}

    mocker.patch.object(
        runner, "_wait_for_workflow_2", side_effect=KisoTimeoutError("timeout")
    )
    mocker.patch.object(runner, "pegasus_statistics")
    mocker.patch.object(runner, "pegasus_analyzer")
    mocker.patch("kiso.pegasus.runner.console.print")

    runner._wait_for_workflow(0)
    # experiment_state suppresses the error but records STATUS_FAILED
    assert runner.env[0]["wait-workflow"] == const.STATUS_FAILED


def test_get_submit_dir_container_sqlite_path(mocker: MockerFixture) -> None:
    """_get_submit_dir uses edge._execute for non-Host sqlite query (lines 861-863).

    When the workflow generation result has no submit_dir in stdout,
    the code falls through to the sqlite query path using edge._execute.
    """
    runner, _ = _make_runner()
    mock_container = mocker.MagicMock()

    # Workflow generation succeeded (rc=0) but no submit_dir pattern in output
    mock_gen_result = mocker.MagicMock()
    mock_gen_result.rc = 0
    mock_gen_result.stdout = "some output without submit dir pattern"
    mock_gen_result.stderr = ""

    # sqlite query result (returned by edge._execute)
    mock_sqlite_result = mocker.MagicMock()
    mock_sqlite_result.rc = 0
    mock_sqlite_result.stdout = "WORKFLOW_STARTED|/workflow/dir|extra"

    mocker.patch(
        "kiso.pegasus.runner.edge._execute",
        return_value=mock_sqlite_result,
    )

    ts = datetime.now()
    result = runner._get_submit_dir(mock_gen_result, mock_container, ts)
    assert str(result) == "/workflow/dir"


def test_generate_workflow_already_ok_returns_none(mocker: MockerFixture) -> None:
    """_generate_workflow with STATUS_OK state returns None early (line 699-700)."""
    runner, _ = _make_runner()
    runner.vms = [mocker.MagicMock()]
    runner.containers = []
    runner.env = {0: {"workflow-generate": const.STATUS_OK}}
    mocker.patch("kiso.pegasus.runner.console.print")

    result = runner._generate_workflow(0)
    assert result is None


def test_generate_workflow_vms_path(mocker: MockerFixture) -> None:
    """_generate_workflow with vms uses utils.actions (lines 708-723)."""
    runner, _ = _make_runner(main="#!/bin/bash\necho hello")
    mock_vm = mocker.MagicMock()
    runner.vms = [mock_vm]
    runner.containers = []
    runner.env = {0: {}}
    runner.remote_wd = "/remote/wd"

    mock_result = mocker.MagicMock()
    mock_result.rc = 0
    mock_result.stdout = "submit_dir: /submit/dir"
    mock_result.stderr = ""

    mock_p = mocker.MagicMock()
    mock_p.results = [mocker.MagicMock(), mock_result, mocker.MagicMock()]

    mock_cm = mocker.MagicMock()
    mock_cm.__enter__ = mocker.MagicMock(return_value=mock_p)
    mock_cm.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("kiso.pegasus.runner.utils.actions", return_value=mock_cm)
    mocker.patch.object(runner, "_get_submit_dir", return_value=Path("/submit/dir"))
    mocker.patch("kiso.pegasus.runner.console.print")

    runner._generate_workflow(0)
    assert runner.env[0]["submit-dir"] == Path("/submit/dir")


def test_generate_workflow_containers_path(mocker: MockerFixture) -> None:
    """_generate_workflow with containers uses edge.run_script (lines 724-733)."""
    runner, _ = _make_runner(main="#!/bin/bash\necho hello")
    mock_container = mocker.MagicMock()
    runner.vms = []
    runner.containers = [mock_container]
    runner.env = {0: {}}
    runner.remote_wd = "/remote/wd"

    mock_status = mocker.MagicMock()
    mock_status.rc = 0
    mock_status.stdout = "submit_dir: /submit/dir"
    mock_status.stderr = ""
    mocker.patch("kiso.pegasus.runner.edge.run_script", return_value=mock_status)
    mocker.patch.object(runner, "_get_submit_dir", return_value=Path("/submit/dir"))
    mocker.patch("kiso.pegasus.runner.console.print")

    runner._generate_workflow(0)
    assert runner.env[0]["submit-dir"] == Path("/submit/dir")


def test_check_submit_labels_passes_when_submit_label_maps_to_submit_node() -> None:

    machine = object()
    deployment = Deployment(htcondor=[HTCondorDaemon(kind="submit", labels=["sub"])])
    kiso_config = _make_kiso(
        deployment=deployment,
        experiments=[_make_exp(submit_node_labels=["sub"])],
    )
    label_to_machines = {"sub": {machine}}
    runner, _ = _make_runner(submit_node_labels=["sub"])
    runner._check_submit_labels_are_submit_nodes(
        kiso_config, label_to_machines
    )  # no raise
