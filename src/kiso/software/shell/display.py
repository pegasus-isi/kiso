"""Kiso utilities to display Pegasus workflow status."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

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
