"""Kiso utilities."""

from __future__ import annotations

import logging
import secrets
import string
from contextlib import ContextDecorator, suppress
from functools import partial, reduce
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import TYPE_CHECKING

import enoslib as en
from enoslib.objects import Roles
from enoslib.task import Environment

from kiso import constants as const

if TYPE_CHECKING:
    from types import TracebackType

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
            lambda a, b: (
                labels[a] | labels[b]
                if isinstance(a, str)
                else a | labels[b]
                if isinstance(b, str)
                else b
            ),
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
    """Retrieve a specific deployment installer entry point by its name.

    Searches for and returns an entry point from the "kiso.deployment" group matching the specified name.

    :param name: The name of the deployment installer entry point to retrieve
    :type name: str
    :return: The matching deployment entry point
    :rtype: EntryPoint
    :raises ValueError: If no entry point with the given name is found
    """  # noqa: E501
    software = _get_single(const.KISO_DEPLOYMENT_ENTRY_POINT_GROUP, name)
    try:
        return software.load()
    except ModuleNotFoundError as e:
        raise ValueError(f"No software found for kind {name}") from e


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
    """Context manager and decorator for tracking the state of an experiment step.

    Stores a status value in a nested environment dictionary under the provided
    key path. On entry the key is initialised to ``STATUS_STARTED`` (unless it
    already has a value). On exit the key is updated to ``STATUS_OK`` or
    ``STATUS_FAILED`` depending on whether an exception was raised.

    Can be used either as a ``with`` block or as a function decorator.
    """

    def __init__(
        self, env: Environment, *args: str | int, on_error_continue: bool = True
    ) -> None:
        """Initialise the context manager.

        Traverses ``env`` using all but the last element of ``args`` as nested
        keys, creating intermediate dicts as needed. The last element of
        ``args`` is used as the state key on enter/exit.

        :param env: The EnOSlib task environment used to persist step state
        :type env: Environment
        :param args: Key path into ``env``; intermediate keys are created
            automatically, the final key stores the status value
        :type args: str | int
        :param on_error_continue: When ``True`` exceptions are suppressed on
            exit (default). Set to ``False`` to let exceptions propagate.
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
        """Enter the context, initialising the state key to ``STATUS_STARTED``.

        If the key already exists in the environment its current value is
        preserved in ``self.status`` so callers can detect a previously
        successful run and skip re-execution.

        :return: This ``experiment_state`` instance
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
        """Exit the context, set the final status, and optionally suppress exceptions.

        Sets the state key to ``STATUS_OK`` when no exception occurred, or
        ``STATUS_FAILED`` when an exception was raised. Returns ``True`` to
        suppress the exception when ``on_error_continue`` is ``True``.

        :param exc_type: Exception type, or ``None`` if no exception was raised
        :type exc_type: type | None
        :param exc_val: Exception instance, or ``None`` if no exception was raised
        :type exc_val: BaseException | None
        :param exc_tb: Traceback, or ``None`` if no exception was raised
        :type exc_tb: TracebackType | None
        :return: ``True`` to suppress exceptions when ``on_error_continue`` is
            ``True``, otherwise ``None`` to propagate them
        :rtype: bool | None
        """
        self.status = self.env[self.arg] = (
            const.STATUS_OK if exc_type is None else const.STATUS_FAILED
        )

        if self.on_error_continue is True:
            return True  # Suppress exceptions

        return None  # Do not suppress exceptions
