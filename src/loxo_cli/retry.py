"""Retry policy for Loxo API calls.

Everything here is pure: no I/O, no sleeping, and no clock except the
HTTP-date branch of parse_retry_after, which must compare against now.
Keeping the decisions here is what lets the sync and async clients share
one implementation and differ only in how they sleep.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Literal, Mapping

import httpx

from loxo_cli.errors import ConfigError

Outcome = Literal["throttled", "server", "timeout", "connect", "fatal"]

# HTTP methods safe to replay. This follows HTTP semantics; Loxo's API is
# undocumented and this has NOT been verified against it. If Loxo's PUT
# merges rather than replaces, a replay could differ from a single call.
IDEMPOTENT = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})

# Outcomes a non-idempotent method (POST, PATCH) may still retry, because
# in both cases the request provably did not take effect: 'throttled' is
# the server stating it did not process the request, and 'connect' means
# the connection was never established so the body never left this machine.
# 'server' and 'timeout' are excluded — the request may have been received
# and committed, and replaying it would duplicate a Loxo record.
_SAFE_FOR_NON_IDEMPOTENT = frozenset({"throttled", "connect"})


# A retry wait at or above this many seconds is announced at WARNING. Below
# it the pause is short enough that, for a CLI, silence reads as normal
# latency; above it the terminal would otherwise look frozen. A consumer on a
# request path wants a much lower bar — see RetryPolicy.notice_threshold.
NOTICE_THRESHOLD = 1.0


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 30.0
    # Total wall-clock budget across all attempts of ONE request, checked
    # before each sleep. Without it, max_retries=3 against a server sending
    # Retry-After: 30 permits ~3.5 minutes on a single call.
    max_elapsed: float = 60.0
    # Delay at or above which a retry is announced at WARNING rather than
    # DEBUG. The default suits a CLI. A short request-path policy computes
    # delays well under a second, so every retry it makes would land at
    # DEBUG; set 0.0 to be told about all of them at WARNING. Lives here
    # because this is already the object a consumer passes to tune retries.
    notice_threshold: float = NOTICE_THRESHOLD


def classify_response(status_code: int) -> Outcome:
    if status_code == 429:
        return "throttled"
    if status_code == 408:
        return "timeout"
    if 500 <= status_code < 600:
        return "server"
    return "fatal"


def classify_exception(exc: httpx.TransportError) -> Outcome:
    """Classify a transport-level failure.

    Deliberately narrower than httpx.HTTPError: an HTTPStatusError carries a
    response and belongs in classify_response, and the non-transport
    RequestError subclasses (TooManyRedirects, DecodingError) are not
    meaningfully retryable. The client routes each of those elsewhere.
    """
    # ConnectTimeout subclasses TimeoutException, so it must be checked
    # first: it means the connection was never established, which is a
    # stronger (and safer) statement than a generic timeout.
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return "connect"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    # Any other transport error (RemoteProtocolError, ReadError, ...) is
    # ambiguous about whether the server saw the request. Treat it like a
    # timeout: retried for idempotent methods, never for POST.
    return "timeout"


def should_retry(method: str, outcome: Outcome) -> bool:
    if outcome == "fatal":
        return False
    if method.upper() in IDEMPOTENT:
        return True
    return outcome in _SAFE_FOR_NON_IDEMPOTENT


def parse_retry_after(
    value: str | None, *, now: Callable[[], datetime] | None = None
) -> float | None:
    """Parse a Retry-After header. Returns None when unusable.

    The RFC permits either integer seconds or an HTTP-date, and Loxo's
    behavior is undocumented, so both are supported. An unparseable value
    falls back to ordinary backoff rather than raising.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return max(0.0, float(int(text)))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    current = now() if now is not None else datetime.now(timezone.utc)
    return max(0.0, (when - current).total_seconds())


def compute_delay(
    attempt: int,
    policy: RetryPolicy,
    *,
    retry_after: float | None = None,
    jitter: Callable[[], float] = random.random,
) -> float:
    """Delay before retry number `attempt` (0-based).

    A server-supplied Retry-After wins, capped at policy.max_delay.
    Otherwise exponential backoff, scaled into [0.5, 1.0] of the computed
    value so concurrent retriers spread out instead of thundering.
    """
    if retry_after is not None:
        return min(retry_after, policy.max_delay)
    raw = min(policy.base_delay * (2**attempt), policy.max_delay)
    return raw * (0.5 + 0.5 * jitter())


def next_delay(
    *,
    attempt: int,
    method: str,
    outcome: Outcome,
    policy: RetryPolicy,
    elapsed: float,
    retry_after: float | None = None,
    jitter: Callable[[], float] = random.random,
) -> float | None:
    """How long to wait before attempt number `attempt` (1-based), or None to give up.

    `elapsed` is wall-clock seconds spent on this request so far.
    """
    if attempt > policy.max_retries:
        return None
    if not should_retry(method, outcome):
        return None
    delay = compute_delay(attempt - 1, policy, retry_after=retry_after, jitter=jitter)
    if elapsed + delay > policy.max_elapsed:
        return None
    return delay


def resolve_max_retries(flag: int | None, env: Mapping[str, str] | None = None) -> int:
    """Resolve max_retries from --retries, then LOXO_MAX_RETRIES, then the default."""
    environ = os.environ if env is None else env
    if flag is not None:
        return max(0, flag)
    raw = environ.get("LOXO_MAX_RETRIES")
    if raw is None or not raw.strip():
        return RetryPolicy().max_retries
    try:
        return max(0, int(raw.strip()))
    except ValueError as exc:
        raise ConfigError(f"LOXO_MAX_RETRIES must be an integer, got {raw!r}.") from exc
