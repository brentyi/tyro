import sys
from typing import List

import pytest

import tyro

collect_ignore_glob: List[str] = []


def pytest_addoption(parser):
    """Add command-line option to select backend."""
    parser.addoption(
        "--backend",
        action="store",
        default="both",
        choices=["argparse", "tyro", "both"],
        help="Backend to test: argparse, tyro, or both (default: use current BACKEND setting)",
    )


def pytest_generate_tests(metafunc):
    """Parametrize tests by backend if --backend=both is specified."""
    backend_option = metafunc.config.getoption("--backend")

    # Parametrize all tests with a backend parameter.
    if backend_option == "both":
        # Run all tests with both backends.
        metafunc.parametrize(
            "backend", ["argparse", "tyro"], scope="function", indirect=True
        )
    elif backend_option in ["argparse", "tyro"]:
        # Run with specified backend.
        metafunc.parametrize(
            "backend", [backend_option], scope="function", indirect=True
        )
    else:
        # No parametrization - use default tyro backend.
        pass


@pytest.fixture(scope="function", autouse=True)
def backend(request):
    """Fixture that sets the backend for tests.

    This can be parametrized indirectly via pytest_generate_tests.
    """

    # Get the backend from the parameter if it exists, otherwise use default.
    if hasattr(request, "param"):
        backend_name = request.param
    else:
        backend_name = "tyro"

    original_backend = tyro._experimental_options["backend"]
    tyro._experimental_options["backend"] = backend_name
    yield backend_name
    tyro._experimental_options["backend"] = original_backend


if not sys.version_info >= (3, 9):
    collect_ignore_glob.append("*min_py39*.py")

if not sys.version_info >= (3, 10):
    collect_ignore_glob.append("*min_py310*.py")

if not sys.version_info >= (3, 11):
    collect_ignore_glob.append("*min_py311*.py")

if not sys.version_info >= (3, 12):
    collect_ignore_glob.append("*min_py312*.py")

if not sys.version_info >= (3, 13):
    collect_ignore_glob.append("*min_py313*.py")

if not sys.version_info >= (3, 11):
    collect_ignore_glob.append("test_py311_generated/*.py")

if sys.version_info >= (3, 13):
    collect_ignore_glob.append("*_exclude_py313*.py")

try:
    import flax  # noqa: I001,F401 # type: ignore
except ImportError:
    collect_ignore_glob.append("*_flax*.py")

try:
    import numpy  # noqa: I001,F401 # type: ignore
except ImportError:
    collect_ignore_glob.append("*_custom_constructors*.py")

try:
    import torch  # noqa: I001,F401 # type: ignore
except ImportError:
    collect_ignore_glob.append("*_torch*.py")
    collect_ignore_glob.append("*_base_configs_nested*.py")
