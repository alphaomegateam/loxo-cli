import logging
from importlib.metadata import PackageNotFoundError, version

# The conventional way a library stays silent until its consumer opts in.
# Without a handler somewhere on this logger, Python's lastResort handler
# would still emit WARNING+ to stderr — exactly the uncontrollable output
# 0.6.1 removed. Applications configure logging themselves; the CLI adds
# its own stderr handler in __main__.
logging.getLogger(__name__).addHandler(logging.NullHandler())

try:
    # Single source of truth: the installed distribution's metadata (driven by
    # pyproject's version), so `loxo --version` can never drift from the release.
    __version__ = version("loxo-cli")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
