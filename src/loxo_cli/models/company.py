from __future__ import annotations

from typing import Optional

from loxo_cli.models.base import LoxoModel


class Company(LoxoModel):
    id: int
    name: Optional[str] = None
    url: Optional[str] = None
