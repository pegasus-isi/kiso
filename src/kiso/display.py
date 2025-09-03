"""Methods to display the status of HTCondor, Docker, and Apptainer installations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

import kiso.constants as const

if TYPE_CHECKING:
    from enoslib.api import CommandResult, CustomCommandResult
    from rich.console import Console


def commons(
    console: Console,
    results: list[CommandResult],
) -> None:
    """Display status of installation of commons."""
    if not results:
        return

    status: dict[str, str] = {}
    for result in results:
        if result.host not in status or status[result.host] != const.STATUS_FAILED:
            status[result.host] = result.status

    table = Table(show_header=True)
    table.add_column("Host", style="bold")
    table.add_column("Status")

    for host, ok in status.items():
        color = const.STATUS_COLOR_MAP[ok]
        table.add_row(host, f"[bold {color}]{ok}[/bold {color}]")

    console.print(table)


def docker(
    console: Console,
    results: list[CustomCommandResult],
) -> None:
    """Display status of installation of Docker."""
    _render(console, results)


def apptainer(
    console: Console,
    results: list[CommandResult],
) -> None:
    """Display status of installation of Apptainer."""
    _render(console, results)


def htcondor(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of installation of HTCondor."""
    _render(console, results)


def _render(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of installation in a table."""
    if not results:
        return

    status: dict[str, str] = {}
    for result in results:
        if result.host not in status or status[result.host] != const.STATUS_FAILED:
            status[result.host] = result.status

    table = Table(show_header=True)
    table.add_column("Host", style="bold")
    table.add_column("Status")

    for host, ok in status.items():
        color = const.STATUS_COLOR_MAP[ok]
        table.add_row(host, f"[bold {color}]{ok}[/bold {color}]")

    console.print(table)
