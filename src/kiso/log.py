"""Kiso logging utilities."""

from __future__ import annotations

import contextlib
import logging
from concurrent.futures import ProcessPoolExecutor
from logging.handlers import QueueHandler, QueueListener
from multiprocessing import Queue
from typing import TYPE_CHECKING, Any

import enoslib as en

from kiso import constants as const

if TYPE_CHECKING:
    from collections.abc import Generator


def init_logging(level: int = logging.INFO, **kwargs: Any) -> None:  # noqa: ANN401
    """init_logging _summary_.

    _extended_summary_

    :param level: _description_, defaults to logging.INFO
    :type level: int, optional
    :yield: _description_
    :rtype: _type_
    """
    # Initialize basic logging using EnOSlib's init_logging method.
    en.init_logging(level=level, **kwargs)
    en.set_config(ansible_stdout="noop")

    #  Create a logging filter to only include logs from kiso.*, enoslib.infra.*,
    # and fablib.*
    class _Filter(logging.Filter):
        """Filter to exclude log records from specific modules."""

        def filter(self, record: logging.LogRecord) -> bool:
            """Filter out log records from specific modules."""
            name = record.name
            return (
                name.startswith("kiso")
                or name.startswith("enoslib")
                or name.startswith("fablib")
            )

    for handler in logging.getLogger().handlers:
        handler.addFilter(_Filter())


@contextlib.contextmanager
def get_process_pool_executor(
    max_workers: int = const.MAX_PROCESSES,
    **kwargs: Any,  # noqa: ANN401
) -> Generator[ProcessPoolExecutor, None, None]:
    """Create a process pool executor with integrated logging.

    Yields a ProcessPoolExecutor configured to send log records to a shared queue,
    with a QueueListener to handle log record routing. Ensures proper logging
    across worker processes and manages the logging lifecycle.

    :param max_workers: Maximum number of worker processes, defaults to system's
    MAX_PROCESSES
    :type max_workers: int, optional
    :yield: Configured ProcessPoolExecutor
    :rtype: Generator[ProcessPoolExecutor, None, None]
    """
    queue: Queue = Queue()
    handler = logging.getLogger().handlers[0]
    listener = QueueListener(queue, handler)
    listener.start()
    yield ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_init_worker,
        initargs=(queue, logging.getLogger().level),
        **kwargs,
    )
    listener.stop()


def _init_worker(queue: Queue, level: int) -> None:
    """Initialize a worker process with a logger that sends log records to a queue.

    This function sets up logging for a worker process by configuring a logger
    with a specific name, log level, and a QueueHandler to send log records
    to a shared logging queue.

    :param queue: Queue to which log records will be sent
    :type queue: Queue
    :param level: Logging level for the worker process logger
    :type level: int
    """
    logger = logging.getLogger()
    logger.setLevel(level)
    handler = QueueHandler(queue)
    logger.handlers = [handler]
    en.set_config(ansible_stdout="noop")
