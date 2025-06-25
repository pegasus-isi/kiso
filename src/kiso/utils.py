"""_summary_.

_extended_summary_
"""

from __future__ import annotations

import logging
import secrets
import string
from concurrent.futures import ThreadPoolExecutor
from contextlib import ContextDecorator
from functools import partial, reduce
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import enoslib as en
from rich.console import ConsoleRenderable, Group, RichCast
from rich.progress import Progress
from rich.spinner import Spinner
from rich.table import Table

from kiso.errors import SkipError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import TracebackType

    from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice
    from enoslib.objects import Roles
    from enoslib.task import Environment

log = logging.getLogger("kiso")


def resolve_roles(roles: Roles, role_names: list[str]) -> Roles:
    """Resolve and combine roles based on provided role names.

    Filters or combines roles from a given Roles object based on the specified role
    names. If no role names are provided, returns the original roles. If multiple
    role names are given, merges the corresponding roles using a logical OR
    operation.

    :param roles: Collection of roles to resolve from
    :type roles: Roles
    :param role_names: List of role names to filter or combine
    :type role_names: list[str]
    :return: Resolved roles matching the specified role names
    :rtype: Roles
    """
    if not role_names:
        return roles

    return (
        roles[role_names[0]]
        if len(role_names) == 1
        else reduce(lambda a, b: roles[a] | roles[b], role_names)
    )


def get_pool_passwd_file() -> str:
    """Get the path to a pool password file, creating it if it doesn't exist.

    Creates a secure password file in the user's home directory with restricted
    permissions.
    If the file already exists, it validates the file permissions.

    :return: Absolute path to the pool password file
    :rtype: str
    :raises ValueError: If the existing file does not have the required 0600 permissions
    """
    pool_passwd_file = Path("~/.kiso/pool_passwd").expanduser()

    if not pool_passwd_file.exists():
        pool_passwd_file.parent.mkdir(parents=True, exist_ok=True)
        with pool_passwd_file.open("w") as f:
            f.write(get_random_string())
        pool_passwd_file.chmod(0o600)
    else:
        if pool_passwd_file.stat().st_mode & 0o777 != 0o600:
            raise ValueError(f"File <{pool_passwd_file}> must have permissions 0600")

    return str(pool_passwd_file)


def get_random_string(length: int = 64) -> str:
    """Generate a cryptographically secure random string.

    Generates a random string of specified length using ASCII letters and digits.

    :param length: Length of the random string to generate, defaults to 64
    :type length: int, optional
    :raises ValueError: If length is not a positive integer
    :return: Randomly generated string
    :rtype: str
    """
    if length <= 0:
        raise ValueError("Length must be a positive integer")

    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def split_roles(split: Roles, roles: Roles) -> tuple[Roles, Roles]:
    """Split a set of roles into virtual machines and containers.

    Separates the input roles into two groups: non-edge virtual machines and edge
    containers.

    :param split: The complete set of roles to be split
    :type split: Roles
    :param roles: The reference role set containing the chameleon-edge role
    :type roles: Roles
    :return: A tuple containing (non-edge VMs, edge containers)
    :rtype: tuple[Roles, Roles]
    """
    vms = split - roles["chameleon-edge"]
    containers = split & roles["chameleon-edge"]

    return vms, containers


def expanduser(container: ChameleonDevice, path: str | Path) -> str | Path:
    """Expand a user's home directory path within a container.

    Resolves paths starting with '~' by executing a shell command in the given container
    to determine the actual home directory path.

    :param container: The Chameleon device (container) to execute the path expansion in
    :type container: ChameleonDevice
    :param path: The path to expand, which may start with '~'
    :type path: str | Path
    :return: The fully resolved path, maintaining the original input type (str or Path)
    :rtype: str | Path
    :raises: Logs an error if home directory expansion fails, but continues with
    original path
    """
    path_s = str(path)
    if path_s[0] != "~":
        return path

    path_p = Path(path)

    expand_user = container.execute(f"sh -c 'echo {path_p.parts[0]}'")
    if expand_user["exit_code"] == 0:
        expand_user = expand_user["output"].strip()
    else:
        log.error("Can't expand user <%s>", path_p.parts[0])
        expand_user = path_p.parts[0]

    resolved_path = Path(expand_user) / path_p.relative_to(path_p.parts[0])
    return resolved_path if isinstance(path, Path) else str(resolved_path)


run_ansible = partial(en.run_ansible, on_error_continue=True)


actions = partial(en.actions, on_error_continue=True)


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
        self, cols: dict[str, str], *args: tuple[Any, ...], **kwargs: dict[str, Any]
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


class container_actions:
    """_summary_.

    _extended_summary_
    """

    def __init__(self, containers: Iterable[ChameleonDevice]) -> None:
        """__init__ _summary_.

        _extended_summary_

        :param containers: _description_
        :type containers: Iterable[ChameleonDevice]
        """
        self._containers: Iterable[ChameleonDevice] = containers
        self._tasks: list[tuple[Callable, tuple, dict]] = []
        self.results: list = []

    def __enter__(self) -> container_actions:
        """__enter__ _summary_.

        _extended_summary_

        :return: _description_
        :rtype: container_actions
        """
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """__exit__ _summary_.

        _extended_summary_

        :param exc_type: _description_
        :type exc_type: type | None
        :param exc_val: _description_
        :type exc_val: BaseException | None
        :param exc_tb: _description_
        :type exc_tb: TracebackType | None
        :raises SkipError: _description_
        :return: _description_
        :rtype: bool | None
        """
        with ThreadPoolExecutor(max_workers=5) as executor:
            for func, args, kwargs in self._tasks:
                futures = [
                    executor.submit(func, container, *args, **kwargs)
                    for container in self._containers
                ]

                for future in futures:
                    try:
                        result = future.result()
                        status = "OK"
                    except Exception as e:
                        result = e
                        status = "FAILED"

                    self.results.append(
                        {
                            "name": func.__name__,
                            "args": args,
                            "kwargs": kwargs,
                            "status": status,
                            "result": result,
                        }
                    )

    def __call__(
        self, func: Callable, *args: tuple[Any, ...], **kwargs: dict[str, Any]
    ) -> None:
        """__call__ _summary_.

        _extended_summary_

        :param func: _description_
        :type func: Callable
        """
        self._tasks.append((func, args, kwargs))


class MyContext(ContextDecorator):
    """MyContext _summary_.

    _extended_summary_

    :param ContextDecorator: _description_
    :type ContextDecorator: _type_
    """

    def __init__(
        self, env: Environment, *args: str | int, rerun_ok: bool = False
    ) -> None:
        """__init__ _summary_.

        _extended_summary_

        :param env: _description_
        :type env: Environment
        :param rerun_ok: _description_, defaults to False
        :type rerun_ok: bool, optional
        """
        self.env = env
        self.arg = args[-1]
        self.rerun_ok = rerun_ok
        self.status = None

        for index, arg in enumerate(args):
            if index == len(args) - 1:
                break

            if arg not in self.env:
                self.env[arg] = {}

            self.env = self.env[arg]

    def __enter__(self) -> MyContext:
        """__enter__ _summary_.

        _extended_summary_

        :raises SkipError: _description_
        :return: _description_
        :rtype: MyContext
        """
        if self.rerun_ok is False and self.env.get(self.arg) == "DONE":
            raise SkipError("This was already DONE")

        self.env[self.arg] = "STARTED"
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """__exit__ _summary_.

        _extended_summary_

        :param exc_type: _description_
        :type exc_type: type | None
        :param exc_val: _description_
        :type exc_val: BaseException | None
        :param exc_tb: _description_
        :type exc_tb: TracebackType | None
        :return: _description_
        :rtype: bool | None
        """
        self.env[self.arg] = "DONE" if exc_type is None else "FAILED"
        return None  # Do not suppress exceptions
