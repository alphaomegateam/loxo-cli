import typer

from loxo_cli import __version__

HELP_EPILOG = "Unofficial — not affiliated with Loxo, Inc."

app = typer.Typer(
    help="loxo — command-line interface for the Loxo recruiting API.",
    epilog=HELP_EPILOG,
    no_args_is_help=True,
    add_completion=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """loxo CLI. Unofficial — not affiliated with Loxo, Inc."""


if __name__ == "__main__":
    app()
