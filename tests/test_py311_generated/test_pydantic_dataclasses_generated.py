from __future__ import annotations

import contextlib
import io

import pytest
from helptext_utils import get_helptext_with_checks
from pydantic import ConfigDict
from pydantic.dataclasses import dataclass

import tyro


def test_pydantic_dataclass_field_docstring() -> None:
    """Test that pydantic dataclass field docstrings are retrieved for helptext."""

    @dataclass
    class SimpleConfig:
        """A simple configuration class."""

        x: str
        """This is the x parameter documentation."""

        y: int = 42
        """This is the y parameter documentation."""

    # Get helptext and check that field docstrings are included
    helptext = get_helptext_with_checks(SimpleConfig)

    # These assertions should pass when the bug is fixed
    assert "This is the x parameter documentation." in helptext
    assert "This is the y parameter documentation." in helptext


def test_pydantic_dataclass_with_config_field_docstring() -> None:
    """Test that pydantic dataclass field docstrings work with ConfigDict."""

    @dataclass(config=ConfigDict(use_attribute_docstrings=True))
    class ConfiguredDataclass:
        """A pydantic dataclass with configuration."""

        value: str
        """The value parameter with docstring."""

        count: int = 1
        """The count parameter with docstring."""

    # Get helptext and check that field docstrings are included
    helptext = get_helptext_with_checks(ConfiguredDataclass)

    # These assertions should pass when the bug is fixed
    assert "The value parameter with docstring." in helptext
    assert "The count parameter with docstring." in helptext


def test_pydantic_dataclass_class_docstring() -> None:
    """Test that pydantic dataclass class docstrings are retrieved."""

    @dataclass
    class ClassWithDocstring:
        """This is the class documentation that should appear in help."""

        param: str

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(ClassWithDocstring, args=["--help"])
    helptext = f.getvalue()

    # Class docstring should appear in helptext
    assert "This is the class documentation that should appear in help." in helptext


def test_pydantic_dataclass_mixed_docstrings() -> None:
    """Test both class and field docstrings together."""

    @dataclass
    class MixedDocstrings:
        """A dataclass with both class and field documentation."""

        name: str
        """The name field documentation."""

        age: int = 25
        """The age field documentation."""

        active: bool = True
        """The active status documentation."""

    helptext = get_helptext_with_checks(MixedDocstrings)

    # Class docstring should appear
    assert "A dataclass with both class and field documentation." in helptext

    # Field docstrings should appear (these will fail until the bug is fixed)
    assert "The name field documentation." in helptext
    assert "The age field documentation." in helptext
    assert "The active status documentation." in helptext
