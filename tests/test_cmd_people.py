import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_people_list_paginates_and_outputs():
    respx.get("https://app.loxo.co/api/acme/people").mock(side_effect=[
        httpx.Response(200, json={"scroll_id": "C2", "people": [{"id": 1, "name": "A"}]}),
        httpx.Response(200, json={"scroll_id": None, "people": [{"id": 2, "name": "B"}]}),
    ])
    result = runner.invoke(app, ["--json", "people", "list", "--all"], env=ENV)
    assert result.exit_code == 0
    assert [p["id"] for p in json.loads(result.stdout)] == [1, 2]


@respx.mock
def test_people_get_outputs_person():
    respx.get("https://app.loxo.co/api/acme/people/5").mock(
        return_value=httpx.Response(200, json={"id": 5, "name": "Jane",
                                               "custom_text_3": "utm"})
    )
    result = runner.invoke(app, ["--json", "people", "get", "5"], env=ENV)
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["id"] == 5 and out["custom_text_3"] == "utm"


@respx.mock
def test_people_create_wraps_person_and_merges_flags():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"person": {"id": 9, "name": "Jane"}})

    respx.post("https://app.loxo.co/api/acme/people").mock(side_effect=handler)
    result = runner.invoke(
        app,
        ["--json", "people", "create", "--name", "Jane",
         "--field", "custom_text_3=utm"],
        env=ENV,
    )
    assert result.exit_code == 0
    assert captured["body"] == {"person": {"name": "Jane", "custom_text_3": "utm"}}
    assert json.loads(result.stdout)["id"] == 9


@respx.mock
def test_people_update_puts_person():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"person": {"id": 5, "title": "VP"}})

    respx.put("https://app.loxo.co/api/acme/people/5").mock(side_effect=handler)
    result = runner.invoke(
        app, ["--json", "people", "update", "5", "--title", "VP"], env=ENV)
    assert result.exit_code == 0
    assert captured["body"] == {"person": {"title": "VP"}}
