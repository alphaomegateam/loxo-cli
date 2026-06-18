from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel
from rich.console import Console
from rich.table import Table


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [to_jsonable(item) for item in obj]
    if isinstance(obj, dict):
        return {key: to_jsonable(value) for key, value in obj.items()}
    return obj


def apply_jq(data: Any, expr: str) -> Any:
    """Minimal selector. Supports '.', '.a.b', '.[]', '.[].field'."""
    expr = expr.strip()
    if expr in ("", "."):
        return data
    if not expr.startswith("."):
        raise ValueError(f"Unsupported --jq expression: {expr!r}")
    rest = expr[1:]
    current = data
    for token in _tokenize(rest):
        if token == "[]":
            if not isinstance(current, list):
                raise ValueError("'[]' applied to non-list")
            current = list(current)
        elif isinstance(current, list):
            current = [item.get(token) if isinstance(item, dict) else None
                       for item in current]
        elif isinstance(current, dict):
            current = current.get(token)
        else:
            raise ValueError(f"Cannot index {token!r} into {type(current).__name__}")
    return current


def _tokenize(rest: str) -> list[str]:
    tokens: list[str] = []
    for part in rest.split("."):
        while "[]" in part:
            head, _, tail = part.partition("[]")
            if head:
                tokens.append(head)
            tokens.append("[]")
            part = tail
        if part:
            tokens.append(part)
    return tokens


def render(
    data: Any,
    *,
    as_json: bool,
    jq: str | None = None,
    columns: list[str] | None = None,
    console: Console | None = None,
) -> None:
    console = console or Console()
    payload = to_jsonable(data)
    if jq:
        payload = apply_jq(payload, jq)

    if as_json or jq:
        if console.is_terminal:
            console.print_json(json.dumps(payload))
        else:
            console.file.write(json.dumps(payload) + "\n")
        return

    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        cols = columns or list(payload[0].keys())
        table = Table(*cols)
        for row in payload:
            table.add_row(*[_fmt(row.get(c)) for c in cols])
        console.print(table)
    elif isinstance(payload, dict):
        table = Table("field", "value")
        for key, value in payload.items():
            table.add_row(key, _fmt(value))
        console.print(table)
    else:
        console.print(_fmt(payload))


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)
