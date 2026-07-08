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
from loxo_cli.models.base import unwrap_envelope
from loxo_cli.models.deal import Deal
from loxo_cli.pagination import paginate

deals_app = typer.Typer(help="Manage deals. Unofficial — not affiliated with Loxo, Inc.")

LIST_COLUMNS = ["id", "name", "amount"]
FILTER_HELP = "Exact client-side match key=value on returned records (repeatable)."


def _typed(name, amount, person_id, company_id, job_id):
    return {
        "name": name,
        "amount": amount,
        "person_id": person_id,
        "company_id": company_id,
        "job_id": job_id,
    }


@deals_app.command("list")
def list_deals(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(None, "--query", "-q", help=QUERY_HELP),
    all_pages: bool = typer.Option(False, "--all"),
    filter_: list[str] = typer.Option([], "--filter", help=FILTER_HELP),
) -> None:
    # The deals endpoint rejects per_page (HTTP 422 "Invalid parameters:
    # [:per_page]"); it scroll_id-paginates with a server-fixed page size, so we
    # never send a page-size parameter.
    state = ctx.obj
    params: dict[str, Any] = {"query": query} if query else {}
    client = state.client()
    if all_pages:
        items = list(
            paginate(
                client,
                "deals",
                scheme="scroll_id",
                items_key="deals",
                params=params,
                per_page=None,
            )
        )
    else:
        data = client.get("deals", params=params)
        items = data.get("deals", [])
    rows = [Deal.model_validate(i) for i in apply_filters(items, filter_)]
    state.emit(rows, columns=LIST_COLUMNS)


@deals_app.command("get")
def get_deal(ctx: typer.Context, deal_id: int = typer.Argument(...)) -> None:
    state = ctx.obj
    data = state.client().get(f"deals/{deal_id}")
    state.emit(Deal.model_validate(unwrap_envelope(data, "deal")))


@deals_app.command("create")
def create_deal(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name"),
    amount: Optional[float] = typer.Option(None, "--amount"),
    person_id: Optional[int] = typer.Option(None, "--person-id"),
    company_id: Optional[int] = typer.Option(None, "--company-id"),
    job_id: Optional[int] = typer.Option(None, "--job-id"),
    field: list[str] = typer.Option([], "--field"),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    raw = load_data(data)
    inner = raw.get("deal", raw)
    typed = _typed(name, amount, person_id, company_id, job_id)
    payload = build_payload("deal", typed, inner, parse_fields(field))
    result = state.client().post("deals", json=payload)
    state.emit(Deal.model_validate(unwrap_envelope(result, "deal")))


@deals_app.command("update")
def update_deal(
    ctx: typer.Context,
    deal_id: int = typer.Argument(...),
    name: Optional[str] = typer.Option(None, "--name"),
    amount: Optional[float] = typer.Option(None, "--amount"),
    person_id: Optional[int] = typer.Option(None, "--person-id"),
    company_id: Optional[int] = typer.Option(None, "--company-id"),
    job_id: Optional[int] = typer.Option(None, "--job-id"),
    field: list[str] = typer.Option([], "--field"),
    data: Optional[str] = typer.Option(None, "--data", "-d"),
) -> None:
    state = ctx.obj
    raw = load_data(data)
    inner = raw.get("deal", raw)
    typed = _typed(name, amount, person_id, company_id, job_id)
    payload = build_payload("deal", typed, inner, parse_fields(field))
    result = state.client().put(f"deals/{deal_id}", json=payload)
    state.emit(Deal.model_validate(unwrap_envelope(result, "deal")))
