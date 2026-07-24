import logging

import httpx
import pytest
import respx

from loxo_cli.client import LoxoClient, url_for
from loxo_cli.config import LoxoSettings
from loxo_cli.errors import LoxoError
from loxo_cli.retry import RetryPolicy

SETTINGS = LoxoSettings(api_key="testkey", slug="acme", base_url="https://app.loxo.co/api")


def test_url_for_joins_parts():
    assert url_for(SETTINGS, "people") == "https://app.loxo.co/api/acme/people"
    assert url_for(SETTINGS, "/people/1") == "https://app.loxo.co/api/acme/people/1"


@respx.mock
def test_request_sends_auth_and_returns_json():
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(200, json={"people": [], "total_count": 0})
    )
    with LoxoClient(SETTINGS) as client:
        data = client.get("people")
    assert data == {"people": [], "total_count": 0}
    assert route.calls.last.request.headers["Authorization"] == "Bearer testkey"


@respx.mock
def test_non_json_success_body_raises_loxo_error():
    # A proxy's HTML error page under a 200, or a truncated body. Every
    # failure out of this client must be a LoxoError, never a bare
    # json.JSONDecodeError with no status_code and no attempts.
    respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(200, text="<html>502 Bad Gateway</html>")
    )
    with LoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            client.get("people")
    assert ei.value.status_code == 200
    assert isinstance(ei.value.__cause__, ValueError)
    assert "testkey" not in str(ei.value)


@respx.mock
def test_empty_success_body_still_decodes_to_none():
    respx.get("https://app.loxo.co/api/acme/people").mock(return_value=httpx.Response(204))
    with LoxoClient(SETTINGS) as client:
        assert client.get("people") is None


@respx.mock
def test_post_sends_json_body():
    captured = {}

    def handler(request):
        captured["body"] = request.content
        return httpx.Response(200, json={"person": {"id": 1}})

    respx.post("https://app.loxo.co/api/acme/people").mock(side_effect=handler)
    with LoxoClient(SETTINGS) as client:
        data = client.post("people", json={"person": {"name": "Jane"}})
    assert data == {"person": {"id": 1}}
    assert b"Jane" in captured["body"]


@respx.mock
def test_4xx_raises_loxo_error():
    respx.get("https://app.loxo.co/api/acme/people/9").mock(
        return_value=httpx.Response(404, text="not found")
    )
    with LoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            client.get("people/9")
    assert ei.value.status_code == 404
    assert ei.value.is_4xx


@respx.mock
def test_timeout_raises_loxo_error():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=httpx.ConnectTimeout("timed out")
    )
    with LoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            client.get("people")
    assert ei.value.is_timeout
    assert ei.value.status_code is None


@respx.mock
def test_error_message_never_contains_api_key():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="server error")
    )
    with LoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            client.get("people")
    assert "testkey" not in str(ei.value)


@respx.mock
def test_429_then_200_succeeds_in_two_calls():
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, text="slow down"),
            httpx.Response(200, json={"people": []}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        assert client.get("people") == {"people": []}
    assert route.call_count == 2


@respx.mock
def test_get_5xx_retries_to_exhaustion_then_raises():
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="boom")
    )
    with LoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            client.get("people")
    # 1 initial attempt + 3 retries
    assert route.call_count == 4
    assert ei.value.attempts == 4


@respx.mock
def test_post_5xx_is_not_retried():
    route = respx.post("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="boom")
    )
    with LoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            client.post("people", json={"person": {}})
    assert route.call_count == 1
    assert ei.value.attempts == 1


@respx.mock
def test_post_429_is_retried():
    route = respx.post("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, text="slow down"),
            httpx.Response(200, json={"person": {"id": 1}}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        assert client.post("people", json={"person": {}}) == {"person": {"id": 1}}
    assert route.call_count == 2


@respx.mock
def test_post_connect_error_is_retried():
    route = respx.post("https://app.loxo.co/api/acme/people").mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, json={"ok": True})]
    )
    with LoxoClient(SETTINGS) as client:
        assert client.post("people", json={}) == {"ok": True}
    assert route.call_count == 2


@respx.mock
def test_retry_after_header_drives_the_delay(slept):
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}, text="slow down"),
            httpx.Response(200, json={"people": []}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        client.get("people")
    assert slept == [2.0]


@respx.mock
def test_retry_after_zero_still_retries(slept):
    # `Retry-After: 0` yields a 0.0 delay. The retry decision must test
    # `delay is None`, not truthiness, or this request gives up immediately.
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, text="slow down"),
            httpx.Response(200, json={"people": []}),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        assert client.get("people") == {"people": []}
    assert route.call_count == 2
    assert slept == [0.0]


@respx.mock
def test_exhausted_retries_chain_the_originating_httpx_error():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="boom")
    )
    with LoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            client.get("people")
    assert isinstance(ei.value.__cause__, httpx.HTTPStatusError)


@respx.mock
def test_long_retry_is_announced_without_verbose(caplog, capsys):
    # 0.6.1: the notice is a log record rather than a print. The CLI turns it
    # back into a stderr line (tests/test_logging.py pins that end to end).
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "5"}, text="slow down"),
            httpx.Response(200, json={"people": []}),
        ]
    )
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS) as client:
            assert client.get("people") == {"people": []}
    assert "retrying in 5.0s" in caplog.text
    assert "testkey" not in caplog.text
    assert capsys.readouterr().out == ""  # stdout stays clean for --json


@respx.mock
def test_short_retry_stays_quiet_without_verbose(caplog):
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={}),
        ]
    )
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS) as client:
            client.get("people")
    assert caplog.text == ""


@respx.mock
def test_retries_can_be_disabled():
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="boom")
    )
    with LoxoClient(SETTINGS, retry=RetryPolicy(max_retries=0)) as client:
        with pytest.raises(LoxoError):
            client.get("people")
    assert route.call_count == 1


@respx.mock
def test_verbose_logs_each_retry_without_leaking_the_key(caplog):
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json={})]
    )
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS, verbose=True) as client:
            client.get("people")
    assert "retry 1" in caplog.text
    assert "testkey" not in caplog.text
    assert "Authorization" not in caplog.text


@respx.mock
def test_verbose_does_not_double_report_the_long_wait_notice(caplog):
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "5"}),
            httpx.Response(200, json={}),
        ]
    )
    with caplog.at_level(logging.DEBUG, logger="loxo_cli"):
        with LoxoClient(SETTINGS, verbose=True) as client:
            client.get("people")
    assert "retry 1 in 5.0s" in caplog.text
    assert "Request failed" not in caplog.text


@respx.mock
@pytest.mark.parametrize("exc_type", [httpx.TooManyRedirects, httpx.DecodingError])
def test_non_transport_request_errors_are_fatal_and_not_retried(exc_type):
    # The `fatal` branch of the client's exception routing: neither is a
    # transport failure, and replaying either only delays the same error.
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=exc_type("boom", request=httpx.Request("GET", "https://x"))
    )
    with LoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            client.get("people")
    assert route.call_count == 1
    assert ei.value.attempts == 1
    assert ei.value.status_code is None
    assert isinstance(ei.value.__cause__, exc_type)


@respx.mock
def test_non_json_body_reports_the_real_attempt_count():
    # The decode failure happens after the retry loop succeeded, so the error
    # must still say how many HTTP calls it took to get here.
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(500, text="boom"),
            httpx.Response(200, text="<html>not json</html>"),
        ]
    )
    with LoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            client.get("people")
    assert ei.value.attempts == 2
