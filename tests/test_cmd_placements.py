import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}
URL = "https://app.loxo.co/api/acme/placements"

# Shape verified against the live API: person and job are nested objects, and
# the money fields come back as STRINGS, not numbers.
RECORD = {
    "id": 547439,
    "person": {"id": 233097840, "name": "Meredith Kirk"},
    "job": {"id": 3406638, "title": "CRM Operations", "company": {"id": 1, "name": "Taskrabbit"}},
    "start_date": "2025-10-08",
    "end_date": "2027-08-31",
    "salary": "6065.0",
    "bill_rate": "105.0",
}


@respx.mock
def test_list_omits_page_size_params():
    # placements rejects BOTH per_page and page with 422 "Invalid parameters",
    # so the command must send neither.
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"scroll_id": None, "placements": [RECORD]})

    respx.get(URL).mock(side_effect=handler)
    result = runner.invoke(app, ["--json", "placements", "list"], env=ENV)
    assert result.exit_code == 0
    assert "per_page" not in seen["params"]
    assert "page" not in seen["params"]
    assert json.loads(result.stdout)[0]["id"] == 547439


@respx.mock
def test_list_sends_server_side_filters():
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"scroll_id": None, "placements": []})

    respx.get(URL).mock(side_effect=handler)
    result = runner.invoke(
        app,
        [
            "--json",
            "placements",
            "list",
            "--job",
            "3406638",
            "-q",
            "meredith",
            "--person-global-status-id",
            "4",
            "--include-related-agencies",
        ],
        env=ENV,
    )
    assert result.exit_code == 0
    assert seen["params"]["job_id"] == "3406638"
    assert seen["params"]["query"] == "meredith"
    assert seen["params"]["person_global_status_id"] == "4"
    assert seen["params"]["include_related_agencies"] == "true"


@respx.mock
def test_list_omits_unset_filters():
    # An unset --job must not become job_id=None in the query string.
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"scroll_id": None, "placements": []})

    respx.get(URL).mock(side_effect=handler)
    assert runner.invoke(app, ["--json", "placements", "list"], env=ENV).exit_code == 0
    assert seen["params"] == {}


@respx.mock
def test_list_all_pages_via_scroll_id():
    seen = []

    def handler(request):
        params = dict(request.url.params)
        seen.append(params)
        if "scroll_id" not in params:
            return httpx.Response(200, json={"scroll_id": "abc", "placements": [RECORD]})
        return httpx.Response(200, json={"scroll_id": None, "placements": []})

    respx.get(URL).mock(side_effect=handler)
    result = runner.invoke(app, ["--json", "placements", "list", "--all"], env=ENV)
    assert result.exit_code == 0
    assert all("per_page" not in p for p in seen)
    assert [p["id"] for p in json.loads(result.stdout)] == [547439]


@respx.mock
def test_list_all_carries_filters_across_pages():
    seen = []

    def handler(request):
        params = dict(request.url.params)
        seen.append(params)
        if "scroll_id" not in params:
            return httpx.Response(200, json={"scroll_id": "abc", "placements": [RECORD]})
        return httpx.Response(200, json={"scroll_id": None, "placements": []})

    respx.get(URL).mock(side_effect=handler)
    result = runner.invoke(
        app, ["--json", "placements", "list", "--all", "--job", "3406638"], env=ENV
    )
    assert result.exit_code == 0
    assert all(p["job_id"] == "3406638" for p in seen)


@respx.mock
def test_list_preserves_string_money_fields():
    # Declaring salary as a float would coerce "6065.0" -> 6065.0 and stop
    # --json from matching what the API actually returned.
    respx.get(URL).mock(
        return_value=httpx.Response(200, json={"scroll_id": None, "placements": [RECORD]})
    )
    result = runner.invoke(app, ["--json", "placements", "list"], env=ENV)
    row = json.loads(result.stdout)[0]
    assert row["salary"] == "6065.0"
    assert row["bill_rate"] == "105.0"


@respx.mock
def test_list_client_side_filter():
    other = {**RECORD, "id": 2, "person": {"id": 9, "name": "Someone Else"}}
    respx.get(URL).mock(
        return_value=httpx.Response(200, json={"scroll_id": None, "placements": [RECORD, other]})
    )
    result = runner.invoke(
        app, ["--json", "placements", "list", "--filter", "person=Meredith Kirk"], env=ENV
    )
    assert [p["id"] for p in json.loads(result.stdout)] == [547439]


@respx.mock
def test_get_is_flat_not_enveloped():
    respx.get(f"{URL}/547439").mock(return_value=httpx.Response(200, json=RECORD))
    result = runner.invoke(app, ["--json", "placements", "get", "547439"], env=ENV)
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["id"] == 547439
    assert body["person"]["name"] == "Meredith Kirk"


@respx.mock
def test_get_still_unwraps_if_enveloped():
    respx.get(f"{URL}/547439").mock(return_value=httpx.Response(200, json={"placement": RECORD}))
    result = runner.invoke(app, ["--json", "placements", "get", "547439"], env=ENV)
    assert json.loads(result.stdout)["id"] == 547439


@respx.mock
def test_get_maps_404_to_exit_code_4():
    respx.get(f"{URL}/1").mock(return_value=httpx.Response(404, json={"error": "Not Found"}))
    result = runner.invoke(app, ["placements", "get", "1"], env=ENV)
    assert result.exit_code == 4


def test_no_write_commands_are_exposed():
    # Writes are deliberately absent: the API drops custom_* fields on write,
    # so agencies with a required custom field cannot create a placement.
    result = runner.invoke(app, ["placements", "--help"], env=ENV)
    assert "create" not in result.stdout
    assert "update" not in result.stdout
