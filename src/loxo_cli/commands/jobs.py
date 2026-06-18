from __future__ import annotations

from typing import Optional

import typer

from loxo_cli.commands._helpers import build_payload, load_data, parse_fields
from loxo_cli.models.base import unwrap_envelope
from loxo_cli.models.job import Job
from loxo_cli.pagination import paginate

jobs_app = typer.Typer(help="Manage jobs. Unofficial — not affiliated with Loxo, Inc.")

LIST_COLUMNS = ["id", "title", "status"]


@jobs_app.command("list")
def list_jobs(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(None, "--query", "-q"),
    all_pages: bool = typer.Option(False, "--all"),
    per_page: int = typer.Option(50, "--per-page"),
) -> None:
    state = ctx.obj
    params = {"query": query} if query else {}
    client = state.client()
    if all_pages:
        rows = [Job.model_validate(i)
                for i in paginate(client, "jobs", scheme="page", items_key="results",
                                  params=params, per_page=per_page)]
    else:
        params["per_page"] = per_page
        data = client.get("jobs", params=params)
        rows = [Job.model_validate(i) for i in data.get("results", [])]
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
    state.emit(Job.model_validate(unwrap_envelope(result, "job")))


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
