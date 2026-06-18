import pytest

from loxo_cli.errors import ConfigError, LoxoError, exit_code_for


@pytest.mark.parametrize(
    "status,timeout,expected",
    [
        (401, False, 3),
        (403, False, 3),
        (404, False, 4),
        (429, False, 5),
        (500, False, 6),
        (503, False, 6),
        (None, True, 7),
        (None, False, 7),
        (418, False, 1),
    ],
)
def test_loxo_error_exit_codes(status, timeout, expected):
    err = LoxoError("boom", status_code=status, is_timeout=timeout)
    assert exit_code_for(err) == expected


def test_4xx_5xx_predicates():
    assert LoxoError("x", status_code=404).is_4xx
    assert not LoxoError("x", status_code=404).is_5xx
    assert LoxoError("x", status_code=502).is_5xx


def test_config_error_exit_code():
    assert exit_code_for(ConfigError("bad config")) == 2


def test_unknown_exception_exit_code():
    assert exit_code_for(ValueError("nope")) == 1
