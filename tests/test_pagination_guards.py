"""Infinite-loop guards for the scroll_id and page schemes.

Each test models an endpoint that ignores its cursor. Without the guard the
drive loop never terminates, so every mock here is capped: once the cap is
exceeded the route raises instead of the suite hanging, and a regression
shows up as a failure with a readable message rather than a wedged run.
"""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from loxo_cli.client import AsyncLoxoClient, LoxoClient
from loxo_cli.config import LoxoSettings
from loxo_cli.pagination import apaginate, paginate

SETTINGS = LoxoSettings(api_key="k", slug="acme", base_url="https://app.loxo.co/api")
BASE = "https://app.loxo.co/api/acme/things"

CAP = 8


class LoopGuardTripped(AssertionError):
    """Raised by a mock when the client keeps refetching past the cap."""


def _stuck_scroll_endpoint():
    """An endpoint that hands back the same scroll_id on every response."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] > CAP:
            raise LoopGuardTripped(f"scroll paginator did not stop after {CAP} requests")
        return httpx.Response(200, json={"things": [{"id": calls["n"]}], "scroll_id": "STUCK"})

    return handler


def _pinned_page_endpoint(last_page: int = 3):
    """An endpoint that always reports current_page=1 and no total_count.

    It still serves real content per requested `page`, going empty after
    `last_page`, so a paginator whose page number advances terminates and
    one that stands still refetches page 1 forever.
    """
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] > CAP:
            raise LoopGuardTripped(f"page paginator did not stop after {CAP} requests")
        page = int(parse_qs(urlparse(str(request.url)).query)["page"][0])
        results = [] if page > last_page else [{"id": page}]
        return httpx.Response(200, json={"results": results, "pagination": {"current_page": 1}})

    return handler


@respx.mock
def test_scroll_stops_when_scroll_id_repeats():
    route = respx.get(BASE).mock(side_effect=_stuck_scroll_endpoint())
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "things", scheme="scroll_id", items_key="things"))
    # Second response repeats the cursor we just sent: stop, and do NOT
    # re-yield that page.
    assert [i["id"] for i in items] == [1]
    assert route.call_count == 2


@respx.mock
async def test_apaginate_scroll_stops_when_scroll_id_repeats():
    route = respx.get(BASE).mock(side_effect=_stuck_scroll_endpoint())
    async with AsyncLoxoClient(SETTINGS) as client:
        items = [
            i async for i in apaginate(client, "things", scheme="scroll_id", items_key="things")
        ]
    assert [i["id"] for i in items] == [1]
    assert route.call_count == 2


@respx.mock
def test_scroll_first_page_behavior_is_unchanged():
    """No cursor has been sent yet on request one, so nothing may be skipped."""
    route = respx.get(BASE).mock(
        side_effect=[
            httpx.Response(200, json={"things": [{"id": 1}], "scroll_id": "s1"}),
            httpx.Response(200, json={"things": [{"id": 2}], "scroll_id": "s2"}),
            httpx.Response(200, json={"things": []}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "things", scheme="scroll_id", items_key="things"))
    assert [i["id"] for i in items] == [1, 2]
    assert route.call_count == 3


@respx.mock
def test_page_advances_when_server_pins_current_page():
    route = respx.get(BASE).mock(side_effect=_pinned_page_endpoint())
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "things", scheme="page", items_key="results", per_page=1))
    assert [i["id"] for i in items] == [1, 2, 3]
    assert route.call_count == 4
    pages = [parse_qs(urlparse(str(c.request.url)).query)["page"][0] for c in route.calls]
    assert pages == ["1", "2", "3", "4"]


@respx.mock
async def test_apaginate_page_advances_when_server_pins_current_page():
    route = respx.get(BASE).mock(side_effect=_pinned_page_endpoint())
    async with AsyncLoxoClient(SETTINGS) as client:
        items = [
            i
            async for i in apaginate(
                client, "things", scheme="page", items_key="results", per_page=1
            )
        ]
    assert [i["id"] for i in items] == [1, 2, 3]
    assert route.call_count == 4


def test_loop_guard_cap_is_enforced_by_the_mock():
    """The caps above are what keep a regression from hanging the suite."""
    handler = _stuck_scroll_endpoint()
    request = httpx.Request("GET", BASE)
    for _ in range(CAP):
        handler(request)
    with pytest.raises(LoopGuardTripped):
        handler(request)
