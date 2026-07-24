"""The page scheme must not crash when it cannot compute the count-based stop.

pagination.py computed `current * size` where size could be None (per_page
None and the server omitting per_page from its pagination block), raising
TypeError. No CLI caller reached it, but apaginate makes this a public
surface where the caller chooses per_page.
"""

import httpx
import respx

from loxo_cli.client import LoxoClient
from loxo_cli.config import LoxoSettings
from loxo_cli.pagination import paginate

SETTINGS = LoxoSettings(api_key="k", slug="acme", base_url="https://app.loxo.co/api")
BASE = "https://app.loxo.co/api/acme/things"


@respx.mock
def test_page_scheme_survives_missing_per_page_in_pagination_block():
    route = respx.get(BASE).mock(
        side_effect=[
            httpx.Response(
                200,
                json={"results": [{"id": 1}], "pagination": {"total_count": 99}},
            ),
            httpx.Response(200, json={"results": []}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        items = list(paginate(client, "things", scheme="page", items_key="results", per_page=None))
    # Falls through to the empty-page guard rather than raising TypeError.
    assert items == [{"id": 1}]
    # And it got there by fetching the second page, not by stopping early for
    # some other reason that happens to yield the same items.
    assert route.call_count == 2
