"""Core public API."""

from __future__ import annotations

import dataclasses
import pathlib
import sys
import warnings
from typing import Callable, Literal, Sequence, TypeVar, cast, overload

import shtab
from typing_extensions import Annotated

from . import _argparse as argparse
from . import (
    _argparse_formatter,
    _arguments,
    _calling,
    _fields,
    _parsers,
    _resolver,
    _singleton,
    _strings,
    _unsafe_cache,
    conf,
)
from ._typing import TypeForm
from .constructors import ConstructorRegistry

OutT = TypeVar("OutT")


# The overload here is necessary for pyright and pylance due to special-casing
# related to using typing.Type[] as a temporary replacement for
# typing.TypeForm[].
#
# https://github.com/microsoft/pyright/issues/4298


@overload
def cli(
    f: TypeForm[OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    args: None | Sequence[str] = None,
    default: None | OutT = None,
    return_unknown_args: Literal[False] = False,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> OutT: ...


@overload
def cli(
    f: TypeForm[OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    args: None | Sequence[str] = None,
    default: None | OutT = None,
    return_unknown_args: Literal[True],
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> tuple[OutT, list[str]]: ...


@overload
def cli(
    f: Callable[..., OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    args: None | Sequence[str] = None,
    # Passing a default makes sense for things like dataclasses, but are not
    # supported for general callables. These can, however, be specified in the
    # signature of the callable itself.
    default: None = None,
    return_unknown_args: Literal[False] = False,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> OutT: ...


@overload
def cli(
    f: Callable[..., OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    args: None | Sequence[str] = None,
    # Passing a default makes sense for things like dataclasses, but are not
    # supported for general callables. These can, however, be specified in the
    # signature of the callable itself.
    default: None = None,
    return_unknown_args: Literal[True],
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> tuple[OutT, list[str]]: ...


def cli(
    f: TypeForm[OutT] | Callable[..., OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    args: None | Sequence[str] = None,
    default: None | OutT = None,
    return_unknown_args: bool = False,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
    **deprecated_kwargs,
) -> OutT | tuple[OutT, list[str]]:
    """Generate a command-line interface from type annotations and populate the target with arguments.

    :func:`cli()` is the core function of tyro. It takes a type-annotated function or class
    and automatically generates a command-line interface to populate it from user arguments.

    Two main usage patterns are supported:

    1. With a function (CLI arguments become function parameters):

       .. code-block:: python

          import tyro

          def main(a: str, b: str) -> None:
              print(a, b)

          if __name__ == "__main__":
              tyro.cli(main)  # Parses CLI args, calls main() with them

    2. With a class (CLI arguments become object attributes):

       .. code-block:: python

          from dataclasses import dataclass
          from pathlib import Path

          import tyro

          @dataclass
          class Config:
              a: str
              b: str

          if __name__ == "__main__":
              config = tyro.cli(Config)  # Parses CLI args, returns populated AppConfig
              print(f"Config: {config}")

    Args:
        f: The function or type to populate from command-line arguments. This must have
            type-annotated inputs for tyro to work correctly.
        prog: The name of the program to display in the help text. If not specified, the
            script filename is used. This mirrors the argument from
            :py:class:`argparse.ArgumentParser()`.
        description: The description text shown at the top of the help output. If not
            specified, the docstring of `f` is used. This mirrors the argument from
            :py:class:`argparse.ArgumentParser()`.
        args: If provided, parse arguments from this sequence of strings instead of
            the command line. This is useful for testing or programmatic usage. This mirrors
            the argument from :py:meth:`argparse.ArgumentParser.parse_args()`.
        default: An instance to use for default values. This is only supported if ``f`` is a
            type like a dataclass or dictionary, not if ``f`` is a general callable like a
            function. This is useful for merging CLI arguments with values loaded from
            elsewhere, such as a config file.
        return_unknown_args: If True, returns a tuple of the output and a list of unknown
            arguments that weren't consumed by the parser. This mirrors the behavior of
            :py:meth:`argparse.ArgumentParser.parse_known_args()`.
        use_underscores: If True, uses underscores as word delimiters in the help text
            instead of hyphens. This only affects the displayed help; both underscores and
            hyphens are treated equivalently during parsing. The default (False) follows the
            GNU style guide for command-line options.
            https://www.gnu.org/software/libc/manual/html_node/Argument-Syntax.html
        console_outputs: If set to False, suppresses parsing errors and help messages.
            This is useful in distributed settings where tyro.cli() is called from multiple
            workers but console output is only desired from the main process.
        config: A sequence of configuration marker objects from :mod:`tyro.conf`. This
            allows applying markers globally instead of annotating individual fields.
            For example: ``tyro.cli(Config, config=(tyro.conf.PositionalRequiredArgs,))``
        registry: A :class:`tyro.constructors.ConstructorRegistry` instance containing custom
            constructor rules.

    Returns:
        If ``f`` is a type (like a dataclass), returns an instance of that type populated
        with values from the command line. If ``f`` is a function, calls the function with
        arguments from the command line and returns its result. If ``return_unknown_args``
        is True, returns a tuple of the result and a list of unused command-line arguments.
    """

    # Make sure we start on a clean slate. Some tests may fail without this due to
    # memory address conflicts.
    _unsafe_cache.clear_cache()

    with _strings.delimeter_context("_" if use_underscores else "-"):
        output = _cli_impl(
            f,
            prog=prog,
            description=description,
            args=args,
            default=default,
            return_parser=False,
            return_unknown_args=return_unknown_args,
            use_underscores=use_underscores,
            console_outputs=console_outputs,
            config=config,
            registry=registry,
            **deprecated_kwargs,
        )

    # Prevent unnecessary memory usage.
    _unsafe_cache.clear_cache()

    if return_unknown_args:
        assert isinstance(output, tuple)
        run_with_args_from_cli = output[0]
        return run_with_args_from_cli(), output[1]
    else:
        run_with_args_from_cli = cast(Callable[[], OutT], output)
        return run_with_args_from_cli()


@overload
def get_parser(
    f: TypeForm[OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    default: None | OutT = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> argparse.ArgumentParser: ...


@overload
def get_parser(
    f: Callable[..., OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    default: None | OutT = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> argparse.ArgumentParser: ...


def get_parser(
    f: TypeForm[OutT] | Callable[..., OutT],
    *,
    # We have no `args` argument, since this is only used when
    # parser.parse_args() is called.
    prog: None | str = None,
    description: None | str = None,
    default: None | OutT = None,
    use_underscores: bool = False,
    console_outputs: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> argparse.ArgumentParser:
    """Get the :py:class:`argparse.ArgumentParser` object generated under-the-hood by
    :func:`tyro.cli`. Useful for tools like ``sphinx-argparse``, ``argcomplete``, etc.

    For tab completion, we recommend using :func:`tyro.cli`'s built-in
    ``--tyro-write-completion`` flag.

    Args:
        f: The function or type to populate from command-line arguments.
        prog: The name of the program to display in the help text.
        description: The description text shown at the top of the help output.
        default: An instance to use for default values.
        use_underscores: If True, uses underscores as word delimiters in the help text.
        console_outputs: If set to False, suppresses parsing errors and help messages.
        config: A sequence of configuration marker objects from :mod:`tyro.conf`.
        registry: A :class:`tyro.constructors.ConstructorRegistry` instance containing custom
            constructor rules.
    """
    with _strings.delimeter_context("_" if use_underscores else "-"):
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
                use_underscores=use_underscores,
                console_outputs=console_outputs,
                config=config,
                registry=registry,
            ),
        )


def _cli_impl(
    f: TypeForm[OutT] | Callable[..., OutT],
    *,
    prog: None | str = None,
    description: None | str,
    args: None | Sequence[str],
    default: None | OutT,
    return_parser: bool,
    return_unknown_args: bool,
    console_outputs: bool,
    config: None | Sequence[conf._markers.Marker],
    registry: None | ConstructorRegistry = None,
    **deprecated_kwargs,
) -> (
    OutT
    | argparse.ArgumentParser
    | tuple[
        Callable[[], OutT],
        list[str],
    ]
):
    """Helper for stitching the `tyro` pipeline together."""

    if config is not None and len(config) > 0:
        f = Annotated[(f, *config)]  # type: ignore

    if "default_instance" in deprecated_kwargs:
        warnings.warn(
            "`default_instance=` is deprecated! use `default=` instead.", stacklevel=2
        )
        default = deprecated_kwargs["default_instance"]
    if deprecated_kwargs.get("avoid_subparsers", False):
        f = conf.AvoidSubcommands[f]  # type: ignore
        warnings.warn(
            "`avoid_subparsers=` is deprecated! use `tyro.conf.AvoidSubcommands[]`"
            " instead.",
            stacklevel=2,
        )

    # Internally, we distinguish between two concepts:
    # - "default", which is used for individual arguments.
    # - "default_instance", which is used for _fields_ (which may be broken down into
    #   one or many arguments, depending on various factors).
    #
    # This could be revisited.
    default_instance_internal: _singleton.NonpropagatingMissingType | OutT = (
        _singleton.MISSING_NONPROP if default is None else default
    )

    # We wrap our type with a dummy dataclass if it can't be treated as a nested type.
    # For example: passing in f=int will result in a dataclass with a single field
    # typed as int.
    if not _fields.is_struct_type(cast(type, f), default_instance_internal):
        dummy_field = cast(
            dataclasses.Field,
            dataclasses.field(),
        )
        f = dataclasses.make_dataclass(
            cls_name="dummy",
            fields=[(_strings.dummy_field_name, cast(type, f), dummy_field)],
            frozen=True,
        )
        default_instance_internal = f(default_instance_internal)  # type: ignore
        dummy_wrapped = True
    else:
        f = _resolver.TypeParamResolver.resolve_params_and_aliases(f)
        dummy_wrapped = False

    # Read and fix arguments. If the user passes in --field_name instead of
    # --field-name, correct for them.
    args = list(sys.argv[1:]) if args is None else list(args)

    # Fix arguments. This will modify all option-style arguments replacing
    # underscores with hyphens, or vice versa if use_underscores=True.
    # If two options are ambiguous, e.g., --a_b and --a-b, raise a runtime error.
    modified_args: dict[str, str] = {}
    for index, arg in enumerate(args):
        if not arg.startswith("--"):
            continue

        if "=" in arg:
            arg, _, val = arg.partition("=")
            fixed = "--" + _strings.swap_delimeters(arg[2:]) + "=" + val
        else:
            fixed = "--" + _strings.swap_delimeters(arg[2:])
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
    print_completion = False
    write_completion = False
    if len(args) >= 2:
        # We replace underscores with hyphens to accomodate for `use_undercores`.
        print_completion = args[0].replace("_", "-") == "--tyro-print-completion"
        write_completion = (
            len(args) >= 3 and args[0].replace("_", "-") == "--tyro-write-completion"
        )

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
    if registry is not None:
        with registry:
            parser_spec = _parsers.ParserSpecification.from_callable_or_type(
                f,
                markers=set(),
                description=description,
                parent_classes=set(),  # Used for recursive calls.
                default_instance=default_instance_internal,  # Overrides for default values.
                intern_prefix="",  # Used for recursive calls.
                extern_prefix="",  # Used for recursive calls.
            )
    else:
        parser_spec = _parsers.ParserSpecification.from_callable_or_type(
            f,
            markers=set(),
            description=description,
            parent_classes=set(),  # Used for recursive calls.
            default_instance=default_instance_internal,  # Overrides for default values.
            intern_prefix="",  # Used for recursive calls.
            extern_prefix="",  # Used for recursive calls.
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
        parser._console_outputs = console_outputs
        parser._args = args
        parser_spec.apply(parser, force_required_subparsers=False)

        # Print help message when no arguments are passed in. (but arguments are
        # expected)
        # if len(args) == 0 and parser_spec.has_required_args:
        #     args = ["--help"]

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

            if write_completion and completion_target_path != pathlib.Path("-"):
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
        get_out, consumed_keywords = _calling.callable_with_args(
            f,
            parser_spec,
            default_instance_internal,
            value_from_prefixed_field_name,
            field_name_prefix="",
        )
    except _calling.InstantiationError as e:
        # Print prettier errors.
        # This doesn't catch errors raised directly by get_out(), since that's
        # called later! This is intentional, because we do less error handling
        # for the root callable. Relevant: the `field_name_prefix == ""`
        # condition in `callable_with_args()`!

        # Emulate argparse's error behavior when invalid arguments are passed in.
        from rich.console import Console, Group
        from rich.padding import Padding
        from rich.panel import Panel
        from rich.rule import Rule
        from rich.style import Style

        from ._argparse_formatter import THEME

        if console_outputs:
            console = Console(theme=THEME.as_rich_theme(), stderr=True)
            console.print(
                Panel(
                    Group(
                        "[bright_red][bold]Error parsing"
                        f" {'/'.join(e.arg.lowered.name_or_flags) if isinstance(e.arg, _arguments.ArgumentDefinition) else e.arg}[/bold]:[/bright_red] {e.message}",
                        *cast(  # Cast to appease mypy...
                            list,
                            (
                                []
                                if not isinstance(e.arg, _arguments.ArgumentDefinition)
                                or e.arg.lowered.help is None
                                else [
                                    Rule(style=Style(color="red")),
                                    "Argument helptext:",
                                    Padding(
                                        Group(
                                            f"{'/'.join(e.arg.lowered.name_or_flags)} [bold]{e.arg.lowered.metavar}[/bold]",
                                            e.arg.lowered.help,
                                        ),
                                        pad=(0, 0, 0, 4),
                                    ),
                                    Rule(style=Style(color="red")),
                                    f"For full helptext, see [bold]{parser.prog} --help[/bold]",
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
        get_wrapped_out = get_out
        get_out = lambda: getattr(get_wrapped_out(), _strings.dummy_field_name)  # noqa

    if return_unknown_args:
        assert unknown_args is not None, "Should have parsed with `parse_known_args()`"
        # If we're parsed unknown args, we should return the original args, not
        # the fixed ones.
        unknown_args = [modified_args.get(arg, arg) for arg in unknown_args]
        return get_out, unknown_args  # type: ignore
    else:
        assert unknown_args is None, "Should have parsed with `parse_args()`"
        return get_out  # type: ignore
