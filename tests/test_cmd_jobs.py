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
