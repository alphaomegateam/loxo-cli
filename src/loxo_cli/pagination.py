from __future__ import annotations

from typing import Any, AsyncIterator, Iterator, Protocol

from loxo_cli.client import AsyncLoxoClient, LoxoClient


def detect_scheme(data: Any) -> str:
    if isinstance(data, dict):
        if "scroll_id" in data:
            return "scroll_id"
        # Offset endpoints come in two shapes: the documented one nests the
        # cursor under "pagination", but `jobs` puts current_page/total_pages/
        # per_page/total_count at the top level. Without the second check the
        # live jobs response falls through to after_id, so
        # `loxo api GET jobs --paginate` sends after_id to an endpoint that
        # paginates by page.
        if "pagination" in data or "current_page" in data:
            return "page"
    return "after_id"


def extract_items(data: Any, items_key: str | None) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if items_key and isinstance(data.get(items_key), list):
            return data[items_key]
        for value in data.values():
            if isinstance(value, list):
                return value
    return []


class Paginator(Protocol):
    """Pure cursor state machine for one pagination scheme.

    The schemes disagree about when yielding happens relative to stopping:
    scroll_id and page yield and then decide, but after_id must be able to
    receive a non-empty page, yield nothing, and stop. So feed() returns
    both, and the drive loop never extracts items itself.
    """

    def next_params(self) -> dict[str, Any] | None:
        """Params for the next request, or None to stop without fetching."""

    def feed(self, data: Any) -> tuple[list, bool]:
        """Consume a response; return (items to yield, done)."""


class _ScrollPaginator:
    def __init__(self, params: dict[str, Any], per_page: int | None, items_key: str | None):
        self._base = params
        self._per_page = per_page
        self._items_key = items_key
        self._scroll_id: str | None = None
        self._done = False

    def next_params(self) -> dict[str, Any] | None:
        if self._done:
            return None
        page_params = dict(self._base)
        # Only when set: scroll endpoints (companies, deals) reject per_page
        # with HTTP 422, so their callers pass per_page=None deliberately.
        if self._per_page is not None:
            page_params.setdefault("per_page", self._per_page)
        if self._scroll_id:
            page_params["scroll_id"] = self._scroll_id
        return page_params

    def feed(self, data: Any) -> tuple[list, bool]:
        items = extract_items(data, self._items_key)
        if not items:
            self._done = True
            return [], True
        next_scroll_id = data.get("scroll_id") if isinstance(data, dict) else None
        # If the endpoint handed back the same scroll_id we just sent, it
        # ignored the cursor. Stop WITHOUT re-yielding the duplicate page,
        # exactly as the after_id guard does; otherwise this loops forever.
        # Only applies once a cursor has actually been sent: on the first
        # request self._scroll_id is None and nothing can repeat.
        #
        # Safe because Loxo's scroll_id is a *position* cursor, not a
        # session handle. (Some scroll APIs, e.g. Elasticsearch, reuse one
        # constant scroll_id for a whole sweep; there this guard would
        # truncate every sweep to one page.) Verified against the live
        # agency on 2026-07-24: two consecutive GET /companies calls
        # returned different scroll_ids and disjoint items, and the value is
        # hex-encoded ASCII — 5B313738343931383338303132302C333134353431
        # 3437375D decodes to "[1784918380120,314541477]", i.e.
        # [timestamp, last_item_id]. A repeat can only mean it was ignored.
        if self._scroll_id is not None and next_scroll_id == self._scroll_id:
            self._done = True
            return [], True
        self._scroll_id = next_scroll_id
        if not self._scroll_id:
            self._done = True
        return items, self._done


class _PagePaginator:
    def __init__(self, params: dict[str, Any], per_page: int | None, items_key: str | None):
        self._base = params
        self._per_page = per_page
        self._items_key = items_key
        self._page = 1
        self._done = False

    def next_params(self) -> dict[str, Any] | None:
        if self._done:
            return None
        page_params = dict(self._base)
        page_params["page"] = self._page
        if self._per_page is not None:
            page_params.setdefault("per_page", self._per_page)
        return page_params

    def feed(self, data: Any) -> tuple[list, bool]:
        items = extract_items(data, self._items_key)
        if not items:
            self._done = True
            return [], True
        # `jobs` reports its cursor at the TOP level (current_page,
        # total_pages, per_page, total_count) even though the documented
        # shape nests them under "pagination". Read the nested object when
        # present and fall back to the envelope itself, so both shapes stop
        # on the count. Without this the count-based stop never fires for
        # jobs: the walk only ends on an empty page, and Loxo answers a
        # page/per_page walk past 10,000 results with a hard 400
        # ("Paginating past the first 10000 results ... not supported")
        # rather than an empty page.
        envelope = data if isinstance(data, dict) else {}
        nested = envelope.get("pagination")
        pag = nested if isinstance(nested, dict) else envelope
        total = pag.get("total_count")
        size = pag.get("per_page", self._per_page)
        current = pag.get("current_page", self._page)
        # Only trust the count-based stop when total_count AND a page size
        # are actually reported; otherwise keep paging until results come
        # back empty, so a missing total_count can't truncate results and a
        # missing per_page can't raise TypeError.
        if total is not None and size is not None and current * size >= total:
            self._done = True
        # Follow the server's own numbering, but never stand still or move
        # backwards: a server that reports the same current_page on every
        # response, with a non-empty page and no usable total_count, would
        # otherwise make this refetch one page forever.
        self._page = max(current + 1, self._page + 1)
        return items, self._done


class _AfterIdPaginator:
    def __init__(self, params: dict[str, Any], items_key: str | None):
        self._base = params
        self._items_key = items_key
        self._after_id: Any = None
        self._done = False

    def next_params(self) -> dict[str, Any] | None:
        if self._done:
            return None
        page_params = dict(self._base)
        # after_id endpoints ignore per_page entirely; never send it.
        if self._after_id is not None:
            page_params["after_id"] = self._after_id
        return page_params

    def feed(self, data: Any) -> tuple[list, bool]:
        items = extract_items(data, self._items_key)
        if not items:
            self._done = True
            return [], True
        next_after_id = items[-1].get("id") if isinstance(items[-1], dict) else None
        # If the endpoint ignored after_id and returned the same page again
        # (some reference endpoints, e.g. dynamic_fields, return a fixed
        # list and ignore the cursor), the cursor won't advance. Stop
        # WITHOUT re-yielding the duplicate page. Without this guard those
        # endpoints loop forever, hammering the API until it 429s us.
        # Only applies once a cursor has actually been sent: on the first
        # page after_id is None, and a no-id last item there is a
        # legitimate single, complete page that must still be yielded.
        if self._after_id is not None and next_after_id == self._after_id:
            self._done = True
            return [], True
        self._after_id = next_after_id
        # Last item has no id -> can't build a next cursor, so this is the
        # final page.
        if next_after_id is None:
            self._done = True
        return items, self._done


def make_paginator(
    scheme: str,
    *,
    params: dict[str, Any] | None = None,
    per_page: int | None = 50,
    items_key: str | None = None,
) -> Paginator:
    base = dict(params or {})
    if scheme == "scroll_id":
        return _ScrollPaginator(base, per_page, items_key)
    if scheme == "page":
        return _PagePaginator(base, per_page, items_key)
    if scheme == "after_id":
        return _AfterIdPaginator(base, items_key)
    raise ValueError(f"Unknown pagination scheme: {scheme}")


def paginate(
    client: LoxoClient,
    endpoint: str,
    *,
    scheme: str,
    items_key: str | None = None,
    params: dict[str, Any] | None = None,
    per_page: int | None = 50,
) -> Iterator[Any]:
    paginator = make_paginator(scheme, params=params, per_page=per_page, items_key=items_key)
    while True:
        page_params = paginator.next_params()
        if page_params is None:
            return
        data = client.get(endpoint, params=page_params)
        items, done = paginator.feed(data)
        yield from items
        if done:
            return


async def apaginate(
    client: AsyncLoxoClient,
    endpoint: str,
    *,
    scheme: str,
    items_key: str | None = None,
    params: dict[str, Any] | None = None,
    per_page: int | None = 50,
) -> AsyncIterator[Any]:
    """Async twin of paginate(). Shares every Paginator, so every guard too."""
    paginator = make_paginator(scheme, params=params, per_page=per_page, items_key=items_key)
    while True:
        page_params = paginator.next_params()
        if page_params is None:
            return
        data = await client.get(endpoint, params=page_params)
        items, done = paginator.feed(data)
        for item in items:
            yield item
        if done:
            return
