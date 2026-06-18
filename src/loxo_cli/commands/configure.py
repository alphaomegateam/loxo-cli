from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from loxo_cli.config import DEFAULT_BASE_URL, config_file_path, list_profiles, write_profile

configure_app = typer.Typer(
    help="Set up credential profiles. Unofficial — not affiliated with Loxo, Inc.",
    invoke_without_command=True,
)


@configure_app.callback(invoke_without_command=True)
def configure(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name"),
    slug: Optional[str] = typer.Option(None, "--slug"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    config_path: Optional[Path] = typer.Option(None, "--config-path"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    name = name or typer.prompt("Profile name", default="default")
    slug = slug or typer.prompt("Agency slug")
    base_url = base_url or DEFAULT_BASE_URL
    api_key = api_key or typer.prompt("API key", hide_input=True)
    write_profile(
        name,
        api_key=api_key,
        slug=slug,
        base_url=base_url,
        make_default=False,
        config_path=config_path,
    )
    target = config_path or config_file_path()
    typer.echo(f"Saved profile '{name}' to {target}")


@configure_app.command("list")
def list_cmd(
    config_path: Optional[Path] = typer.Option(None, "--config-path"),
) -> None:
    profiles = list_profiles(config_path=config_path)
    if not profiles:
        typer.echo("No profiles configured. Run `loxo configure`.")
        return
    for pname, info in profiles.items():
        default = " (default)" if info["default"] else ""
        key = "set" if info["has_key"] else "missing"
        typer.echo(
            f"{pname}{default}: slug={info['slug']} " f"base_url={info['base_url']} api_key={key}"
        )
