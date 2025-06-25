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

#: Default workflow timeout.
WORKFLOW_TIMEOUT: int = 600

#: HTCondor trust domain.
TRUST_DOMAIN: str = "kiso.scitech.isi.edu"

#: HTCondor port to expose.
HTCONDOR_PORT: int = 9618
