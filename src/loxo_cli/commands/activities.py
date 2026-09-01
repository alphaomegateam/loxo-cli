from __future__ import annotations

from typing import Optional

import typer

from loxo_cli.commands._helpers import apply_filters, build_payload, load_data, parse_fields
from loxo_cli.errors import LoxoError
from loxo_cli.models.base import unwrap_envelope
from loxo_cli.pagination import paginate

FILTER_HELP = "Exact client-side match key=value on returned records (repeatable)."

activities_app = typer.Typer(
    help="Manage person events/activities. Unofficial — not affiliated with Loxo, Inc."
)


@activities_app.command("list")
def list_activities(
    ctx: typer.Context,
    person_id: Optional[int] = typer.Option(None, "--person-id"),
    company_id: Optional[int] = typer.Option(None, "--company-id"),
    all_pages: bool = typer.Option(False, "--all"),
    per_page: int = typer.Option(50, "--per-page"),
    filter_: list[str] = typer.Option([], "--filter", help=FILTER_HELP),
) -> None:
    # Loxo's person_events endpoint only accepts person_id / company_id as
    # server-side filters. job_id is not a valid query param (returns 422), so
    # it is intentionally not exposed here — filter by person or company instead.
    state = ctx.obj
    params: dict = {}
    if person_id is not None:
        params["person_id"] = person_id
    if company_id is not None:
        params["company_id"] = company_id
    client = state.client()
    if all_pages:
        rows = list(
            paginate(
                client,
                "person_events",
                scheme="scroll_id",
                items_key="person_events",
                params=params,
                per_page=per_page,
            )
        )
    else:
        params["per_page"] = per_page
        data = client.get("person_events", params=params)
        rows = data.get("person_events", []) if isinstance(data, dict) else data
    rows = apply_filters(rows, filter_)
    state.emit(rows, columns=["id", "activity_type_id", "person_id", "notes"])


@activities_app.command("get")
def get_activity(
    ctx: typer.Context,
    activity_id: int = typer.Argument(..., help="Person event (activity) id."),
) -> None:
    state = ctx.obj
    # Verified live: an unknown person_event id answers HTTP 200 with a bare
    # `null` body instead of a 404, so a missing record has to be detected here
    # or the command would print "null" and exit 0. Anything that isn't a JSON
    # object is treated as not found and reported as a 404 (exit code 4), which
    # is what every other `get` in this CLI does.
    data = state.client().get(f"person_events/{activity_id}")
    if not isinstance(data, dict):
        raise LoxoError(f"Activity {activity_id} not found.", status_code=404)
    # Single GET comes back flat; unwrap defensively in case that changes.
    state.emit(unwrap_envelope(data, "person_event"))


@activities_app.command("add")
def add_activity(
    ctx: typer.Context,
    activity_type_id: int = typer.Option(..., "--activity-type-id"),
    person_id: int = typer.Option(..., "--person-id"),
    job_id: Optional[int] = typer.Option(None, "--job-id"),
    company_id: Optional[int] = typer.Option(None, "--company-id"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    field: list[str] = typer.Option([], "--field"),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    raw = load_data(data)
    inner = raw.get("person_event", raw)
    typed = {
        "activity_type_id": activity_type_id,
        "person_id": person_id,
        "job_id": job_id,
        "company_id": company_id,
        "notes": notes,
    }
    payload = build_payload("person_event", typed, inner, parse_fields(field))
    result = state.client().post("person_events", json=payload)
    state.emit(result)
