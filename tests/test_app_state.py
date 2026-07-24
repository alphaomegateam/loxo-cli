import re

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    """Strip ANSI styling so Rich-rendered --help is assertable regardless of
    the terminal color environment (CI forces color, splitting tokens)."""
    return _ANSI.sub("", text)


@respx.mock
def test_appstate_settings_and_client(tmp_path):
    from loxo_cli.__main__ import AppState

    respx.get("https://app.loxo.co/api/acme/ping").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    state = AppState(
        profile=None,
        api_key="k",
        slug="acme",
        base_url=None,
        json_out=True,
        jq=None,
        verbose=False,
        no_color=True,
    )
    assert state.settings().slug == "acme"
    assert state.client().get("ping") == {"ok": True}


def test_callback_registers_global_options():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = _plain(result.stdout)
    assert "--profile" in out
    assert "--json" in out
    assert "--jq" in out


from loxo_cli.__main__ import AppState  # noqa: E402
from loxo_cli.retry import RetryPolicy  # noqa: E402


def _retry_state(**kw):
    base = dict(
        profile=None,
        api_key="k",
        slug="acme",
        base_url="https://app.loxo.co/api",
        json_out=False,
        jq=None,
        verbose=False,
        no_color=False,
    )
    base.update(kw)
    return AppState(**base)


def test_client_uses_the_default_policy_when_no_flag_or_env(monkeypatch):
    monkeypatch.delenv("LOXO_MAX_RETRIES", raising=False)
    client = _retry_state().client()
    try:
        assert client._retry.max_retries == RetryPolicy().max_retries
    finally:
        client.close()


def test_retries_flag_overrides_the_default(monkeypatch):
    monkeypatch.delenv("LOXO_MAX_RETRIES", raising=False)
    client = _retry_state(retries=0).client()
    try:
        assert client._retry.max_retries == 0
    finally:
        client.close()


def test_env_var_is_honored_when_no_flag(monkeypatch):
    monkeypatch.setenv("LOXO_MAX_RETRIES", "7")
    client = _retry_state().client()
    try:
        assert client._retry.max_retries == 7
    finally:
        client.close()


def test_flag_beats_env(monkeypatch):
    monkeypatch.setenv("LOXO_MAX_RETRIES", "7")
    client = _retry_state(retries=1).client()
    try:
        assert client._retry.max_retries == 1
    finally:
        client.close()
