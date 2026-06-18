import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_api_get_emits_json():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(200, json={"people": [{"id": 1}]})
    )
    result = runner.invoke(app, ["--json", "api", "GET", "people"], env=ENV)
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"people": [{"id": 1}]}


@respx.mock
def test_api_post_with_inline_data():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"person": {"id": 9}})

    respx.post("https://app.loxo.co/api/acme/people").mock(side_effect=handler)
    result = runner.invoke(
        app,
        ["--json", "api", "POST", "people", "--data", '{"person":{"name":"J"}}'],
        env=ENV,
    )
    assert result.exit_code == 0
    assert captured["body"] == {"person": {"name": "J"}}


@respx.mock
def test_api_query_params():
    route = respx.get("https://app.loxo.co/api/acme/people").mock(
        return_value=httpx.Response(200, json={"people": []})
    )
    result = runner.invoke(
        app,
        ["--json", "api", "GET", "people", "-p", "query=eng", "-p", "per_page=5"],
        env=ENV,
    )
    assert result.exit_code == 0
    assert dict(route.calls.last.request.url.params) == {"query": "eng", "per_page": "5"}


@respx.mock
def test_api_all_autopaginates():
    respx.get("https://app.loxo.co/api/acme/people").mock(
        side_effect=[
            httpx.Response(200, json={"scroll_id": "C2", "people": [{"id": 1}]}),
            httpx.Response(200, json={"scroll_id": None, "people": [{"id": 2}]}),
        ]
    )
    result = runner.invoke(app, ["--json", "api", "GET", "people", "--all"], env=ENV)
    assert result.exit_code == 0
    assert [i["id"] for i in json.loads(result.stdout)] == [1, 2]


@respx.mock
def test_api_404_exit_code_4():
    respx.get("https://app.loxo.co/api/acme/people/9").mock(
        return_value=httpx.Response(404, text="nope")
    )
    result = runner.invoke(app, ["api", "GET", "people/9"], env=ENV)
    assert result.exit_code == 4
