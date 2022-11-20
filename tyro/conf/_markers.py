from typing import TYPE_CHECKING, Callable, Type, TypeVar

from typing_extensions import Annotated

from .. import _singleton

# Current design issue: markers are applied recursively to nested structures, but can't
# be unapplied.

# Note that all Annotated[T, None] values are just for static checkers. The real marker
# singletons are instantiated dynamically below.
#
# An alias could ideally be made, but SpecialForm aliases are not well supported by static analysis tools.

T = TypeVar("T", bound=Type)

Positional = Annotated[T, None]
"""A type `T` can be annotated as `Positional[T]` if we want to parse it as a positional
argument."""

# Private marker. For when an argument is not only positional in the CLI, but also in
# the callable.
_PositionalCall = Annotated[T, None]

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
"""Make flags used for keyword arguments in subcommands shorter by omitting prefixes.

If we have a structure with the field:

    cmd: Union[NestedTypeA, NestedTypeB]

By default, `--cmd.arg` may be generated as a flag for each dataclass in the union.
If subcommand prefixes are omitted, we would instead simply have `--arg`.
"""

CallableType = TypeVar("CallableType", bound=Callable)

# Dynamically generate marker singletons.
# These can be used one of two ways:
# - Marker[T]
# - Annotated[T, Marker]


class Marker(_singleton.Singleton):
    def __getitem__(self, key):
        return Annotated.__class_getitem__((key, self))  # type: ignore


def configure(*markers: Marker) -> Callable[[CallableType], CallableType]:
    """Decorator for configuring functions.

    Configuration markers are implemented via `typing.Annotated` and straightforward to
    apply to types, for example:

    ```python
    field: tyro.conf.FlagConversionOff[bool]
    ```

    This decorator makes markers applicable to general functions as well:

    ```python
    # Recursively apply FlagConversionOff to all field in `main()`.
    @tyro.conf.configure_function(tyro.conf.FlagConversionOff)
    def main(field: bool) -> None:
        ...
    ```
    """

    def _inner(callable: CallableType) -> CallableType:
        return Annotated.__class_getitem__((callable,) + tuple(markers))  # type: ignore

    return _inner


if not TYPE_CHECKING:

    def _make_marker(description: str) -> Marker:
        class _InnerMarker(Marker):
            def __repr__(self):
                return description

        return _InnerMarker()

    _dynamic_marker_types = {}
    for k, v in dict(globals()).items():
        if v == Annotated[T, None]:
            _dynamic_marker_types[k] = _make_marker(k)
    globals().update(_dynamic_marker_types)
    del _dynamic_marker_types
