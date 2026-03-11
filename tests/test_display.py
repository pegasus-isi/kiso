"""Tests for kiso.display, kiso.shell.display, and kiso.pegasus.display."""

from __future__ import annotations

import io
from types import SimpleNamespace

from rich.console import Console

import kiso.constants as const
from kiso import display as kiso_display
from kiso.pegasus import display as pegasus_display
from kiso.pegasus.display import PegasusWorkflowProgress
from kiso.shell import display as shell_display

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _console() -> Console:
    """Return a Console that writes to a buffer (no terminal I/O)."""
    return Console(file=io.StringIO(), highlight=False)


def _result(
    host: str = "h1",
    status: str = const.STATUS_OK,
    skip_reason: str = "",
    stdout: str = "",
    stderr: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        host=host,
        status=status,
        payload={"skip_reason": skip_reason} if skip_reason else {},
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# kiso.display — commons and _render
# ---------------------------------------------------------------------------


def test_commons_empty_results_is_noop() -> None:
    console = _console()
    kiso_display.commons(console, [])
    # No exception; nothing printed


def test_commons_ok_result() -> None:
    console = _console()
    kiso_display.commons(console, [_result("host1", const.STATUS_OK)])


def test_commons_failed_result_stays_failed() -> None:
    console = _console()
    results = [
        _result("host1", const.STATUS_FAILED),
        _result("host1", const.STATUS_OK),  # should NOT override FAILED
    ]
    kiso_display.commons(console, results)
    # The function itself aggregates status; we just verify it doesn't crash


def test_commons_skip_reason_preserves_prior_status() -> None:
    console = _console()
    results = [
        _result("host1", const.STATUS_OK),
        _result("host1", const.STATUS_OK, skip_reason="conditional result was false"),
    ]
    kiso_display.commons(console, results)


def test_render_empty_results_is_noop() -> None:
    console = _console()
    kiso_display._render(console, [])


def test_render_ok_result() -> None:
    console = _console()
    kiso_display._render(console, [_result("host1", const.STATUS_OK)])


def test_render_failed_result() -> None:
    console = _console()
    kiso_display._render(console, [_result("host1", const.STATUS_FAILED)])


# ---------------------------------------------------------------------------
# shell.display — _group_results and _generate_table
# ---------------------------------------------------------------------------


def _shell_results_tuple(index: int, results: list) -> tuple:
    """Build the (index, location, results_list) tuple that shell display expects."""
    return (index, SimpleNamespace(), results)


def test_shell_group_results_ok() -> None:
    r = _result("h1", const.STATUS_OK)
    grouped = shell_display._group_results([_shell_results_tuple(0, [r])])
    assert grouped[(0, "h1")] == const.STATUS_OK


def test_shell_group_results_failed_stays_failed() -> None:
    r_fail = _result("h1", const.STATUS_FAILED)
    r_ok = _result("h1", const.STATUS_OK)
    grouped = shell_display._group_results([_shell_results_tuple(0, [r_fail, r_ok])])
    assert grouped[(0, "h1")] == const.STATUS_FAILED


def test_shell_group_results_empty_list_is_skipped() -> None:
    grouped = shell_display._group_results([_shell_results_tuple(0, [])])
    assert grouped[(0, "*0")] == const.STATUS_SKIPPED


def test_shell_generate_table_basic() -> None:
    status = {(0, "h1"): const.STATUS_OK}
    table = shell_display._generate_table(status, "Input")
    assert table is not None


def test_shell_generate_table_wildcard_host() -> None:
    status = {(0, "*0"): const.STATUS_SKIPPED}
    table = shell_display._generate_table(status, "Output")
    assert table is not None


# ---------------------------------------------------------------------------
# shell.display — inputs / outputs / scripts wrappers
# ---------------------------------------------------------------------------


def test_shell_inputs_empty() -> None:
    shell_display.inputs(_console(), [])


def test_shell_outputs_empty() -> None:
    shell_display.outputs(_console(), [])


def test_shell_scripts_empty() -> None:
    shell_display.scripts(_console(), [])


def test_shell_inputs_with_result() -> None:
    r = _result("h1", const.STATUS_OK)
    shell_display.inputs(_console(), [_shell_results_tuple(0, [r])])


def test_shell_outputs_with_result() -> None:
    r = _result("h1", const.STATUS_OK)
    shell_display.outputs(_console(), [_shell_results_tuple(0, [r])])


# ---------------------------------------------------------------------------
# shell.display — _scripts (complex per-host rendering)
# ---------------------------------------------------------------------------


def test_shell_scripts_copy_failed_path() -> None:
    cp_fail = _result("h1", const.STATUS_FAILED)
    # Only copy result — script/cleanup not accessed because copy failed
    shell_display.scripts(_console(), [(0, SimpleNamespace(), [cp_fail])])


def test_shell_scripts_script_failed_path() -> None:
    cp_ok = _result("h1", const.STATUS_OK)
    run_fail = _result("h1", const.STATUS_FAILED, stdout="out", stderr="err")
    shell_display.scripts(_console(), [(0, SimpleNamespace(), [cp_ok, run_fail])])


def test_shell_scripts_success_path() -> None:
    cp_ok = _result("h1", const.STATUS_OK)
    run_ok = _result("h1", const.STATUS_OK, stdout="hello", stderr="")
    cleanup_ok = _result("h1", const.STATUS_OK)
    shell_display.scripts(
        _console(), [(0, SimpleNamespace(), [cp_ok, run_ok, cleanup_ok])]
    )


def test_shell_scripts_cleanup_failed_path() -> None:
    cp_ok = _result("h1", const.STATUS_OK)
    run_ok = _result("h1", const.STATUS_OK, stdout="", stderr="")
    cleanup_fail = _result("h1", const.STATUS_FAILED, stdout="", stderr="err")
    shell_display.scripts(
        _console(), [(0, SimpleNamespace(), [cp_ok, run_ok, cleanup_fail])]
    )


# ---------------------------------------------------------------------------
# pegasus.display — _group_results and _generate_table (same logic as shell)
# ---------------------------------------------------------------------------


def test_pegasus_group_results_ok() -> None:
    r = _result("h1", const.STATUS_OK)
    grouped = pegasus_display._group_results([(0, SimpleNamespace(), [r])])
    assert grouped[(0, "h1")] == const.STATUS_OK


def test_pegasus_group_results_empty_skipped() -> None:
    grouped = pegasus_display._group_results([(0, SimpleNamespace(), [])])
    assert grouped[(0, "*0")] == const.STATUS_SKIPPED


def test_pegasus_generate_table_basic() -> None:
    status = {(0, "h1"): const.STATUS_OK}
    table = pegasus_display._generate_table(status, "Setup Script")
    assert table is not None


# ---------------------------------------------------------------------------
# pegasus.display — inputs / outputs / setup_scripts / post_scripts wrappers
# ---------------------------------------------------------------------------


def test_pegasus_inputs_empty() -> None:
    pegasus_display.inputs(_console(), [])


def test_pegasus_outputs_empty() -> None:
    pegasus_display.outputs(_console(), [])


def test_pegasus_setup_scripts_empty() -> None:
    pegasus_display.setup_scripts(_console(), [])


def test_pegasus_post_scripts_empty() -> None:
    pegasus_display.post_scripts(_console(), [])


def test_pegasus_inputs_with_result() -> None:
    r = _result("h1", const.STATUS_OK)
    pegasus_display.inputs(_console(), [(0, SimpleNamespace(), [r])])


def test_pegasus_outputs_with_result() -> None:
    r = _result("h1", const.STATUS_OK)
    pegasus_display.outputs(_console(), [(0, SimpleNamespace(), [r])])


def test_pegasus_setup_scripts_with_result() -> None:
    r = _result("h1", const.STATUS_OK)
    pegasus_display.setup_scripts(_console(), [(0, SimpleNamespace(), [r])])


# ---------------------------------------------------------------------------
# pegasus.display — generate_workflow
# ---------------------------------------------------------------------------


def test_pegasus_generate_workflow_with_result() -> None:
    r = _result("h1", const.STATUS_OK)
    # generate_workflow wraps its argument in a list; pass (index, meta, results)
    pegasus_display.generate_workflow(_console(), (0, SimpleNamespace(), [r]))


# ---------------------------------------------------------------------------
# PegasusWorkflowProgress
# ---------------------------------------------------------------------------

_COLS = {
    "State": "state",
    "Succeeded": "succeeded",
    "Failed": "failed",
    "%": "percent",
}


def _make_status(
    state: str, succeeded: int = 0, failed: int = 0, percent: int = 0
) -> dict:
    return {
        "dags": {
            "root": {
                "state": state,
                "succeeded": succeeded,
                "failed": failed,
                "percent": percent,
            }
        }
    }


def test_progress_init() -> None:
    p = PegasusWorkflowProgress(_COLS)
    assert p.table is not None


def test_progress_update_table_none_is_noop() -> None:
    p = PegasusWorkflowProgress(_COLS)
    p.update_table(None)  # should not raise


def test_progress_update_table_running() -> None:
    p = PegasusWorkflowProgress(_COLS)
    p.update_table(_make_status("Running"))


def test_progress_update_table_success() -> None:
    p = PegasusWorkflowProgress(_COLS)
    p.update_table(_make_status("Success", succeeded=5, percent=100))


def test_progress_update_table_failure() -> None:
    p = PegasusWorkflowProgress(_COLS)
    p.update_table(_make_status("Failure", failed=2))


def test_progress_update_table_running_with_failures() -> None:
    p = PegasusWorkflowProgress(_COLS)
    p.update_table(_make_status("Running", succeeded=3, failed=1, percent=50))


def test_progress_get_renderable() -> None:
    p = PegasusWorkflowProgress(_COLS)
    renderable = p.get_renderable()
    assert renderable is not None
