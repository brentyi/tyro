"""Utilities for working with strings."""

import enum
import functools
import re
import textwrap
from typing import Type, TypeVar

from typing_extensions import get_args

from . import _resolver

NESTED_DATACLASS_DELIMETER: str = "."
SUBPARSER_DEST_FMT: str = "{name} (positional)"


def dedent(text: str) -> str:
    """Same as textwrap.dedent, but ignores the first line."""
    first_line, line_break, rest = text.partition("\n")
    if line_break == "":
        return textwrap.dedent(text)
    return f"{first_line.strip()}\n{textwrap.dedent(rest)}"


_camel_separator_pattern = functools.lru_cache(maxsize=1)(
    lambda: re.compile("((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))")
)


def hyphen_separated_from_camel_case(name: str) -> str:
    return _camel_separator_pattern().sub(r"-\1", name).lower()


def subparser_name_from_type(cls: Type) -> str:
    cls, type_from_typevar = _resolver.resolve_generic_classes(cls)
    if len(type_from_typevar) == 0:
        assert hasattr(cls, "__name__")
        return hyphen_separated_from_camel_case(cls.__name__)  # type: ignore

    return "-".join(
        map(
            subparser_name_from_type,
            [cls] + list(type_from_typevar.values()),
        )
    )


T = TypeVar("T")


def instance_from_string(typ: Type[T], arg: str) -> T:
    """Given a type and and a string from the command-line, reconstruct an object. Not
    intended to deal with containers.

    This is intended to replace all calls to `type(string)`, which can cause unexpected
    behavior. As an example, note that the following argparse code will always print
    `True`, because `bool("True") == bool("False") == bool("0") == True`.
    ```
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--flag", type=bool)

    print(parser.parse_args().flag)
    ```
    """
    assert len(get_args(typ)) == 0, f"Type {typ} cannot be instantiated."
    if typ is bool:
        if arg == "True":
            return True  # type: ignore
        elif arg == "False":
            return False  # type: ignore
        else:
            raise ValueError(f"Boolean (True/False) expected, but got {arg}.")
    elif issubclass(typ, enum.Enum):
        try:
            return typ[arg]  # type: ignore
        except KeyError as e:
            # Raise enum key errors as value errors.
            raise ValueError(*e.args)
    else:
        return typ(arg)  # type: ignore
