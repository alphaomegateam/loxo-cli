from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console

from loxo_cli import __version__
from loxo_cli.client import LoxoClient, build_client
from loxo_cli.commands._app import LoxoTyper
from loxo_cli.config import LoxoSettings, load_settings
from loxo_cli.output import render

HELP_EPILOG = "Unofficial — not affiliated with Loxo, Inc."

app = LoxoTyper(
    help="loxo — command-line interface for the Loxo recruiting API.",
    epilog=HELP_EPILOG,
    no_args_is_help=True,
)


@dataclass
class AppState:
    profile: Optional[str]
    api_key: Optional[str]
    slug: Optional[str]
    base_url: Optional[str]
    json_out: bool
    jq: Optional[str]
    verbose: bool
    no_color: bool
    config_path: Optional[Path] = None
    _settings: Optional[LoxoSettings] = field(default=None, repr=False)

    def settings(self) -> LoxoSettings:
        if self._settings is None:
            self._settings = load_settings(
                profile=self.profile,
                api_key=self.api_key,
                slug=self.slug,
                base_url=self.base_url,
                config_path=self.config_path,
            )
        return self._settings

    def client(self) -> LoxoClient:
        return build_client(self.settings(), verbose=self.verbose)

    def console(self) -> Console:
        return Console(no_color=self.no_color)

    def emit(self, data: Any, *, columns: list[str] | None = None) -> None:
        render(
            data,
            as_json=self.json_out,
            jq=self.jq,
            columns=columns,
            console=self.console(),
        )


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit."),
    profile: Optional[str] = typer.Option(None, "--profile", help="Config profile."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Loxo API key."),
    slug: Optional[str] = typer.Option(None, "--slug", help="Agency slug."),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="API base URL."),
    json_out: bool = typer.Option(False, "--json", help="Force JSON output."),
    jq: Optional[str] = typer.Option(None, "--jq", help="Filter output (dotted path)."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-error output."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Log requests to stderr."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable color."),
) -> None:
    """loxo CLI. Unofficial — not affiliated with Loxo, Inc."""
    ctx.obj = AppState(
        profile=profile, api_key=api_key, slug=slug, base_url=base_url,
        json_out=json_out, jq=jq, verbose=verbose, no_color=no_color,
    )


from loxo_cli.commands import api as _api_cmd  # noqa: E402

_api_cmd.register(app)


def run() -> None:
    # Exit-code mapping happens in LoxoCommand.invoke (see commands/_app.py):
    # Typer does NOT honor a raised ClickException's exit_code, so each command
    # converts LoxoError/ConfigError into typer.Exit with the mapped code.
    app()


if __name__ == "__main__":
    run()
