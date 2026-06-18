import tomllib

from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()


def test_configure_writes_profile_noninteractive(tmp_path):
    cfg = tmp_path / "config.toml"
    result = runner.invoke(
        app,
        [
            "configure",
            "--name",
            "cp",
            "--slug",
            "acme",
            "--api-key",
            "secret",
            "--base-url",
            "https://app.loxo.co/api",
            "--config-path",
            str(cfg),
        ],
    )
    assert result.exit_code == 0
    data = tomllib.loads(cfg.read_text())
    assert data["profile"]["cp"]["slug"] == "acme"
    assert data["default_profile"] == "cp"
    assert oct(cfg.stat().st_mode)[-3:] == "600"


def test_configure_list_hides_key(tmp_path):
    cfg = tmp_path / "config.toml"
    runner.invoke(
        app,
        [
            "configure",
            "--name",
            "cp",
            "--slug",
            "acme",
            "--api-key",
            "topsecret",
            "--config-path",
            str(cfg),
        ],
    )
    result = runner.invoke(app, ["configure", "list", "--config-path", str(cfg)])
    assert result.exit_code == 0
    assert "cp" in result.stdout
    assert "acme" in result.stdout
    assert "topsecret" not in result.stdout


def test_configure_with_api_key_cmd(tmp_path):
    cfg = tmp_path / "config.toml"
    result = runner.invoke(
        app,
        [
            "configure",
            "--name",
            "vault",
            "--slug",
            "acme",
            "--api-key-cmd",
            "op read op://Private/loxo/credential",
            "--config-path",
            str(cfg),
        ],
    )
    assert result.exit_code == 0
    data = tomllib.loads(cfg.read_text())
    assert data["profile"]["vault"]["api_key_cmd"] == "op read op://Private/loxo/credential"
    assert "api_key" not in data["profile"]["vault"]  # stores the command, not a key
    # `list` reports the key as set (resolvable via command) without printing it.
    listing = runner.invoke(app, ["configure", "list", "--config-path", str(cfg)])
    assert "api_key=set" in listing.stdout
    assert "op read" not in listing.stdout
