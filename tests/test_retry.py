from datetime import datetime, timedelta, timezone

import httpx
import pytest

from loxo_cli.errors import ConfigError
from loxo_cli.retry import (
    RetryPolicy,
    classify_exception,
    classify_response,
    compute_delay,
    next_delay,
    parse_retry_after,
    resolve_max_retries,
    should_retry,
)

POLICY = RetryPolicy()


@pytest.mark.parametrize(
    "status,expected",
    [
        (429, "throttled"),
        (408, "timeout"),
        (500, "server"),
        (503, "server"),
        (404, "fatal"),
        (401, "fatal"),
        (422, "fatal"),
    ],
)
def test_classify_response(status, expected):
    assert classify_response(status) == expected


@pytest.mark.parametrize(
    "exc,expected",
    [
        (httpx.ConnectError("boom"), "connect"),
        # ConnectTimeout subclasses TimeoutException, so ordering matters:
        # it is a connect failure, not an ambiguous read timeout.
        (httpx.ConnectTimeout("boom"), "connect"),
        (httpx.ReadTimeout("boom"), "timeout"),
        (httpx.WriteTimeout("boom"), "timeout"),
        (httpx.PoolTimeout("boom"), "timeout"),
        (httpx.RemoteProtocolError("boom"), "timeout"),
    ],
)
def test_classify_exception(exc, expected):
    assert classify_exception(exc) == expected


@pytest.mark.parametrize("method", ["GET", "HEAD", "PUT", "DELETE", "OPTIONS", "get"])
@pytest.mark.parametrize("outcome", ["throttled", "server", "timeout", "connect"])
def test_idempotent_methods_retry_everything_but_fatal(method, outcome):
    assert should_retry(method, outcome) is True


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
def test_no_method_retries_fatal(method):
    assert should_retry(method, "fatal") is False


@pytest.mark.parametrize(
    "outcome,expected",
    [
        ("throttled", True),  # server says it did not process the request
        ("connect", True),  # connection never established; body never sent
        ("server", False),  # may have been received and committed
        ("timeout", False),  # may have been received and committed
    ],
)
def test_post_retries_only_when_the_request_cannot_have_landed(outcome, expected):
    assert should_retry("POST", outcome) is expected
    # PATCH is non-idempotent too and gets the same treatment as POST.
    assert should_retry("PATCH", outcome) is expected


def test_parse_retry_after_seconds():
    assert parse_retry_after("120") == 120.0
    assert parse_retry_after("0") == 0.0


def test_parse_retry_after_http_date():
    now = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
    later = now + timedelta(seconds=90)
    header = later.strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert parse_retry_after(header, now=lambda: now) == pytest.approx(90.0, abs=1.0)


def test_parse_retry_after_past_date_clamps_to_zero():
    now = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
    header = (now - timedelta(seconds=60)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert parse_retry_after(header, now=lambda: now) == 0.0


@pytest.mark.parametrize("value", [None, "", "   ", "soon", "not-a-date"])
def test_parse_retry_after_rejects_unusable_values(value):
    assert parse_retry_after(value) is None


def test_compute_delay_grows_exponentially_and_caps():
    full = lambda: 1.0  # noqa: E731 — jitter at its maximum
    assert compute_delay(0, POLICY, jitter=full) == pytest.approx(0.5)
    assert compute_delay(1, POLICY, jitter=full) == pytest.approx(1.0)
    assert compute_delay(2, POLICY, jitter=full) == pytest.approx(2.0)
    assert compute_delay(99, POLICY, jitter=full) == pytest.approx(POLICY.max_delay)


def test_compute_delay_jitter_stays_in_the_upper_half():
    for attempt in range(5):
        low = compute_delay(attempt, POLICY, jitter=lambda: 0.0)
        high = compute_delay(attempt, POLICY, jitter=lambda: 1.0)
        assert low == pytest.approx(high / 2)
        assert low > 0


def test_retry_after_wins_over_backoff_and_is_capped():
    assert compute_delay(0, POLICY, retry_after=7.0) == 7.0
    assert compute_delay(0, POLICY, retry_after=999.0) == POLICY.max_delay


def test_next_delay_stops_after_max_retries():
    assert (
        next_delay(attempt=3, method="GET", outcome="server", policy=POLICY, elapsed=0.0)
        is not None
    )
    assert next_delay(attempt=4, method="GET", outcome="server", policy=POLICY, elapsed=0.0) is None


def test_next_delay_converts_the_1_based_attempt_to_a_0_based_backoff():
    # attempt=1 is the FIRST retry, so it must use compute_delay(0) — one
    # base_delay, not two. An off-by-one here silently doubles every backoff.
    assert next_delay(
        attempt=1,
        method="GET",
        outcome="server",
        policy=POLICY,
        elapsed=0.0,
        jitter=lambda: 1.0,
    ) == pytest.approx(POLICY.base_delay)


def test_next_delay_returns_zero_not_none_for_retry_after_zero():
    # `Retry-After: 0` is a legitimate "retry immediately". The client checks
    # `delay is None`, so 0.0 must survive as a real delay; a truthiness check
    # anywhere on this path would turn it into "give up".
    delay = next_delay(
        attempt=1,
        method="GET",
        outcome="throttled",
        policy=POLICY,
        elapsed=0.0,
        retry_after=0.0,
    )
    assert delay == 0.0
    assert delay is not None


def test_next_delay_stops_when_policy_forbids_the_method():
    assert (
        next_delay(attempt=1, method="POST", outcome="server", policy=POLICY, elapsed=0.0) is None
    )


def test_next_delay_stops_when_the_budget_would_be_exceeded():
    policy = RetryPolicy(max_elapsed=10.0)
    assert (
        next_delay(
            attempt=1,
            method="GET",
            outcome="throttled",
            policy=policy,
            elapsed=9.0,
            retry_after=5.0,
        )
        is None
    )
    assert (
        next_delay(
            attempt=1,
            method="GET",
            outcome="throttled",
            policy=policy,
            elapsed=1.0,
            retry_after=5.0,
        )
        == 5.0
    )


def test_max_retries_zero_disables_retrying():
    policy = RetryPolicy(max_retries=0)
    assert (
        next_delay(attempt=1, method="GET", outcome="throttled", policy=policy, elapsed=0.0) is None
    )


def test_resolve_max_retries_precedence():
    assert resolve_max_retries(1, env={"LOXO_MAX_RETRIES": "9"}) == 1
    assert resolve_max_retries(None, env={"LOXO_MAX_RETRIES": "9"}) == 9
    assert resolve_max_retries(None, env={}) == RetryPolicy().max_retries
    assert resolve_max_retries(None, env={"LOXO_MAX_RETRIES": "  "}) == RetryPolicy().max_retries
    assert resolve_max_retries(0, env={}) == 0


def test_resolve_max_retries_rejects_garbage_env():
    with pytest.raises(ConfigError):
        resolve_max_retries(None, env={"LOXO_MAX_RETRIES": "lots"})


def test_resolve_max_retries_clamps_negatives():
    assert resolve_max_retries(-5, env={}) == 0
