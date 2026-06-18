from loxo_cli.models.base import LoxoModel, unwrap_envelope
from loxo_cli.models.company import Company
from loxo_cli.models.person import Person
from loxo_cli.models.webhook import Webhook


def test_extra_fields_preserved():
    p = Person.model_validate({"id": 1, "name": "Jane", "custom_text_3": "utm-x"})
    assert p.id == 1
    assert p.name == "Jane"
    assert p.model_extra["custom_text_3"] == "utm-x"
    # round-trips into JSON output, custom field included
    assert p.model_dump(mode="json")["custom_text_3"] == "utm-x"


def test_unwrap_envelope_unwraps_when_present():
    assert unwrap_envelope({"person": {"id": 5}}, "person") == {"id": 5}


def test_unwrap_envelope_passthrough_when_flat():
    assert unwrap_envelope({"id": 5}, "company") == {"id": 5}


def test_company_optional_name():
    c = Company.model_validate({"id": 2})
    assert c.id == 2
    assert c.name is None


def test_webhook_fields():
    w = Webhook.model_validate(
        {"id": 7, "item_type": "candidate", "action": "create",
         "endpoint_url": "https://x"}
    )
    assert (w.item_type, w.action) == ("candidate", "create")


def test_base_is_extra_allow():
    assert LoxoModel.model_config["extra"] == "allow"
