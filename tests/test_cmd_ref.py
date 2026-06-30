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


# A representative slice of GET /dynamic_fields: built-in and agency-defined
# fields spread across more than one object (item_type).
DYNAMIC_FIELDS = [
    {
        "id": 1,
        "name": "Account manager",
        "key": "owned_by_id",
        "item_type": "Deal",
        "dynamic_field_type": {"id": 3, "name": "Enumeration"},
        "built_in": True,
    },
    {
        "id": 2,
        "name": "UTM Medium",
        "key": "custom_text_3",
        "item_type": "Deal",
        "dynamic_field_type": {"id": 1, "name": "Text"},
        "built_in": False,
    },
    {
        "id": 3,
        "name": "First Name",
        "key": "first_name",
        "item_type": "Person",
        "dynamic_field_type": {"id": 1, "name": "Text"},
        "built_in": True,
    },
]


@respx.mock
def test_ref_custom_fields_single_fetch():
    # dynamic_fields is a flat config list that ignores after_id, so the command
    # fetches it exactly once rather than driving the keyset paginator (which the
    # endpoint would loop forever, causing 429s). A single non-empty response is
    # all the endpoint ever returns. With no filter every field comes back, and
    # each row now exposes its `key`.
    route = respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=DYNAMIC_FIELDS)
    )
    result = runner.invoke(app, ["--json", "ref", "custom-fields"], env=ENV)
    keys = [x["key"] for x in json.loads(result.stdout)]
    assert keys == ["owned_by_id", "custom_text_3", "first_name"]
    assert route.call_count == 1


@respx.mock
def test_ref_custom_fields_filter_by_object():
    # --object matches item_type case-insensitively and returns only that
    # object's fields.
    respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=DYNAMIC_FIELDS)
    )
    result = runner.invoke(app, ["--json", "ref", "custom-fields", "--object", "deal"], env=ENV)
    rows = json.loads(result.stdout)
    assert {x["item_type"] for x in rows} == {"Deal"}
    assert [x["key"] for x in rows] == ["owned_by_id", "custom_text_3"]


@respx.mock
def test_ref_custom_fields_unknown_object_errors():
    # An item_type that isn't present is a usage error that names the available
    # object types.
    respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=DYNAMIC_FIELDS)
    )
    result = runner.invoke(app, ["ref", "custom-fields", "--object", "bogus"], env=ENV)
    assert result.exit_code == 2
    combined = result.output + (result.stderr if result.stderr_bytes else "")
    assert "Deal" in combined and "Person" in combined


@respx.mock
def test_ref_custom_fields_custom_only_drops_builtins():
    # --custom-only keeps only agency-defined (built_in == False) fields.
    respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=DYNAMIC_FIELDS)
    )
    result = runner.invoke(app, ["--json", "ref", "custom-fields", "--custom-only"], env=ENV)
    rows = json.loads(result.stdout)
    assert [x["key"] for x in rows] == ["custom_text_3"]


@respx.mock
def test_ref_custom_fields_json_carries_key_and_derived_type():
    # JSON output preserves the full record and adds a flat `type` derived from
    # dynamic_field_type.name.
    respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=DYNAMIC_FIELDS)
    )
    result = runner.invoke(app, ["--json", "ref", "custom-fields", "--object", "deal"], env=ENV)
    row = json.loads(result.stdout)[0]
    assert row["key"] == "owned_by_id"
    assert row["type"] == "Enumeration"


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


# The same hierarchy key is reused across objects with distinct ids, so a key
# lookup is ambiguous without --object.
HIER_FIELDS = [
    {
        "id": 100,
        "name": "Website Lead",
        "key": "custom_hierarchy_4",
        "item_type": "Deal",
        "dynamic_field_type": {"id": 6, "name": "Hierarchy"},
        "built_in": False,
    },
    {
        "id": 200,
        "name": "Hires for",
        "key": "custom_hierarchy_4",
        "item_type": "Person",
        "dynamic_field_type": {"id": 6, "name": "Hierarchy"},
        "built_in": False,
    },
]

# GET dynamic_fields/{id} (detail) embeds the field's own option list under
# `hierarchies` — this is the real per-field option set.
DEAL_FIELD_DETAIL = {
    "id": 100,
    "name": "Website Lead",
    "key_for_inline_edit": "custom_hierarchy_4",
    "item_type": "Deal",
    "dynamic_field_type": {"id": 6, "name": "Hierarchy"},
    "hierarchies": [{"id": 6251428, "name": "Yes", "hierarchies": []}],
    "built_in": False,
}


@respx.mock
def test_ref_hierarchies_numeric_id_uses_detail_endpoint():
    # A numeric id fetches the field DETAIL and emits its embedded options, NOT
    # the global taxonomy from the /hierarchies subpath.
    detail = respx.get("https://app.loxo.co/api/acme/dynamic_fields/100").mock(
        return_value=httpx.Response(200, json=DEAL_FIELD_DETAIL)
    )
    legacy = respx.get("https://app.loxo.co/api/acme/dynamic_fields/100/hierarchies").mock(
        return_value=httpx.Response(200, json={"hierarchies": [{"id": 1, "name": "GLOBAL"}]})
    )
    result = runner.invoke(app, ["--json", "ref", "hierarchies", "100"], env=ENV)
    rows = json.loads(result.stdout)
    assert [(r["id"], r["name"]) for r in rows] == [(6251428, "Yes")]
    assert detail.call_count == 1
    assert legacy.call_count == 0


@respx.mock
def test_ref_hierarchies_by_key_scoped_to_object():
    respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=HIER_FIELDS)
    )
    respx.get("https://app.loxo.co/api/acme/dynamic_fields/100").mock(
        return_value=httpx.Response(200, json=DEAL_FIELD_DETAIL)
    )
    result = runner.invoke(
        app, ["--json", "ref", "hierarchies", "custom_hierarchy_4", "--object", "deal"], env=ENV
    )
    assert [r["name"] for r in json.loads(result.stdout)] == ["Yes"]


@respx.mock
def test_ref_hierarchies_ambiguous_key_errors():
    # custom_hierarchy_4 exists on Deal and Person; without --object it's
    # ambiguous and the error lists the matches.
    respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=HIER_FIELDS)
    )
    result = runner.invoke(app, ["ref", "hierarchies", "custom_hierarchy_4"], env=ENV)
    assert result.exit_code == 2
    combined = result.output + (result.stderr if result.stderr_bytes else "")
    assert "Deal" in combined and "Person" in combined


@respx.mock
def test_ref_hierarchies_key_object_no_match_errors():
    # The key isn't present on the requested object.
    respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=HIER_FIELDS)
    )
    result = runner.invoke(
        app, ["ref", "hierarchies", "custom_hierarchy_4", "--object", "company"], env=ENV
    )
    assert result.exit_code == 2


@respx.mock
def test_ref_hierarchies_unknown_key_errors():
    respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        return_value=httpx.Response(200, json=HIER_FIELDS)
    )
    result = runner.invoke(app, ["ref", "hierarchies", "custom_text_99"], env=ENV)
    assert result.exit_code == 2
