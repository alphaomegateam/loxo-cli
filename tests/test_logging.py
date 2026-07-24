"""Client output goes through `logging`, and only the CLI writes to stderr.

A library must not print at an application that owns its own logger, so the
package logs and stays silent until something attaches a handler. The CLI is
that something: it attaches a stderr handler so the end-to-end behavior a
terminal user sees is unchanged.
"""

import json
import logging

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app
from loxo_cli.client import LoxoClient
from loxo_cli.config import LoxoSettings

SETTINGS = LoxoSettings(api_key="testkey", slug="acme", base_url="https://app.loxo.co/api")
PEOPLE = "https://app.loxo.co/api/acme/people"
JOB_TYPES = "https://app.loxo.co/api/acme/job_types"

runner = CliRunner()
ENV = {"LOXO_API_KEY": "testkey", "LOXO_API_SLUG": "acme"}


def _throttled_then_ok(payload):
    return [
        httpx.Response(429, headers={"Retry-After": "5"}, text="slow down"),
        httpx.Response(200, json=payload),
    ]


@respx.mock
def test_library_writes_nothing_to_stderr_by_default(capsys):
    # The FastAPI-style consumer: no logging configured, and a long retry.
    # The package's NullHandler must keep even the WARNING off stderr,
    # which Python's lastResort handler would otherwise emit.
    respx.get(PEOPLE).mock(side_effect=_throttled_then_ok({"people": []}))
    with LoxoClient(SETTINGS) as client:
        client.get("people")
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


def test_package_logger_has_a_null_handler():
    handlers = logging.getLogger("loxo_cli").handlers
    assert any(isinstance(h, logging.NullHandler) for h in handlers)


@respx.mock
def test_retry_notice_is_logged_at_warning(caplog):
    respx.get(PEOPLE).mock(side_effect=_throttled_then_ok({"people": []}))
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS) as client:
            client.get("people")
    notices = [r for r in caplog.records if "retrying in" in r.getMessage()]
    assert len(notices) == 1
    assert notices[0].levelno == logging.WARNING
    assert notices[0].getMessage() == "Request failed; retrying in 5.0s (attempt 1)..."


@respx.mock
def test_verbose_request_lines_are_logged_at_debug(caplog):
    respx.get(PEOPLE).mock(return_value=httpx.Response(200, json={}))
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS, verbose=True) as client:
            client.get("people")
    lines = [r for r in caplog.records if r.getMessage() == f"GET {PEOPLE}"]
    assert lines and all(r.levelno == logging.DEBUG for r in lines)


@respx.mock
def test_no_log_record_ever_carries_the_api_key(caplog):
    respx.get(PEOPLE).mock(side_effect=_throttled_then_ok({"people": []}))
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS, verbose=True) as client:
            client.get("people")
    assert caplog.records
    for record in caplog.records:
        assert "testkey" not in record.getMessage()
        assert "Authorization" not in record.getMessage()


# --- CLI end-to-end: today's terminal behavior is preserved -----------------


@respx.mock
def test_cli_announces_a_long_retry_without_verbose():
    respx.get(JOB_TYPES).mock(side_effect=_throttled_then_ok([{"id": 1, "name": "Perm"}]))
    result = runner.invoke(app, ["--json", "ref", "job-types"], env=ENV)
    assert result.exit_code == 0
    assert "retrying in 5.0s" in result.stderr
    # stdout stays parseable: the notice never contaminates --json.
    assert json.loads(result.stdout) == [{"id": 1, "name": "Perm"}]


@respx.mock
def test_cli_quiet_suppresses_the_retry_notice():
    respx.get(JOB_TYPES).mock(side_effect=_throttled_then_ok([{"id": 1, "name": "Perm"}]))
    result = runner.invoke(app, ["--quiet", "--json", "ref", "job-types"], env=ENV)
    assert result.exit_code == 0
    assert "retrying" not in result.stderr
    assert json.loads(result.stdout) == [{"id": 1, "name": "Perm"}]


@respx.mock
def test_cli_verbose_logs_requests_to_stderr_and_keeps_stdout_clean():
    respx.get(JOB_TYPES).mock(return_value=httpx.Response(200, json=[{"id": 1, "name": "Perm"}]))
    result = runner.invoke(app, ["--verbose", "--json", "ref", "job-types"], env=ENV)
    assert result.exit_code == 0
    assert f"GET {JOB_TYPES}" in result.stderr
    assert "testkey" not in result.stderr
    assert json.loads(result.stdout) == [{"id": 1, "name": "Perm"}]


@respx.mock
def test_cli_quiet_wins_over_verbose():
    respx.get(JOB_TYPES).mock(side_effect=_throttled_then_ok([{"id": 1, "name": "Perm"}]))
    result = runner.invoke(app, ["--quiet", "--verbose", "--json", "ref", "job-types"], env=ENV)
    assert result.exit_code == 0
    assert result.stderr == ""


@respx.mock
def test_cli_without_flags_stays_silent_on_a_short_retry():
    respx.get(JOB_TYPES).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=[{"id": 1, "name": "Perm"}]),
        ]
    )
    result = runner.invoke(app, ["--json", "ref", "job-types"], env=ENV)
    assert result.exit_code == 0
    assert result.stderr == ""
