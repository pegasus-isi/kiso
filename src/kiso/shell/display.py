"""Kiso utilities to display Pegasus workflow status."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

import kiso.constants as const

if TYPE_CHECKING:
    from enoslib.api import CommandResult, CustomCommandResult
    from rich.console import Console


def scripts(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of running the setup scripts."""
    _scripts(console, results, "Script")


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

    status: dict[str, tuple] = {}
    for _results in results:
        for result in _results[-1]:
            if result.host not in status or status[result.host][-1] == const.STATUS_OK:
                status[result.host] = (_results[0], result.status)
        else:
            if not _results[-1]:
                status[f"*{_results[0]}"] = (_results[0], const.STATUS_SKIPPED)

    table = Table(show_header=True)
    table.add_column(col_name, style="bold")
    table.add_column("Host", style="bold")
    table.add_column("Status")

    for host, ok in status.items():
        color = const.STATUS_COLOR_MAP[ok[1]]
        table.add_row(
            f"{ok[0] + 1}",
            "*" if host[0] == "*" else host,
            f"[bold {color}]{ok[1]}[/bold {color}]",
        )

    console.print(table)


def _scripts(
    console: Console, results: list[CommandResult | CustomCommandResult], col_name: str
) -> None:
    """Display status of running the scripts."""
    if not results:
        return

    status: dict[str, tuple] = {}
    for _results in results:
        for result in _results[-1]:
            if result.host not in status or status[result.host][-1] == const.STATUS_OK:
                status[result.host] = (_results[0], result.status)
        else:
            if not _results[-1]:
                status[f"*{_results[0]}"] = (_results[0], const.STATUS_SKIPPED)

    table = Table(show_header=True)
    table.add_column(col_name, style="bold")
    table.add_column("Host", style="bold")
    table.add_column("Status")

    for host, ok in status.items():
        color = const.STATUS_COLOR_MAP[ok[1]]
        table.add_row(
            f"{ok[0] + 1}",
            "*" if host[0] == "*" else host,
            f"[bold {color}]{ok[1]}[/bold {color}]",
        )

    console.print(table)
