"""Unit tests for kiso.log utilities."""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor
from logging.handlers import QueueHandler
from multiprocessing import Queue
from typing import cast
from unittest.mock import patch

import kiso.log as kiso_log
from kiso.log import init_logging


def test_init_logging_does_not_raise() -> None:
    with patch("kiso.log.en.init_logging"), patch("kiso.log.en.set_config"):
        init_logging(level=logging.DEBUG)


def test_init_logging_info_level() -> None:
    with (
        patch("kiso.log.en.init_logging") as mock_init,
        patch("kiso.log.en.set_config"),
    ):
        init_logging(level=logging.INFO)
        mock_init.assert_called_once_with(level=logging.INFO)


def test_init_logging_filter_applied() -> None:
    """Filter added to root logger handlers after init_logging."""
    handler = logging.StreamHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        with patch("kiso.log.en.init_logging"), patch("kiso.log.en.set_config"):
            init_logging(level=logging.WARNING)
        # At least one filter was added
        assert any(len(h.filters) > 0 for h in root.handlers)
    finally:
        root.removeHandler(handler)


def test_filter_passes_kiso_records() -> None:
    """The internal filter must pass kiso.* records."""
    handler = logging.StreamHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        with patch("kiso.log.en.init_logging"), patch("kiso.log.en.set_config"):
            init_logging()
        _filter = cast("logging.Filter", root.handlers[-1].filters[-1])
        record = logging.LogRecord("kiso.task", logging.INFO, "", 0, "msg", (), None)
        assert _filter.filter(record) is True
    finally:
        root.removeHandler(handler)


def test_filter_blocks_other_records() -> None:
    """The internal filter must block records from unrelated modules."""
    handler = logging.StreamHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        with patch("kiso.log.en.init_logging"), patch("kiso.log.en.set_config"):
            init_logging()
        _filter = cast("logging.Filter", root.handlers[-1].filters[-1])
        record = logging.LogRecord(
            "unrelated.module", logging.INFO, "", 0, "msg", (), None
        )
        assert _filter.filter(record) is False
    finally:
        root.removeHandler(handler)


def test_filter_passes_enoslib_records() -> None:
    """The internal filter must pass enoslib.* records."""
    handler = logging.StreamHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        with patch("kiso.log.en.init_logging"), patch("kiso.log.en.set_config"):
            init_logging()
        _filter = cast("logging.Filter", root.handlers[-1].filters[-1])
        record = logging.LogRecord(
            "enoslib.infra", logging.INFO, "", 0, "msg", (), None
        )
        assert _filter.filter(record) is True
    finally:
        root.removeHandler(handler)


def test_get_process_pool_executor_yields_executor() -> None:
    """get_process_pool_executor yields a ProcessPoolExecutor."""
    handler = logging.StreamHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        with kiso_log.get_process_pool_executor(max_workers=1) as executor:
            assert isinstance(executor, ProcessPoolExecutor)
    finally:
        root.removeHandler(handler)


def test_init_worker_sets_up_queue_handler() -> None:
    """_init_worker configures a QueueHandler on the root logger."""
    queue: Queue = Queue()
    with patch("kiso.log.en.set_config"):
        kiso_log._init_worker(queue, logging.DEBUG)

    root = logging.getLogger()
    assert any(isinstance(h, QueueHandler) for h in root.handlers)
    # Clean up added handler
    for h in list(root.handlers):
        if isinstance(h, QueueHandler):
            root.removeHandler(h)
            break
