"""Kiso utilities."""

from __future__ import annotations

import logging
import secrets
import shlex
import string
import tempfile
from contextlib import ContextDecorator, suppress
from functools import partial, reduce
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Any

import enoslib as en
from enoslib.api import CommandResult
from enoslib.objects import Roles
from enoslib.task import Environment

from kiso import constants as const
from kiso import edge, utils

if TYPE_CHECKING:
    from types import TracebackType

    from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice
    from enoslib.objects import Roles
    from enoslib.task import Environment

with suppress(ImportError):
    from importlib.metadata import EntryPoints

log = logging.getLogger("kiso")

run_ansible = partial(en.run_ansible, on_error_continue=True)

actions = partial(en.actions, on_error_continue=True)

undefined = type("undefined", (), {})


def resolve_labels(labels: Roles, label_names: list[str]) -> Roles:
    """Resolve and combine labels based on provided label names.

    Filters or combines labels from a given Roles object based on the specified label
    names. If no label names are provided, returns the original labels. If multiple
    label names are given, merges the corresponding labels using a logical OR
    operation.

    :param labels: Collection of labels to resolve from
    :type labels: Roles
    :param label_names: List of label names to filter or combine
    :type label_names: list[str]
    :return: Resolved labels matching the specified label names
    :rtype: Roles
    """
    if not label_names:
        return labels

    return (
        labels[label_names[0]]
        if len(label_names) == 1
        else reduce(
            lambda a, b: labels[a]
            if isinstance(a, str)
            else a | labels[b]
            if isinstance(b, str)
            else b,
            label_names,
        )
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


def split_labels(split: Roles, labels: Roles) -> tuple[Roles, Roles]:
    """Split a set of labels into virtual machines and containers.

    Separates the input labels into two groups: non-edge virtual machines and edge
    containers.

    :param split: The complete set of labels to be split
    :type split: Roles
    :param labels: The reference label set containing the chameleon-edge label
    :type labels: Roles
    :return: A tuple containing (non-edge VMs, edge containers)
    :rtype: tuple[Roles, Roles]
    """
    vms = split - labels["chameleon-edge"]
    containers = split & labels["chameleon-edge"]

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

    expand_user = edge._execute(container, f"echo {path_p.parts[0]}")
    if expand_user.rc == 0:
        expand_user = expand_user.stdout
    else:
        log.error("Can't expand user <%s>", path_p.parts[0])
        expand_user = path_p.parts[0]

    resolved_path = Path(expand_user) / path_p.relative_to(path_p.parts[0])
    return resolved_path if isinstance(path, Path) else str(resolved_path)


def command_result(
    container: ChameleonDevice, status: dict[str, Any], task_name: str | None
) -> CommandResult:
    """Create a CommandResult object from a dictionary.

    Creates a CommandResult object from a dictionary containing container execution
    status information. The dictionary should contain the following keys:
    - exit_code: The exit code of the command
    - output: The output of the command

    :param container: The Chameleon device where the command was executed
    :type container: ChameleonDevice
    :param status: The dictionary containing container execution status information
    :type status: dict[str, Any]
    :param task_name: Optional name for the task, defaults to "container-task"
    :type task_name: str | None
    :return: A CommandResult object containing container execution status information
    :rtype: CommandResult
    """
    status_code = (
        const.STATUS_STARTED
        if status["exit_code"] is None
        else const.STATUS_OK
        if status["exit_code"] == 0
        else const.STATUS_FAILED
    )
    rc = None if status["exit_code"] is None else int(status["exit_code"])
    return CommandResult(
        container.address,
        task_name or "container-task",
        status_code,
        {"stdout": status["output"].strip(), "stderr": "", "rc": rc},
    )


def get_runner(kind: str) -> EntryPoint:
    """Retrieve a specific workflow runner entry point by its kind.

    Searches for and returns an entry point from the "kiso.experiment" group matching the specified kind.

    :param kind: The name of the workflow runner entry point to retrieve
    :type kind: str
    :return: The matching workflow runner entry point
    :rtype: EntryPoint
    :raises ValueError: If no entry point with the given kind is found
    """  # noqa: E501
    runner = _get_single(const.KISO_EXPERIMENT_ENTRY_POINT_GROUP, kind)
    try:
        return runner.load()
    except ModuleNotFoundError as e:
        raise ValueError(f"No runner found for kind {kind}") from e


def get_software(name: str) -> EntryPoint:
    """Retrieve a specific software installer entry point by its name.

    Searches for and returns an entry point from the "kiso.software" group matching the specified name.

    :param name: The name of the software installer entry point to retrieve
    :type name: str
    :return: The matching software entry point
    :rtype: EntryPoint
    :raises ValueError: If no entry point with the given name is found
    """  # noqa: E501
    software = _get_single(const.KISO_SOFTWARE_ENTRY_POINT_GROUP, name)
    try:
        return software.load()
    except ModuleNotFoundError as e:
        raise ValueError(f"No software found for kind {name}") from e


def get_deployment(name: str) -> EntryPoint:
    """Retrieve a specific software installer entry point by its name.

    Searches for and returns an entry point from the "kiso.deployment" group matching the specified name.

    :param name: The name of the software installer entry point to retrieve
    :type name: str
    :return: The matching software entry point
    :rtype: EntryPoint
    :raises ValueError: If no entry point with the given name is found
    """  # noqa: E501
    software = _get_single(const.KISO_DEPLOYMENT_ENTRY_POINT_GROUP, name)
    try:
        return software.load()
    except ModuleNotFoundError as e:
        raise ValueError(f"No software found for kind {name}") from e


def run_script(
    container: ChameleonDevice,
    script: Path,
    *args: str,
    workdir: str | None = None,
    user: str | None = None,
    poll_interval: int = const.POLL_INTERVAL,
    task_name: str | None = None,  # noqa: ARG001
) -> CommandResult:
    """Run a script on a container with specified parameters.

    Uploads a script to a container, sets appropriate permissions, executes it, and
    handles cleanup.

    :param container: The target container device for script execution
    :type container: ChameleonDevice
    :param script: Path to the script to be executed
    :type script: Path
    :param args: Optional additional arguments to pass to the script
    :type args: str
    :param workdir: Working directory for script execution, defaults to system
    temporary directory
    :type workdir: str | None, optional
    :param user: User to execute the script as, defaults to root
    :type user: str | None, optional
    :param poll_interval: Interval between script execution status checks
    :type poll_interval: int, optional
    :param task_name: name for the task, defaults to None
    :type task_name: str | None, optional
    :return: _description_
    :rtype: CommandResult
    """
    workdir = shlex.quote(str(utils.expanduser(container, workdir or const.TMP_DIR)))

    with (
        tempfile.NamedTemporaryFile(mode="w") as file,
        script.open() as script_file,
    ):
        file.write(script_file.read())
        file.seek(0)

        remote_script = f"{workdir}/{Path(file.name).name}"
        edge._upload_file(container, file.name, workdir)
        edge._ch_perms_remotely(container, Path(remote_script), user=user, perms="+x")

        status = edge.execute(
            container,
            remote_script,
            *args,
            user=user,
            workdir=workdir,
            poll_interval=poll_interval,
        )
        log.debug(
            "Script <%s> executed on container <%s>, status <%d> <%s> <%s>",
            script,
            container.address,
            status.rc,
            status.stdout,
            status.stderr,
        )

        edge._rm_remotely(container, Path(remote_script))
        return status


def _get_single(group: str, name: str) -> EntryPoint:
    """Retrieve a single entry point from a specified group by its name.

    Searches through all registered entry points in a given group and returns
    the entry point that matches the specified name.

    :param group: The entry point group to search within
    :type group: str
    :param name: The name of the specific entry point to retrieve
    :type name: str
    :return: The matching entry point
    :rtype: EntryPoint
    :raises ValueError: If no entry point with the given name is found in the group
    """
    all_eps: dict | EntryPoints = entry_points()
    if isinstance(all_eps, dict):
        all_eps = all_eps.get(group, [])
    else:
        all_eps = all_eps.select(group=group)

    for ep in all_eps:
        if ep.name == name:
            return ep

    raise ValueError(f"No such entrypoint <{group}>:{name}> found")


class experiment_state(ContextDecorator):
    """kiso_state _summary_.

    _extended_summary_

    :param ContextDecorator: _description_
    :type ContextDecorator: _type_
    """

    def __init__(
        self, env: Environment, *args: str | int, on_error_continue: bool = True
    ) -> None:
        """__init__ _summary_.

        _extended_summary_

        :param env: _description_
        :type env: Environment
        :param on_error_continue: _description_, defaults to True
        :type on_error_continue: bool, optional
        """
        self.env = env
        self.arg = args[-1]
        self.status = None
        self.on_error_continue = on_error_continue

        for index, arg in enumerate(args):
            if index == len(args) - 1:
                break

            if arg not in self.env:
                self.env[arg] = {}

            self.env = self.env[arg]

    def __enter__(self) -> experiment_state:
        """__enter__ _summary_.

        _extended_summary_

        :return: _description_
        :rtype: experiment_state
        """
        self.status = self.env.setdefault(self.arg, const.STATUS_STARTED)
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
        self.status = self.env[self.arg] = (
            const.STATUS_OK if exc_type is None else const.STATUS_FAILED
        )

        if self.on_error_continue is True:
            return True  # Suppress exceptions

        return None  # Do not suppress exceptions
