from __future__ import annotations

from typing import Optional

import typer

from loxo_cli.commands._helpers import load_data, parse_fields
from loxo_cli.models.candidate import Candidate
from loxo_cli.pagination import paginate

candidates_app = typer.Typer(
    help="Manage job candidates. Unofficial — not affiliated with Loxo, Inc."
)

LIST_COLUMNS = ["id", "person_id", "job_id"]


@candidates_app.command("list")
def list_candidates(
    ctx: typer.Context,
    job: int = typer.Option(..., "--job", "-j"),
    all_pages: bool = typer.Option(False, "--all"),
    per_page: int = typer.Option(50, "--per-page"),
) -> None:
    state = ctx.obj
    endpoint = f"jobs/{job}/candidates"
    client = state.client()
    if all_pages:
        rows = [
            Candidate.model_validate(i)
            for i in paginate(
                client, endpoint, scheme="scroll_id", items_key="candidates", per_page=per_page
            )
        ]
    else:
        data = client.get(endpoint, params={"per_page": per_page})
        rows = [Candidate.model_validate(i) for i in data.get("candidates", [])]
    state.emit(rows, columns=LIST_COLUMNS)


@candidates_app.command("get")
def get_candidate(
    ctx: typer.Context,
    candidate_id: int = typer.Argument(...),
    job: int = typer.Option(..., "--job", "-j"),
) -> None:
    state = ctx.obj
    data = state.client().get(f"jobs/{job}/candidates/{candidate_id}")
    state.emit(Candidate.model_validate(data))


@candidates_app.command(
    "add",
    help="Add a person to a job as a candidate. If Loxo rejects the body shape, "
    "use `loxo api POST jobs/<id>/candidates --data @body.json`.",
)
def add_candidate(
    ctx: typer.Context,
    job: int = typer.Option(..., "--job", "-j"),
    person: int = typer.Option(..., "--person"),
    field: list[str] = typer.Option([], "--field"),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    body = load_data(data)
    body.setdefault("person_id", person)
    body.update(parse_fields(field))
    result = state.client().post(f"jobs/{job}/candidates", json=body)
    state.emit(Candidate.model_validate(result) if isinstance(result, dict) else result)


@candidates_app.command("update")
def update_candidate(
    ctx: typer.Context,
    candidate_id: int = typer.Argument(...),
    job: int = typer.Option(..., "--job", "-j"),
    highlights: Optional[str] = typer.Option(None, "--highlights"),
    field: list[str] = typer.Option([], "--field"),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    body = load_data(data)
    if highlights is not None:
        body["highlights"] = highlights
    body.update(parse_fields(field))
    result = state.client().put(f"jobs/{job}/candidates/{candidate_id}", json=body)
    state.emit(result)
