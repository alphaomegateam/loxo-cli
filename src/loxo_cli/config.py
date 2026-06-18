from __future__ import annotations

import os
import shlex
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from loxo_cli.errors import ConfigError

DEFAULT_BASE_URL = "https://app.loxo.co/api"


@dataclass(frozen=True)
class LoxoSettings:
    api_key: str
    slug: str
    base_url: str


def config_file_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "loxo" / "config.toml"


def _read_config(config_path: Path | None) -> dict[str, Any]:
    path = config_path or config_file_path()
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _resolve_key(profile_data: Mapping[str, Any]) -> str | None:
    if profile_data.get("api_key"):
        return str(profile_data["api_key"])
    cmd = profile_data.get("api_key_cmd")
    if cmd:
        out = subprocess.run(
            shlex.split(str(cmd)), capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    return None


def load_settings(
    *,
    profile: str | None = None,
    api_key: str | None = None,
    slug: str | None = None,
    base_url: str | None = None,
    env: Mapping[str, str] | None = None,
    config_path: Path | None = None,
) -> LoxoSettings:
    env = os.environ if env is None else env
    config = _read_config(config_path)
    profile_name = profile or env.get("LOXO_PROFILE") or config.get("default_profile")

    profile_data: dict[str, Any] = {}
    if profile_name:
        profiles = config.get("profile", {})
        if profile_name not in profiles:
            raise ConfigError(f"Profile '{profile_name}' not found in config.")
        profile_data = profiles[profile_name]

    file_key = _resolve_key(profile_data)
    resolved_key = api_key or env.get("LOXO_API_KEY") or file_key
    resolved_slug = slug or env.get("LOXO_API_SLUG") or profile_data.get("slug")
    resolved_base = (
        base_url
        or env.get("LOXO_BASE_URL")
        or profile_data.get("base_url")
        or DEFAULT_BASE_URL
    )

    if not resolved_key:
        raise ConfigError(
            "No API key found. Set --api-key, LOXO_API_KEY, or run `loxo configure`."
        )
    if not resolved_slug:
        raise ConfigError(
            "No agency slug found. Set --slug, LOXO_API_SLUG, or run `loxo configure`."
        )
    return LoxoSettings(
        api_key=str(resolved_key),
        slug=str(resolved_slug),
        base_url=str(resolved_base).rstrip("/"),
    )


def list_profiles(*, config_path: Path | None = None) -> dict[str, dict]:
    config = _read_config(config_path)
    result: dict[str, dict] = {}
    for name, data in config.get("profile", {}).items():
        result[name] = {
            "slug": data.get("slug", ""),
            "base_url": data.get("base_url", DEFAULT_BASE_URL),
            "has_key": bool(data.get("api_key") or data.get("api_key_cmd")),
            "default": config.get("default_profile") == name,
        }
    return result


def _dump_toml(config: dict[str, Any]) -> str:
    lines: list[str] = []
    if config.get("default_profile"):
        lines.append(f'default_profile = "{config["default_profile"]}"')
        lines.append("")
    for name, data in config.get("profile", {}).items():
        lines.append(f"[profile.{name}]")
        for key, value in data.items():
            lines.append(f'{key} = "{value}"')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_profile(
    name: str,
    *,
    api_key: str | None = None,
    api_key_cmd: str | None = None,
    slug: str,
    base_url: str = DEFAULT_BASE_URL,
    make_default: bool = False,
    config_path: Path | None = None,
) -> None:
    path = config_path or config_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    config = _read_config(config_path)
    profiles = config.setdefault("profile", {})
    entry: dict[str, Any] = {"slug": slug, "base_url": base_url}
    if api_key:
        entry["api_key"] = api_key
    if api_key_cmd:
        entry["api_key_cmd"] = api_key_cmd
    profiles[name] = entry
    if make_default or not config.get("default_profile"):
        config["default_profile"] = name
    path.write_text(_dump_toml(config))
    path.chmod(0o600)
