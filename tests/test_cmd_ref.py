import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_ref_job_types_single_fetch():
    # job_types ignores after_id (returns its full list every call), so the
    # command fetches once instead of driving the keyset paginator.
    route = respx.get("https://app.loxo.co/api/acme/job_types").mock(
        return_value=httpx.Response(
            200, json=[{"id": 1, "name": "Perm"}, {"id": 2, "name": "Temp"}]
        )
    )
    result = runner.invoke(app, ["--json", "ref", "job-types"], env=ENV)
    assert [x["name"] for x in json.loads(result.stdout)] == ["Perm", "Temp"]
    assert route.call_count == 1


@respx.mock
def test_ref_activity_types_single_fetch_no_after_id():
    # activity_types REJECTS after_id with HTTP 422. The command must not send
    # it: a single fetch with no after_id param, and never a second request.
    def handler(request):
        assert "after_id" not in request.url.params, "must not send after_id to activity_types"
        return httpx.Response(200, json=[{"id": 9, "name": "Call"}])

    route = respx.get("https://app.loxo.co/api/acme/activity_types").mock(side_effect=handler)
    result = runner.invoke(app, ["--json", "ref", "activity-types"], env=ENV)
    assert result.exit_code == 0
    assert [x["name"] for x in json.loads(result.stdout)] == ["Call"]
    assert route.call_count == 1


@respx.mock
def test_ref_source_types_still_paginates():
    # source_types genuinely honors after_id; the command must keep paging.
    route = respx.get("https://app.loxo.co/api/acme/source_types").mock(
        side_effect=[
            httpx.Response(200, json=[{"id": 10, "name": "A"}, {"id": 11, "name": "B"}]),
            httpx.Response(200, json=[{"id": 12, "name": "C"}]),
            httpx.Response(200, json=[]),
        ]
    )
    result = runner.invoke(app, ["--json", "ref", "source-types"], env=ENV)
    assert [x["name"] for x in json.loads(result.stdout)] == ["A", "B", "C"]
    assert route.call_count == 3


@respx.mock
def test_ref_custom_fields_single_fetch():
    # dynamic_fields is a flat config list that ignores after_id, so the command
    # fetches it exactly once rather than driving the keyset paginator (which the
    # endpoint would loop forever, causing 429s). A single non-empty response is
    # all the endpoint ever returns.
    route = respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "custom_text_3"}])
    )
    result = runner.invoke(app, ["--json", "ref", "custom-fields"], env=ENV)
    assert json.loads(result.stdout)[0]["name"] == "custom_text_3"
    assert route.call_count == 1


@respx.mock
def test_ref_lists_uses_person_lists_endpoint():
    # `ref lists` maps to the person_lists endpoint (GET /lists 404s). It returns
    # the full list in one response and ignores after_id -> single fetch.
    lists_route = respx.get("https://app.loxo.co/api/acme/lists").mock(
        return_value=httpx.Response(404, json={"status": 404, "error": "Not Found"})
    )
    person_lists_route = respx.get("https://app.loxo.co/api/acme/person_lists").mock(
        return_value=httpx.Response(200, json=[{"id": 5, "name": "Hot Leads"}])
    )
    result = runner.invoke(app, ["--json", "ref", "lists"], env=ENV)
    assert result.exit_code == 0
    assert [x["name"] for x in json.loads(result.stdout)] == ["Hot Leads"]
    assert person_lists_route.call_count == 1
    assert lists_route.call_count == 0  # must not hit the 404 path


@respx.mock
def test_ref_hierarchies():
    respx.get("https://app.loxo.co/api/acme/dynamic_fields/7/hierarchies").mock(
        return_value=httpx.Response(200, json={"hierarchies": [{"id": 1, "name": "L1"}]})
    )
    result = runner.invoke(app, ["--json", "ref", "hierarchies", "7"], env=ENV)
    assert json.loads(result.stdout)[0]["name"] == "L1"
