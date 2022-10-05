"""The :mod:`tyro.extras` submodule contains helpers that complement :func:`tyro.cli()`.

Compared to the core interface, APIs here are more likely to be changed or deprecated. """

from .._argparse_formatter import set_accent_color
from .._cli import get_parser
from ._base_configs import subcommand_type_from_defaults
from ._choices_type import literal_type_from_choices
from ._serialization import from_yaml, to_yaml

__all__ = [
    "set_accent_color",
    "subcommand_type_from_defaults",
    "get_parser",
    "literal_type_from_choices",
    "from_yaml",
    "to_yaml",
]
