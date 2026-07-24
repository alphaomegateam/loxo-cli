"""Shared fixtures.

Retries are on by default from 0.6.0, so any test provoking a 5xx, a
timeout, or a 429 would otherwise sleep through real backoff. Both sleeps
are patched to no-ops for the whole suite; tests that care about the
delay values assert on the pure helpers in loxo_cli.retry instead.
"""

import asyncio
import time

import pytest


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
