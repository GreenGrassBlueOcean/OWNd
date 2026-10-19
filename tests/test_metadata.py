"""Package metadata regression tests."""

import re
from importlib.metadata import version

from packaging.version import Version

import OWNd

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:(?:a|b|rc)(?:0|[1-9]\d*)"
    r"|-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def test_runtime_version_is_semver() -> None:
    """Require the public version to follow canonical PEP 440 / Semantic Versioning."""
    assert SEMVER_PATTERN.fullmatch(OWNd.__version__)
    assert str(Version(OWNd.__version__)) == OWNd.__version__


def test_runtime_version_matches_installed_package() -> None:
    """Keep the public runtime version aligned with package metadata."""
    assert Version(OWNd.__version__) == Version(version("OWNd"))

