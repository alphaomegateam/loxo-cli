"""apaginate must reproduce every guard the sync drive loop has."""

import httpx
import respx

from loxo_cli.client import AsyncLoxoClient
from loxo_cli.config import LoxoSettings
from loxo_cli.pagination import apaginate

SETTINGS = LoxoSettings(api_key="k", slug="acme", base_url="https://app.loxo.co/api")
BASE = "https://app.loxo.co/api/acme/things"


async def _collect(client, **kw):
    return [item async for item in apaginate(client, "things", **kw)]


@respx.mock
async def test_scroll_id_pagination():
    respx.get(BASE).mock(
        side_effect=[
            httpx.Response(200, json={"things": [{"id": 1}], "scroll_id": "s1"}),
            httpx.Response(200, json={"things": [{"id": 2}], "scroll_id": "s2"}),
            httpx.Response(200, json={"things": []}),
        ]
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        items = await _collect(client, scheme="scroll_id", items_key="things", per_page=None)
    assert [i["id"] for i in items] == [1, 2]


@respx.mock
async def test_page_pagination_stops_on_total_count():
    respx.get(BASE).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "results": [{"id": 1}, {"id": 2}],
                    "pagination": {"total_count": 2, "per_page": 2, "current_page": 1},
                },
            )
        ]
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        items = await _collect(client, scheme="page", items_key="results", per_page=2)
    assert [i["id"] for i in items] == [1, 2]


@respx.mock
async def test_page_pagination_without_total_count_keeps_going():
    respx.get(BASE).mock(
        side_effect=[
            httpx.Response(200, json={"results": [{"id": 1}], "pagination": {}}),
            httpx.Response(200, json={"results": [{"id": 2}], "pagination": {}}),
            httpx.Response(200, json={"results": []}),
        ]
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        items = await _collect(client, scheme="page", items_key="results", per_page=1)
    assert [i["id"] for i in items] == [1, 2]


@respx.mock
async def test_after_id_pagination():
    respx.get(BASE).mock(
        side_effect=[
            httpx.Response(200, json=[{"id": 1}, {"id": 2}]),
            httpx.Response(200, json=[{"id": 3}]),
            httpx.Response(200, json=[]),
        ]
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        items = await _collect(client, scheme="after_id")
    assert [i["id"] for i in items] == [1, 2, 3]


@respx.mock
async def test_after_id_stops_when_cursor_does_not_advance():
    route = respx.get(BASE).mock(return_value=httpx.Response(200, json=[{"id": 1}, {"id": 2}]))
    async with AsyncLoxoClient(SETTINGS) as client:
        items = await _collect(client, scheme="after_id")
    # The duplicate second page is NOT re-yielded, and we stop instead of
    # looping forever.
    assert [i["id"] for i in items] == [1, 2]
    assert route.call_count == 2
