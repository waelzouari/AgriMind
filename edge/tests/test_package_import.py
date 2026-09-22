from agrimind_edge import __version__


def test_package_exposes_foundation_version() -> None:
    assert __version__ == "0.0.0"
