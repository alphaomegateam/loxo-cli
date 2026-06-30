import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_deals_list_omits_per_page():
    # The deals endpoint rejects per_page with HTTP 422
    # ({"errors":["Invalid parameters: [:per_page]"]}), so the command must not
    # send it. It uses scroll_id pagination with a server-fixed page size.
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200, json={"scroll_id": None, "deals": [{"id": 1, "name": "D1", "amount": 100.0}]}
        )

    respx.get("https://app.loxo.co/api/acme/deals").mock(side_effect=handler)
    result = runner.invoke(app, ["--json", "deals", "list"], env=ENV)
    assert result.exit_code == 0
    assert "per_page" not in seen["params"]
    assert json.loads(result.stdout)[0]["amount"] == 100.0


@respx.mock
def test_deals_list_all_omits_per_page():
    # --all must page via scroll_id without ever sending per_page.
    seen = []

    def handler(request):
        params = dict(request.url.params)
        seen.append(params)
        if "scroll_id" not in params:
            return httpx.Response(
                200, json={"scroll_id": "abc", "deals": [{"id": 1, "name": "D1"}]}
            )
        return httpx.Response(200, json={"scroll_id": None, "deals": []})

    respx.get("https://app.loxo.co/api/acme/deals").mock(side_effect=handler)
    result = runner.invoke(app, ["--json", "deals", "list", "--all"], env=ENV)
    assert result.exit_code == 0
    assert all("per_page" not in p for p in seen)
    assert [d["id"] for d in json.loads(result.stdout)] == [1]


@respx.mock
def test_deals_get_unwraps_envelope():
    respx.get("https://app.loxo.co/api/acme/deals/4").mock(
        return_value=httpx.Response(200, json={"deal": {"id": 4, "name": "D"}})
    )
    result = runner.invoke(app, ["--json", "deals", "get", "4"], env=ENV)
    assert json.loads(result.stdout)["id"] == 4


@respx.mock
def test_deals_create_wraps_and_types_amount():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"deal": {"id": 9}})

    respx.post("https://app.loxo.co/api/acme/deals").mock(side_effect=handler)
    result = runner.invoke(
        app,
        ["--json", "deals", "create", "--name", "Big", "--amount", "2500", "--person-id", "7"],
        env=ENV,
    )
    assert result.exit_code == 0
    assert captured["body"] == {"deal": {"name": "Big", "amount": 2500.0, "person_id": 7}}
