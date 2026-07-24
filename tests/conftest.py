"""Shared fixtures.

Retries are on by default from 0.6.0, so any test provoking a 5xx, a
timeout, or a 429 would otherwise sleep through real backoff. Both sleeps
are patched to no-ops for the whole suite; tests that care about the
delay values assert on the pure helpers in loxo_cli.retry instead.
"""

import asyncio
import logging
import time

import pytest


@pytest.fixture(autouse=True)
def _reset_package_logger():
    """Undo whatever a CLI invocation did to the `loxo_cli` logger.

    The CLI attaches a stderr handler and sets a level on the package
    logger. Both are process-global, so without this a test that invokes
    the CLI would leave a handler bound to a dead capture stream and change
    what later library-level tests see.
    """
    logger = logging.getLogger("loxo_cli")
    handlers = list(logger.handlers)
    level = logger.level
    propagate = logger.propagate
    yield
    logger.handlers = handlers
    logger.setLevel(level)
    logger.propagate = propagate


@pytest.fixture(autouse=True)
def slept(monkeypatch) -> list[float]:
    """Record requested sleep durations without actually sleeping."""
    recorded: list[float] = []

    def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    async def fake_async_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(time, "sleep", fake_sleep)
    monkeypatch.setattr(asyncio, "sleep", fake_async_sleep)
    return recorded
