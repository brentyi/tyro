from __future__ import annotations

import shutil
import sys
from typing import Any, Dict, Literal

from tyro.constructors._registry import check_default_instances_context
from tyro.constructors._struct_spec import (
    InvalidDefaultInstanceError,
    UnsupportedStructTypeMessage,
)

from . import _fields, _settings, _singleton
from . import _fmtlib as fmt
from .conf import _confstruct


def _count_matching_fields(
    default: Any,
    subcommand_default: Any,
    subcommand_type: Any,
) -> int:
    """Count the number of matching fields between default and subcommand_default.

    Returns 0 if subcommand has no configured default.
    For nested structs, recursively counts matching fields (not normalized).
    """
    if subcommand_default in _singleton.MISSING_AND_MISSING_NONPROP:
        return 0

    # Get field lists for both the provided default and subcommand default.
    # This uses tyro's own field extraction logic rather than raw getattr.
    # No need for check_default_instances_context here since we're just extracting
    # field values, not validating type compatibility (that's done by _recursive_struct_match).
    maybe_default_fields = _fields.field_list_from_type_or_callable(
        subcommand_type,
        default,
        support_single_arg_types=True,
        in_union_context=False,
    )
    maybe_subcommand_fields = _fields.field_list_from_type_or_callable(
        subcommand_type,
        subcommand_default,
        support_single_arg_types=True,
        in_union_context=False,
    )

    # Not a struct type: compare directly.
    if isinstance(
        maybe_default_fields,
        (UnsupportedStructTypeMessage, InvalidDefaultInstanceError),
    ) or isinstance(
        maybe_subcommand_fields,
        (UnsupportedStructTypeMessage, InvalidDefaultInstanceError),
    ):
        try:
            return 1 if default == subcommand_default else 0
        except Exception:
            return 0

    _, default_fields = maybe_default_fields
    _, subcommand_fields = maybe_subcommand_fields

    if len(default_fields) == 0:
        # Empty struct: check direct equality.
        try:
            return 1 if default == subcommand_default else 0
        except Exception:
            return 0

    # Build a map from field name to default value for the subcommand.
    subcommand_defaults_from_name = {
        f.intern_name: f.default for f in subcommand_fields
    }
    count = 0
    for field in default_fields:
        default_val = field.default
        subcommand_val = subcommand_defaults_from_name.get(field.intern_name, None)
        if subcommand_val is None:
            continue

        # For nested structs, recursively count matching fields.
        if _fields.is_struct_type(
            field.type_stripped, default_val, in_union_context=False
        ):
            count += _count_matching_fields(
                default_val, subcommand_val, field.type_stripped
            )
        else:
            try:
                if default_val == subcommand_val:
                    count += 1
            except Exception:
                pass

    return count


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

    # Find all type-compatible subcommands.
    compatible_matches: list[str] = []
    errors: list[InvalidDefaultInstanceError] = []
    for subcommand_name, subcommand_type in subcommand_type_from_name.items():
        maybe_error = _recursive_struct_match(subcommand_type, default, root=True)
        if not isinstance(maybe_error, InvalidDefaultInstanceError):
            compatible_matches.append(subcommand_name)
        else:
            errors.append(maybe_error)

    # Fast path: if only one match, return it immediately.
    # For argparse backend, always compute similarity to catch errors early.
    use_argparse_backend = _settings._experimental_options["backend"] == "argparse"
    if len(compatible_matches) == 1 and not use_argparse_backend:
        return compatible_matches[0]

    # Multiple matches (or argparse backend): use field counting to pick the best.
    if len(compatible_matches) > 0:
        best_match: str | None = None
        best_count: int = -1
        for subcommand_name in compatible_matches:
            subcommand_type = subcommand_type_from_name[subcommand_name]
            conf = subcommand_config_from_name.get(subcommand_name)
            conf_default = (
                conf.default if conf is not None else _singleton.MISSING_NONPROP
            )
            count = _count_matching_fields(default, conf_default, subcommand_type)
            if count > best_count:
                best_count = count
                best_match = subcommand_name

        if best_match is not None:
            return best_match

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
            subcommand_type,
            default,
            support_single_arg_types=root,
            in_union_context=False,
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
