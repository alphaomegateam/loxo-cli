import httpx
import respx

from loxo_cli.client import LoxoClient
from loxo_cli.config import LoxoSettings
from loxo_cli.pagination import detect_scheme, extract_items, paginate

SETTINGS = LoxoSettings(api_key="k", slug="acme", base_url="https://app.loxo.co/api")


def test_detect_scheme():
    assert detect_scheme({"scroll_id": "x", "people": []}) == "scroll_id"
    # jobs reports its cursor at the top level, not under "pagination".
    assert detect_scheme({"current_page": 1, "total_count": 9, "results": []}) == "page"
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
        httpx.Response(
            200,
            json={
                "pagination": {"total_count": 3, "per_page": 2, "current_page": 1},
                "results": [{"id": 1}, {"id": 2}],
            },
        ),
        httpx.Response(
            200,
            json={
                "pagination": {"total_count": 3, "per_page": 2, "current_page": 2},
                "results": [{"id": 3}],
            },
        ),
    ]
    respx.get(base).mock(side_effect=responses)
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "jobs", scheme="page", items_key="results", per_page=2))
    assert [i["id"] for i in items] == [1, 2, 3]


@respx.mock
def test_page_pagination_without_total_count():
    # Some page-scheme endpoints may omit total_count. Pagination must NOT stop
    # after page 1 in that case — it should keep going until results are empty.
    base = "https://app.loxo.co/api/acme/jobs"
    responses = [
        httpx.Response(
            200,
            json={
                "pagination": {"per_page": 2, "current_page": 1},
                "results": [{"id": 1}, {"id": 2}],
            },
        ),
        httpx.Response(
            200,
            json={
                "pagination": {"per_page": 2, "current_page": 2},
                "results": [{"id": 3}],
            },
        ),
        httpx.Response(
            200,
            json={"pagination": {"per_page": 2, "current_page": 3}, "results": []},
        ),
    ]
    respx.get(base).mock(side_effect=responses)
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "jobs", scheme="page", items_key="results", per_page=2))
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


@respx.mock
def test_after_id_stops_when_cursor_does_not_advance():
    # Some reference endpoints (e.g. dynamic_fields) return a fixed, complete
    # list and IGNORE the after_id query param — so they hand back the same
    # non-empty page on every request. The after_id paginator must detect the
    # non-advancing cursor and stop, instead of looping forever and getting
    # rate-limited (429). It must also not re-yield the duplicate page.
    base = "https://app.loxo.co/api/acme/dynamic_fields"
    same = [{"id": 1, "name": "custom_text_3"}, {"id": 2, "name": "custom_hierarchy_5"}]
    route = respx.get(base).mock(return_value=httpx.Response(200, json=same))
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "dynamic_fields", scheme="after_id"))
    assert [i["id"] for i in items] == [1, 2]
    # One real page + one probe that proves the cursor didn't advance, then stop.
    assert route.call_count == 2


def test_page_scheme_reads_top_level_cursor_keys():
    """`jobs` reports its cursor at the top level, not under "pagination".

    Loxo hard-400s a page/per_page walk past 10,000 results, so a paginator
    that cannot see total_count would page until that error instead of
    stopping on the count.
    """
    pages = []

    class _Client:
        def get(self, endpoint, params=None):
            pages.append(dict(params or {}))
            # Bounded on purpose. This server never returns an empty page, so
            # before the top-level-cursor fix the walk did not merely overrun
            # by one request — it never terminated at all. Raising here makes
            # a regression fail fast instead of hanging the suite.
            if len(pages) > 5:
                raise AssertionError("paginator did not stop on total_count")
            page = (params or {}).get("page", 1)
            return {
                "current_page": page,
                "total_pages": 2,
                "per_page": 2,
                "total_count": 4,
                "results": [{"id": page * 10}, {"id": page * 10 + 1}],
            }

    items = list(paginate(_Client(), "jobs", scheme="page", items_key="results", per_page=2))
    # Stops on the count after page 2 rather than fetching an empty page 3.
    assert [p["page"] for p in pages] == [1, 2]
    assert [i["id"] for i in items] == [10, 11, 20, 21]


def test_page_scheme_still_reads_nested_pagination_object():
    pages = []

    class _Client:
        def get(self, endpoint, params=None):
            pages.append(dict(params or {}))
            page = (params or {}).get("page", 1)
            return {
                "pagination": {"current_page": page, "per_page": 2, "total_count": 4},
                "results": [{"id": page}],
            }

    items = list(paginate(_Client(), "jobs", scheme="page", items_key="results", per_page=2))
    assert [p["page"] for p in pages] == [1, 2]
    assert len(items) == 2
