from __future__ import annotations

from typing import Any, Optional

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


def _emit_custom_fields(
    ctx: typer.Context, object_filter: Optional[str], custom_only: bool
) -> None:
    state = ctx.obj
    # dynamic_fields returns its full config list in one response and ignores
    # after_id, so fetch once (driving the keyset paginator would loop -> 429).
    rows: list[dict[str, Any]] = extract_items(state.client().get("dynamic_fields"), None)
    if object_filter:
        wanted = object_filter.strip().lower()
        available = sorted({r["item_type"] for r in rows if r.get("item_type")})
        if wanted not in {a.lower() for a in available}:
            raise typer.BadParameter(
                f"Unknown object {object_filter!r}. Available: {', '.join(available)}",
                param_hint="--object",
            )
        rows = [r for r in rows if (r.get("item_type") or "").lower() == wanted]
    if custom_only:
        rows = [r for r in rows if not r.get("built_in")]
    for r in rows:
        r["type"] = (r.get("dynamic_field_type") or {}).get("name")
    # item_type is constant once filtered, so drop that column.
    cols = ["key", "name", "type"] if object_filter else ["key", "name", "type", "item_type"]
    state.emit(rows, columns=cols)


@ref_app.command("custom-fields")
def custom_fields(
    ctx: typer.Context,
    object_filter: Optional[str] = typer.Option(
        None,
        "--object",
        "-o",
        help="Filter to one object's fields (matches item_type, case-insensitive).",
    ),
    custom_only: bool = typer.Option(
        False,
        "--custom-only",
        help="Show only agency-defined fields (exclude built-ins).",
    ),
) -> None:
    """List agency custom (dynamic) field definitions."""
    _emit_custom_fields(ctx, object_filter, custom_only)


@ref_app.command("dynamic-fields", hidden=True)
def dynamic_fields_alias(
    ctx: typer.Context,
    object_filter: Optional[str] = typer.Option(None, "--object", "-o"),
    custom_only: bool = typer.Option(False, "--custom-only"),
) -> None:
    """Alias of custom-fields."""
    _emit_custom_fields(ctx, object_filter, custom_only)


@ref_app.command("hierarchies")
def hierarchies(ctx: typer.Context, dynamic_field_id: int = typer.Argument(...)) -> None:
    """List hierarchy options for a hierarchy custom field."""
    state = ctx.obj
    data = state.client().get(f"dynamic_fields/{dynamic_field_id}/hierarchies")
    state.emit(extract_items(data, "hierarchies"), columns=COLUMNS)
