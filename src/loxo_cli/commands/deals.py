from __future__ import annotations

from typing import Optional

import typer

from loxo_cli.commands._helpers import build_payload, load_data, parse_fields
from loxo_cli.models.base import unwrap_envelope
from loxo_cli.models.deal import Deal
from loxo_cli.pagination import paginate

deals_app = typer.Typer(help="Manage deals. Unofficial — not affiliated with Loxo, Inc.")

LIST_COLUMNS = ["id", "name", "amount"]


def _typed(name, amount, person_id, company_id, job_id):
    return {
        "name": name, "amount": amount, "person_id": person_id,
        "company_id": company_id, "job_id": job_id,
    }


@deals_app.command("list")
def list_deals(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(None, "--query", "-q"),
    all_pages: bool = typer.Option(False, "--all"),
    per_page: int = typer.Option(50, "--per-page"),
) -> None:
    state = ctx.obj
    params = {"query": query} if query else {}
    client = state.client()
    if all_pages:
        rows = [Deal.model_validate(i)
                for i in paginate(client, "deals", scheme="scroll_id",
                                  items_key="deals", params=params, per_page=per_page)]
    else:
        params["per_page"] = per_page
        data = client.get("deals", params=params)
        rows = [Deal.model_validate(i) for i in data.get("deals", [])]
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
