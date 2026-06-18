import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_companies_list():
    respx.get("https://app.loxo.co/api/acme/companies").mock(
        return_value=httpx.Response(
            200, json={"scroll_id": None, "companies": [{"id": 1, "name": "Acme"}]}
        )
    )
    result = runner.invoke(app, ["--json", "companies", "list"], env=ENV)
    assert json.loads(result.stdout)[0]["name"] == "Acme"


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
