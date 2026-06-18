from __future__ import annotations

from typing import Optional

from loxo_cli.models.base import LoxoModel


class Job(LoxoModel):
    id: int
    title: Optional[str] = None
    status: Optional[str] = None
