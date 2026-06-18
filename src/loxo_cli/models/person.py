from __future__ import annotations

from typing import Any, Optional

from loxo_cli.models.base import LoxoModel


class Person(LoxoModel):
    id: int
    name: Optional[str] = None
    emails: Optional[list[Any]] = None
    phones: Optional[list[Any]] = None
    linkedin_url: Optional[str] = None
    title: Optional[str] = None
