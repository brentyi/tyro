"""Core public API."""
import argparse
import dataclasses
import pathlib
import sys
import warnings
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)

import shtab
from typing_extensions import Literal

from . import (
    _argparse_formatter,
    _arguments,
    _calling,
    _fields,
    _parsers,
    _strings,
    _unsafe_cache,
    conf,
)
from ._typing import TypeForm

OutT = TypeVar("OutT")


# Note that the overload here is necessary for pyright and pylance due to special-casing
# related to using typing.Type[] as a temporary replacement for typing.TypeForm[].
#
# https://github.com/microsoft/pyright/issues/4298


@overload
def cli(
    f: TypeForm[OutT],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    default: Optional[OutT] = None,
    return_unknown_args: Literal[False] = False,
) -> OutT:
    ...


@overload
def cli(
    f: TypeForm[OutT],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    default: Optional[OutT] = None,
    return_unknown_args: Literal[True],
) -> Tuple[OutT, List[str]]:
    ...


@overload
def cli(
    f: Callable[..., OutT],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    # Note that passing a default makes sense for things like dataclasses, but are not
    # supported for general callables. These can, however, be specified in the signature
    # of the callable itself.
    default: None = None,
    return_unknown_args: Literal[False] = False,
) -> OutT:
    ...


@overload
def cli(
    f: Callable[..., OutT],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    # Note that passing a default makes sense for things like dataclasses, but are not
    # supported for general callables. These can, however, be specified in the signature
    # of the callable itself.
    default: None = None,
    return_unknown_args: Literal[True],
) -> Tuple[OutT, List[str]]:
    ...


def cli(
    f: Union[TypeForm[OutT], Callable[..., OutT]],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    args: Optional[Sequence[str]] = None,
    default: Optional[OutT] = None,
    return_unknown_args: bool = False,
    **deprecated_kwargs,
) -> Union[OutT, Tuple[OutT, List[str]]]:
    """Call or instantiate `f`, with inputs populated from an automatically generated
    CLI interface.

    `f` should have type-annotated inputs, and can be a function or type. Note that if
    `f` is a type, `tyro.cli()` returns an instance.

    The parser is generated by populating helptext from docstrings and types from
    annotations; a broad range of core type annotations are supported.
    - Types natively accepted by `argparse`: str, int, float, pathlib.Path, etc.
    - Default values for optional parameters.
    - Booleans, which are automatically converted to flags when provided a default
      value.
    - Enums (via `enum.Enum`).
    - Various annotations from the standard typing library. Some examples:
      - `typing.ClassVar[T]`.
      - `typing.Optional[T]`.
      - `typing.Literal[T]`.
      - `typing.Sequence[T]`.
      - `typing.List[T]`.
      - `typing.Dict[K, V]`.
      - `typing.Tuple`, such as `typing.Tuple[T1, T2, T3]` or
        `typing.Tuple[T, ...]`.
      - `typing.Set[T]`.
      - `typing.Final[T]` and `typing.Annotated[T]`.
      - `typing.Union[T1, T2]`.
      - Various nested combinations of the above: `Optional[Literal[T]]`,
        `Final[Optional[Sequence[T]]]`, etc.
    - Hierarchical structures via nested dataclasses, TypedDict, NamedTuple,
      classes.
      - Simple nesting.
      - Unions over nested structures (subparsers).
      - Optional unions over nested structures (optional subparsers).
    - Generics (including nested generics).

    Completion script generation for interactive shells is also provided. To write a
    script that can be used for tab completion, pass in:
        `--tyro-write-completion {bash/zsh/tcsh} {path to script to write}`.

    Args:
        f: Function or type.
        prog: The name of the program printed in helptext. Mirrors argument from
            `argparse.ArgumentParser()`.
        description: Description text for the parser, displayed when the --help flag is
            passed in. If not specified, `f`'s docstring is used. Mirrors argument from
            `argparse.ArgumentParser()`.
        args: If set, parse arguments from a sequence of strings instead of the
            commandline. Mirrors argument from `argparse.ArgumentParser.parse_args()`.
        default: An instance of `OutT` to use for default values; supported if `f` is a
            type like a dataclass or dictionary, but not if `f` is a general callable like
            a function or standard class. Helpful for merging CLI arguments with values
            loaded from elsewhere. (for example, a config object loaded from a yaml file)
        return_unknown_args: If True, return a tuple of the output of `f` and a list of
            unknown arguments. Mirrors the unknown arguments returned from
            `argparse.ArgumentParser.parse_known_args()`.

    Returns:
        The output of `f(...)` or an instance `f`. If `f` is a class, the two are
        equivalent. If `return_unknown_args` is True, returns a tuple of the output of
        `f(...)` and a list of unknown arguments.
    """

    # Make sure we start on a clean slate. Some tests may fail without this due to
    # memory address conflicts.
    _unsafe_cache.clear_cache()

    output = _cli_impl(
        f,
        prog=prog,
        description=description,
        args=args,
        default=default,
        return_parser=False,
        return_unknown_args=return_unknown_args,
        **deprecated_kwargs,
    )

    # Prevent unnecessary memory usage.
    _unsafe_cache.clear_cache()

    if return_unknown_args:
        return cast(Tuple[OutT, List[str]], output)
    else:
        return cast(OutT, output)


@overload
def get_parser(
    f: TypeForm[OutT],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    default: Optional[OutT] = None,
) -> argparse.ArgumentParser:
    ...


@overload
def get_parser(
    f: Callable[..., OutT],
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
    default: Optional[OutT] = None,
) -> argparse.ArgumentParser:
    ...


def get_parser(
    f: Union[TypeForm[OutT], Callable[..., OutT]],
    *,
    # Note that we have no `args` argument, since this is only used when
    # parser.parse_args() is called.
    prog: Optional[str] = None,
    description: Optional[str] = None,
    default: Optional[OutT] = None,
) -> argparse.ArgumentParser:
    """Get the `argparse.ArgumentParser` object generated under-the-hood by
    `tyro.cli()`. Useful for tools like `sphinx-argparse`, `argcomplete`, etc.

    For tab completion, we recommend using `tyro.cli()`'s built-in `--tyro-write-completion`
    flag."""
    return cast(
        argparse.ArgumentParser,
        _cli_impl(
            f,
            prog=prog,
            description=description,
            args=None,
            default=default,
            return_parser=True,
            return_unknown_args=False,
        ),
    )


def _cli_impl(
    f: Union[TypeForm[OutT], Callable[..., OutT]],
    *,
    prog: Optional[str] = None,
    description: Optional[str],
    args: Optional[Sequence[str]],
    default: Optional[OutT],
    return_parser: bool,
    return_unknown_args: bool,
    **deprecated_kwargs,
) -> Union[OutT, argparse.ArgumentParser, Tuple[OutT, List[str]],]:
    """Helper for stitching the `tyro` pipeline together."""
    if "default_instance" in deprecated_kwargs:
        warnings.warn(
            "`default_instance=` is deprecated! use `default=` instead.", stacklevel=2
        )
        default = deprecated_kwargs["default_instance"]
    if deprecated_kwargs.get("avoid_subparsers", False):
        f = conf.AvoidSubcommands[f]  # type: ignore
        warnings.warn(
            "`avoid_subparsers=` is deprecated! use `tyro.conf.AvoidSubparsers[]`"
            " instead.",
            stacklevel=2,
        )

    # Internally, we distinguish between two concepts:
    # - "default", which is used for individual arguments.
    # - "default_instance", which is used for _fields_ (which may be broken down into
    #   one or many arguments, depending on various factors).
    #
    # This could be revisited.
    default_instance_internal: Union[_fields.NonpropagatingMissingType, OutT] = (
        _fields.MISSING_NONPROP if default is None else default
    )

    # We wrap our type with a dummy dataclass if it can't be treated as a nested type.
    # For example: passing in f=int will result in a dataclass with a single field
    # typed as int.
    if not _fields.is_nested_type(cast(type, f), default_instance_internal):
        dummy_field = cast(
            dataclasses.Field,
            dataclasses.field(),
        )
        f = dataclasses.make_dataclass(
            cls_name="",
            fields=[(_strings.dummy_field_name, cast(type, f), dummy_field)],
            frozen=True,
        )
        default_instance_internal = f(default_instance_internal)  # type: ignore
        dummy_wrapped = True
    else:
        dummy_wrapped = False

    # Read and fix arguments. If the user passes in --field_name instead of
    # --field-name, correct for them.
    args = list(sys.argv[1:]) if args is None else list(args)

    # Fix arguments. This will modify all option-style arguments replacing
    # underscores with dashes. This is to support the common convention of using
    # underscores in variable names, but dashes in command line arguments.
    # If two options are ambiguous, e.g., --a_b and --a-b, raise a runtime error.
    modified_args: Dict[str, str] = {}
    for index, arg in enumerate(args):
        if not arg.startswith("--"):
            continue

        if "=" in arg:
            arg, _, val = arg.partition("=")
            fixed = arg.replace("_", "-") + "=" + val
        else:
            fixed = arg.replace("_", "-")
        if (
            return_unknown_args
            and fixed in modified_args
            and modified_args[fixed] != arg
        ):
            raise RuntimeError(
                "Ambiguous arguments: " + modified_args[fixed] + " and " + arg
            )
        modified_args[fixed] = arg
        args[index] = fixed

    # If we pass in the --tyro-print-completion or --tyro-write-completion flags: turn
    # formatting tags, and get the shell we want to generate a completion script for
    # (bash/zsh/tcsh).
    #
    # shtab also offers an add_argument_to() functions that fulfills a similar goal, but
    # manual parsing of argv is convenient for turning off formatting.
    #
    # Note: --tyro-print-completion is deprecated! --tyro-write-completion is less prone
    # to errors from accidental logging, print statements, etc.
    print_completion = len(args) >= 2 and args[0] == "--tyro-print-completion"
    write_completion = len(args) >= 3 and args[0] == "--tyro-write-completion"

    # Note: setting USE_RICH must happen before the parser specification is generated.
    # TODO: revisit this. Ideally we should be able to eliminate the global state
    # changes.
    completion_shell = None
    completion_target_path = None
    if print_completion or write_completion:
        completion_shell = args[1]
    if write_completion:
        completion_target_path = pathlib.Path(args[2])
    if print_completion or write_completion or return_parser:
        _arguments.USE_RICH = False
    else:
        _arguments.USE_RICH = True

    # Map a callable to the relevant CLI arguments + subparsers.
    parser_spec = _parsers.ParserSpecification.from_callable_or_type(
        f,
        description=description,
        parent_classes=set(),  # Used for recursive calls.
        default_instance=default_instance_internal,  # Overrides for default values.
        prefix="",  # Used for recursive calls.
        subcommand_prefix="",  # Used for recursive calls.
    )

    # Generate parser!
    with _argparse_formatter.ansi_context():
        parser = _argparse_formatter.TyroArgumentParser(
            prog=prog,
            formatter_class=_argparse_formatter.TyroArgparseHelpFormatter,
            allow_abbrev=False,
        )
        parser._parser_specification = parser_spec
        parser._parsing_known_args = return_unknown_args
        parser._args = args
        parser_spec.apply(parser)

        # Print help message when no arguments are passed in. (but arguments are
        # expected)
        if len(args) == 0 and parser_spec.has_required_args:
            args = ["--help"]

        if return_parser:
            _arguments.USE_RICH = True
            return parser

        if print_completion or write_completion:
            _arguments.USE_RICH = True
            assert completion_shell in (
                "bash",
                "zsh",
                "tcsh",
            ), (
                "Shell should be one `bash`, `zsh`, or `tcsh`, but got"
                f" {completion_shell}"
            )

            if write_completion:
                assert completion_target_path is not None
                completion_target_path.write_text(
                    shtab.complete(
                        parser=parser,
                        shell=completion_shell,
                        root_prefix=f"tyro_{parser.prog}",
                    )
                )
            else:
                print(
                    shtab.complete(
                        parser=parser,
                        shell=completion_shell,
                        root_prefix=f"tyro_{parser.prog}",
                    )
                )
            sys.exit()

        if return_unknown_args:
            namespace, unknown_args = parser.parse_known_args(args=args)
        else:
            unknown_args = None
            namespace = parser.parse_args(args=args)
        value_from_prefixed_field_name = vars(namespace)

    if dummy_wrapped:
        value_from_prefixed_field_name = {
            k.replace(_strings.dummy_field_name, ""): v
            for k, v in value_from_prefixed_field_name.items()
        }

    try:
        # Attempt to call `f` using whatever was passed in.
        out, consumed_keywords = _calling.call_from_args(
            f,
            parser_spec,
            default_instance_internal,
            value_from_prefixed_field_name,
            field_name_prefix="",
        )
    except _calling.InstantiationError as e:
        assert isinstance(e, _calling.InstantiationError)

        # Emulate argparse's error behavior when invalid arguments are passed in.
        from rich.console import Console, Group, RenderableType
        from rich.padding import Padding
        from rich.panel import Panel
        from rich.rule import Rule
        from rich.style import Style

        from ._argparse_formatter import THEME

        console = Console(theme=THEME.as_rich_theme())
        parser._print_usage_succinct(console)
        console.print(
            Panel(
                Group(
                    "[bright_red][bold]Error parsing"
                    f" {e.arg.lowered.name_or_flag}[/bold]:[/bright_red] {e.message}",
                    *cast(  # Cast to appease mypy...
                        List[RenderableType],
                        (
                            []
                            if e.arg.lowered.help is None
                            else [
                                Rule(style=Style(color="red")),
                                "Argument helptext:",
                                Padding(
                                    Group(
                                        f"{e.arg.lowered.name_or_flag} [bold]{e.arg.lowered.metavar}[/bold]",
                                        e.arg.lowered.help,
                                    ),
                                    pad=(0, 0, 0, 4),
                                ),
                            ]
                        ),
                    ),
                ),
                title="[bold]Value error[/bold]",
                title_align="left",
                border_style=Style(color="red"),
            )
        )
        sys.exit(2)

    assert len(value_from_prefixed_field_name.keys() - consumed_keywords) == 0, (
        f"Parsed {value_from_prefixed_field_name.keys()}, but only consumed"
        f" {consumed_keywords}"
    )

    if dummy_wrapped:
        out = getattr(out, _strings.dummy_field_name)

    if return_unknown_args:
        assert unknown_args is not None, "Should have parsed with `parse_known_args()`"
        # If we're parsed unknown args, we should return the original args, not
        # the fixed ones.
        unknown_args = [modified_args.get(arg, arg) for arg in unknown_args]
        return out, unknown_args
    else:
        assert unknown_args is None, "Should have parsed with `parse_args()`"
        return out
