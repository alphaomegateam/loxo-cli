from __future__ import annotations

from typing import Optional

import typer

from loxo_cli.commands._helpers import load_data, parse_fields
from loxo_cli.errors import LoxoError
from loxo_cli.pagination import detect_scheme, extract_items, paginate

api_app = typer.Typer()


def register(app: typer.Typer) -> None:
    app.command("api", help="Call any Loxo endpoint directly. "
                            "Unofficial — not affiliated with Loxo, Inc.")(api_command)


def api_command(
    ctx: typer.Context,
    method: str = typer.Argument(..., help="HTTP method: GET/POST/PUT/DELETE."),
    path: str = typer.Argument(..., help="Endpoint path, e.g. people or jobs/123."),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="Query param key=value (repeatable)."),
    data: Optional[str] = typer.Option(
        None, "--data", "-d", help="JSON body: inline, @file, or - for stdin."),
    raw: bool = typer.Option(
        False, "--raw", help="No-op for the generic command (always raw)."),
    all_pages: bool = typer.Option(False, "--all", help="Auto-paginate all pages."),
    paginate_scheme: Optional[str] = typer.Option(
        None, "--paginate", help="Force scheme: scroll_id|page|after_id."),
) -> None:
    state = ctx.obj
    params = parse_fields(param)
    body = load_data(data) or None
    client = state.client()

    try:
        if all_pages:
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
                            paginate(client, path, scheme=scheme, params=cont_params)
                        )
                    else:
                        items = first_items
                else:
                    # For page / after_id schemes, fall back to re-paginating from
                    # the start; the first-page data is small and the scheme is rare.
                    items = list(paginate(client, path, scheme=scheme, params=params))
            else:
                items = list(paginate(client, path, scheme=scheme, params=params))
            state.emit(items)
            return

        result = client.request(method.upper(), path, params=params, json=body)
        state.emit(result)

    except LoxoError as e:
        typer.echo(f"Error: {e.format_message()}", err=True)
        raise typer.Exit(code=e.exit_code)
