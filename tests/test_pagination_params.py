"""Pins the query parameters each pagination scheme puts on the wire.

The other pagination tests mock a bare URL, so respx matches regardless of
query string — they cannot catch a scheme that starts sending the wrong
params. These can. Two Loxo endpoints (companies, deals) reject `per_page`
with HTTP 422, which is why their commands pass per_page=None; that behavior
is load-bearing and is pinned here.
"""

from urllib.parse import parse_qs, urlparse

import httpx
import respx

from loxo_cli.client import LoxoClient
from loxo_cli.config import LoxoSettings
from loxo_cli.pagination import paginate

SETTINGS = LoxoSettings(api_key="k", slug="acme", base_url="https://app.loxo.co/api")
BASE = "https://app.loxo.co/api/acme/things"


def _queries(route) -> list[dict[str, list[str]]]:
    return [parse_qs(urlparse(str(call.request.url)).query) for call in route.calls]


@respx.mock
def test_scroll_omits_per_page_when_none():
    route = respx.get(BASE).mock(
        side_effect=[
            httpx.Response(200, json={"things": [{"id": 1}], "scroll_id": "s1"}),
            httpx.Response(200, json={"things": []}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        list(paginate(client, "things", scheme="scroll_id", items_key="things", per_page=None))
    queries = _queries(route)
    assert "per_page" not in queries[0]
    assert queries[1]["scroll_id"] == ["s1"]


@respx.mock
def test_scroll_sends_per_page_when_given():
    route = respx.get(BASE).mock(
        side_effect=[
            httpx.Response(200, json={"things": [{"id": 1}], "scroll_id": "s1"}),
            httpx.Response(200, json={"things": []}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        list(paginate(client, "things", scheme="scroll_id", items_key="things", per_page=25))
    assert _queries(route)[0]["per_page"] == ["25"]


@respx.mock
def test_after_id_never_sends_per_page_and_carries_cursor():
    route = respx.get(BASE).mock(
        side_effect=[
            httpx.Response(200, json=[{"id": 7}, {"id": 9}]),
            httpx.Response(200, json=[]),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        list(paginate(client, "things", scheme="after_id", per_page=50))
    queries = _queries(route)
    assert "per_page" not in queries[0]
    assert "per_page" not in queries[1]
    assert "after_id" not in queries[0]
    assert queries[1]["after_id"] == ["9"]


@respx.mock
def test_page_scheme_follows_server_reported_current_page():
    route = respx.get(BASE).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "results": [{"id": 1}],
                    # total_count is deliberately far from exhausted, so the
                    # count-based stop does NOT fire and a second request happens.
                    "pagination": {"total_count": 100, "per_page": 10, "current_page": 4},
                },
            ),
            httpx.Response(200, json={"results": []}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        list(paginate(client, "things", scheme="page", items_key="results", per_page=10))
    queries = _queries(route)
    assert queries[0]["page"] == ["1"]
    # The server said it served page 4, so the next request is page 5 — not 2.
    assert queries[1]["page"] == ["5"]
    assert queries[0]["per_page"] == ["10"]


@respx.mock
def test_caller_supplied_params_survive_on_every_page():
    route = respx.get(BASE).mock(
        side_effect=[
            httpx.Response(200, json={"things": [{"id": 1}], "scroll_id": "s1"}),
            httpx.Response(200, json={"things": []}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        list(
            paginate(
                client,
                "things",
                scheme="scroll_id",
                items_key="things",
                params={"query": "acme"},
                per_page=None,
            )
        )
    for query in _queries(route):
        assert query["query"] == ["acme"]
