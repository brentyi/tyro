import dataclasses
from typing import Union

import pytest
from pydantic import BaseModel
from typing_extensions import Literal

import tyro


def test_duplicate_subcommand_warning():
    """Test that a warning is raised when a subcommand is duplicated.
    
    Adapted from an example by @foges in https://github.com/brentyi/tyro/issues/273
    """

    class foo:
        class Config(BaseModel):
            name: Literal["foo"] = "foo"

    class bar:
        class Config(BaseModel):
            name: Literal["bar"] = "bar"

    ConfigType = Union[foo.Config, bar.Config]  # Python 3.7 compatible syntax

    # This should raise a warning about duplicate subcommands
    with pytest.warns(UserWarning, match=r".*subcommand.*already exists.*"):
        tyro.cli(ConfigType, args=["--help"])