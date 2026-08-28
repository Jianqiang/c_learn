"""Sanity check that the package is importable and pytest is wired correctly."""
import learning_os


def test_package_importable():
    assert learning_os.__version__ == "0.1.0"
