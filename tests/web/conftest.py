"""Fixtures for Web tests with in-process instrument and file doubles."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from queue import Queue
from types import SimpleNamespace

import pytest


@pytest.fixture
def treatment_thread_executor(monkeypatch):
    """Keep local conversion doubles visible while testing concurrent workflows."""
    import treatment_api

    monkeypatch.setattr(
        treatment_api, "_cpu_executor",
        lambda worker_count: ThreadPoolExecutor(max_workers=worker_count),
    )
    # Production uses a spawned Manager for inter-process progress. These doubles
    # share memory, so an ordinary queue exercises the same progress callbacks.
    monkeypatch.setattr(
        treatment_api, "get_context",
        lambda _method: SimpleNamespace(
            Manager=lambda: nullcontext(SimpleNamespace(Queue=Queue)),
        ),
    )
