from __future__ import annotations

from typing import Any, Optional

import typer

from loxo_cli.commands._helpers import build_payload, load_data, parse_fields
from loxo_cli.models.person import Person
from loxo_cli.models.base import unwrap_envelope
from loxo_cli.pagination import paginate

people_app = typer.Typer(help="Manage people. Unofficial — not affiliated with Loxo, Inc.")

LIST_COLUMNS = ["id", "name", "title", "linkedin_url"]


@people_app.command("list")
def list_people(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Lucene search."),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages."),
    per_page: int = typer.Option(50, "--per-page", help="Page size."),
) -> None:
    state = ctx.obj
    params: dict[str, Any] = {"query": query} if query else {}
    client = state.client()
    if all_pages:
        rows = [
            Person.model_validate(i)
            for i in paginate(
                client,
                "people",
                scheme="scroll_id",
                items_key="people",
                params=params,
                per_page=per_page,
            )
        ]
    else:
        params["per_page"] = per_page
        data = client.get("people", params=params)
        rows = [Person.model_validate(i) for i in data.get("people", [])]
    state.emit(rows, columns=LIST_COLUMNS)


@people_app.command("get")
def get_person(ctx: typer.Context, person_id: int = typer.Argument(...)) -> None:
    state = ctx.obj
    data = state.client().get(f"people/{person_id}")
    state.emit(Person.model_validate(unwrap_envelope(data, "person")))


@people_app.command("create")
def create_person(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name"),
    email: Optional[str] = typer.Option(None, "--email"),
    linkedin: Optional[str] = typer.Option(None, "--linkedin"),
    title: Optional[str] = typer.Option(None, "--title"),
    field: list[str] = typer.Option([], "--field", help="Custom field key=value."),
    data: Optional[str] = typer.Option(
        None, "--data", "-d", help="JSON body: inline, @file, or -."
    ),
) -> None:
    state = ctx.obj
    raw = load_data(data)
    inner = raw.get("person", raw)
    typed = {"name": name, "email": email, "linkedin_url": linkedin, "title": title}
    payload = build_payload("person", typed, inner, parse_fields(field))
    result = state.client().post("people", json=payload)
    state.emit(Person.model_validate(unwrap_envelope(result, "person")))


@people_app.command("update")
def update_person(
    ctx: typer.Context,
    person_id: int = typer.Argument(...),
    name: Optional[str] = typer.Option(None, "--name"),
    email: Optional[str] = typer.Option(None, "--email"),
    linkedin: Optional[str] = typer.Option(None, "--linkedin"),
    title: Optional[str] = typer.Option(None, "--title"),
    field: list[str] = typer.Option([], "--field", help="Custom field key=value."),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    raw = load_data(data)
    inner = raw.get("person", raw)
    typed = {"name": name, "email": email, "linkedin_url": linkedin, "title": title}
    payload = build_payload("person", typed, inner, parse_fields(field))
    result = state.client().put(f"people/{person_id}", json=payload)
    state.emit(Person.model_validate(unwrap_envelope(result, "person")))
