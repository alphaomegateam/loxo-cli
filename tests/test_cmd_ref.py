import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_ref_job_types_after_id():
    respx.get("https://app.loxo.co/api/acme/job_types").mock(
        side_effect=[
            httpx.Response(200, json=[{"id": 1, "name": "Perm"}, {"id": 2, "name": "Temp"}]),
            httpx.Response(200, json=[]),
        ]
    )
    result = runner.invoke(app, ["--json", "ref", "job-types"], env=ENV)
    assert [x["name"] for x in json.loads(result.stdout)] == ["Perm", "Temp"]


@respx.mock
def test_ref_custom_fields():
    respx.get("https://app.loxo.co/api/acme/dynamic_fields").mock(
        side_effect=[
            httpx.Response(200, json=[{"id": 1, "name": "custom_text_3"}]),
            httpx.Response(200, json=[]),
        ]
    )
    result = runner.invoke(app, ["--json", "ref", "custom-fields"], env=ENV)
    assert json.loads(result.stdout)[0]["name"] == "custom_text_3"


@respx.mock
def test_ref_hierarchies():
    respx.get("https://app.loxo.co/api/acme/dynamic_fields/7/hierarchies").mock(
        return_value=httpx.Response(200, json={"hierarchies": [{"id": 1, "name": "L1"}]})
    )
    result = runner.invoke(app, ["--json", "ref", "hierarchies", "7"], env=ENV)
    assert json.loads(result.stdout)[0]["name"] == "L1"
