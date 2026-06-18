import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()


@respx.mock
def test_appstate_settings_and_client(tmp_path):
    from loxo_cli.__main__ import AppState

    respx.get("https://app.loxo.co/api/acme/ping").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    state = AppState(
        profile=None, api_key="k", slug="acme", base_url=None,
        json_out=True, jq=None, verbose=False, no_color=True,
    )
    assert state.settings().slug == "acme"
    assert state.client().get("ping") == {"ok": True}


def test_callback_registers_global_options():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--profile" in result.stdout
    assert "--json" in result.stdout
    assert "--jq" in result.stdout
