from __future__ import annotations

import click

# Subclassing click.ClickException is deliberate: Click's standalone mode
# (used by both the installed `loxo` command AND typer.testing.CliRunner)
# automatically catches ClickException, prints it to stderr, and calls
# sys.exit(exc.exit_code). That gives every command the correct exit code
# with no per-command try/except. ClickException still subclasses Exception,
# so `pytest.raises(LoxoError)` and the `.status_code`/`.is_4xx` predicates
# used by client.py and its tests keep working.


class ConfigError(click.ClickException):
    """Raised when credentials/profile resolution fails."""

    exit_code = 2


class LoxoError(click.ClickException):
    """Normalized error from a Loxo API call.

    status_code is None for network failures and timeouts.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        is_timeout: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.is_timeout = is_timeout
        self.exit_code = _loxo_exit_code(self)

    @property
    def is_4xx(self) -> bool:
        return self.status_code is not None and 400 <= self.status_code < 500

    @property
    def is_5xx(self) -> bool:
        return self.status_code is not None and 500 <= self.status_code < 600


def _loxo_exit_code(err: "LoxoError") -> int:
    if err.is_timeout or err.status_code is None:
        return 7
    if err.status_code in (401, 403):
        return 3
    if err.status_code == 404:
        return 4
    if err.status_code == 429:
        return 5
    if err.is_5xx:
        return 6
    return 1


def exit_code_for(exc: BaseException) -> int:
    if isinstance(exc, click.ClickException):
        return exc.exit_code
    return 1
