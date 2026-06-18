from __future__ import annotations

from typing import Optional

from loxo_cli.models.base import LoxoModel


class Webhook(LoxoModel):
    id: int
    item_type: Optional[str] = None
    action: Optional[str] = None
    endpoint_url: Optional[str] = None
