from typing import TYPE_CHECKING, Any, Callable, TypeVar

from typing_extensions import Annotated

from .. import _singleton

# Current design issue: markers are applied recursively to nested structures, but can't
# be unapplied.

# Note that all Annotated[T, None] values are just for static checkers. The real marker
# singletons are instantiated dynamically below.
#
# An alias could ideally be made, but SpecialForm aliases are not well supported by static analysis tools.

T = TypeVar("T")

Positional = Annotated[T, None]
"""A type `T` can be annotated as `Positional[T]` if we want to parse it as a positional
argument."""

PositionalRequiredArgs = Annotated[T, None]
"""Make all arguments without defaults positional."""

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
"""A type `T` can be annotated as `Fixed[T]` to prevent `tyro.cli` from parsing it; a
default value should be set instead. Note that fields with defaults that can't be parsed
will also be marked as fixed automatically."""

Suppress = Annotated[T, None]
"""A type `T` can be annotated as `Suppress[T]` to prevent `tyro.cli` from parsing it, and
to prevent it from showing up in helptext."""

SuppressFixed = Annotated[T, None]
"""Hide fields that are either manually or automatically marked as fixed."""

FlagConversionOff = Annotated[T, None]
"""Turn off flag conversion for booleans with default values. Instead, types annotated
with `bool` will expect an explicit True or False.

Can be used directly on boolean annotations, `FlagConversionOff[bool]`, or recursively
applied to nested types."""

AvoidSubcommands = Annotated[T, None]
"""Avoid creating subcommands when a default is provided for unions over nested types.
This simplifies CLI interfaces, but makes them less expressive.

Can be used directly on union types, `AvoidSubcommands[Union[...]]`, or recursively
applied to nested types."""

ConsolidateSubcommandArgs = Annotated[T, None]
"""Consolidate arguments applied to subcommands. Makes CLI less sensitive to argument
ordering, at the cost of support for optional subcommands.

By default, `tyro` will generate a traditional CLI interface where args are applied to
the directly preceding subcommand. When we have two subcommands `s1` and `s2`:
```
python x.py {--root options} s1 {--s1 options} s2 {--s2 options}
```

This can be frustrating because the resulting CLI is sensitive the exact positioning and
ordering of options.

To consolidate subcommands, we push arguments to the end, after all subcommands:
```
python x.py s1 s2 {--root, s1, and s2 options}
```

This is more robust to reordering of options, ensuring that any new options can simply
be placed at the end of the command>
"""

OmitSubcommandPrefixes = Annotated[T, None]
"""Make flags used for keyword arguments in subcommands shorter by omitting the
subcommand-specific portion of the prefix.

If we have a structure with the field:

    cmd: Union[NestedTypeA, NestedTypeB]

By default, `--cmd.arg` may be generated as a flag for each dataclass in the union.
If subcommand prefixes are omitted, we would instead simply have `--arg`.
"""

OmitArgPrefixes = Annotated[T, None]
"""Make flags used for keyword arguments shorter by omitting prefixes.

If we have a structure with the field:

    cmd: NestedType

By default, `--cmd.arg` may be generated as a flag. If prefixes are omitted, we would
instead simply have `--arg`.
"""

UseAppendAction = Annotated[T, None]
"""Use "append" actions for variable-length arguments.

Given an annotation like `x: List[int]`, this means that `x = [0, 1, 2]` can be set via
the CLI syntax `--x 0 --x 1 --x 2` instead of the default of `--x 0 1 2`.

The resulting syntax may be more user-friendly; for `tyro`, it also enables support for
otherwise ambiguous annotations like `List[List[int]]`.

Can be applied to all variable-length sequences (`List[T]`, `Sequence[T]`,
`Tuple[T, ...]`, etc), including dictionaries without default values.
"""

CallableType = TypeVar("CallableType", bound=Callable)

# Dynamically generate marker singletons.
# These can be used one of two ways:
# - Marker[T]
# - Annotated[T, Marker]


class _Marker(_singleton.Singleton):
    def __getitem__(self, key):
        return Annotated.__class_getitem__((key, self))  # type: ignore


Marker = Any


def configure(*markers: Marker) -> Callable[[CallableType], CallableType]:
    """Decorator for applying configuration options.

    Configuration markers are implemented via `typing.Annotated` and straightforward to
    apply to types, for example:

    ```python
    field: tyro.conf.FlagConversionOff[bool]
    ```

    This decorator makes markers applicable to general functions as well:

    ```python
    # Recursively apply FlagConversionOff to all fields in `main()`.
    @tyro.conf.configure(tyro.conf.FlagConversionOff)
    def main(field: bool) -> None:
        ...
    ```

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
