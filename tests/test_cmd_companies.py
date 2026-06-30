import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_companies_list():
    # The companies endpoint rejects per_page with HTTP 422 (like deals); it
    # scroll_id-paginates with a server-fixed page size, so the command must not
    # send per_page.
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200, json={"scroll_id": None, "companies": [{"id": 1, "name": "Acme"}]}
        )

    respx.get("https://app.loxo.co/api/acme/companies").mock(side_effect=handler)
    result = runner.invoke(app, ["--json", "companies", "list"], env=ENV)
    assert result.exit_code == 0
    assert "per_page" not in seen["params"]
    assert json.loads(result.stdout)[0]["name"] == "Acme"


@respx.mock
def test_companies_list_all_omits_per_page():
    seen = []

    def handler(request):
        params = dict(request.url.params)
        seen.append(params)
        if "scroll_id" not in params:
            return httpx.Response(
                200, json={"scroll_id": "abc", "companies": [{"id": 1, "name": "Acme"}]}
            )
        return httpx.Response(200, json={"scroll_id": None, "companies": []})

    respx.get("https://app.loxo.co/api/acme/companies").mock(side_effect=handler)
    result = runner.invoke(app, ["--json", "companies", "list", "--all"], env=ENV)
    assert result.exit_code == 0
    assert all("per_page" not in p for p in seen)
    assert [c["id"] for c in json.loads(result.stdout)] == [1]


@respx.mock
def test_companies_get_flat():
    respx.get("https://app.loxo.co/api/acme/companies/3").mock(
        return_value=httpx.Response(200, json={"id": 3, "name": "Acme", "custom_text_3": "utm"})
    )
    result = runner.invoke(app, ["--json", "companies", "get", "3"], env=ENV)
    out = json.loads(result.stdout)
    assert out["id"] == 3 and out["custom_text_3"] == "utm"


@respx.mock
def test_companies_search_passes_query():
    route = respx.get("https://app.loxo.co/api/acme/companies").mock(
        return_value=httpx.Response(200, json={"scroll_id": None, "companies": []})
    )
    result = runner.invoke(app, ["--json", "companies", "search", "--query", "acme.com"], env=ENV)
    assert result.exit_code == 0
    assert route.calls.last.request.url.params["query"] == "acme.com"
    assert "per_page" not in route.calls.last.request.url.params


@respx.mock
def test_companies_create_wraps_company():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 5, "name": "New"})

    respx.post("https://app.loxo.co/api/acme/companies").mock(side_effect=handler)
    result = runner.invoke(
        app, ["--json", "companies", "create", "--name", "New", "--url", "https://n"], env=ENV
    )
    assert result.exit_code == 0
    assert captured["body"] == {"company": {"name": "New", "url": "https://n"}}
