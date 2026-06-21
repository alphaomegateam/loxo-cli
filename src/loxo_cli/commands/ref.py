from __future__ import annotations

import typer

from loxo_cli.pagination import extract_items, paginate

ref_app = typer.Typer(help="Reference data lookups. Unofficial — not affiliated with Loxo, Inc.")

COLUMNS = ["id", "name"]


def _list_reference(ctx: typer.Context, endpoint: str, *, paginated: bool = True) -> None:
    state = ctx.obj
    client = state.client()
    if paginated:
        rows = list(paginate(client, endpoint, scheme="after_id"))
    else:
        # Several reference endpoints return a fixed, complete list in one
        # response and don't support keyset pagination: dynamic_fields/job_types/
        # person_types ignore after_id (driving the paginator loops forever ->
        # 429), and activity_types rejects after_id with HTTP 422. Fetch once.
        rows = extract_items(client.get(endpoint), None)
    state.emit(rows, columns=COLUMNS)


@ref_app.command("job-types")
def job_types(ctx: typer.Context) -> None:
    _list_reference(ctx, "job_types", paginated=False)


@ref_app.command("activity-types")
def activity_types(ctx: typer.Context) -> None:
    _list_reference(ctx, "activity_types", paginated=False)


@ref_app.command("source-types")
def source_types(ctx: typer.Context) -> None:
    # source_types genuinely keyset-paginates (honors after_id); keep paging.
    _list_reference(ctx, "source_types")


@ref_app.command("person-types")
def person_types(ctx: typer.Context) -> None:
    _list_reference(ctx, "person_types", paginated=False)


@ref_app.command("lists")
def lists(ctx: typer.Context) -> None:
    """List the agency's people lists."""
    # The endpoint is person_lists (GET /lists is 404). It returns the full list
    # in one response and ignores after_id, so fetch once.
    _list_reference(ctx, "person_lists", paginated=False)


@ref_app.command("custom-fields")
def custom_fields(ctx: typer.Context) -> None:
    """List agency custom (dynamic) field definitions."""
    _list_reference(ctx, "dynamic_fields", paginated=False)


@ref_app.command("dynamic-fields", hidden=True)
def dynamic_fields_alias(ctx: typer.Context) -> None:
    """Alias of custom-fields."""
    _list_reference(ctx, "dynamic_fields", paginated=False)


@ref_app.command("hierarchies")
def hierarchies(ctx: typer.Context, dynamic_field_id: int = typer.Argument(...)) -> None:
    """List hierarchy options for a hierarchy custom field."""
    state = ctx.obj
    data = state.client().get(f"dynamic_fields/{dynamic_field_id}/hierarchies")
    state.emit(extract_items(data, "hierarchies"), columns=COLUMNS)
