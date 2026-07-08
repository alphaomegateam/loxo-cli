from __future__ import annotations

from typing import Any, Optional

from loxo_cli.models.base import LoxoModel


class Job(LoxoModel):
    id: int
    title: Optional[str] = None
    # Loxo returns status as a nested object ({"id": ..., "name": ...}), not a
    # string, so this must accept an object (or a bare string on older shapes).
    # Sibling fields that are also objects in the API (company, job_type,
    # category, salary_type, ...) are undeclared and tolerated by extra="allow".
    status: Optional[Any] = None
