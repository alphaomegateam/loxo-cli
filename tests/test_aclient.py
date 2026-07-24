"""Async client tests — the mirror of test_client.py."""

import httpx
import pytest
import respx

from loxo_cli.client import AsyncLoxoClient, build_async_client
from loxo_cli.config import LoxoSettings
from loxo_cli.errors import LoxoError
from loxo_cli.retry import RetryPolicy

SETTINGS = LoxoSettings(api_key="testkey", slug="acme", base_url="https://app.loxo.co/api")


@respx.mock
async def test_request_sends_auth_and_returns_json():
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(200, json={"people": []})
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        assert await client.get("people") == {"people": []}
    assert route.calls.last.request.headers["Authorization"] == "Bearer testkey"


@respx.mock
async def test_non_json_success_body_raises_loxo_error():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(200, text="<html>502 Bad Gateway</html>")
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            await client.get("people")
    assert ei.value.status_code == 200
    assert isinstance(ei.value.__cause__, ValueError)


@respx.mock
async def test_post_sends_json_body():
    captured = {}

    def handler(request):
        captured["body"] = request.content
        return httpx.Response(200, json={"person": {"id": 1}})

    respx.post("https://app.loxo.co/api/acme/people").mock(side_effect=handler)
    async with AsyncLoxoClient(SETTINGS) as client:
        assert await client.post("people", json={"person": {"name": "Jane"}}) == {
            "person": {"id": 1}
        }
    assert b"Jane" in captured["body"]


@respx.mock
async def test_4xx_raises_loxo_error():
    respx.get("https://app.loxo.co/api/acme/people/9").mock(
        return_value=httpx.Response(404, text="not found")
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            await client.get("people/9")
    assert ei.value.status_code == 404
    assert ei.value.is_4xx
    assert ei.value.attempts == 1


@respx.mock
async def test_429_then_200_succeeds_in_two_calls():
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json={"people": []})]
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        assert await client.get("people") == {"people": []}
    assert route.call_count == 2


@respx.mock
async def test_get_5xx_retries_to_exhaustion():
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="boom")
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            await client.get("people")
    assert route.call_count == 4
    assert ei.value.attempts == 4


@respx.mock
async def test_post_5xx_is_not_retried():
    route = respx.post("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="boom")
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError):
            await client.post("people", json={})
    assert route.call_count == 1


@respx.mock
async def test_retry_after_header_drives_the_delay(slept):
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json={}),
        ]
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        await client.get("people")
    assert slept == [2.0]


@respx.mock
async def test_retry_after_zero_still_retries(slept):
    # Mirror of the sync guard: a 0.0 delay must not be read as "give up".
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"people": []}),
        ]
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        assert await client.get("people") == {"people": []}
    assert route.call_count == 2
    assert slept == [0.0]


@respx.mock
async def test_exhausted_retries_chain_the_originating_httpx_error():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="boom")
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            await client.get("people")
    assert isinstance(ei.value.__cause__, httpx.HTTPStatusError)


@respx.mock
async def test_long_retry_is_announced_on_stderr_without_verbose(capsys):
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "5"}),
            httpx.Response(200, json={"people": []}),
        ]
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        assert await client.get("people") == {"people": []}
    captured = capsys.readouterr()
    assert "retrying in 5.0s" in captured.err
    assert "testkey" not in captured.err
    assert captured.out == ""


@respx.mock
async def test_retries_can_be_disabled():
    route = respx.get("https://app.loxo.co/api/acme/people").mock(return_value=httpx.Response(500))
    async with AsyncLoxoClient(SETTINGS, retry=RetryPolicy(max_retries=0)) as client:
        with pytest.raises(LoxoError):
            await client.get("people")
    assert route.call_count == 1


@respx.mock
async def test_error_message_never_contains_api_key():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(500, text="server error")
    )
    async with AsyncLoxoClient(SETTINGS) as client:
        with pytest.raises(LoxoError) as ei:
            await client.get("people")
    assert "testkey" not in str(ei.value)


@respx.mock
async def test_build_async_client_returns_a_usable_client():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    client = build_async_client(SETTINGS)
    try:
        assert await client.get("people") == {"ok": True}
    finally:
        await client.aclose()
