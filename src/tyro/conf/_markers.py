from typing import TYPE_CHECKING, Any, Callable, TypeVar

from typing_extensions import Annotated

from .. import _singleton

# Current design issue: markers are applied recursively to nested structures, but can't
# be unapplied.

# All Annotated[T, None] values are just for static checkers. The real marker
# singletons are instantiated dynamically below.
#
# An alias could ideally be made, but SpecialForm aliases aren't well supported by
# type checkers.

T = TypeVar("T")

Positional = Annotated[T, None]
"""Mark a parameter to be parsed as a positional argument rather than a keyword argument.

Example::

    @dataclass
    class Args:
        input_file: Positional[str]  # Will be a positional arg
        output_file: str  # Will be a keyword arg (--output-file)

With this configuration, the CLI would accept: ``python script.py input.txt --output-file output.txt``
"""

PositionalRequiredArgs = Annotated[T, None]
"""Make all required arguments (those without default values) positional.

This marker applies to an entire interface when passed to the `config` parameter of `tyro.cli()`.

Example::

    @dataclass
    class Args:
        input_file: str  # No default, will be positional
        output_file: str = "output.txt"  # Has default, will be a keyword arg

    args = tyro.cli(Args, config=(tyro.conf.PositionalRequiredArgs,))
"""

# Private marker. For when an argument is not only positional in the CLI, but also in
# the callable.
_PositionalCall = Annotated[T, None]

# Private markers for when arguments should be passed in via *args or **kwargs.
_UnpackArgsCall = Annotated[T, None]
_UnpackKwargsCall = Annotated[T, None]

# Private marker.
_OPTIONAL_GROUP = Annotated[T, None]

# TODO: the verb tenses here are inconsistent, naming could be revisited.
# Perhaps Suppress should be Suppressed? But SuppressedFixed would be weird.

Fixed = Annotated[T, None]
"""Mark a field as fixed, preventing it from being modified through the CLI.

When a field is marked as Fixed, tyro will use the default value and will not
create a CLI option for it. This is useful for fields that should not be configurable
via command line arguments.

Example::

    @dataclass
    class Config:
        input_path: str
        debug_mode: Fixed[bool] = False  # Cannot be changed via CLI
        version: Fixed[str] = "1.0.0"    # Cannot be changed via CLI

Fields that aren't support by tyro but have defaults will be automatically marked as fixed.
"""

Suppress = Annotated[T, None]
"""Remove a field from the CLI interface and helptext.

Unlike :data:`Fixed`, which shows the field in the helptext but prevents modification,
:data:`Suppress` hides the field from both the CLI and the helptext.

Example::

    @dataclass
    class Config:
        input_path: str
        # Internal fields that users don't need to see
        _cached_data: Suppress[dict] = dataclasses.field(default_factory=dict)
        _debug_level: Suppress[int] = 0
"""

SuppressFixed = Annotated[T, None]
"""Hide fields that are marked as :data:`Fixed` from the helptext.

This marker can be applied globally to hide all fixed fields from the helptext,
making the interface cleaner by showing only fields that can be modified via CLI.

Example::

    tyro.cli(Config, config=(tyro.conf.SuppressFixed,))
"""

FlagConversionOff = Annotated[T, None]
"""Disable automatic flag-style conversion for boolean fields.

By default, boolean fields with default values are converted to flags that can be enabled
or disabled with command-line options. With :data:`FlagConversionOff`, the boolean fields will
expect an explicit True or False value.

Example::

    # Default behavior (with flag conversion)
    debug: bool = False
    # Usage: python script.py --debug      # Sets to True
    #        python script.py --no-debug   # Sets to False

    # With FlagConversionOff
    debug: FlagConversionOff[bool] = False
    # Usage: python script.py --debug True  # Explicit value required
    #        python script.py --debug False

This marker can be applied to specific boolean fields or globally using the config parameter.
"""

FlagCreatePairsOff = Annotated[T, None]
"""Disable creation of matching flag pairs for boolean types.

By default, tyro creates both positive and negative flags for boolean values
(like ``--flag`` and ``--no-flag``). With :data:`FlagCreatePairsOff`, only one flag will be created:

- ``--flag`` if the default is False
- ``--no-flag`` if the default is True

Example::

    # Default behavior (with flag pairs)
    debug: bool = False
    # Usage: python script.py --debug      # Sets to True
    #        python script.py --no-debug   # Sets to False

    # With FlagCreatePairsOff
    debug: FlagCreatePairsOff[bool] = False
    # Usage: python script.py --debug      # Sets to True
    #        (--no-debug flag is not created)

This can make the helptext less cluttered but is less robust if default values change.
"""

AvoidSubcommands = Annotated[T, None]
"""Avoid creating subcommands for union types that have a default value.

When a union type has a default value, tyro creates a subcommand interface.
With :data:`AvoidSubcommands`, tyro will use the default value and not create subcommands,
simplifying the CLI interface (but making it less expressive).

Example::

    # Without AvoidSubcommands
    @dataclass
    class Config:
        mode: Union[ClassA, ClassB] = ClassA()
        # CLI would have subcommands: python script.py mode:class-a ... or mode:class-b ...

    # With AvoidSubcommands
    @dataclass
    class Config:
        mode: AvoidSubcommands[Union[ClassA, ClassB]] = ClassA()
        # CLI would not have subcommands, would use ClassA() as default

This can be applied to specific union fields or globally with the config parameter.
"""

ConsolidateSubcommandArgs = Annotated[T, None]
"""Consolidate arguments for nested subcommands to make CLI less position-sensitive.

By default, tyro generates CLI interfaces where arguments apply to the directly preceding
subcommand, which creates position-dependent behavior:

.. code-block:: bash

    # Default behavior - position matters
    python x.py {--root options} s1 {--s1 options} s2 {--s2 options}

With :data:`ConsolidateSubcommandArgs`, all arguments are moved to the end, after all subcommands:

.. code-block:: bash

    # With ConsolidateSubcommandArgs - all options at the end
    python x.py s1 s2 {--root, s1, and s2 options}

This makes the interface more robust to argument reordering, but has a tradeoff: if
root options are required (have no defaults), all subcommands must be specified
before providing those required arguments.

Example::

    tyro.cli(NestedConfig, config=(tyro.conf.ConsolidateSubcommandArgs,))
"""

OmitSubcommandPrefixes = Annotated[T, None]
"""Simplify subcommand names by removing parent field prefixes from subcommands.

By default, tyro uses prefixes to create namespaced subcommands and arguments.
With :data:`OmitSubcommandPrefixes`, subcommand prefixes are omitted, making CLI commands shorter.

Example::

    @dataclass
    class Config:
        mode: Union[ProcessorA, ProcessorB]

    # Default CLI (with prefixes):
    # python script.py mode:processor-a --mode.option value

    # With OmitSubcommandPrefixes:
    # python script.py processor-a --option value

This is useful for deeply nested structures where the fully prefixed arguments would
become unwieldy.
"""

OmitArgPrefixes = Annotated[T, None]
"""Simplify argument names by removing parent field prefixes from flags.

By default, tyro creates namespaced flags for nested structures (like ``--parent.child.option``).
With :data:`OmitArgPrefixes`, the prefixes are omitted, resulting in shorter argument names.

Example::

    @dataclass
    class NestedConfig:
        option: str = "value"

    @dataclass
    class Config:
        nested: OmitArgPrefixes[NestedConfig]

    # Default CLI (with prefixes):
    # python script.py --nested.option value

    # With OmitArgPrefixes:
    # python script.py --option value

This can simplify command lines but may cause name conflicts if multiple nested
structures have fields with the same name.
"""

UseAppendAction = Annotated[T, None]
"""Enable specifying list elements through repeated flag usage rather than space-separated values.

By default, tyro expects list elements to be provided as space-separated values after a single flag.
With :data:`UseAppendAction`, each element is provided by repeating the flag multiple times.

Example::

    @dataclass
    class Config:
        # Default list behavior
        numbers: list[int]
        # With UseAppendAction
        tags: UseAppendAction[list[str]]

    # Default list usage:
    # python script.py --numbers 1 2 3

    # UseAppendAction usage:
    # python script.py --tags red --tags green --tags blue

This provides two benefits:
1. More intuitive for some users who prefer repeating arguments
2. Enables support for nested lists like `list[list[int]]` that would otherwise be ambiguous
"""

UseCounterAction = Annotated[T, None]
"""Create a counter-style flag that increments an integer each time it appears.

This marker converts an integer parameter into a counter where each occurrence of the flag
increases the value by 1, similar to common CLI tools like ``-v``, ``-vv``, ``-vvv`` for verbosity.

Example::

    @dataclass
    class Config:
        verbose: UseCounterAction[int] = 0

    # Usage:
    # python script.py            # verbose = 0
    # python script.py --verbose  # verbose = 1
    # python script.py --verbose --verbose  # verbose = 2
    # python script.py --verbose --verbose --verbose  # verbose = 3

This is useful for verbosity levels or similar numeric settings where repeated flags
are more intuitive than explicit values.
"""

EnumChoicesFromValues = Annotated[T, None]
"""Use enum values instead of enum names for command-line choices.

By default, tyro uses enum member names as the choices shown in the CLI.
With :data:`EnumChoicesFromValues`, the enum values are used as choices instead.

Example::

    import enum
    from dataclasses import dataclass
    import tyro

    class OutputFormat(enum.StrEnum):
        JSON = enum.auto()      # value is "json"
        PRETTY = enum.auto()    # value is "pretty"
        RICH = enum.auto()      # value is "rich"
        TOML = enum.auto()      # value is "toml"

    @dataclass
    class Config:
        # Default behavior: choices would be JSON, PRETTY, RICH, TOML
        format: OutputFormat = OutputFormat.PRETTY

        # With EnumChoicesFromValues: choices are json, pretty, rich, toml
        alt_format: EnumChoicesFromValues[OutputFormat] = OutputFormat.PRETTY

This is useful with auto-generated enum values like those in
:py:class:`enum.StrEnum`, where the values may be more user-friendly than the internal
names.

When :data:`EnumChoicesFromValues` is used, enum aliases aren't considered. The first enum member with a
matching value will be selected.
"""

HelptextFromCommentsOff = Annotated[T, None]
"""Disable automatic helptext generation from code comments.

By default, tyro extracts helptext from comments in the source code:
- Comments before a field definition are used as helptext
- Inline comments following a field definition are used as helptext

Example::

    @dataclass
    class Config:
        # This comment becomes helptext for input_file
        input_file: str

        output_file: str  # This inline comment becomes helptext for output_file

If you have code with many organizational or implementation comments that shouldn't
appear in the CLI help, this automatic extraction might be unhelpful. This marker
disables comment extraction while preserving docstring extraction.

Example::

    tyro.cli(Config, config=(tyro.conf.HelptextFromCommentsOff,))

Triple-quoted docstrings on fields are still used for helptext
even when this marker is applied.
"""


CallableType = TypeVar("CallableType", bound=Callable)

# Dynamically generate marker singletons.
# These can be used one of two ways:
# - Marker[T]
# - Annotated[T, Marker]


class _Marker(_singleton.Singleton):
    def __getitem__(self, key):
        return Annotated[(key, self)]  # type: ignore


Marker = Any


def configure(*markers: Marker) -> Callable[[CallableType], CallableType]:
    """Decorator for applying configuration options.

    .. warning::

        We recommend avoiding this function if possible. For global flags,
        prefer passing ``config=`` to :func:`tyro.cli()` instead.

    Consider using the ``config=`` argument of :func:`tyro.cli()` instead, which takes
    the same config marker objects as inputs.

    Configuration markers are implemented via :py:data:`typing.Annotated` and
    straightforward to apply to types, for example:

    .. code-block:: python

        field: tyro.conf.FlagConversionOff[bool]

    This decorator makes markers applicable to general functions as well:

    .. code-block:: python

        # Recursively apply FlagConversionOff to all fields in `main()`.
        @tyro.conf.configure(tyro.conf.FlagConversionOff)
        def main(field: bool) -> None:
            ...

    Args:
        markers: Options to apply.
    """

    def _inner(callable: CallableType) -> CallableType:
        # We'll read from __tyro_markers__ in `_resolver.unwrap_annotated()`.
        callable.__tyro_markers__ = markers  # type: ignore
        return callable

    return _inner


if not TYPE_CHECKING:

    def _make_marker(description: str) -> _Marker:
        class _InnerMarker(_Marker):
            def __repr__(self):
                return description

        return _InnerMarker()

    _dynamic_marker_types = {}
    for k, v in dict(globals()).items():
        if v == Annotated[T, None]:
            _dynamic_marker_types[k] = _make_marker(k)
    globals().update(_dynamic_marker_types)
    del _dynamic_marker_types
