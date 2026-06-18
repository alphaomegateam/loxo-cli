from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LoxoModel(BaseModel):
    model_config = ConfigDict(extra="allow")


def unwrap_envelope(data: dict, key: str) -> dict:
    if isinstance(data, dict) and isinstance(data.get(key), dict):
        return data[key]
    return data
