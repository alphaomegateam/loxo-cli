import httpx
import respx

from loxo_cli.client import LoxoClient
from loxo_cli.config import LoxoSettings
from loxo_cli.pagination import detect_scheme, extract_items, paginate

SETTINGS = LoxoSettings(api_key="k", slug="acme", base_url="https://app.loxo.co/api")


def test_detect_scheme():
    assert detect_scheme({"scroll_id": "x", "people": []}) == "scroll_id"
    assert detect_scheme({"pagination": {}, "results": []}) == "page"
    assert detect_scheme([{"id": 1}]) == "after_id"


def test_extract_items():
    assert extract_items([{"id": 1}], None) == [{"id": 1}]
    assert extract_items({"people": [{"id": 1}]}, "people") == [{"id": 1}]
    assert extract_items({"results": [{"id": 9}]}, None) == [{"id": 9}]
    assert extract_items({"total_count": 0}, "people") == []


@respx.mock
def test_scroll_id_pagination():
    base = "https://app.loxo.co/api/acme/people"
    responses = [
        httpx.Response(200, json={"scroll_id": "C2", "people": [{"id": 1}, {"id": 2}]}),
        httpx.Response(200, json={"scroll_id": None, "people": [{"id": 3}]}),
    ]
    respx.get(base).mock(side_effect=responses)
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "people", scheme="scroll_id", items_key="people"))
    assert [i["id"] for i in items] == [1, 2, 3]


@respx.mock
def test_page_pagination():
    base = "https://app.loxo.co/api/acme/jobs"
    responses = [
        httpx.Response(200, json={
            "pagination": {"total_count": 3, "per_page": 2, "current_page": 1},
            "results": [{"id": 1}, {"id": 2}]}),
        httpx.Response(200, json={
            "pagination": {"total_count": 3, "per_page": 2, "current_page": 2},
            "results": [{"id": 3}]}),
    ]
    respx.get(base).mock(side_effect=responses)
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "jobs", scheme="page", items_key="results",
                              per_page=2))
    assert [i["id"] for i in items] == [1, 2, 3]


@respx.mock
def test_after_id_pagination():
    base = "https://app.loxo.co/api/acme/source_types"
    responses = [
        httpx.Response(200, json=[{"id": 10}, {"id": 11}]),
        httpx.Response(200, json=[{"id": 12}]),
        httpx.Response(200, json=[]),
    ]
    respx.get(base).mock(side_effect=responses)
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "source_types", scheme="after_id"))
    assert [i["id"] for i in items] == [10, 11, 12]
