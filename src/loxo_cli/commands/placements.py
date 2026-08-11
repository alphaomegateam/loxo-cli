from __future__ import annotations

from typing import Any, Optional

import typer

from loxo_cli.commands._helpers import QUERY_HELP, apply_filters
from loxo_cli.models.base import unwrap_envelope
from loxo_cli.models.placement import Placement
from loxo_cli.pagination import paginate

placements_app = typer.Typer(
    help="List and inspect placements. Unofficial — not affiliated with Loxo, Inc.",
    epilog=(
        "Creating and updating placements is not exposed here: the API silently "
        "drops custom_* fields on writes, so agencies that mark any custom field "
        "required cannot satisfy validation. Use `loxo api POST placements "
        "--data @body.json` if you need to try anyway."
    ),
)

LIST_COLUMNS = ["id", "person", "job", "start_date", "end_date"]
FILTER_HELP = "Exact client-side match key=value on returned records (repeatable)."
JOB_HELP = "Server-side filter by job id (unlike --filter, this narrows before paging)."


@placements_app.command("list")
def list_placements(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(None, "--query", "-q", help=QUERY_HELP),
    job: Optional[int] = typer.Option(None, "--job", "-j", help=JOB_HELP),
    person_global_status_id: Optional[int] = typer.Option(
        None, "--person-global-status-id", help="Server-side filter by person global status id."
    ),
    include_related_agencies: bool = typer.Option(
        False, "--include-related-agencies", help="Include placements from related agencies."
    ),
    all_pages: bool = typer.Option(False, "--all"),
    filter_: list[str] = typer.Option([], "--filter", help=FILTER_HELP),
) -> None:
    # Verified live: placements accepts only query, job_id,
    # person_global_status_id, include_related_agencies and scroll_id. It
    # rejects per_page AND page with 422 "Invalid parameters", so this
    # scroll_id-paginates with a server-fixed page size and never sends a
    # page-size parameter (same shape as deals).
    state = ctx.obj
    params: dict[str, Any] = {}
    if query:
        params["query"] = query
    if job is not None:
        params["job_id"] = job
    if person_global_status_id is not None:
        params["person_global_status_id"] = person_global_status_id
    if include_related_agencies:
        params["include_related_agencies"] = "true"

    client = state.client()
    if all_pages:
        items = list(
            paginate(
                client,
                "placements",
                scheme="scroll_id",
                items_key="placements",
                params=params,
                per_page=None,
            )
        )
    else:
        data = client.get("placements", params=params)
        items = data.get("placements", [])
    rows = [Placement.model_validate(i) for i in apply_filters(items, filter_)]
    state.emit(rows, columns=LIST_COLUMNS)


@placements_app.command("get")
def get_placement(ctx: typer.Context, placement_id: int = typer.Argument(...)) -> None:
    state = ctx.obj
    # Single GET comes back flat; unwrap defensively in case that changes.
    data = state.client().get(f"placements/{placement_id}")
    state.emit(Placement.model_validate(unwrap_envelope(data, "placement")))
