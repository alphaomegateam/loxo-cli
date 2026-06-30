from __future__ import annotations

from typing import Any, Optional

import typer

from loxo_cli.models.base import unwrap_envelope
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


def _resolve_dynamic_field_id(client: Any, field: str, object_filter: Optional[str]) -> int:
    """Turn a FIELD argument (numeric id or field key) into a dynamic_field id."""
    if field.isdigit():
        return int(field)
    rows = extract_items(client.get("dynamic_fields"), None)
    matches = [r for r in rows if r.get("key") == field]
    if not matches:
        raise typer.BadParameter(f"No custom field with key {field!r}.", param_hint="FIELD")
    if object_filter:
        wanted = object_filter.strip().lower()
        scoped = [r for r in matches if (r.get("item_type") or "").lower() == wanted]
        if not scoped:
            present = ", ".join(sorted({r["item_type"] for r in matches if r.get("item_type")}))
            raise typer.BadParameter(
                f"Key {field!r} is not on object {object_filter!r}; it exists on: {present}.",
                param_hint="--object",
            )
        matches = scoped
    if len(matches) > 1:
        listed = ", ".join(
            f"{r.get('item_type')} id={r['id']}"
            for r in sorted(matches, key=lambda r: r.get("item_type") or "")
        )
        raise typer.BadParameter(
            f"Key {field!r} matches multiple objects: {listed}. Use --object to disambiguate.",
            param_hint="FIELD",
        )
    return int(matches[0]["id"])


@ref_app.command("hierarchies")
def hierarchies(
    ctx: typer.Context,
    field: str = typer.Argument(
        ..., metavar="FIELD", help="Dynamic field id or key (e.g. custom_hierarchy_4)."
    ),
    object_filter: Optional[str] = typer.Option(
        None,
        "--object",
        "-o",
        help="Disambiguate a key by object (matches item_type, case-insensitive).",
    ),
) -> None:
    """List the options for a hierarchy custom field, by id or key."""
    client = ctx.obj.client()
    field_id = _resolve_dynamic_field_id(client, field, object_filter)
    detail = unwrap_envelope(client.get(f"dynamic_fields/{field_id}"), "dynamic_field")
    ctx.obj.emit(extract_items(detail, "hierarchies"), columns=COLUMNS)
