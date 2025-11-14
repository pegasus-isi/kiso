"""Kiso utilities to display Pegasus workflow status."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rich.table import Table

import kiso.constants as const

if TYPE_CHECKING:
    from enoslib.api import CommandResult, CustomCommandResult
    from rich.console import Console

log = logging.getLogger(__name__)


def scripts(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of running the setup scripts."""
    _scripts(console, results)


def outputs(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of moving outputs back to the local machine."""
    _transfers(console, results, "Output")


def _transfers(
    console: Console, results: list[CommandResult | CustomCommandResult], col_name: str
) -> None:
    """Display status of file transfers to/from the provisioned nodes."""
    if not results:
        return

    status: dict[tuple[int, str], str] = _group_results(results)
    table = _generate_table(status=status, col_name=col_name)
    console.print(table)


def _scripts(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of running the scripts."""
    if not results:
        return

    result_grouped_by_host: dict[
        tuple[int, str], list[CommandResult | CustomCommandResult]
    ] = {}
    for index, _script, _results in results:
        for result in _results:
            result_grouped_by_host.setdefault((index, result.host), []).append(result)

    for (index, host), _results in result_grouped_by_host.items():
        status = _results[-1].status
        color = const.STATUS_COLOR_MAP[status]

        console.rule(
            f"[bold {color}]Script {index + 1} on {host}[/bold {color}]", style=color
        )

        cp = _results[0]
        log.debug("Copying script %s to %s, %s", index + 1, host, cp.status)
        if cp.status == const.STATUS_FAILED:
            console.print(f"Copying script {index + 1} to {host}, {cp.status}")
            continue

        script = _results[1]
        log.debug(
            """Running script %s on %s, %s
Standard Out: %s
Standard Error: %s""",
            index + 1,
            host,
            script.status,
            script.stdout,
            script.stderr,
        )
        console.print(f"Running script {index + 1} on {host}, {script.status}")
        console.print(f"Standard Out: {script.stdout}")
        console.print(f"Standard Err: {script.stderr}")
        if script.status == const.STATUS_FAILED:
            continue

        cleanup = _results[2]
        log.debug(
            """Cleaning up script %s on %s, %s.
Standard Out: %s
Standard Error: %s
""",
            index + 1,
            host,
            cleanup.status,
            cleanup.stdout,
            cleanup.stderr,
        )
        if cleanup.status == const.STATUS_FAILED:
            console.print(f"Cleaning up script {index + 1} on {host}, {cleanup.status}")
            console.print(f"Standard Out: {cleanup.stdout}")
            console.print(f"Standard Err: {cleanup.stderr}")


def _group_results(
    results: list[CommandResult | CustomCommandResult],
) -> dict[tuple[int, str], str]:
    status: dict[tuple[int, str], str] = {}
    for _results in results:
        for result in _results[-1]:
            status.setdefault((_results[0], result.host), result.status)
            if (
                status[(_results[0], result.host)] != const.STATUS_FAILED
                and result.payload.get("skip_reason", "").lower()
                != "conditional result was false"
            ):
                status[(_results[0], result.host)] = result.status
        else:
            if not _results[-1]:
                status[(_results[0], f"*{_results[0]}")] = const.STATUS_SKIPPED

    return status


def _generate_table(status: dict[tuple[int, str], str], col_name: str) -> Table:
    table = Table(show_header=True)
    table.add_column(col_name, style="bold")
    table.add_column("Host", style="bold")
    table.add_column("Status")

    for (index, host), ok in status.items():
        color = const.STATUS_COLOR_MAP[ok]
        table.add_row(
            f"{index + 1}",
            "*" if host[0] == "*" else host,
            f"[bold {color}]{ok}[/bold {color}]",
        )

    return table
