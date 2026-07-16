import io

import pytest
import typer

from loxo_cli.commands._helpers import (
    apply_filters,
    build_payload,
    load_data,
    parse_fields,
)


def test_apply_filters_empty_is_passthrough():
    items = [{"id": 1}, {"id": 2}]
    assert apply_filters(items, []) is items


def test_apply_filters_exact_scalar():
    items = [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]
    assert apply_filters(items, ["title=A"]) == [{"id": 1, "title": "A"}]


def test_apply_filters_matches_object_name():
    items = [
        {"id": 1, "status": {"id": 1, "name": "Active"}},
        {"id": 2, "status": {"id": 2, "name": "Closed"}},
    ]
    assert [i["id"] for i in apply_filters(items, ["status=Active"])] == [1]


def test_apply_filters_multiple_are_anded():
    items = [
        {"id": 1, "title": "A", "stage": "x"},
        {"id": 2, "title": "A", "stage": "y"},
    ]
    assert [i["id"] for i in apply_filters(items, ["title=A", "stage=y"])] == [2]


def test_apply_filters_bad_pair_raises():
    with pytest.raises(typer.BadParameter):
        apply_filters([{"id": 1}], ["broken"])


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


@pytest.mark.parametrize("raw", ["[1, 2]", '"just a string"', "42", "true", "null"])
def test_load_data_non_object_raises(raw):
    # Regression (#15): well-formed JSON that isn't an object must be rejected
    # with a clean BadParameter, not pass through and blow up later as a TypeError.
    with pytest.raises(typer.BadParameter):
        load_data(raw)


def test_load_data_non_object_from_file_raises(tmp_path):
    p = tmp_path / "body.json"
    p.write_text("[1, 2]")
    with pytest.raises(typer.BadParameter):
        load_data(f"@{p}")


def test_load_data_non_object_from_stdin_raises():
    with pytest.raises(typer.BadParameter):
        load_data("-", stdin=io.StringIO("[1, 2]"))


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
