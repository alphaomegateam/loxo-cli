import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_candidates_list_under_job():
    respx.get("https://app.loxo.co/api/acme/jobs/3/candidates").mock(
        return_value=httpx.Response(
            200, json={"scroll_id": None, "candidates": [{"id": 1, "person_id": 50}]}
        )
    )
    result = runner.invoke(app, ["--json", "candidates", "list", "--job", "3"], env=ENV)
    assert json.loads(result.stdout)[0]["person_id"] == 50


@respx.mock
def test_candidates_add_sends_person_id():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 9, "person_id": 50})

    respx.post("https://app.loxo.co/api/acme/jobs/3/candidates").mock(side_effect=handler)
    result = runner.invoke(
        app, ["--json", "candidates", "add", "--job", "3", "--person", "50"], env=ENV
    )
    assert result.exit_code == 0
    assert captured["body"] == {"person_id": 50}


@respx.mock
def test_candidates_update_highlights():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 9})

    respx.put("https://app.loxo.co/api/acme/jobs/3/candidates/9").mock(side_effect=handler)
    result = runner.invoke(
        app,
        ["--json", "candidates", "update", "9", "--job", "3", "--highlights", "Strong"],
        env=ENV,
    )
    assert result.exit_code == 0
    assert captured["body"] == {"highlights": "Strong"}
