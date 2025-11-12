from __future__ import annotations

import shutil
import sys
from typing import Any, Dict, Literal

from tyro.constructors._registry import check_default_instances_context
from tyro.constructors._struct_spec import (
    InvalidDefaultInstanceError,
    UnsupportedStructTypeMessage,
)

from . import _fields, _singleton
from . import _fmtlib as fmt
from .conf import _confstruct


def match_subcommand(
    default: Any,
    subcommand_config_from_name: Dict[str, _confstruct._SubcommandConfig],
    subcommand_type_from_name: Dict[str, type],
    extern_prefix: str,
) -> str:
    """Given a subcommand mapping and a default, return which subcommand the default
    corresponds to.

    TOOD: this function is based on heuristics. While it should be robust to
    most real-world scenarios, there's room for improvement for generic types.
    """

    # Get default subcommand name: by identity.
    for subcommand_name, conf in subcommand_config_from_name.items():
        if conf.default in _singleton.MISSING_AND_MISSING_NONPROP:
            continue
        if default is conf.default:
            return subcommand_name

    # Get default subcommand name: by default value.
    for subcommand_name, conf in subcommand_config_from_name.items():
        if conf.default in _singleton.MISSING_AND_MISSING_NONPROP:
            continue
        equal = default == conf.default
        if isinstance(equal, bool) and equal:
            return subcommand_name

    # Get first subcommand that doesn't throw an error in strict mode.
    errors: list[InvalidDefaultInstanceError] = []
    for subcommand_name, subcommand_type in subcommand_type_from_name.items():
        # We could also use typeguard here, but for now (November 19, 2024)
        # our own implementation has better support for nested generics.

        # try:
        #     import typeguard
        #
        #     typeguard.check_type(default, subcommand_type)
        #     return subcommand_name
        # except typeguard.TypeCheckError:
        #     continue
        maybe_error = _recursive_struct_match(subcommand_type, default, root=True)
        if not isinstance(maybe_error, InvalidDefaultInstanceError):
            return subcommand_name
        errors.append(maybe_error)

    # Failed. This should never happen, we'll raise an error outside of this function if
    # this is the case.
    details = []
    for subcommand_name, error in zip(subcommand_type_from_name, errors):
        details.append("")
        details.append(
            fmt.text(
                fmt.text["yellow", "bold"](subcommand_name),
                " was not a match because:",
            )
        )
        # Add each message in the tuple as its own bullet point.
        for msg in error.message:
            details.append(fmt.cols((fmt.text["dim"]("• "), 2), msg))
    details.append("")
    details.append(fmt.hr["red"]())
    details.append(
        "Debugging: check that the field default matches a member of the union type."
    )

    error_message = fmt.box["bright_red"](
        fmt.text["bright_red", "bold"]("Invalid input to tyro.cli()"),
        fmt.rows(
            fmt.text(
                "The default value of the ",
                fmt.text["green", "bold"](extern_prefix),
                " field could not be matched to any of its subcommands.",
            ),
            fmt.hr["red"](),
            *details,
        ),
    )
    print(
        "\n".join(error_message.render(width=min(shutil.get_terminal_size()[0], 80))),
        file=sys.stderr,
        flush=True,
    )
    sys.exit(2)


def _recursive_struct_match(
    subcommand_type: Any, default: Any, root: bool, intern_prefix: str = ""
) -> Literal[True] | InvalidDefaultInstanceError:
    """Returns `True` if the given type and default instance are compatible
    with each other."""
    # Can we generate a field list from this type?
    with check_default_instances_context():
        maybe_field_list = _fields.field_list_from_type_or_callable(
            subcommand_type, default, support_single_arg_types=root
        )

    # Found a struct type that matches, but the default instance isn't compatible.
    if isinstance(maybe_field_list, InvalidDefaultInstanceError):
        return maybe_field_list

    # Base case: found a leaf.
    if isinstance(maybe_field_list, UnsupportedStructTypeMessage):
        return True

    field_list = maybe_field_list
    for field in field_list[1]:
        field_check = _recursive_struct_match(
            field.type,
            field.default,
            root=False,
            intern_prefix=intern_prefix + field.intern_name + ".",
        )
        if isinstance(field_check, InvalidDefaultInstanceError):
            # Add context about which field failed.
            field_path = (
                field.intern_name
                if intern_prefix == ""
                else intern_prefix + field.intern_name
            )
            return InvalidDefaultInstanceError(
                (
                    fmt.text(
                        "Field ",
                        fmt.text["magenta", "bold"](field_path),
                        " has invalid default",
                    ),
                    *field_check.message,
                )
            )

    return True
