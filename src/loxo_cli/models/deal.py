from __future__ import annotations

from typing import Optional

from loxo_cli.models.base import LoxoModel


class Deal(LoxoModel):
    id: int
    name: Optional[str] = None
    amount: Optional[float] = None
