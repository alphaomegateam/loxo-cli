import pytest

from loxo_cli.config import (
    DEFAULT_BASE_URL,
    list_profiles,
    load_settings,
    write_profile,
)
from loxo_cli.errors import ConfigError


def test_flags_take_precedence(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[profile.x]\napi_key="filekey"\nslug="fileslug"\n'
        'base_url="https://file"\n'
    )
    s = load_settings(
        profile="x",
        api_key="flagkey",
        env={"LOXO_API_KEY": "envkey"},
        config_path=cfg,
    )
    assert s.api_key == "flagkey"  # flag beats env beats file
    assert s.slug == "fileslug"  # falls back to file
    assert s.base_url == "https://file"


def test_env_beats_file(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[profile.x]\napi_key="filekey"\nslug="fileslug"\n')
    s = load_settings(
        profile="x",
        env={"LOXO_API_KEY": "envkey", "LOXO_API_SLUG": "envslug"},
        config_path=cfg,
    )
    assert s.api_key == "envkey"
    assert s.slug == "envslug"
    assert s.base_url == DEFAULT_BASE_URL  # nothing set anywhere -> default


def test_default_profile_used(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        'default_profile="prod"\n'
        '[profile.prod]\napi_key="k"\nslug="prodslug"\n'
    )
    s = load_settings(env={}, config_path=cfg)
    assert s.slug == "prodslug"


def test_api_key_cmd_executed(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[profile.x]\napi_key_cmd="printf secret-from-cmd"\nslug="s"\n'
    )
    s = load_settings(profile="x", env={}, config_path=cfg)
    assert s.api_key == "secret-from-cmd"


def test_missing_key_raises(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[profile.x]\nslug="s"\n')
    with pytest.raises(ConfigError):
        load_settings(profile="x", env={}, config_path=cfg)


def test_unknown_profile_raises(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[profile.x]\napi_key="k"\nslug="s"\n')
    with pytest.raises(ConfigError):
        load_settings(profile="nope", env={}, config_path=cfg)


def test_write_and_list_profiles_hides_key(tmp_path):
    cfg = tmp_path / "config.toml"
    write_profile(
        "cp", api_key="topsecret", slug="cp", base_url="https://app.loxo.co/api",
        make_default=True, config_path=cfg,
    )
    profiles = list_profiles(config_path=cfg)
    assert profiles["cp"]["slug"] == "cp"
    assert profiles["cp"]["has_key"] is True
    assert "topsecret" not in str(profiles)
    assert oct(cfg.stat().st_mode)[-3:] == "600"


def test_api_key_cmd_not_run_when_flag_present(tmp_path):
    # Regression: a profile with a failing api_key_cmd must NOT be invoked when a
    # higher-precedence source (flag/env) already supplies the key.
    cfg = tmp_path / "config.toml"
    cfg.write_text('[profile.x]\napi_key_cmd="false"\nslug="s"\n')
    s = load_settings(profile="x", api_key="flagkey", env={}, config_path=cfg)
    assert s.api_key == "flagkey"


def test_api_key_cmd_failure_raises_config_error(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[profile.x]\napi_key_cmd="false"\nslug="s"\n')
    with pytest.raises(ConfigError):
        load_settings(profile="x", env={}, config_path=cfg)
