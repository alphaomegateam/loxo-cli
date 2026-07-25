from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Mapping

import httpx

from loxo_cli.config import LoxoSettings
from loxo_cli.errors import LoxoError
from loxo_cli.retry import NOTICE_THRESHOLD as _DEFAULT_NOTICE_THRESHOLD
from loxo_cli.retry import (
    Outcome,
    RetryPolicy,
    classify_exception,
    classify_response,
    next_delay,
    parse_retry_after,
)

# Default per-attempt timeout, and the ceiling on how long one hung request
# can block. Thirty seconds suits a CLI; a service answering an HTTP request
# should pass a smaller `timeout=` — a retry policy's `max_elapsed` only gates
# whether a *further* retry is allowed, so it cannot bound the attempt in
# flight.
TIMEOUT = 30.0

# Kept for anyone who imported it from this module in 0.6.1. The threshold is
# now per-policy: RetryPolicy.notice_threshold, which defaults to this value.
NOTICE_THRESHOLD = _DEFAULT_NOTICE_THRESHOLD

# Silent for library consumers: the package attaches a NullHandler in
# __init__, and the CLI attaches a stderr handler in __main__. Never log
# headers — that would leak the bearer token.
logger = logging.getLogger(__name__)


def url_for(settings: LoxoSettings, endpoint: str) -> str:
    return f"{settings.base_url}/{settings.slug}/{endpoint.lstrip('/')}"


class _BaseClient:
    """Everything the sync and async clients share.

    Python cannot share a try/except body across sync and async functions,
    so the httpx-to-LoxoError mapping lives here rather than being written
    twice. Only the transport and the sleep differ between the facades.
    """

    def __init__(
        self,
        settings: LoxoSettings,
        *,
        verbose: bool = False,
        retry: RetryPolicy | None = None,
        timeout: float = TIMEOUT,
    ) -> None:
        self._settings = settings
        self._verbose = verbose
        self._retry = retry if retry is not None else RetryPolicy()
        self._timeout = timeout

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Accept": "application/json",
        }

    def _target(self, endpoint: str) -> str:
        return url_for(self._settings, endpoint)

    def _headers(self, json: Any | None) -> dict[str, str] | None:
        return {"Content-Type": "application/json"} if json is not None else None

    def _log(self, method: str, target: str) -> None:
        # Method + URL only. Never headers (would leak the bearer token).
        if self._verbose:
            logger.debug("%s %s", method.upper(), target)

    def _log_retry(self, method: str, target: str, attempt: int, delay: float) -> None:
        # Verbose substitutes its detailed DEBUG line for the terse notice,
        # so the two never double-report the same retry. Without verbose, a
        # wait at or above the policy's threshold is a WARNING: a retry
        # signals degraded service, and an application that configured
        # logging should see it. A shorter wait is not dropped — it drops to
        # DEBUG, because a consumer watching at DEBUG asked for everything.
        if self._verbose:
            logger.debug("%s %s -> retry %d in %.1fs", method.upper(), target, attempt, delay)
            return
        level = logging.WARNING if delay >= self._retry.notice_threshold else logging.DEBUG
        logger.log(level, "Request failed; retrying in %.1fs (attempt %d)...", delay, attempt)

    def _delay_or_raise(
        self,
        *,
        error: LoxoError,
        cause: BaseException,
        outcome: Outcome,
        method: str,
        target: str,
        attempt: int,
        started: float,
    ) -> float:
        """Decide whether to retry: return the delay, or raise the error.

        Shared by both request loops — the decision contains no I/O, so the
        sync and async loops differ only in the HTTP call and the sleep.
        `cause` is the httpx exception this attempt failed with; raising
        `from` it keeps the transport traceback attached to LoxoError.
        """
        error.attempts = attempt
        delay = next_delay(
            attempt=attempt,
            method=method,
            outcome=outcome,
            policy=self._retry,
            elapsed=time.monotonic() - started,
            retry_after=error.retry_after,
        )
        # `is None` deliberately, not truthiness: next_delay legitimately
        # returns 0.0 when the server sends `Retry-After: 0`, and treating
        # that as "give up" would skip a retry the server asked for.
        if delay is None:
            raise error from cause
        self._log_retry(method, target, attempt, delay)
        return delay

    def _map_status_error(
        self, exc: httpx.HTTPStatusError, method: str, endpoint: str
    ) -> LoxoError:
        return LoxoError(
            f"Loxo {method} {endpoint} returned {exc.response.status_code}: "
            f"{exc.response.text[:500]}",
            status_code=exc.response.status_code,
            retry_after=parse_retry_after(exc.response.headers.get("Retry-After")),
        )

    def _map_exception(self, exc: httpx.HTTPError, method: str, endpoint: str) -> LoxoError:
        if isinstance(exc, httpx.TimeoutException):
            return LoxoError(
                f"Loxo {method} {endpoint} timed out", status_code=None, is_timeout=True
            )
        return LoxoError(f"Loxo {method} {endpoint} request failed: {exc}", status_code=None)

    def _decode(self, response: httpx.Response, attempt: int = 1) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            # json.JSONDecodeError subclasses ValueError. A 2xx carrying a
            # non-JSON body (a proxy's HTML error page, a truncated
            # response) must still surface as a LoxoError: every failure out
            # of this client carries a status_code and an attempt count.
            # `attempt` is passed in because this runs after the retry loop
            # succeeded, outside the bookkeeping in _delay_or_raise — without
            # it a body that failed to decode on attempt 3 would report 1.
            error = LoxoError(
                f"Loxo returned {response.status_code} with a non-JSON body: "
                f"{response.text[:500]}",
                status_code=response.status_code,
            )
            error.attempts = attempt
            raise error from exc


class LoxoClient(_BaseClient):
    def __init__(
        self,
        settings: LoxoSettings,
        *,
        verbose: bool = False,
        retry: RetryPolicy | None = None,
        timeout: float = TIMEOUT,
    ) -> None:
        super().__init__(settings, verbose=verbose, retry=retry, timeout=timeout)
        self._http = httpx.Client(
            headers=self._auth_headers(),
            follow_redirects=True,
            timeout=self._timeout,
        )

    def __enter__(self) -> "LoxoClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        target = self._target(endpoint)
        headers = self._headers(json)
        started = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            self._log(method, target)
            try:
                response = self._http.request(
                    method, target, params=params, json=json, headers=headers
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                error = self._map_status_error(exc, method, endpoint)
                outcome = classify_response(exc.response.status_code)
                cause: httpx.HTTPError = exc
            except httpx.TransportError as exc:
                error = self._map_exception(exc, method, endpoint)
                outcome = classify_exception(exc)
                cause = exc
            except httpx.HTTPError as exc:
                # TooManyRedirects / DecodingError: request-level failures that
                # are not transport problems and gain nothing from a replay.
                error = self._map_exception(exc, method, endpoint)
                outcome = "fatal"
                cause = exc
            else:
                return self._decode(response, attempt)

            delay = self._delay_or_raise(
                error=error,
                cause=cause,
                outcome=outcome,
                method=method,
                target=target,
                attempt=attempt,
                started=started,
            )
            time.sleep(delay)

    def get(self, endpoint: str, **kw: Any) -> Any:
        return self.request("GET", endpoint, **kw)

    def post(self, endpoint: str, **kw: Any) -> Any:
        return self.request("POST", endpoint, **kw)

    def put(self, endpoint: str, **kw: Any) -> Any:
        return self.request("PUT", endpoint, **kw)

    def delete(self, endpoint: str, **kw: Any) -> Any:
        return self.request("DELETE", endpoint, **kw)


def build_client(
    settings: LoxoSettings,
    *,
    verbose: bool = False,
    retry: RetryPolicy | None = None,
    timeout: float = TIMEOUT,
) -> LoxoClient:
    return LoxoClient(settings, verbose=verbose, retry=retry, timeout=timeout)


class AsyncLoxoClient(_BaseClient):
    """Async twin of LoxoClient.

    Safe for concurrent use from many tasks. Long-lived services should
    build ONE of these at startup and aclose() it at shutdown so the
    connection pool is reused; the `async with` form is for scripts.
    """

    def __init__(
        self,
        settings: LoxoSettings,
        *,
        verbose: bool = False,
        retry: RetryPolicy | None = None,
        timeout: float = TIMEOUT,
    ) -> None:
        super().__init__(settings, verbose=verbose, retry=retry, timeout=timeout)
        self._http = httpx.AsyncClient(
            headers=self._auth_headers(),
            follow_redirects=True,
            timeout=self._timeout,
        )

    async def __aenter__(self) -> "AsyncLoxoClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        target = self._target(endpoint)
        headers = self._headers(json)
        started = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            self._log(method, target)
            try:
                response = await self._http.request(
                    method, target, params=params, json=json, headers=headers
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                error = self._map_status_error(exc, method, endpoint)
                outcome = classify_response(exc.response.status_code)
                cause: httpx.HTTPError = exc
            except httpx.TransportError as exc:
                error = self._map_exception(exc, method, endpoint)
                outcome = classify_exception(exc)
                cause = exc
            except httpx.HTTPError as exc:
                # TooManyRedirects / DecodingError: request-level failures that
                # are not transport problems and gain nothing from a replay.
                error = self._map_exception(exc, method, endpoint)
                outcome = "fatal"
                cause = exc
            else:
                return self._decode(response, attempt)

            delay = self._delay_or_raise(
                error=error,
                cause=cause,
                outcome=outcome,
                method=method,
                target=target,
                attempt=attempt,
                started=started,
            )
            await asyncio.sleep(delay)

    async def get(self, endpoint: str, **kw: Any) -> Any:
        return await self.request("GET", endpoint, **kw)

    async def post(self, endpoint: str, **kw: Any) -> Any:
        return await self.request("POST", endpoint, **kw)

    async def put(self, endpoint: str, **kw: Any) -> Any:
        return await self.request("PUT", endpoint, **kw)

    async def delete(self, endpoint: str, **kw: Any) -> Any:
        return await self.request("DELETE", endpoint, **kw)


def build_async_client(
    settings: LoxoSettings,
    *,
    verbose: bool = False,
    retry: RetryPolicy | None = None,
    timeout: float = TIMEOUT,
) -> AsyncLoxoClient:
    return AsyncLoxoClient(settings, verbose=verbose, retry=retry, timeout=timeout)
