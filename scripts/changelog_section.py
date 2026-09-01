"""Extract one version's section from CHANGELOG.md.

Used by .github/workflows/publish.yml to build a GitHub Release body from the
same text that already lives in the changelog, so the release notes and the
repo can never disagree.

    python scripts/changelog_section.py v0.8.0 [CHANGELOG.md]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Matches "## [0.8.0]" and "## 0.8.0", optionally followed by a date.
_HEADING = re.compile(r"^##\s+\[?(?P<version>[^\]\s]+)\]?", re.MULTILINE)


def extract(changelog: str, version: str) -> str:
    """Return the body of `version`'s section, without its heading.

    `version` may carry a leading "v" so a git tag name can be passed straight
    through. Raises KeyError if there is no such section — returning "" instead
    would publish a release with an empty body and no obvious cause.
    """
    wanted = version.lstrip("v")
    matches = list(_HEADING.finditer(changelog))
    for index, match in enumerate(matches):
        if match.group("version").lstrip("v") != wanted:
            continue
        start = match.end()
        # Run to the next version heading, or to EOF for the oldest entry.
        end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
        return changelog[start:end].strip()
    raise KeyError(f"CHANGELOG.md has no section for version {wanted}")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[1]) if len(argv) > 1 else Path("CHANGELOG.md")
    try:
        print(extract(path.read_text(encoding="utf-8"), argv[0]))
    except (KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
