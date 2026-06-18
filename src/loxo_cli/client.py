from __future__ import annotations

import sys
from typing import Any, Mapping

import httpx

from loxo_cli.config import LoxoSettings
from loxo_cli.errors import LoxoError

TIMEOUT = 30.0


def url_for(settings: LoxoSettings, endpoint: str) -> str:
    return f"{settings.base_url}/{settings.slug}/{endpoint.lstrip('/')}"


class LoxoClient:
    def __init__(self, settings: LoxoSettings, *, verbose: bool = False) -> None:
        self._settings = settings
        self._verbose = verbose
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Accept": "application/json",
            },
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
        target = url_for(self._settings, endpoint)
        if self._verbose:
            # Method + URL only. Never headers (would leak the bearer token).
            print(f"{method.upper()} {target}", file=sys.stderr)
        headers = {"Content-Type": "application/json"} if json is not None else None
        try:
            response = self._http.request(method, target, params=params, json=json, headers=headers)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LoxoError(
                f"Loxo {method} {endpoint} timed out", status_code=None, is_timeout=True
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LoxoError(
                f"Loxo {method} {endpoint} returned {exc.response.status_code}: "
                f"{exc.response.text[:500]}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise LoxoError(
                f"Loxo {method} {endpoint} request failed: {exc}", status_code=None
            ) from exc
        if not response.content:
            return None
        return response.json()

    def get(self, endpoint: str, **kw: Any) -> Any:
        return self.request("GET", endpoint, **kw)

    def post(self, endpoint: str, **kw: Any) -> Any:
        return self.request("POST", endpoint, **kw)

    def put(self, endpoint: str, **kw: Any) -> Any:
        return self.request("PUT", endpoint, **kw)

    def delete(self, endpoint: str, **kw: Any) -> Any:
        return self.request("DELETE", endpoint, **kw)


def build_client(settings: LoxoSettings, *, verbose: bool = False) -> LoxoClient:
    return LoxoClient(settings, verbose=verbose)
