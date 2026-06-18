from __future__ import annotations

from typing import Optional

from loxo_cli.models.base import LoxoModel


class Candidate(LoxoModel):
    id: int
    person_id: Optional[int] = None
    job_id: Optional[int] = None
