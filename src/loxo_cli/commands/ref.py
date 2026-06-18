from __future__ import annotations

import typer

from loxo_cli.pagination import extract_items, paginate

ref_app = typer.Typer(
    help="Reference data lookups. Unofficial — not affiliated with Loxo, Inc.")

COLUMNS = ["id", "name"]


def _list_reference(ctx: typer.Context, endpoint: str) -> None:
    state = ctx.obj
    rows = list(paginate(state.client(), endpoint, scheme="after_id"))
    state.emit(rows, columns=COLUMNS)


@ref_app.command("job-types")
def job_types(ctx: typer.Context) -> None:
    _list_reference(ctx, "job_types")


@ref_app.command("activity-types")
def activity_types(ctx: typer.Context) -> None:
    _list_reference(ctx, "activity_types")


@ref_app.command("source-types")
def source_types(ctx: typer.Context) -> None:
    _list_reference(ctx, "source_types")


@ref_app.command("person-types")
def person_types(ctx: typer.Context) -> None:
    _list_reference(ctx, "person_types")


@ref_app.command("lists")
def lists(ctx: typer.Context) -> None:
    _list_reference(ctx, "lists")


@ref_app.command("custom-fields")
def custom_fields(ctx: typer.Context) -> None:
    """List agency custom (dynamic) field definitions."""
    _list_reference(ctx, "dynamic_fields")


@ref_app.command("dynamic-fields", hidden=True)
def dynamic_fields_alias(ctx: typer.Context) -> None:
    """Alias of custom-fields."""
    _list_reference(ctx, "dynamic_fields")


@ref_app.command("hierarchies")
def hierarchies(ctx: typer.Context, dynamic_field_id: int = typer.Argument(...)) -> None:
    """List hierarchy options for a hierarchy custom field."""
    state = ctx.obj
    data = state.client().get(f"dynamic_fields/{dynamic_field_id}/hierarchies")
    state.emit(extract_items(data, "hierarchies"), columns=COLUMNS)
