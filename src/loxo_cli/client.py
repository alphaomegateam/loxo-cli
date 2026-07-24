from __future__ import annotations

import sys
import time
from typing import Any, Mapping

import httpx

from loxo_cli.config import LoxoSettings
from loxo_cli.errors import LoxoError
from loxo_cli.retry import (
    RetryPolicy,
    classify_exception,
    classify_response,
    next_delay,
    parse_retry_after,
)

TIMEOUT = 30.0


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
    ) -> None:
        self._settings = settings
        self._verbose = verbose
        self._retry = retry if retry is not None else RetryPolicy()

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
            print(f"{method.upper()} {target}", file=sys.stderr)

    def _log_retry(self, method: str, target: str, attempt: int, delay: float) -> None:
        if self._verbose:
            print(
                f"{method.upper()} {target} -> retry {attempt} in {delay:.1f}s",
                file=sys.stderr,
            )

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

    def _decode(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        return response.json()


class LoxoClient(_BaseClient):
    def __init__(
        self,
        settings: LoxoSettings,
        *,
        verbose: bool = False,
        retry: RetryPolicy | None = None,
    ) -> None:
        super().__init__(settings, verbose=verbose, retry=retry)
        self._http = httpx.Client(
            headers=self._auth_headers(),
            follow_redirects=True,
            timeout=TIMEOUT,
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
            except httpx.HTTPError as exc:
                error = self._map_exception(exc, method, endpoint)
                outcome = classify_exception(exc)
            else:
                return self._decode(response)

            error.attempts = attempt
            delay = next_delay(
                attempt=attempt,
                method=method,
                outcome=outcome,
                policy=self._retry,
                elapsed=time.monotonic() - started,
                retry_after=error.retry_after,
            )
            if delay is None:
                raise error
            self._log_retry(method, target, attempt, delay)
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
) -> LoxoClient:
    return LoxoClient(settings, verbose=verbose, retry=retry)
