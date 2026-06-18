from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth: the installed distribution's metadata (driven by
    # pyproject's version), so `loxo --version` can never drift from the release.
    __version__ = version("loxo-cli")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
