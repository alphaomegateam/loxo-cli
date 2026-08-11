from __future__ import annotations

from typing import Any, Optional

from loxo_cli.models.base import LoxoModel


class Placement(LoxoModel):
    """A person placed into a job.

    Only the fields the table view needs are declared; everything else the
    API returns (rates, fee, splits, custom_* fields, ...) rides through on
    ``extra="allow"``.

    ``salary``/``bill_rate``/``pay_rate`` are deliberately NOT declared:
    Loxo returns them as strings (``"6065.0"``), and a typed float field
    would silently coerce them, so `--json` would stop matching the API.
    """

    id: int
    # Both are nested objects: person is {"id", "name"}, job is
    # {"id", "title", "company": {...}} — not scalar ids.
    person: Optional[Any] = None
    job: Optional[Any] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
