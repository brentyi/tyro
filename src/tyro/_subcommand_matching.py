from __future__ import annotations

import sys
from typing import Any, Dict, Literal, Tuple

from tyro.constructors._registry import (
    ConstructorRegistry,
    check_default_instances_context,
)
from tyro.constructors._struct_spec import (
    InvalidDefaultInstanceError,
    UnsupportedStructTypeMessage,
)

from . import _fields, _resolver, _settings, _singleton, _unsafe_cache
from . import _fmtlib as fmt
from .conf import _confstruct, _markers


def _strip_subcommand_configs(typ: Any) -> Any:
    """Strip configuration objects that aren't relevant when a default is provided. This
    only does anything if it will result in a plain type."""
    unwrapped, annotations = _resolver.unwrap_annotated(typ, "all")
    if (
        type(typ) is not type
        and type(unwrapped) is type
        and all(isinstance(x, _confstruct._SubcommandConfig) for x in annotations)
    ):
        return unwrapped
    return typ


def _is_definitely_incompatible(typ: Any, default: Any) -> bool:
    """Returns True if we're certain that `_recursive_struct_match()` will return an
    error. This is much cheaper to check."""
    typ = _strip_subcommand_configs(typ)
    if ConstructorRegistry._has_custom_rules() or type(typ) is not type:
        return False
    if typ is type(None):
        return default is not None
    return (
        hasattr(typ, "__dataclass_fields__")
        and not hasattr(typ, "__parameters__")
        and not hasattr(typ, "__tyro_markers__")
        and not isinstance(default, typ)
    )


def _count_matching_fields(
    default: Any,
    subcommand_default: Any,
    subcommand_type: Any,
    default_args_cache: Dict[Any, Dict[str, Any]],
) -> Tuple[int, int]:
    """Count matching fields between default and subcommand_default.

    Returns (name_matches, value_matches) for lexicographic comparison:
    - name_matches: number of argument names that appear in both
    - value_matches: number of arguments with matching default values

    Note: Type compatibility is already confirmed by _recursive_struct_match.
    This comparison handles edge cases like dictionaries where structural
    comparison via ParserSpecification is more robust than field-level checks.
    """
    if _singleton.is_missing(subcommand_default):
        return (0, 0)

    # Import here to avoid circular dependency.
    from . import _parsers

    def get_arg_defaults(instance: Any, typ: Any) -> Dict[str, Any]:
        """Generate a ParserSpecification and extract {name: default} dict."""
        spec = _parsers.ParserSpecification.from_callable_or_type(
            f=typ,
            markers={_markers.AvoidSubcommands},
            description=None,
            parent_classes=set(),
            default_instance=instance,
            intern_prefix="",
            extern_prefix="",
            subcommand_prefix="",
            support_single_arg_types=True,
            prog_suffix="",
        )
        result: Dict[str, Any] = {}
        for arg_ctx in spec.get_args_including_children():
            arg = arg_ctx.arg
            key = arg.get_output_key()
            result[key] = arg.field.default
        return result

    # The default is often compared to many subcommands that share a type.
    subcommand_type = _strip_subcommand_configs(subcommand_type)
    key = _unsafe_cache.type_key(subcommand_type)
    if key not in default_args_cache:
        default_args_cache[key] = get_arg_defaults(default, subcommand_type)
    default_args = default_args_cache[key]
    subcommand_args = get_arg_defaults(subcommand_default, subcommand_type)

    # Count matching names (structural similarity).
    common_names = set(default_args.keys()) & set(subcommand_args.keys())
    name_matches = len(common_names)

    # Count matching values among common names.
    value_matches = 0
    for name in common_names:
        default_val = default_args[name]
        subcommand_val = subcommand_args[name]
        # Ignore any equality check that raises an exception, like numpy arrays.
        try:
            if default_val == subcommand_val:
                value_matches += 1
        except Exception:
            pass

    return (name_matches, value_matches)


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
        if _singleton.is_missing(conf.default):
            continue
        if default is conf.default:
            return subcommand_name

    # Get default subcommand name: by default value.
    for subcommand_name, conf in subcommand_config_from_name.items():
        if _singleton.is_missing(conf.default):
            continue
        # Ignore any equality check that raises an exception, like numpy arrays.
        try:
            if default == conf.default:
                return subcommand_name
        except Exception:
            continue

    # Find all type-compatible subcommands.
    compatible_matches: list[str] = []
    is_match_cache: Dict[Any, bool] = {}
    for subcommand_name, subcommand_type in subcommand_type_from_name.items():
        key = _unsafe_cache.type_key(_strip_subcommand_configs(subcommand_type))
        is_match = is_match_cache.get(key)
        if is_match is None:
            is_match = not _is_definitely_incompatible(
                subcommand_type, default
            ) and not isinstance(
                _recursive_struct_match(subcommand_type, default, root=True),
                InvalidDefaultInstanceError,
            )
            is_match_cache[key] = is_match
        if is_match:
            compatible_matches.append(subcommand_name)

    # Fast path: if only one match, return it immediately.
    # For argparse backend, always compute similarity to catch errors early.
    use_argparse_backend = _settings._experimental_options["backend"] == "argparse"
    if len(compatible_matches) == 1 and not use_argparse_backend:
        return compatible_matches[0]

    # Multiple matches (or argparse backend): use field counting to pick the best.
    if len(compatible_matches) > 0:
        best_match: str | None = None
        best_count: Tuple[int, int] = (-1, -1)
        default_args_cache: Dict[Any, Dict[str, Any]] = {}
        for subcommand_name in compatible_matches:
            subcommand_type = subcommand_type_from_name[subcommand_name]
            conf = subcommand_config_from_name.get(subcommand_name)
            conf_default = (
                conf.default if conf is not None else _singleton.MISSING_NONPROP
            )
            count = _count_matching_fields(
                default, conf_default, subcommand_type, default_args_cache
            )
            if count > best_count:
                best_count = count
                best_match = subcommand_name

        assert best_match is not None
        return best_match

    # No compatible matches found. Print a detailed error message showing why each
    # subcommand was rejected.
    details = []
    for subcommand_name, subcommand_type in subcommand_type_from_name.items():
        error = _recursive_struct_match(subcommand_type, default, root=True)
        assert isinstance(error, InvalidDefaultInstanceError)
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
        "\n".join(error_message.render(width=min(fmt.get_terminal_columns(), 80))),
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
