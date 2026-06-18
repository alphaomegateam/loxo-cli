import httpx
import pytest
import respx

from loxo_cli.client import LoxoClient, url_for
from loxo_cli.config import LoxoSettings
from loxo_cli.errors import LoxoError

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
