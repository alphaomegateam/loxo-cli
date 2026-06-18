import json

import httpx
import respx
from typer.testing import CliRunner

from loxo_cli.__main__ import app

runner = CliRunner()
ENV = {"LOXO_API_KEY": "k", "LOXO_API_SLUG": "acme"}


@respx.mock
def test_webhooks_list_handles_list_response():
    respx.get("https://app.loxo.co/api/acme/webhooks").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "item_type": "candidate"}]))
    result = runner.invoke(app, ["--json", "webhooks", "list"], env=ENV)
    assert json.loads(result.stdout)[0]["id"] == 1


@respx.mock
def test_webhooks_create_validates_and_wraps():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 9, "item_type": "candidate",
                                         "action": "create",
                                         "endpoint_url": "https://x"})

    respx.post("https://app.loxo.co/api/acme/webhooks").mock(side_effect=handler)
    result = runner.invoke(
        app, ["--json", "webhooks", "create", "--item-type", "candidate",
              "--action", "create", "--url", "https://x"],
        env=ENV)
    assert result.exit_code == 0
    assert captured["body"] == {"webhook": {"item_type": "candidate",
                                            "action": "create",
                                            "endpoint_url": "https://x"}}


def test_webhooks_create_rejects_bad_item_type():
    result = runner.invoke(
        app, ["webhooks", "create", "--item-type", "banana",
              "--action", "create", "--url", "https://x"],
        env=ENV)
    assert result.exit_code == 2  # Typer usage error


@respx.mock
def test_webhooks_delete_requires_confirmation():
    route = respx.delete("https://app.loxo.co/api/acme/webhooks/5").mock(
        return_value=httpx.Response(200, json={}))
    # No --yes and declining the prompt -> no DELETE call.
    result = runner.invoke(app, ["webhooks", "delete", "5"], input="n\n", env=ENV)
    assert route.called is False
    # With --yes -> DELETE happens.
    result = runner.invoke(app, ["webhooks", "delete", "5", "--yes"], env=ENV)
    assert result.exit_code == 0
    assert route.called is True
