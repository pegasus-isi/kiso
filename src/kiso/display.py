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
        status.setdefault(result.host, result.status)
        if (
            status[result.host] != const.STATUS_FAILED
            and result.payload.get("skip_reason", "").lower()
            != "conditional result was false"
        ):
            status[result.host] = result.status

    table = Table(show_header=True)
    table.add_column("Host", style="bold")
    table.add_column("Status")

    for host, ok in status.items():
        color = const.STATUS_COLOR_MAP[ok]
        table.add_row(host, f"[bold {color}]{ok}[/bold {color}]")

    console.print(table)


def _render(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of installation in a table."""
    if not results:
        return

    status: dict[str, str] = {}
    for result in results:
        status.setdefault(result.host, result.status)
        if (
            status[result.host] != const.STATUS_FAILED
            and result.payload.get("skip_reason", "").lower()
            != "conditional result was false"
        ):
            status[result.host] = result.status

    table = Table(show_header=True)
    table.add_column("Host", style="bold")
    table.add_column("Status")

    for host, ok in status.items():
        color = const.STATUS_COLOR_MAP[ok]
        table.add_row(host, f"[bold {color}]{ok}[/bold {color}]")

    console.print(table)
