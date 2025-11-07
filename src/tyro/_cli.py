"""Core public API."""

from __future__ import annotations

import pathlib
import sys
import warnings
from typing import Callable, Literal, Sequence, TypeVar, cast, overload

from typing_extensions import Annotated, assert_never

from . import (
    _arguments,
    _calling,
    _parsers,
    _resolver,
    _settings,
    _strings,
    _unsafe_cache,
    conf,
)
from . import _fmtlib as fmt
from ._backends import _argparse as argparse
from ._singleton import (
    MISSING_NONPROP,
    NonpropagatingMissingType,
    PropagatingMissingType,
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
    default: OutT
    | NonpropagatingMissingType
    | PropagatingMissingType = MISSING_NONPROP,
    return_unknown_args: Literal[False] = False,
    use_underscores: bool = False,
    console_outputs: bool = True,
    add_help: bool = True,
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
    default: OutT
    | NonpropagatingMissingType
    | PropagatingMissingType = MISSING_NONPROP,
    return_unknown_args: Literal[True],
    use_underscores: bool = False,
    console_outputs: bool = True,
    add_help: bool = True,
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
    default: NonpropagatingMissingType | PropagatingMissingType = MISSING_NONPROP,
    return_unknown_args: Literal[False] = False,
    use_underscores: bool = False,
    console_outputs: bool = True,
    add_help: bool = True,
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
    default: NonpropagatingMissingType | PropagatingMissingType = MISSING_NONPROP,
    return_unknown_args: Literal[True],
    use_underscores: bool = False,
    console_outputs: bool = True,
    add_help: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> tuple[OutT, list[str]]: ...


def cli(
    f: TypeForm[OutT] | Callable[..., OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    args: None | Sequence[str] = None,
    default: OutT
    | NonpropagatingMissingType
    | PropagatingMissingType = MISSING_NONPROP,
    return_unknown_args: bool = False,
    use_underscores: bool = False,
    console_outputs: bool = True,
    add_help: bool = True,
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
            type like a dataclass or dictionary, not if ``f`` is a general
            callable like a function. This is useful for merging CLI arguments
            with values loaded from elsewhere, such as a config file. The
            default value is :data:`tyro.MISSING_NONPROP`.
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
        add_help: Add a -h/--help option to the parser. This mirrors the argument from
            :py:class:`argparse.ArgumentParser()`.
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
            add_help=add_help,
            config=config,
            registry=registry,
            **deprecated_kwargs,
        )

    # Prevent unnecessary memory usage.
    _unsafe_cache.clear_cache()

    if return_unknown_args:
        assert isinstance(output, tuple)
        run_with_args_from_cli = output[0]
        out = run_with_args_from_cli()
        while isinstance(out, _calling.DummyWrapper):
            out = out.__tyro_dummy_inner__
        return out, output[1]  # type: ignore
    else:
        run_with_args_from_cli = cast(Callable[[], OutT], output)
        out = run_with_args_from_cli()
        while isinstance(out, _calling.DummyWrapper):
            out = out.__tyro_dummy_inner__
        return out


@overload
def get_parser(
    f: TypeForm[OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    default: OutT
    | NonpropagatingMissingType
    | PropagatingMissingType = MISSING_NONPROP,
    use_underscores: bool = False,
    console_outputs: bool = True,
    add_help: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> argparse.ArgumentParser: ...


@overload
def get_parser(
    f: Callable[..., OutT],
    *,
    prog: None | str = None,
    description: None | str = None,
    default: OutT
    | NonpropagatingMissingType
    | PropagatingMissingType = MISSING_NONPROP,
    use_underscores: bool = False,
    console_outputs: bool = True,
    add_help: bool = True,
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
    default: OutT
    | NonpropagatingMissingType
    | PropagatingMissingType = MISSING_NONPROP,
    use_underscores: bool = False,
    console_outputs: bool = True,
    add_help: bool = True,
    config: None | Sequence[conf._markers.Marker] = None,
    registry: None | ConstructorRegistry = None,
) -> argparse.ArgumentParser:
    """Get an :py:class:`argparse.ArgumentParser` object that approximates the CLI generated
    by :func:`tyro.cli`. Useful for tools like ``sphinx-argparse``, ``argcomplete``, etc.

    .. note::

        The returned parser uses argparse-style subparsers, which is less flexible than
        tyro's subcommand parser.

    For tab completion, we recommend using :func:`tyro.cli`'s built-in
    ``--tyro-write-completion`` flag.

    Args:
        f: The function or type to populate from command-line arguments.
        prog: The name of the program to display in the help text.
        description: The description text shown at the top of the help output.
        default: An instance to use for default values.
        use_underscores: If True, uses underscores as word delimiters in the help text.
        console_outputs: If set to False, suppresses parsing errors and help messages.
        add_help: Add a -h/--help option to the parser. This mirrors the argument from
            :py:class:`argparse.ArgumentParser()`.
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
                add_help=add_help,
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
    default: OutT | NonpropagatingMissingType | PropagatingMissingType,
    return_parser: bool,
    return_unknown_args: bool,
    console_outputs: bool,
    add_help: bool,
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

    # Resolve any aliases, apply custom constructors that are directly attached
    # to the input type, etc.
    f = _resolver.TypeParamResolver.resolve_params_and_aliases(f)

    # Internally, we distinguish between two concepts:
    # - "default", which is used for individual arguments.
    # - "default_instance", which is used for _fields_ (which may be broken down into
    #   one or many arguments, depending on various factors).
    #
    # This could be revisited.
    default_instance = default

    # Read and fix arguments. If the user passes in --field_name instead of
    # --field-name, correct for them.
    args = list(sys.argv[1:]) if args is None else list(args)

    # Fix arguments. This will modify all option-style arguments replacing
    # underscores with hyphens, or vice versa if use_underscores=True.
    # If two options are ambiguous, e.g., --a_b and --a-b, raise a runtime error.
    #
    # This is only done for the argparse backend; the tyro backend handles
    # conversion internally.
    modified_args: dict[str, str] | None = None
    backend_name = _settings._experimental_options["backend"]
    if backend_name == "argparse":
        modified_args = {}
        for index, arg in enumerate(args):
            if not arg.startswith("--"):
                continue

            if "=" in arg:
                argname, _, val = arg.partition("=")
                fixed = "--" + _strings.swap_delimeters(argname[2:]) + "=" + val
                del argname, val
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

    # Map a callable to the relevant CLI arguments + subparsers.
    with _settings.timing_context("Generate parser specification"):
        if registry is not None:
            with registry:
                parser_spec = _parsers.ParserSpecification.from_callable_or_type(
                    f,
                    markers=set(),
                    description=description,
                    parent_classes=set(),  # Used for recursive calls.
                    default_instance=default_instance,  # Overrides for default values.
                    intern_prefix="",  # Used for recursive calls.
                    extern_prefix="",  # Used for recursive calls.
                    subcommand_prefix="",
                    support_single_arg_types=False,
                    prog_suffix="",
                )
        else:
            parser_spec = _parsers.ParserSpecification.from_callable_or_type(
                f,
                markers=set(),
                description=description,
                parent_classes=set(),  # Used for recursive calls.
                default_instance=default_instance,  # Overrides for default values.
                intern_prefix="",  # Used for recursive calls.
                extern_prefix="",  # Used for recursive calls.
                subcommand_prefix="",
                support_single_arg_types=False,
                prog_suffix="",
            )

    # Initialize backend.
    if backend_name == "argparse":
        from ._backends._argparse_backend import ArgparseBackend

        backend = ArgparseBackend()
    elif backend_name == "tyro":
        from ._backends._tyro_backend import TyroBackend

        backend = TyroBackend()
    else:
        assert_never(backend_name)

    # Handle shell completion.
    if print_completion or write_completion:
        assert completion_shell in (
            "bash",
            "zsh",
            "tcsh",
        ), f"Shell should be one `bash`, `zsh`, or `tcsh`, but got {completion_shell}"

        # Determine program name for completion script.
        if prog is None:
            prog = sys.argv[0]

        # Sanitize prog for use in function/variable names by replacing
        # non-alphanumeric characters with underscores.
        safe_prog = "".join(c if c.isalnum() or c == "_" else "_" for c in prog)

        # Generate completion script using the backend's method.
        completion_script = backend.generate_completion(
            parser_spec,
            prog=prog,
            shell=completion_shell,  # type: ignore
            root_prefix=f"tyro_{safe_prog}",
        )

        if write_completion and completion_target_path != pathlib.Path("-"):
            assert completion_target_path is not None
            completion_target_path.write_text(completion_script)
        else:
            print(completion_script)
        sys.exit()

    # For backwards compatibility with get_parser().
    if return_parser:
        return backend.get_parser_for_completion(
            parser_spec, prog=prog, add_help=add_help
        )

    # Parse arguments using the backend.
    if prog is None:
        prog = sys.argv[0]

    with _settings.timing_context("Parsing arguments"):
        value_from_prefixed_field_name, unknown_args = backend.parse_args(
            parser_spec=parser_spec,
            args=args,
            prog=prog,
            return_unknown_args=return_unknown_args,
            console_outputs=console_outputs,
            add_help=add_help,
        )

    try:
        # Attempt to call `f` using whatever was passed in.
        get_out, consumed_keywords = _calling.callable_with_args(
            f,
            parser_spec,
            default_instance,
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
        error_box_rows: list[str | fmt.Element] = []
        if isinstance(e.arg, _arguments.ArgumentDefinition):
            display_name = (
                str(e.arg.lowered.metavar)
                if e.arg.is_positional()
                else "/".join(e.arg.lowered.name_or_flags)
            )
            error_box_rows.extend(
                [
                    fmt.text(
                        fmt.text["bright_red", "bold"](
                            f"Error parsing {display_name}:"
                        ),
                        " ",
                        e.message,
                    ),
                    fmt.hr["red"](),
                    "Argument helptext:",
                    fmt.cols(
                        ("", 4),
                        fmt.rows(
                            e.arg.get_invocation_text()[1],
                            _arguments.generate_argument_helptext(e.arg, e.arg.lowered),
                        ),
                    ),
                ]
            )
        else:
            error_box_rows.append(
                fmt.text(
                    fmt.text["bright_red", "bold"](
                        f"Error parsing {e.arg}:",
                    ),
                    " ",
                    e.message,
                ),
            )

        if add_help:
            error_box_rows.extend(
                [
                    fmt.hr["red"](),
                    fmt.text(
                        "For full helptext, see ",
                        fmt.text["bold"](f"{prog} --help"),
                    ),
                ]
            )
        print(
            fmt.box["red"](fmt.text["red"]("Value error"), fmt.rows(*error_box_rows)),
            file=sys.stderr,
            flush=True,
        )
        sys.exit(2)

    assert len(value_from_prefixed_field_name.keys() - consumed_keywords) == 0, (
        f"Parsed {value_from_prefixed_field_name.keys()}, but only consumed"
        f" {consumed_keywords}"
    )
    if return_unknown_args:
        assert unknown_args is not None, "Should have parsed with `parse_known_args()`"
        # If we're parsed unknown args, we should return the original args, not
        # the fixed ones.
        if modified_args is not None:
            unknown_args = [modified_args.get(arg, arg) for arg in unknown_args]
        return get_out, unknown_args  # type: ignore
    else:
        assert unknown_args is None, "Should have parsed with `parse_args()`"
        return get_out  # type: ignore
