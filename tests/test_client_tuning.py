"""Knobs a request-path consumer needs: retry notices and the per-attempt timeout.

Both defaults here are tuned for a CLI, where a sub-second pause is invisible
noise and thirty seconds of patience costs nothing. A service answering an HTTP
request wants the opposite on both counts, so each is overridable without
changing what an existing caller sees.
"""

import logging

import httpx
import pytest
import respx

from loxo_cli.client import (
    TIMEOUT,
    AsyncLoxoClient,
    LoxoClient,
    build_async_client,
    build_client,
)
from loxo_cli.config import LoxoSettings
from loxo_cli.retry import RetryPolicy

SETTINGS = LoxoSettings(api_key="testkey", slug="acme", base_url="https://app.loxo.co/api")
PEOPLE = "https://app.loxo.co/api/acme/people"

# The portal's policy: one retry, a short cap, a ~5s budget. With no
# Retry-After the delay lands in [0.25, 0.5) — under the 1.0s default
# threshold, which is exactly the case that used to log nothing at all.
REQUEST_PATH = RetryPolicy(max_retries=1, max_delay=2.0, max_elapsed=5.0)


def _bare_throttle_then_ok():
    """A 429 with NO Retry-After, so the delay comes from backoff alone."""
    return [
        httpx.Response(429, text="slow down"),
        httpx.Response(200, json={"people": []}),
    ]


def _notices(caplog):
    return [r for r in caplog.records if "retrying in" in r.getMessage()]


# --- notice threshold -------------------------------------------------------


@respx.mock
def test_sub_threshold_retry_emits_no_warning_by_default(caplog):
    respx.get(PEOPLE).mock(side_effect=_bare_throttle_then_ok())
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS, retry=REQUEST_PATH) as client:
            client.get("people")
    assert [r for r in _notices(caplog) if r.levelno == logging.WARNING] == []


@respx.mock
def test_sub_threshold_retry_still_emits_at_debug(caplog):
    # Silently dropping the event surprises a consumer who asked, by turning
    # on DEBUG, to be told everything.
    respx.get(PEOPLE).mock(side_effect=_bare_throttle_then_ok())
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS, retry=REQUEST_PATH) as client:
            client.get("people")
    notices = _notices(caplog)
    assert len(notices) == 1
    assert notices[0].levelno == logging.DEBUG


@respx.mock
def test_zero_threshold_promotes_a_sub_threshold_retry_to_warning(caplog):
    policy = RetryPolicy(max_retries=1, max_delay=2.0, max_elapsed=5.0, notice_threshold=0.0)
    respx.get(PEOPLE).mock(side_effect=_bare_throttle_then_ok())
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS, retry=policy) as client:
            client.get("people")
    notices = _notices(caplog)
    assert len(notices) == 1
    assert notices[0].levelno == logging.WARNING
    assert "attempt 1" in notices[0].getMessage()


@respx.mock
async def test_zero_threshold_works_on_the_async_client(caplog):
    policy = RetryPolicy(max_retries=1, max_delay=2.0, max_elapsed=5.0, notice_threshold=0.0)
    respx.get(PEOPLE).mock(side_effect=_bare_throttle_then_ok())
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        async with AsyncLoxoClient(SETTINGS, retry=policy) as client:
            await client.get("people")
    notices = _notices(caplog)
    assert len(notices) == 1
    assert notices[0].levelno == logging.WARNING


@respx.mock
def test_raising_the_threshold_demotes_a_long_retry(caplog):
    policy = RetryPolicy(notice_threshold=60.0)
    respx.get(PEOPLE).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "5"}),
            httpx.Response(200, json={"people": []}),
        ]
    )
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS, retry=policy) as client:
            client.get("people")
    notices = _notices(caplog)
    assert len(notices) == 1
    assert notices[0].levelno == logging.DEBUG


def test_default_notice_threshold_is_one_second():
    assert RetryPolicy().notice_threshold == 1.0


@respx.mock
def test_verbose_still_replaces_the_notice_even_at_zero_threshold(caplog):
    # Unchanged from 0.6.1: verbose substitutes its detailed DEBUG line, so
    # the two never double-report one retry.
    policy = RetryPolicy(max_retries=1, max_delay=2.0, max_elapsed=5.0, notice_threshold=0.0)
    respx.get(PEOPLE).mock(side_effect=_bare_throttle_then_ok())
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS, verbose=True, retry=policy) as client:
            client.get("people")
    assert _notices(caplog) == []
    assert [r for r in caplog.records if "-> retry 1 in" in r.getMessage()]


# --- per-attempt timeout ----------------------------------------------------


def test_sync_client_defaults_to_the_module_timeout():
    with LoxoClient(SETTINGS) as client:
        assert client._http.timeout == httpx.Timeout(TIMEOUT)


def test_sync_client_accepts_a_custom_timeout():
    with LoxoClient(SETTINGS, timeout=5.0) as client:
        assert client._http.timeout == httpx.Timeout(5.0)


async def test_async_client_defaults_to_the_module_timeout():
    async with AsyncLoxoClient(SETTINGS) as client:
        assert client._http.timeout == httpx.Timeout(TIMEOUT)


async def test_async_client_accepts_a_custom_timeout():
    async with AsyncLoxoClient(SETTINGS, timeout=5.0) as client:
        assert client._http.timeout == httpx.Timeout(5.0)


@respx.mock
def test_custom_timeout_reaches_the_wire(caplog):
    seen = {}

    def handler(request):
        seen["timeout"] = request.extensions.get("timeout")
        return httpx.Response(200, json={"people": []})

    respx.get(PEOPLE).mock(side_effect=handler)
    with LoxoClient(SETTINGS, timeout=5.0) as client:
        client.get("people")
    assert seen["timeout"] == {"connect": 5.0, "read": 5.0, "write": 5.0, "pool": 5.0}


# --- both knobs through the builders ----------------------------------------


def test_build_client_passes_timeout_and_policy():
    policy = RetryPolicy(notice_threshold=0.0)
    client = build_client(SETTINGS, timeout=5.0, retry=policy)
    try:
        assert client._http.timeout == httpx.Timeout(5.0)
        assert client._retry.notice_threshold == 0.0
    finally:
        client.close()


def test_build_client_defaults_are_unchanged():
    client = build_client(SETTINGS)
    try:
        assert client._http.timeout == httpx.Timeout(TIMEOUT)
        assert client._retry.notice_threshold == 1.0
    finally:
        client.close()


async def test_build_async_client_passes_timeout_and_policy():
    policy = RetryPolicy(notice_threshold=0.0)
    client = build_async_client(SETTINGS, timeout=5.0, retry=policy)
    try:
        assert client._http.timeout == httpx.Timeout(5.0)
        assert client._retry.notice_threshold == 0.0
    finally:
        await client.aclose()


async def test_build_async_client_defaults_are_unchanged():
    client = build_async_client(SETTINGS)
    try:
        assert client._http.timeout == httpx.Timeout(TIMEOUT)
    finally:
        await client.aclose()


def test_timeout_is_keyword_only():
    with pytest.raises(TypeError):
        LoxoClient(SETTINGS, 5.0)  # type: ignore[misc]
