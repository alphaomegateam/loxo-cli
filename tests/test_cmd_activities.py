import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}
URL = "https://app.loxo.co/api/acme/person_events"

# Shape verified against the live API: a single GET comes back flat (no
# "person_event" envelope) and carries fields the list response omits.
RECORD = {
    "id": 1306041823,
    "notes": "<p>Phone call - closing search</p>",
    "person_id": 235668896,
    "activity_type_id": 2318706,
    "activity_type": {"id": 2318706, "key": "client_catch_up", "name": "Client Catch Up"},
    "job_id": 3633818,
    "company_id": 246412609,
    "event_deal_links": [],
    "ring_central_call": None,
    "twilio_call": None,
}


@respx.mock
def test_activities_list():
    respx.get("https://app.loxo.co/api/acme/person_events").mock(
        return_value=httpx.Response(
            200, json={"scroll_id": None, "person_events": [{"id": 1, "notes": "called"}]}
        )
    )
    result = runner.invoke(app, ["--json", "activities", "list"], env=ENV)
    assert json.loads(result.stdout)[0]["notes"] == "called"


@respx.mock
def test_activities_list_filters_by_person_and_company():
    route = respx.get("https://app.loxo.co/api/acme/person_events").mock(
        return_value=httpx.Response(200, json={"scroll_id": None, "person_events": []})
    )
    result = runner.invoke(
        app,
        ["--json", "activities", "list", "--person-id", "50", "--company-id", "7"],
        env=ENV,
    )
    assert result.exit_code == 0
    assert dict(route.calls.last.request.url.params) == {
        "person_id": "50",
        "company_id": "7",
        "per_page": "50",
    }


def test_activities_list_has_no_job_id_option():
    # job_id is not a valid person_events query param (Loxo returns 422), so the
    # list command must not advertise a --job-id filter.
    result = runner.invoke(app, ["activities", "list", "--help"], env=ENV)
    assert "--job-id" not in result.stdout


@respx.mock
def test_activities_add_wraps_person_event():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 9})

    respx.post("https://app.loxo.co/api/acme/person_events").mock(side_effect=handler)
    result = runner.invoke(
        app,
        [
            "--json",
            "activities",
            "add",
            "--activity-type-id",
            "2",
            "--person-id",
            "50",
            "--notes",
            "Followed up",
        ],
        env=ENV,
    )
    assert result.exit_code == 0
    assert captured["body"] == {
        "person_event": {"activity_type_id": 2, "person_id": 50, "notes": "Followed up"}
    }


@respx.mock
def test_get_is_flat_not_enveloped():
    respx.get(f"{URL}/1306041823").mock(return_value=httpx.Response(200, json=RECORD))
    result = runner.invoke(app, ["--json", "activities", "get", "1306041823"], env=ENV)
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["id"] == 1306041823
    assert body["activity_type"]["name"] == "Client Catch Up"


@respx.mock
def test_get_still_unwraps_if_enveloped():
    respx.get(f"{URL}/1306041823").mock(
        return_value=httpx.Response(200, json={"person_event": RECORD})
    )
    result = runner.invoke(app, ["--json", "activities", "get", "1306041823"], env=ENV)
    assert json.loads(result.stdout)["id"] == 1306041823


@respx.mock
def test_get_maps_null_body_to_exit_code_4():
    # Verified live: an unknown person_event id returns HTTP 200 with a bare
    # `null` body instead of a 404, so the command has to detect that itself
    # rather than printing "null" and exiting 0.
    respx.get(f"{URL}/1").mock(return_value=httpx.Response(200, json=None))
    result = runner.invoke(app, ["activities", "get", "1"], env=ENV)
    assert result.exit_code == 4


@respx.mock
def test_get_maps_404_to_exit_code_4():
    respx.get(f"{URL}/1").mock(return_value=httpx.Response(404, json={"error": "Not Found"}))
    result = runner.invoke(app, ["activities", "get", "1"], env=ENV)
    assert result.exit_code == 4
