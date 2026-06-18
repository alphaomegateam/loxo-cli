from __future__ import annotations

from typing import Optional

import typer

from loxo_cli.commands._helpers import build_payload, load_data, parse_fields
from loxo_cli.models.base import unwrap_envelope
from loxo_cli.models.company import Company
from loxo_cli.pagination import paginate

companies_app = typer.Typer(help="Manage companies. Unofficial — not affiliated with Loxo, Inc.")

LIST_COLUMNS = ["id", "name", "url"]


def _list(state, query, all_pages, per_page):
    params = {"query": query} if query else {}
    client = state.client()
    if all_pages:
        rows = [
            Company.model_validate(i)
            for i in paginate(
                client,
                "companies",
                scheme="scroll_id",
                items_key="companies",
                params=params,
                per_page=per_page,
            )
        ]
    else:
        params["per_page"] = per_page
        data = client.get("companies", params=params)
        rows = [Company.model_validate(i) for i in data.get("companies", [])]
    state.emit(rows, columns=LIST_COLUMNS)


@companies_app.command("list")
def list_companies(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(None, "--query", "-q"),
    all_pages: bool = typer.Option(False, "--all"),
    per_page: int = typer.Option(50, "--per-page"),
) -> None:
    _list(ctx.obj, query, all_pages, per_page)


@companies_app.command(
    "search",
    help="Search companies by query. NOTE: the company 'url' field is not a "
    "searchable Lucene field; pass a bare domain as a full-text query.",
)
def search_companies(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query", "-q"),
    all_pages: bool = typer.Option(False, "--all"),
    per_page: int = typer.Option(50, "--per-page"),
) -> None:
    _list(ctx.obj, query, all_pages, per_page)


@companies_app.command("get")
def get_company(ctx: typer.Context, company_id: int = typer.Argument(...)) -> None:
    state = ctx.obj
    data = state.client().get(f"companies/{company_id}")
    state.emit(Company.model_validate(unwrap_envelope(data, "company")))


@companies_app.command("create")
def create_company(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name"),
    url: Optional[str] = typer.Option(None, "--url"),
    field: list[str] = typer.Option([], "--field"),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    raw = load_data(data)
    inner = raw.get("company", raw)
    payload = build_payload("company", {"name": name, "url": url}, inner, parse_fields(field))
    result = state.client().post("companies", json=payload)
    state.emit(Company.model_validate(unwrap_envelope(result, "company")))


@companies_app.command("update")
def update_company(
    ctx: typer.Context,
    company_id: int = typer.Argument(...),
    name: Optional[str] = typer.Option(None, "--name"),
    url: Optional[str] = typer.Option(None, "--url"),
    field: list[str] = typer.Option([], "--field"),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    raw = load_data(data)
    inner = raw.get("company", raw)
    payload = build_payload("company", {"name": name, "url": url}, inner, parse_fields(field))
    result = state.client().put(f"companies/{company_id}", json=payload)
    state.emit(Company.model_validate(unwrap_envelope(result, "company")))
