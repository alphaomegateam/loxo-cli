import json

from rich.console import Console

from loxo_cli.models.person import Person
from loxo_cli.output import apply_jq, render, to_jsonable


def test_to_jsonable_model():
    p = Person.model_validate({"id": 1, "name": "Jane", "custom_text_3": "x"})
    out = to_jsonable(p)
    assert out["id"] == 1 and out["custom_text_3"] == "x"


def test_to_jsonable_list_of_models():
    out = to_jsonable([Person.model_validate({"id": 1})])
    assert out == [
        {"id": 1, "name": None, "emails": None, "phones": None, "linkedin_url": None, "title": None}
    ]


def test_apply_jq_dotted():
    assert apply_jq({"a": {"b": 5}}, ".a.b") == 5


def test_apply_jq_map_field():
    data = [{"id": 1}, {"id": 2}]
    assert apply_jq(data, ".[].id") == [1, 2]


def test_render_json_to_nontty(capsys):
    console = Console(force_terminal=False)
    render([{"id": 1, "name": "Jane"}], as_json=True, console=console)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed == [{"id": 1, "name": "Jane"}]


def test_render_json_includes_custom_fields(capsys):
    p = Person.model_validate({"id": 1, "name": "Jane", "custom_text_3": "utm"})
    console = Console(force_terminal=False)
    render(p, as_json=True, console=console)
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["custom_text_3"] == "utm"


def test_render_table_to_tty(capsys):
    console = Console(force_terminal=True, width=80)
    render([{"id": 1, "name": "Jane"}], as_json=False, columns=["id", "name"], console=console)
    out = capsys.readouterr().out
    assert "Jane" in out
    assert "id" in out
