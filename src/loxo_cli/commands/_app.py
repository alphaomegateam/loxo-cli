from __future__ import annotations

from typing import Any

import typer
from typer.core import TyperCommand

from loxo_cli.errors import ConfigError, LoxoError


class LoxoCommand(TyperCommand):
    """Typer command that maps loxo's domain errors to documented exit codes.

    Typer's invocation path does NOT honor a raised ``ClickException``'s
    ``exit_code`` (it surfaces as a generic exit 1 with no message). So we catch
    ``LoxoError``/``ConfigError`` here, print a clean message to stderr, and
    re-raise as ``typer.Exit`` with the mapped code — the only reliable way to
    make every command honor the exit-code contract (auth=3, not-found=4, …).
    """

    def invoke(self, ctx: typer.Context) -> Any:
        try:
            return super().invoke(ctx)
        except (LoxoError, ConfigError) as exc:
            typer.echo(f"Error: {exc.format_message()}", err=True)
            raise typer.Exit(code=exc.exit_code) from exc


class LoxoTyper(typer.Typer):
    """``typer.Typer`` whose commands default to :class:`LoxoCommand`.

    Command files create their sub-app with ``LoxoTyper(...)`` instead of
    ``typer.Typer(...)`` so every registered command gets unified error handling
    with no per-command try/except.
    """

    def command(self, *args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("cls", LoxoCommand)
        return super().command(*args, **kwargs)
