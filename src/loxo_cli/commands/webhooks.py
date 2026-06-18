from __future__ import annotations

import enum

import typer

from loxo_cli.models.base import unwrap_envelope
from loxo_cli.models.webhook import Webhook
from loxo_cli.pagination import extract_items

webhooks_app = typer.Typer(help="Manage webhooks. Unofficial — not affiliated with Loxo, Inc.")


class ItemType(str, enum.Enum):
    candidate = "candidate"
    company = "company"
    company_document = "company_document"
    deal = "deal"
    deal_document = "deal_document"
    job = "job"
    job_document = "job_document"
    person_education_profile = "person_education_profile"
    person_event = "person_event"
    person_event_document = "person_event_document"
    person_job_profile = "person_job_profile"
    person = "person"
    person_document = "person_document"
    placement_split = "placement_split"
    placement = "placement"
    resume = "resume"


class Action(str, enum.Enum):
    create = "create"
    update = "update"
    destroy = "destroy"


LIST_COLUMNS = ["id", "item_type", "action", "endpoint_url"]


@webhooks_app.command("list")
def list_webhooks(ctx: typer.Context) -> None:
    state = ctx.obj
    data = state.client().get("webhooks")
    rows = [Webhook.model_validate(i) for i in extract_items(data, "webhooks")]
    state.emit(rows, columns=LIST_COLUMNS)


@webhooks_app.command("get")
def get_webhook(ctx: typer.Context, webhook_id: int = typer.Argument(...)) -> None:
    state = ctx.obj
    data = state.client().get(f"webhooks/{webhook_id}")
    state.emit(Webhook.model_validate(unwrap_envelope(data, "webhook")))


@webhooks_app.command("create")
def create_webhook(
    ctx: typer.Context,
    item_type: ItemType = typer.Option(..., "--item-type"),
    action: Action = typer.Option(..., "--action"),
    url: str = typer.Option(..., "--url"),
) -> None:
    state = ctx.obj
    payload = {
        "webhook": {"item_type": item_type.value, "action": action.value, "endpoint_url": url}
    }
    result = state.client().post("webhooks", json=payload)
    state.emit(Webhook.model_validate(unwrap_envelope(result, "webhook")))


@webhooks_app.command("update")
def update_webhook(
    ctx: typer.Context,
    webhook_id: int = typer.Argument(...),
    item_type: ItemType = typer.Option(..., "--item-type"),
    action: Action = typer.Option(..., "--action"),
    url: str = typer.Option(..., "--url"),
) -> None:
    state = ctx.obj
    payload = {
        "webhook": {"item_type": item_type.value, "action": action.value, "endpoint_url": url}
    }
    result = state.client().put(f"webhooks/{webhook_id}", json=payload)
    state.emit(Webhook.model_validate(unwrap_envelope(result, "webhook")))


@webhooks_app.command("delete")
def delete_webhook(
    ctx: typer.Context,
    webhook_id: int = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    state = ctx.obj
    if not yes:
        typer.confirm(f"Delete webhook {webhook_id}?", abort=True)
    state.client().delete(f"webhooks/{webhook_id}")
    typer.echo(f"Deleted webhook {webhook_id}.")
