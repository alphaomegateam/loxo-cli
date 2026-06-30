from __future__ import annotations

from typing import Any, Iterator

from loxo_cli.client import LoxoClient


def detect_scheme(data: Any) -> str:
    if isinstance(data, dict):
        if "scroll_id" in data:
            return "scroll_id"
        if "pagination" in data:
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


def paginate(
    client: LoxoClient,
    endpoint: str,
    *,
    scheme: str,
    items_key: str | None = None,
    params: dict[str, Any] | None = None,
    per_page: int | None = 50,
) -> Iterator[Any]:
    base_params = dict(params or {})

    if scheme == "scroll_id":
        scroll_id: str | None = None
        while True:
            page_params = dict(base_params)
            if per_page is not None:
                page_params.setdefault("per_page", per_page)
            if scroll_id:
                page_params["scroll_id"] = scroll_id
            data = client.get(endpoint, params=page_params)
            items = extract_items(data, items_key)
            if not items:
                return
            yield from items
            scroll_id = data.get("scroll_id") if isinstance(data, dict) else None
            if not scroll_id:
                return

    elif scheme == "page":
        page = 1
        while True:
            page_params = dict(base_params)
            page_params["page"] = page
            if per_page is not None:
                page_params.setdefault("per_page", per_page)
            data = client.get(endpoint, params=page_params)
            items = extract_items(data, items_key)
            if not items:
                return
            yield from items
            pag = data.get("pagination", {}) if isinstance(data, dict) else {}
            total = pag.get("total_count")
            size = pag.get("per_page", per_page)
            current = pag.get("current_page", page)
            # Only trust the count-based stop when total_count is actually
            # reported; otherwise keep paging until results come back empty
            # (the guard above) so a missing total_count can't truncate results.
            if total is not None and current * size >= total:
                return
            page = current + 1

    elif scheme == "after_id":
        after_id: Any = None
        while True:
            page_params = dict(base_params)
            if after_id is not None:
                page_params["after_id"] = after_id
            data = client.get(endpoint, params=page_params)
            items = extract_items(data, items_key)
            if not items:
                return
            next_after_id = items[-1].get("id") if isinstance(items[-1], dict) else None
            # If the endpoint ignored after_id and returned the same page again
            # (some reference endpoints, e.g. dynamic_fields, return a fixed list
            # and ignore the cursor), the cursor won't advance. Stop without
            # re-yielding the duplicate page. Without this guard those endpoints
            # loop forever, hammering the API until it rate-limits us (429).
            # Only applies once a cursor has actually been sent: on the first
            # page after_id is None, and a no-id last item there is a legitimate
            # single, complete page that must still be yielded.
            if after_id is not None and next_after_id == after_id:
                return
            yield from items
            # Last item has no id -> can't build a next cursor, so this is the
            # final page.
            if next_after_id is None:
                return
            after_id = next_after_id
    else:
        raise ValueError(f"Unknown pagination scheme: {scheme}")
