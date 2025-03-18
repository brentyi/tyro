from typing import Union

import pytest
from pydantic import BaseModel
from typing_extensions import Literal

import tyro


def test_duplicate_subcommand_warning():
    """Test that a warning is raised when a subcommand is duplicated.

    Adapted from an example by @foges in https://github.com/brentyi/tyro/issues/273
    """

    # Creating two classes that will generate the same subcommand name
    class Config:
        class Nested(BaseModel):
            name: Literal["foo"] = "foo"

    class ConfigAgain:
        class Nested(BaseModel):
            value: Literal["bar"] = "bar"

    # This will create duplicate 'nested' subcommands
    ConfigType = Union[Config.Nested, ConfigAgain.Nested]

    # This should raise a warning about duplicate subcommands
    with pytest.warns(
        UserWarning,
        match=r"Duplicate subcommand name detected:.*'nested'.*will be overwritten.*Consider using distinct class names",
    ):
        try:
            # We need to catch SystemExit since tyro.cli() will exit
            # when called with --help or with no arguments for required options
            tyro.cli(ConfigType, args=["nested"])  # type: ignore
        except SystemExit:
            pass  # We're just testing for the warning, not the actual execution
