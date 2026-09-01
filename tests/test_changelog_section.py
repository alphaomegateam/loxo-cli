import pytest

from changelog_section import extract

CHANGELOG = """# Changelog

## [0.8.0]

### Added

- `loxo activities get <id>`.

## [0.7.0]

### Added

- `loxo placements list`.

### Fixed

- Something else.

## [0.1.0]

Initial release.
"""


def test_extracts_named_section_without_its_heading():
    assert extract(CHANGELOG, "0.8.0") == "### Added\n\n- `loxo activities get <id>`."


def test_stops_at_the_next_version_heading():
    section = extract(CHANGELOG, "0.7.0")
    assert "- `loxo placements list`." in section
    assert "- Something else." in section
    assert "0.1.0" not in section
    assert "Initial release." not in section


def test_extracts_the_final_section_with_no_following_heading():
    # The oldest entry has no "## " after it; the scan must run to EOF rather
    # than returning empty.
    assert extract(CHANGELOG, "0.1.0") == "Initial release."


def test_accepts_a_v_prefixed_tag_name():
    # publish.yml passes $GITHUB_REF_NAME, which is "v0.8.0", not "0.8.0".
    assert extract(CHANGELOG, "v0.8.0") == extract(CHANGELOG, "0.8.0")


def test_unknown_version_raises():
    # A silent empty string would publish a release with a blank body.
    with pytest.raises(KeyError):
        extract(CHANGELOG, "9.9.9")


def test_real_changelog_has_a_section_for_the_current_version():
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    section = extract((root / "CHANGELOG.md").read_text(), version)
    assert section.strip(), f"CHANGELOG.md has no entry for version {version}"
