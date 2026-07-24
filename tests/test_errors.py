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


def test_is_rate_limited():
    assert LoxoError("throttled", status_code=429).is_rate_limited
    assert not LoxoError("nope", status_code=404).is_rate_limited
    assert not LoxoError("network", status_code=None).is_rate_limited


def test_attempts_defaults_to_one_and_is_writable():
    err = LoxoError("boom", status_code=500)
    assert err.attempts == 1
    err.attempts = 4
    assert err.attempts == 4


def test_retry_after_defaults_to_none_and_round_trips():
    assert LoxoError("boom", status_code=429).retry_after is None
    assert LoxoError("boom", status_code=429, retry_after=2.5).retry_after == 2.5


def test_exit_code_mapping_is_unchanged_by_the_new_fields():
    assert LoxoError("t", status_code=429, retry_after=1.0).exit_code == 5
    assert LoxoError("t", status_code=404).exit_code == 4
    assert LoxoError("t", status_code=500).exit_code == 6
    assert LoxoError("t", status_code=None, is_timeout=True).exit_code == 7
