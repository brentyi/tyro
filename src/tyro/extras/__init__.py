"""The :mod:`tyro.extras` submodule contains helpers that complement :func:`tyro.cli()`.

.. warning::

    Compared to the core interface, APIs here are more likely to be changed or deprecated.

"""

from .._argparse_formatter import set_accent_color as set_accent_color
from .._cli import get_parser as get_parser
from ._base_configs import overridable_config_cli as overridable_config_cli
from ._base_configs import (
    subcommand_type_from_defaults as subcommand_type_from_defaults,
)
from ._choices_type import literal_type_from_choices as literal_type_from_choices
from ._serialization import from_yaml as from_yaml
from ._serialization import to_yaml as to_yaml
from ._subcommand_app import SubcommandApp as SubcommandApp
from ._subcommand_cli_from_dict import (
    subcommand_cli_from_dict as subcommand_cli_from_dict,
)
