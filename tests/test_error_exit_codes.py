"""Central error -> exit-code mapping (LoxoGroup in commands/_app.py).

Typer does not honor a raised ClickException's exit_code, so LoxoGroup.invoke
converts LoxoError/ConfigError into typer.Exit with the mapped code. These tests
exercise that path through a real command (`loxo api`).
"""

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_loxo_error_maps_to_exit_code_and_prints_message():
    respx.get("https://app.loxo.co/api/acme/people/9").mock(
        return_value=httpx.Response(404, text="nope")
    )
    result = runner.invoke(app, ["api", "GET", "people/9"], env=ENV)
    assert result.exit_code == 4  # 404 -> not found
    assert "Error" in result.output  # clean message, not a raw traceback


def test_config_error_maps_to_exit_code_2():
    # No credentials anywhere -> ConfigError raised inside the command -> exit 2.
    result = runner.invoke(app, ["api", "GET", "people"], env={})
    assert result.exit_code == 2
    assert "Error" in result.output


@respx.mock
def test_server_error_maps_to_exit_code_6():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="boom")
    )
    result = runner.invoke(app, ["api", "GET", "people"], env=ENV)
    assert result.exit_code == 6  # 5xx -> server error


@respx.mock
def test_nested_subcommand_error_maps_to_exit_code():
    # LoxoGroup must map errors from NESTED sub-app commands, not just the
    # root-level `api` command.
    respx.get("https://app.loxo.co/api/acme/people/9").mock(
        return_value=httpx.Response(401, text="unauthorized")
    )
    result = runner.invoke(app, ["people", "get", "9"], env=ENV)
    assert result.exit_code == 3  # 401 -> auth error
