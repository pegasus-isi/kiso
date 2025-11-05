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

    status: dict[tuple[int, str], str] = _group_results(results)
    table = _generate_table(status=status, col_name=col_name)
    console.print(table)


def _scripts(
    console: Console, results: list[CommandResult | CustomCommandResult], col_name: str
) -> None:
    """Display status of running the scripts."""
    if not results:
        return

    status: dict[tuple[int, str], str] = _group_results(results)
    table = _generate_table(status=status, col_name=col_name)
    console.print(table)


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
