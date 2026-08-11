from __future__ import annotations

from typing import Any, Optional

import typer

from loxo_cli.commands._helpers import (
    QUERY_HELP,
    apply_filters,
    build_payload,
    load_data,
    parse_fields,
)
from loxo_cli.errors import LoxoError
from loxo_cli.models.base import unwrap_envelope
from loxo_cli.models.job import Job
from loxo_cli.pagination import paginate

FILTER_HELP = "Exact client-side match key=value on returned records (repeatable)."

jobs_app = typer.Typer(help="Manage jobs. Unofficial — not affiliated with Loxo, Inc.")

LIST_COLUMNS = ["id", "title", "status"]


def _require_created_job(result: Any) -> dict:
    """Reject a create response that echoes an unsaved job back.

    Loxo answers some `POST jobs` calls 200 with the payload it was given
    and `"id": null` — nothing is persisted, and the job never appears in
    `jobs list`. Validating that straight into the model raised a raw
    pydantic ValidationError at the user ("Input should be a valid
    integer"), so translate it into the CLI's normal error channel.
    """
    body = unwrap_envelope(result, "job") if isinstance(result, dict) else result
    if not isinstance(body, dict) or body.get("id") is None:
        raise LoxoError(
            "Loxo accepted POST jobs but returned no job id, which means the job "
            "was not created. This usually indicates a required field is missing; "
            "the API does not report which. Try creating the job in the Loxo UI, "
            "or inspect the raw response with `loxo api POST jobs --data @body.json`.",
            status_code=422,
        )
    return body


@jobs_app.command("list")
def list_jobs(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(None, "--query", "-q", help=QUERY_HELP),
    all_pages: bool = typer.Option(False, "--all"),
    per_page: int = typer.Option(50, "--per-page"),
    filter_: list[str] = typer.Option([], "--filter", help=FILTER_HELP),
) -> None:
    state = ctx.obj
    params: dict[str, Any] = {"query": query} if query else {}
    client = state.client()
    if all_pages:
        items = list(
            paginate(
                client, "jobs", scheme="page", items_key="results", params=params, per_page=per_page
            )
        )
    else:
        params["per_page"] = per_page
        data = client.get("jobs", params=params)
        items = data.get("results", [])
    rows = [Job.model_validate(i) for i in apply_filters(items, filter_)]
    state.emit(rows, columns=LIST_COLUMNS)


@jobs_app.command("get")
def get_job(ctx: typer.Context, job_id: int = typer.Argument(...)) -> None:
    state = ctx.obj
    data = state.client().get(f"jobs/{job_id}")
    state.emit(Job.model_validate(unwrap_envelope(data, "job")))


@jobs_app.command("create")
def create_job(
    ctx: typer.Context,
    title: Optional[str] = typer.Option(None, "--title"),
    field: list[str] = typer.Option([], "--field"),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    raw = load_data(data)
    inner = raw.get("job", raw)
    payload = build_payload("job", {"title": title}, inner, parse_fields(field))
    result = state.client().post("jobs", json=payload)
    state.emit(Job.model_validate(_require_created_job(result)))


@jobs_app.command("update")
def update_job(
    ctx: typer.Context,
    job_id: int = typer.Argument(...),
    title: Optional[str] = typer.Option(None, "--title"),
    field: list[str] = typer.Option([], "--field"),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    raw = load_data(data)
    inner = raw.get("job", raw)
    payload = build_payload("job", {"title": title}, inner, parse_fields(field))
    result = state.client().put(f"jobs/{job_id}", json=payload)
    state.emit(Job.model_validate(unwrap_envelope(result, "job")))
