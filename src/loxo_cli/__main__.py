from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console

from loxo_cli import __version__
from loxo_cli.client import LoxoClient, build_client
from loxo_cli.commands._app import LoxoGroup
from loxo_cli.config import LoxoSettings, load_settings
from loxo_cli.output import render
from loxo_cli.retry import RetryPolicy, resolve_max_retries

HELP_EPILOG = "Unofficial — not affiliated with Loxo, Inc."

app = typer.Typer(
    cls=LoxoGroup,
    help="loxo — command-line interface for the Loxo recruiting API.",
    epilog=HELP_EPILOG,
    no_args_is_help=True,
)


@dataclass
class AppState:
    profile: Optional[str]
    # repr=False for the same reason as LoxoSettings.api_key: AppState is
    # ctx.obj, so any traceback through Click's invocation path or a pytest
    # assertion dump would otherwise repr a live key.
    api_key: Optional[str] = field(repr=False)
    slug: Optional[str]
    base_url: Optional[str]
    json_out: bool
    jq: Optional[str]
    verbose: bool
    no_color: bool
    retries: Optional[int] = None
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
        policy = RetryPolicy(max_retries=resolve_max_retries(self.retries))
        return build_client(self.settings(), verbose=self.verbose, retry=policy)

    def console(self) -> Console:
        # Disable color when the user asked (--no-color), when the NO_COLOR
        # convention is set (https://no-color.org/), or when stdout is not a
        # TTY (piped/redirected). The explicit isatty check is needed because
        # Rich forces color on when FORCE_COLOR is set even into a pipe.
        no_color = self.no_color or bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()
        return Console(no_color=no_color)

    def emit(self, data: Any, *, columns: list[str] | None = None) -> None:
        render(
            data,
            as_json=self.json_out,
            jq=self.jq,
            columns=columns,
            console=self.console(),
        )


class _CliLogHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Marker subclass so repeated invocations replace their own handler."""


def _configure_logging(*, verbose: bool, quiet: bool) -> None:
    """Attach the CLI's stderr handler to the package logger.

    The library itself only logs; this is what makes a terminal user see
    anything. stderr, never stdout, so `--json` output stays parseable.

    --verbose lowers the threshold to DEBUG (the per-request lines);
    the default is WARNING (the long-retry notice); --quiet raises it to
    ERROR, and wins over --verbose, since asking for quiet after asking
    for verbose is the more specific request.
    """
    package_logger = logging.getLogger("loxo_cli")
    for existing in list(package_logger.handlers):
        if isinstance(existing, _CliLogHandler):
            package_logger.removeHandler(existing)
    # Built fresh per invocation: StreamHandler binds the stream at
    # construction, and sys.stderr is not stable across a test runner's
    # captures.
    handler = _CliLogHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    level = logging.ERROR if quiet else (logging.DEBUG if verbose else logging.WARNING)
    handler.setLevel(level)
    package_logger.setLevel(level)
    package_logger.addHandler(handler)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="Config profile."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Loxo API key."),
    slug: Optional[str] = typer.Option(None, "--slug", help="Agency slug."),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="API base URL."),
    json_out: bool = typer.Option(False, "--json", help="Force JSON output."),
    jq: Optional[str] = typer.Option(
        None,
        "--jq",
        help="Select part of the output by path, e.g. '.results' or "
        "'.results.0.title'. The leading '.' is optional ('results' works too).",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress non-error diagnostics on stderr, including retry notices. "
        "Command results on stdout are unaffected.",
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Log requests to stderr."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable color."),
    retries: Optional[int] = typer.Option(
        None,
        "--retries",
        help="Retries for throttled or failed requests (default 3; 0 disables). "
        "Overrides LOXO_MAX_RETRIES.",
    ),
) -> None:
    """loxo CLI. Unofficial — not affiliated with Loxo, Inc."""
    _configure_logging(verbose=verbose, quiet=quiet)
    ctx.obj = AppState(
        profile=profile,
        api_key=api_key,
        slug=slug,
        base_url=base_url,
        json_out=json_out,
        jq=jq,
        verbose=verbose,
        no_color=no_color,
        retries=retries,
    )


from loxo_cli.commands import api as _api_cmd  # noqa: E402
from loxo_cli.commands.activities import activities_app  # noqa: E402
from loxo_cli.commands.candidates import candidates_app  # noqa: E402
from loxo_cli.commands.companies import companies_app  # noqa: E402
from loxo_cli.commands.configure import configure_app  # noqa: E402
from loxo_cli.commands.deals import deals_app  # noqa: E402
from loxo_cli.commands.jobs import jobs_app  # noqa: E402
from loxo_cli.commands.people import people_app  # noqa: E402
from loxo_cli.commands.placements import placements_app  # noqa: E402
from loxo_cli.commands.ref import ref_app  # noqa: E402
from loxo_cli.commands.webhooks import webhooks_app  # noqa: E402

_api_cmd.register(app)
app.add_typer(configure_app, name="configure")
app.add_typer(people_app, name="people")
app.add_typer(jobs_app, name="jobs")
app.add_typer(companies_app, name="companies")
app.add_typer(deals_app, name="deals")
app.add_typer(candidates_app, name="candidates")
app.add_typer(placements_app, name="placements")
app.add_typer(activities_app, name="activities")
app.add_typer(webhooks_app, name="webhooks")
app.add_typer(ref_app, name="ref")


def run() -> None:
    # Exit-code mapping happens in LoxoGroup.invoke (commands/_app.py, set via
    # typer.Typer(cls=LoxoGroup)): Typer does NOT honor a raised ClickException's
    # exit_code, so domain errors become typer.Exit with the mapped code.
    app()


if __name__ == "__main__":
    run()
