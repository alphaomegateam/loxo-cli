from __future__ import annotations

from typing import Optional

import typer

from loxo_cli.commands._helpers import load_data, parse_fields
from loxo_cli.pagination import detect_scheme, extract_items, paginate


def _per_page(scheme: str) -> int | None:
    # Scroll endpoints (e.g. companies, deals) reject per_page with HTTP 422
    # ("Invalid parameters: [:per_page]") and page themselves at a server-fixed
    # size, so never send it for that scheme. Page-based endpoints accept it and
    # benefit from a larger page; after_id ignores per_page entirely.
    return None if scheme == "scroll_id" else 50


def register(app: typer.Typer) -> None:
    app.command(
        "api",
        help="Call any Loxo endpoint directly. " "Unofficial — not affiliated with Loxo, Inc.",
    )(api_command)


def api_command(
    ctx: typer.Context,
    method: str = typer.Argument(..., help="HTTP method: GET/POST/PUT/DELETE."),
    path: str = typer.Argument(..., help="Endpoint path, e.g. people or jobs/123."),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="Query param key=value (repeatable)."
    ),
    data: Optional[str] = typer.Option(
        None, "--data", "-d", help="JSON body: inline, @file, or - for stdin."
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="No-op: pass the global --json flag for raw JSON. Without --json "
        "the response renders as a table.",
    ),
    all_pages: bool = typer.Option(False, "--all", help="Auto-paginate all pages."),
    paginate_scheme: Optional[str] = typer.Option(
        None, "--paginate", help="Force scheme: scroll_id|page|after_id."
    ),
) -> None:
    state = ctx.obj
    params = parse_fields(param)
    body = load_data(data) or None
    client = state.client()

    if all_pages:
        if method.upper() != "GET":
            raise typer.BadParameter("--all only supports GET (pagination is GET-only).")
        scheme = paginate_scheme
        if scheme is None:
            first = client.get(path, params=params)
            scheme = detect_scheme(first)
            # Collect first page items and build continuation params so we
            # don't re-fetch the first page inside paginate().
            first_items = extract_items(first, None)
            cont_params = dict(params or {})
            if scheme == "scroll_id" and isinstance(first, dict):
                next_sid = first.get("scroll_id")
                if next_sid:
                    cont_params["scroll_id"] = next_sid
                    items = first_items + list(
                        paginate(
                            client,
                            path,
                            scheme=scheme,
                            params=cont_params,
                            per_page=_per_page(scheme),
                        )
                    )
                else:
                    items = first_items
            else:
                # For page / after_id schemes, fall back to re-paginating from
                # the start; the first-page data is small and the scheme is rare.
                items = list(
                    paginate(client, path, scheme=scheme, params=params, per_page=_per_page(scheme))
                )
        else:
            items = list(
                paginate(client, path, scheme=scheme, params=params, per_page=_per_page(scheme))
            )
        state.emit(items)
        return

    result = client.request(method.upper(), path, params=params, json=body)
    state.emit(result)
