from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

import typer


def load_data(raw: str | None, *, stdin: TextIO | None = None) -> dict:
    if raw is None:
        return {}
    try:
        if raw == "-":
            source = stdin or sys.stdin
            return json.load(source)
        if raw.startswith("@"):
            return json.loads(Path(raw[1:]).read_text())
        return json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        raise typer.BadParameter(f"Invalid --data JSON: {exc}") from exc


def parse_fields(fields: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in fields:
        if "=" not in item:
            raise typer.BadParameter(f"--field must be key=value, got {item!r}")
        key, value = item.split("=", 1)
        force_list = key.endswith("[]")
        if force_list:
            key = key[:-2]
        if key in result:
            existing = result[key]
            result[key] = existing + [value] if isinstance(existing, list) else [existing, value]
        elif force_list:
            result[key] = [value]
        else:
            result[key] = value
    return result


def build_payload(resource_key: str, typed: dict, data: dict, fields: dict) -> dict:
    merged: dict[str, Any] = dict(data)
    merged.update({k: v for k, v in typed.items() if v is not None})
    merged.update(fields)
    return {resource_key: merged}
