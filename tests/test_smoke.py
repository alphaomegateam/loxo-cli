import re

from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip()  # prints some version string


def test_help_has_disclaimer():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Strip ANSI so the assertion holds regardless of the terminal color env.
    assert "not affiliated with Loxo" in _ANSI.sub("", result.stdout)
