import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_activities_list():
    respx.get("https://app.loxo.co/api/acme/person_events").mock(
        return_value=httpx.Response(200, json={
            "scroll_id": None, "person_events": [{"id": 1, "notes": "called"}]}))
    result = runner.invoke(app, ["--json", "activities", "list"], env=ENV)
    assert json.loads(result.stdout)[0]["notes"] == "called"


@respx.mock
def test_activities_add_wraps_person_event():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 9})

    respx.post("https://app.loxo.co/api/acme/person_events").mock(side_effect=handler)
    result = runner.invoke(
        app, ["--json", "activities", "add", "--activity-type-id", "2",
              "--person-id", "50", "--notes", "Followed up"],
        env=ENV)
    assert result.exit_code == 0
    assert captured["body"] == {"person_event": {"activity_type_id": 2,
                                                 "person_id": 50,
                                                 "notes": "Followed up"}}
