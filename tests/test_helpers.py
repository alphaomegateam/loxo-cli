import io

import pytest
import typer

from loxo_cli.commands._helpers import build_payload, load_data, parse_fields


def test_load_data_none():
    assert load_data(None) == {}


def test_load_data_inline_json():
    assert load_data('{"a": 1}') == {"a": 1}


def test_load_data_from_file(tmp_path):
    p = tmp_path / "body.json"
    p.write_text('{"person": {"name": "Jane"}}')
    assert load_data(f"@{p}") == {"person": {"name": "Jane"}}


def test_load_data_from_stdin():
    assert load_data("-", stdin=io.StringIO('{"x": 2}')) == {"x": 2}


def test_load_data_invalid_json_raises():
    with pytest.raises(typer.BadParameter):
        load_data("{not json}")


def test_parse_fields_simple():
    assert parse_fields(["name=Jane", "title=Eng"]) == {"name": "Jane", "title": "Eng"}


def test_parse_fields_repeated_key_becomes_list():
    assert parse_fields(["tag=a", "tag=b"]) == {"tag": ["a", "b"]}


def test_parse_fields_bracket_forces_list():
    assert parse_fields(["custom_hierarchy_5[]=x"]) == {"custom_hierarchy_5": ["x"]}


def test_parse_fields_missing_equals_raises():
    with pytest.raises(typer.BadParameter):
        parse_fields(["broken"])


def test_build_payload_merge_order():
    out = build_payload(
        "person",
        typed={"name": "Typed", "title": None},
        data={"name": "Data", "description": "d"},
        fields={"name": "Field"},
    )
    assert out == {"person": {"name": "Field", "description": "d"}}
