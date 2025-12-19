"""Constants for Kiso configuration and system settings.

This class defines various default configuration parameters and system-wide
constants used throughout the Kiso application, including process management, user
settings, and HTCondor-related configurations.
"""

#: Default maximum number of processes to use when distributing tasks across processes.
MAX_PROCESSES: int = 5

#: Default root user.
ROOT_USER: str = "root"

#: Default root user.
TMP_DIR: str = "/tmp"  # noqa: S108

#: Default Kiso user.
KISO_USER: str = "kiso"

#: Default polling interval.
POLL_INTERVAL: int = 3

#: Default command timeout.
COMMAND_TIMEOUT: int = 300

#: Default workflow timeout.
WORKFLOW_TIMEOUT: int = 600

#: HTCondor trust domain.
TRUST_DOMAIN: str = "kiso.scitech.isi.edu"

#: HTCondor port to expose.
HTCONDOR_PORT: int = 9618

#: SSHD port to expose.
SSHD_PORT: int = 22

#: Task started status.
STATUS_STARTED: str = "STARTED"

#: Task skipped status.
STATUS_SKIPPED: str = "SKIPPED"

#: Task completed status.
STATUS_OK: str = "OK"

#: Task failed status.
STATUS_FAILED: str = "FAILED"

#: Task timeout status.
STATUS_TIMEOUT: str = "TIMEOUT"

#: Entry point group for software installers.
KISO_SOFTWARE_ENTRY_POINT_GROUP: str = "kiso.software"

#: Entry point group for deployment installers.
KISO_DEPLOYMENT_ENTRY_POINT_GROUP: str = "kiso.deployment"

#: Entry point group for workflow runners.
KISO_EXPERIMENT_ENTRY_POINT_GROUP: str = "kiso.experiment"

#: Map status code to console color.
STATUS_COLOR_MAP: dict[str, str] = {
    STATUS_STARTED: "green",
    STATUS_SKIPPED: "blue",
    STATUS_OK: "green",
    STATUS_FAILED: "red",
    STATUS_TIMEOUT: "yellow",
}
