import json

import click
import pytest
from rich.console import Console

from loxo_cli.models.person import Person
from loxo_cli.output import _fmt, apply_jq, render, to_jsonable


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


def test_apply_jq_bare_path():
    # Leading '.' is optional (issue #8).
    assert apply_jq({"results": [{"id": 1}]}, "results") == [{"id": 1}]


def test_apply_jq_numeric_index():
    data = {"results": [{"title": "A"}, {"title": "B"}]}
    assert apply_jq(data, "results.1.title") == "B"
    assert apply_jq(data, ".results.0.title") == "A"


def test_apply_jq_index_out_of_range_is_none():
    assert apply_jq({"results": []}, "results.0") is None


def test_apply_jq_bracket_on_non_list_raises_clean_error():
    # A clean ClickException (rendered as "Error: ...") rather than a raw
    # ValueError traceback (issue #8).
    with pytest.raises(click.ClickException):
        apply_jq({"a": 1}, ".a[]")


def test_fmt_object_shows_name():
    # Loxo returns status/job_type/etc. as {"id", "name"} objects; tables show
    # the name (issue #6).
    assert _fmt({"id": 70251, "name": "Active"}) == "Active"


def test_fmt_object_without_name_falls_back_to_json():
    assert _fmt({"id": 1}) == json.dumps({"id": 1})


def test_render_json_never_colorized_even_when_forced(capsys):
    # Rich reports is_terminal=True under FORCE_COLOR even for a pipe; JSON must
    # still be emitted plain so json.loads works (issue #7).
    console = Console(force_terminal=True, force_interactive=False)
    render([{"id": 1}], as_json=True, console=console)
    out = capsys.readouterr().out
    assert "\x1b[" not in out
    assert json.loads(out) == [{"id": 1}]


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
