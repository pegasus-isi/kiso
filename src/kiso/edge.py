"""Common functions used by Kiso to interact with ChameleonEdge devices."""

from __future__ import annotations

import logging
import os
import shlex
import time
from contextlib import redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING

import enoslib as en
from enoslib.api import CommandResult

from kiso import constants as const
from kiso import utils

if TYPE_CHECKING:
    from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice

if hasattr(en, "ChameleonEdge"):
    from zunclient.common.apiclient.exceptions import GatewayTimeout
else:
    GatewayTimeout = utils.undefined

log = logging.getLogger(__name__)


def upload(
    container: ChameleonDevice,
    src: Path | str,
    dst: Path | str,
    user: str | None = None,
) -> CommandResult:
    """Upload a file or directory to a Chameleon device.

    This function uploads a file or directory to a Chameleon device using the
    ChameleonEdge API. It handles file and directory uploads, setting ownership
    of uploaded files, and handling potential upload timeouts.

    :param container: The Chameleon device to upload files to
    :type container: ChameleonDevice
    :param src: Source path of file or directory to upload
    :type src: Path | str
    :param dst: Destination path on the container
    :type dst: Path | str
    :param user: User to set as owner of uploaded files (defaults to root)
    :type user: str, optional
    :raises ValueError: If source does not exist or destination is invalid
    :return: CommandResult containing upload status
    :rtype: CommandResult
    """
    status = CommandResult(
        container.address,
        "upload",
        const.STATUS_OK,
        {"stdout": "", "stderr": "", "rc": 0},
    )
    src = Path(src)
    dst = Path(dst)

    # Check the source exists locally
    if not _exists_locally(src):
        raise ValueError(f"Source {src} doesn't exist", src)

    # The Chameleon Edge API does not resolve destinations with a ~, i.e., ~kiso is not
    # resolved to /home/kiso, so we need to expand and resolve it
    dst = _resolve_remotely(container, dst)
    log.debug("Resolved destination directory is <%s>", dst)

    # The upload method of the Chameleon Edge API requires the destination to be a
    # directory.
    if _is_dir_remote(container, dst) is False:
        raise ValueError(
            f"Destination {dst} is either not a directory or can't be accessed", dst
        )

    try:
        _upload_file(container, src, dst)
    except (Exception, GatewayTimeout):
        if src.is_file():
            log.error("Failed to upload file <%s> to <%s>", src, dst)
            log.debug("Failed to upload file <%s> to <%s>", src, dst, exc_info=True)
            status.rc = 1
            status.status = const.STATUS_FAILED
        else:
            log.debug(
                "Failed to upload directory <%s> to <%s>, will retry uploading one "
                "file at a time",
                src,
                dst,
            )
            _upload_directory(container, src, dst)

    _ch_perms_remotely(container, dst, user)

    return status


def download(
    container: ChameleonDevice,
    src: Path | str,
    dst: Path | str,
) -> CommandResult:
    """Download a file or directory from a Chameleon device.

    This function downloads a file or directory from a Chameleon device using the
    ChameleonEdge API. It handles file and directory downloads, setting ownership
    of downloaded files, and handling potential download timeouts.

    :param container: The Chameleon device to download files from
    :type container: ChameleonDevice
    :param src: Source path of file or directory to download
    :type src: str
    :param dst: Destination path on the host
    :type dst: str
    :raises ValueError: If source does not exist or destination is invalid
    :return: CommandResult containing download status
    :rtype: CommandResult
    """
    status = CommandResult(
        container.address,
        "upload",
        const.STATUS_OK,
        {"stdout": "", "stderr": "", "rc": 0},
    )
    src = Path(src)
    dst = Path(dst)

    # The download method of the Chameleon Edge API requires the source to be a
    # directory. Also, it does not resolve destinations with a ~, i.e., ~kiso is not
    # resolved to /home/kiso, so we need to check directory exists and resolve it
    _resolve_remotely(container, src)

    log.debug("Check source <%s> exists", src)
    _exists_remotely(container, src)

    log.debug("Check destination <%s> exists and is a directory", dst)
    if not _exists_locally(dst) or not _is_dir_locally(dst):
        raise ValueError(
            f"Destination {dst} is either not a directory or can't be accessed", dst
        )

    dst = _resolve_locally(dst)

    if _is_file_remote(container, src):
        _download_file(container, src, dst, mktemp=True)
    else:
        try:
            _download_file(container, src, dst, mktemp=False)
        except (Exception, GatewayTimeout):
            _download_directory(container, src, dst)

    return status


def execute(
    container: ChameleonDevice,
    command: Path | str,
    *args: str,
    workdir: Path | str | None = None,
    timeout: int = const.COMMAND_TIMEOUT,
    poll_interval: int = const.POLL_INTERVAL,
    user: str | None = None,
) -> CommandResult:
    """Execute a command on a Chameleon device.

    This function executes a command on a Chameleon device using the ChameleonEdge
    API. It handles command execution, setting ownership of the executed command,
    and handling potential command execution timeouts.

    :param container: The Chameleon device to execute the command on
    :type container: ChameleonDevice
    :param command: The command to execute
    :type command: Path | str
    :param args: Additional arguments to pass to the command
    :type args: str
    :param workdir: Working directory for the command execution, defaults to None
    :type workdir: str, optional
    :param timeout: Maximum time to wait for command execution, defaults to 180
    :type timeout: int, optional
    :param poll_interval: Time between command execution status checks, defaults to 1
    :type poll_interval: int, optional
    :param user: User to set as owner of the executed command (defaults to root)
    :type user: str, optional
    :raises ValueError: If command execution fails
    :return: CommandResult containing execution status and output
    :rtype: CommandResult
    """
    cmd = []
    command = str(command)
    workdir = Path(workdir if workdir else const.TMP_DIR)
    poll_interval = poll_interval or const.POLL_INTERVAL

    # Check if the command is to be executed from a specific directory
    workdir = str(_resolve_remotely(container, workdir))
    cmd.extend(["(", "cd", shlex.quote(str(workdir)), "&&"])

    # Quote the command arguments
    cmd.append(command)
    if args:
        cmd.extend([shlex.quote(arg) for arg in args])

    status_file = f"{const.TMP_DIR}/{utils.get_random_string(length=5)}"

    # Check if the command already has a redirect to stdout
    stdout = len({">", ">>", "&>", "&>>", "2>&1"}.intersection(set(args))) == 0
    if stdout:
        cmd.extend([">", f"{status_file}.out"])

    # Check if the command already has a redirect to stderr
    stderr = len({"2>", "2>>", "&>", "&>>", "1>&2"}.intersection(set(args))) == 0
    if stderr:
        cmd.extend(["2>", f"{status_file}.log"])

    cmd.extend(
        [
            ")",
            ";",
            "echo",
            "$?",
            ">",
            f"{status_file}.done",
            ";",
            "exit",
            "`",
            "cat",
            f"{status_file}.done",
            "`",
        ]
    )

    start_time = time.time()
    result = _execute(container, " ".join(cmd), user=user)
    if result.rc is None:
        while timeout == -1 or time.time() - start_time <= timeout:
            is_done = _execute(container, f"cat {status_file}.done", user=user)
            if is_done.rc == 0:
                result.rc = is_done.rc
                break

            time.sleep(poll_interval)
        else:
            result.rc = -1
            result.status = const.STATUS_TIMEOUT
            log.debug("Command did not finish within the timeout <%d>", timeout)

    result.status = const.STATUS_OK if result.rc == 0 else const.STATUS_FAILED

    if stdout:
        result.stdout = _execute(container, f"cat {status_file}.out", user=user).stdout

    if stderr:
        result.stderr = _execute(container, f"cat {status_file}.log", user=user).stderr

    _rm_remotely(
        container, f"{status_file}.out", f"{status_file}.log", f"{status_file}.done"
    )

    return result


def _upload_file(
    container: ChameleonDevice, src: Path, dst: Path, check: bool = False
) -> None:
    """Upload a file to a Chameleon device.

    This function uploads a file to a Chameleon device using the ChameleonEdge
    API. It sets the ownership of the uploaded file and handles potential upload
    timeouts.

    :param container: The Chameleon device to upload files to
    :type container: ChameleonDevice
    :param src: Source path of file to upload
    :type src: Path
    :param dst: Destination path on the container
    :type dst: Path
    :param check: Check file was uploaded successfully, defaults to False
    :type check: bool, optional
    :raises ValueError: If source does not exist or destination is invalid
    """
    with redirect_stdout(Path(os.devnull).open("w")):
        container.upload(str(src), dest=str(dst))
        if check:
            exists = _exists_remotely(container, dst / src.name)
            if exists is False:
                log.warning("File <%s> was not uploaded", dst / src.name)


def _upload_directory(container: ChameleonDevice, src: Path, dst: Path) -> None:
    """Upload a directory to a Chameleon device.

    This function uploads a directory to a Chameleon device using the ChameleonEdge
    API. It sets the ownership of the uploaded directory and handles potential upload
    timeouts.

    :param container: The Chameleon device to upload files to
    :type container: ChameleonDevice
    :param src: Source path of directory to upload
    :type src: Path
    :param dst: Destination path on the container
    :type dst: Path
    :raises ValueError: If source does not exist or destination is invalid
    """
    # If the source is a directory, create a destination directory with the
    # same name
    log.debug("Create directory <%s> on edge", dst / src.name)
    _mkdir_remotely(container, dst / src.name)

    # The Chameleon Edge API's upload method times out after ~60 seconds.
    # Uploading  an entire directory is less likely to time out. To minimize the
    # chances of time outs, we walk over the source directory. We create directories
    # as necessary and upload files one at a time. If the file is itself too large
    # and the method times out, then there is no work around for it
    first = True
    for file in Path(src).rglob("**"):
        _dst = dst / file.relative_to(src.parent)
        if file.is_dir():
            log.debug("Create directory <%s> on edge", _dst)
            _mkdir_remotely(container, _dst)
        elif file.is_file():
            try:
                log.debug("Upload file <%s> to <%s>", file, _dst.parent)
                _upload_file(container, file, _dst.parent, check=first)
                first = False
            except GatewayTimeout:
                log.error("Failed to upload file <%s> to <%s>", file, _dst.parent)
                log.debug(
                    "Failed to upload file <%s> to <%s>",
                    file,
                    _dst.parent,
                    exc_info=True,
                )


def _download_file(
    container: ChameleonDevice,
    src: Path,
    dst: Path,
    mktemp: bool = True,
    check: bool = False,
) -> None:
    """Download a file from a Chameleon device.

    This function downloads a file from a Chameleon device using the ChameleonEdge
    API. It sets the ownership of the downloaded file and handles potential download
    timeouts.

    :param container: The Chameleon device to download files from
    :type container: ChameleonDevice
    :param src: Source path of file to download
    :type src: Path
    :param dst: Destination path on the host
    :type dst: Path
    :param mktemp: Whether to create a temporary directory on the Chameleon device
    :type mktemp: bool, optional
    :param check: Check the file was downloaded successfully, defaults to False
    :type check: bool, optional
    :raises ValueError: If source does not exist or destination is invalid
    """
    if mktemp:
        # Make a temp directory on the container
        tmpdir = Path(const.TMP_DIR) / utils.get_random_string(5)
        _mkdir_remotely(container, tmpdir)

        # Copy the src file to the temporary directory
        _cp_remotely(container, src, tmpdir)

    with redirect_stdout(Path(os.devnull).open("w")):
        container.download(str(tmpdir) if mktemp else str(src), str(dst))
        if check:
            exists = _exists_locally(dst / src.name)
            if exists is False:
                log.warning("File <%s> was not downloaded", dst / src.name)

    if mktemp:
        # Remove the temporary directory
        _rm_remotely(container, tmpdir)


def _download_directory(container: ChameleonDevice, src: Path, dst: Path) -> None:
    """Download a directory from a Chameleon device.

    This function downloads a directory from a Chameleon device using the ChameleonEdge
    API. It sets the ownership of the downloaded directory and handles potential
    download timeouts.

    :param container: The Chameleon device to download files from
    :type container: ChameleonDevice
    :param src: Source path of directory to download
    :type src: Path
    :param dst: Destination path on the host
    :type dst: Path
    :param user: User to set as owner of downloaded directory (defaults to root)
    :type user: str, optional
    :raises ValueError: If source does not exist or destination is invalid
    """
    # Fetch all files in the source directory
    cmd = f"find {src} -type f"
    ls_files = _execute(container, cmd)

    # Make a temp directory on the container
    tmpdir = Path(const.TMP_DIR) / utils.get_random_string(5)
    _mkdir_remotely(container, tmpdir)

    # The Chameleon Edge API's download method times out after ~60 seconds.
    # Downloading an entire directory is more likely to time out. To minimize the
    # chances of time outs, we walk over the source directory. We create
    # directories as necessary and download files one at a time. If the file is
    # itself too large and the method times out, then there is no work around for it
    for file in ls_files.splitlines():
        file = Path(file)
        _dst = dst / file.parent.relative_to(src)
        # Make the destination directory if it does not exist
        _dst.mkdir(parents=True, exist_ok=True)

        # Copy the src file to the temporary directory
        _cp_remotely(container, file, tmpdir)

        # Download the file from the temporary directory to the destination
        try:
            _download_file(container, tmpdir, _dst, mktemp=False)
        except GatewayTimeout:
            log.error("Failed to download file <%s> to <%s>", file, _dst)
            log.debug("Failed to upload file <%s> to <%s>", file, _dst, exc_info=True)

        # Remove the file from the temporary directory
        _rm_remotely(container, tmpdir / file.name)

    # Remove the temporary directory
    _rm_remotely(container, tmpdir)


def _exists_locally(src: Path) -> bool:
    """Check if the source file or directory exists.

    This function checks if the source file or directory exists locally.

    :param src: Source path of file or directory to upload
    :type src: Path
    :raises ValueError: If source does not exist
    :return: True if the source exists, False otherwise
    :rtype: bool
    """
    return src.exists()


def _resolve_locally(src: Path) -> Path:
    """Resolve the source file or directory for a Chameleon device.

    This function resolves the source file or directory for a Chameleon device
    based on the provided source path. If the source path is a directory, it is
    returned as is. If the source path is a file, the parent directory is returned.

    :param src: Source path of file or directory to upload
    :type src: Path
    :return: The resolved source directory
    :rtype: Path
    :raises ValueError: If source is not a directory or file
    """
    _exists_locally(src)
    return Path(src).expanduser().resolve()


def _is_dir_locally(dst: Path) -> bool:
    """Check if a path is a directory on the ChameleonEdge host.

    :param dst: Destination path on the ChameleonEdge host
    :type dst: Path
    :return: True if the path is a directory, False otherwise
    :rtype: bool
    """
    return dst.is_dir()


def _exists_remotely(container: ChameleonDevice, dst: Path) -> bool:
    """Check if the destination file or directory exists on the Chameleon device.

    This function checks if the destination file or directory exists on the Chameleon
    device. If the destination does not exist, a ValueError is raised.

    :param container: The Chameleon device to check the destination on
    :type container: ChameleonDevice
    :param dst: Destination path on the container
    :type dst: Path
    :raises ValueError: If destination does not exist
    """
    cmd = f"[ -e {shlex.quote(str(dst))} ]"
    result = _execute(container, cmd)
    return result.rc == 0


def _resolve_remotely(container: ChameleonDevice, dst: Path) -> Path:
    """Resolve the destination directory for a Chameleon device.

    This function resolves the destination directory for a Chameleon device
    based on the provided destination path. If the destination path is a
    directory, it is returned as is. If the destination path is a file, the
    parent directory is returned.

    :param container: The Chameleon device to upload files to
    :type container: ChameleonDevice
    :param dst: Destination path on the container
    :type dst: Path
    :return: The resolved destination directory
    :rtype: Path
    :raises ValueError: If destination is not a directory or file
    """
    if dst.is_absolute() or str(dst)[0] != "~":
        return dst

    expand_user = _execute(container, f"echo {dst.parts[0]}")
    if expand_user.rc == 0:
        expand_user = expand_user.stdout
    else:
        log.error("Can't expand user <%s>", dst.parts[0])
        expand_user = dst.parts[0]

    return Path(expand_user) / dst.relative_to(dst.parts[0])


def _is_dir_remote(container: ChameleonDevice, dst: Path) -> bool:
    """Check if a path is a directory on the ChameleonEdge host.

    :param container: ChameleonEdge host
    :type container: ChameleonDevice
    :param dst: Destination path on the ChameleonEdge host
    :type dst: Path
    :return: True if the path is a directory, False otherwise
    :rtype: bool
    """
    cmd = f"cd {shlex.quote(str(dst))} && pwd"
    is_dir = _execute(container, cmd)
    return is_dir.rc == 0


def _is_file_remote(container: ChameleonDevice, dst: Path) -> bool:
    """Check if a path is a file on the ChameleonEdge host.

    :param container: ChameleonEdge host
    :type container: ChameleonDevice
    :param dst: Destination path on the ChameleonEdge host
    :type dst: Path
    :return: True if the path is a file, False otherwise
    :rtype: bool
    """
    cmd = f"[ -f {shlex.quote(str(dst))} ]"
    is_dir = _execute(container, cmd)
    return is_dir.rc == 0


def _ch_perms_remotely(
    container: ChameleonDevice,
    dst: Path,
    user: str | None = None,
    perms: str | None = None,
) -> CommandResult | None:
    """Set ownership and permissions on a file or directory on a Chameleon device.

    This function sets the ownership and sets permissions on files or directories on a
    Chameleon device using the ChameleonEdge API.

    :param container: The Chameleon device to set ownership on
    :type container: ChameleonDevice
    :param dst: Destination path on the container
    :type dst: Path
    :param user: User to set as owner of the file or directory (defaults to root)
    :type user: str | None, optional
    :param perms: Permissions to set on the file or directory (defaults to None)
    :type perms: str | None, optional
    :return: CommandResult containing execution status and output
    :rtype: CommandResult | None
    """
    cmd = ""
    if user:
        cmd = f"chown -R {user}:{user} {shlex.quote(str(dst))} ;"

    if perms:
        cmd = f"{cmd} chmod {perms} {shlex.quote(str(dst))}"

    if user or perms:
        return _execute(container, cmd)

    return None


def _mkdir_remotely(container: ChameleonDevice, *dst: Path) -> CommandResult:
    """Create a directory on a Chameleon device.

    This function creates a directory on a Chameleon device using the ChameleonEdge
    API.

    :param container: The Chameleon device to create the directory on
    :type container: ChameleonDevice
    :param dst: Destination path on the container
    :type dst: Path
    :return: CommandResult containing execution status and output
    :rtype: CommandResult
    """
    cmd = f"mkdir -p {shlex.quote(str(dst))}"
    return _execute(container, cmd)


def _rm_remotely(container: ChameleonDevice, *dst: Path | str) -> CommandResult:
    """Remove a directory on a Chameleon device.

    This function removes a directory on a Chameleon device using the ChameleonEdge
    API.

    :param container: The Chameleon device to remove the directory on
    :type container: ChameleonDevice
    :param dst: Destination path on the container
    :type dst: Path | str
    :return: CommandResult containing execution status and output
    :rtype: CommandResult
    """
    args = " ".join([shlex.quote(str(_dst)) for _dst in dst])
    cmd = f"rm -rf {args}"
    _execute(container, cmd)


def _cp_remotely(container: ChameleonDevice, src: Path, dst: Path) -> CommandResult:
    """Copy a file to and on the same Chameleon device.

    This function copies a file to and on the same Chameleon device using the
    ChameleonEdge API.

    :param container: The Chameleon device to copy files to and from
    :type container: ChameleonDevice
    :param src: Source path of file to copy
    :type src: Path
    :param dst: Destination path on the container
    :type dst: Path
    :return: CommandResult containing execution status and output
    :rtype: CommandResult
    """
    cmd = f"cp {shlex.quote(str(src))} {shlex.quote(str(dst))}"
    return _execute(container, cmd)


def _execute(
    container: ChameleonDevice,
    command: str,
    user: str | None = None,
    task_name: str | None = None,
) -> CommandResult:
    """Execute a command on a Chameleon device.

    This function executes a command on a Chameleon device using the ChameleonEdge
    API.

    :param container: The Chameleon device to execute the command on
    :type container: ChameleonDevice
    :param command: The command to execute
    :type command: str
    :param user: User to execute the command as, defaults to None
    :type user: str, optional
    :param task_name: name for the task, defaults to None
    :type task_name: str | None, optional
    :return: CommandResult containing execution status and output
    :rtype: CommandResult
    """
    with redirect_stdout(Path(os.devnull).open("w")):
        cmd = f"sh -c {shlex.quote(command)}"

        # Check if the command is to be executed as a specific user
        if user:
            cmd = f"sudo -u {shlex.quote(user)} {cmd}"

        result = container.execute(cmd)
        result = utils.command_result(container, result, task_name=task_name)
        log.debug(
            "Run command <%s> on container <%s>, status <%s> stdout <%s> stderr <%s>",
            cmd,
            container.address,
            result.rc,
            result.stdout,
            result.stderr,
        )
        return result
