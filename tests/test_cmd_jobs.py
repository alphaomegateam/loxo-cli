import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_jobs_list_page_pagination():
    respx.get("https://app.loxo.co/api/acme/jobs").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "pagination": {"total_count": 3, "per_page": 2, "current_page": 1},
                    "results": [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}],
                },
            ),
            httpx.Response(
                200,
                json={
                    "pagination": {"total_count": 3, "per_page": 2, "current_page": 2},
                    "results": [{"id": 3, "title": "C"}],
                },
            ),
        ]
    )
    result = runner.invoke(app, ["--json", "jobs", "list", "--all", "--per-page", "2"], env=ENV)
    assert result.exit_code == 0
    assert [j["id"] for j in json.loads(result.stdout)] == [1, 2, 3]


@respx.mock
def test_jobs_list_status_object_does_not_crash():
    # Regression for issue #6: status comes back as an object.
    respx.get("https://app.loxo.co/api/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "pagination": {"total_count": 1, "per_page": 50, "current_page": 1},
                "results": [{"id": 1, "title": "VP", "status": {"id": 70251, "name": "Active"}}],
            },
        )
    )
    result = runner.invoke(app, ["--json", "jobs", "list"], env=ENV)
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["status"] == {"id": 70251, "name": "Active"}


@respx.mock
def test_jobs_list_status_object_renders_name_in_table():
    respx.get("https://app.loxo.co/api/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "pagination": {"total_count": 1, "per_page": 50, "current_page": 1},
                "results": [{"id": 1, "title": "VP", "status": {"id": 70251, "name": "Active"}}],
            },
        )
    )
    result = runner.invoke(app, ["jobs", "list"], env=ENV)
    assert result.exit_code == 0
    assert "Active" in result.stdout


@respx.mock
def test_jobs_list_filter_narrows_by_object_name():
    # Client-side --filter matches nested object 'name' (issue #10).
    respx.get("https://app.loxo.co/api/acme/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "pagination": {"total_count": 2, "per_page": 50, "current_page": 1},
                "results": [
                    {"id": 1, "title": "A", "status": {"id": 1, "name": "Active"}},
                    {"id": 2, "title": "B", "status": {"id": 2, "name": "Closed"}},
                ],
            },
        )
    )
    result = runner.invoke(app, ["--json", "jobs", "list", "--filter", "status=Active"], env=ENV)
    assert result.exit_code == 0
    assert [j["id"] for j in json.loads(result.stdout)] == [1]


@respx.mock
def test_jobs_get():
    respx.get("https://app.loxo.co/api/acme/jobs/7").mock(
        return_value=httpx.Response(200, json={"id": 7, "title": "Eng"})
    )
    result = runner.invoke(app, ["--json", "jobs", "get", "7"], env=ENV)
    assert json.loads(result.stdout)["title"] == "Eng"


@respx.mock
def test_jobs_create_wraps_job():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 11, "title": "New"})

    respx.post("https://app.loxo.co/api/acme/jobs").mock(side_effect=handler)
    result = runner.invoke(app, ["--json", "jobs", "create", "--title", "New"], env=ENV)
    assert result.exit_code == 0
    assert captured["body"] == {"job": {"title": "New"}}


@respx.mock
def test_jobs_create_rejects_unsaved_response():
    # Loxo answers some POST jobs calls 200 with the submitted payload and
    # "id": null — nothing is persisted. That used to surface as a raw pydantic
    # ValidationError traceback; it must be a clean CLI error instead.
    respx.post("https://app.loxo.co/api/acme/jobs").mock(
        return_value=httpx.Response(200, json={"job": {"id": None, "title": "T"}})
    )
    result = runner.invoke(app, ["jobs", "create", "--title", "T"], env=ENV)
    assert result.exit_code != 0
    combined = result.output + (result.stderr if result.stderr_bytes else "")
    assert "was not created" in combined
    # The old failure mode: an unhandled pydantic error rendered as a traceback.
    assert "ValidationError" not in combined
    assert "Traceback" not in combined


@respx.mock
def test_jobs_create_accepts_saved_response():
    respx.post("https://app.loxo.co/api/acme/jobs").mock(
        return_value=httpx.Response(200, json={"job": {"id": 7, "title": "T"}})
    )
    result = runner.invoke(app, ["--json", "jobs", "create", "--title", "T"], env=ENV)
    assert result.exit_code == 0
    assert json.loads(result.stdout)["id"] == 7
