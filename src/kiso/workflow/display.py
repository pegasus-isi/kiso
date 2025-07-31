"""Kiso utilities to display Pegasus workflow status."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import ConsoleRenderable, Group, RichCast
from rich.progress import Progress
from rich.spinner import Spinner
from rich.table import Table

import kiso.constants as const

if TYPE_CHECKING:
    from enoslib.api import CommandResult, CustomCommandResult
    from rich.console import Console


def inputs(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of moving inputs the provisioned nodes."""
    _transfers(console, results, "Input")


def setup_scripts(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of running the setup scripts."""
    _scripts(console, results, "Setup Script")


def outputs(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of moving outputs back to the local machine."""
    _transfers(console, results, "Output")


def post_scripts(
    console: Console, results: list[CommandResult | CustomCommandResult]
) -> None:
    """Display status of running the post scripts."""
    _scripts(console, results, "Post Script")


def generate_workflow(
    console: Console, results: CommandResult | CustomCommandResult | None
) -> None:
    """Display status of generating the workflow."""
    _scripts(console, [results], "Generate Workflow")


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


class PegasusWorkflowProgress(Progress):
    """A custom Progress subclass for tracking Pegasus workflow progress.

    This class extends the Progress class to create a table-based progress tracker
    specifically for Pegasus workflows. It allows updating and rendering a table
    with row IDs and results.

    Example:

    .. code-block:: python
        with PegasusWorkflowProgress(table_max_rows=1) as progress:
            task = progress.add_task("Task", total=100)
            for row in range(100):
                time.sleep(0.1)
                progress.update(task, advance=1)
                progress.update_table((f"{row}", f"Result for row {row}"))

    Reference: <https://github.com/Textualize/rich/discussions/482#discussioncomment-9353238>`__.

    :param args: Positional arguments passed to the parent Progress class
    :param kwargs: Keyword arguments passed to the parent Progress class
    """

    def __init__(
        self,
        cols: dict[str, str],
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """__init__ _summary_.

        _extended_summary_

        :param cols: _description_
        :type cols: dict[str, str]
        """
        self.table = Table()
        self.cols = cols
        super().__init__(*args, **kwargs)
        self.update_table()

    def update_table(
        self, status: dict[str, dict[str, dict[str, str | int | float]]] | None = None
    ) -> None:
        """update_table _summary_.

        _extended_summary_

        :param status: _description_, defaults to None
        :type status: tuple[str] | None, optional
        """
        if status is None:
            return

        result = status["dags"]["root"]
        self.table = table = Table()
        row = []
        is_failing = False
        for name, column in self.cols.items():
            table.add_column(name)
            text: str | Spinner = str(result[column])
            if (
                name == "Failed"
                or (name == "%" and result[self.cols["Failed"]])
                or (name == "State" and result[self.cols["State"]] == "Failure")
            ):
                text = f"[bold red]{text}[/bold red]"
                is_failing = True
            elif (
                name == "Succeeded"
                or (name == "%" and result[self.cols["Succeeded"]])
                or (name == "State" and result[self.cols["State"]] == "Success")
            ):
                text = f"[bold green]{text}[/bold green]"
            elif name == "State" and result[self.cols["State"]] == "Running":
                style = "bold blue" if is_failing else "bold yellow"
                text = Spinner("moon", text=f"[{style}]Running...[/{style}]")

            row.append(text)

        table.add_row(*row)

    def get_renderable(self) -> ConsoleRenderable | RichCast | str:
        """get_renderable _summary_.

        _extended_summary_

        :return: _description_
        :rtype: ConsoleRenderable | RichCast | str
        """
        return Group(self.table, *self.get_renderables())
