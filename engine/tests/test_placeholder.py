"""A trivial test that proves the package imports and pytest is wired up."""

import gridmind_engine


def test_package_imports_and_version():
    # If this fails, pytest.ini's "pythonpath = engine" is not being picked up.
    assert gridmind_engine.__version__ == "0.1.0"
