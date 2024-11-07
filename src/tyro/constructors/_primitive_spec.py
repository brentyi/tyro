from __future__ import annotations

import collections
import collections.abc
import dataclasses
import datetime
import enum
import inspect
import json
import os
import pathlib
import sys
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from typing_extensions import TYPE_CHECKING, Literal, get_args, get_origin

if TYPE_CHECKING:
    from ._registry import ConstructorRegistry

# There are cases where typing.Literal doesn't match typing_extensions.Literal:
# https://github.com/python/typing_extensions/pull/148
try:
    from typing import Literal as LiteralAlternate
except ImportError:
    LiteralAlternate = Literal  # type: ignore


from .. import _resolver, _strings
from .._typing import TypeForm
from ..conf import _markers


class UnsupportedTypeAnnotationError(Exception):
    """Exception raised when an unsupported type annotation is detected."""


T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class PrimitiveTypeInfo:
    """Information used to generate constructors for primitive types."""

    type: TypeForm
    """Annotated field type. Forward references, aliases, and type
    variables/parameters will have been resolved and runtime annotations
    (typing.Annotated) will have been stripped."""
    type_origin: TypeForm | None
    """The output of get_origin() on the static type."""
    markers: set[_markers.Marker]
    """Set of tyro markers used to configure this field."""
    _primitive_spec: PrimitiveConstructorSpec | None
    """Primitive constructor spec that was scraped from runtime annotations."""

    @staticmethod
    def make(
        raw_annotation: TypeForm | Callable,
        parent_markers: set[_markers.Marker],
    ) -> PrimitiveTypeInfo:
        _, primitive_specs = _resolver.unwrap_annotated(
            raw_annotation, search_type=PrimitiveConstructorSpec
        )
        primitive_spec = primitive_specs[0] if len(primitive_specs) > 0 else None

        typ, extra_markers = _resolver.unwrap_annotated(
            raw_annotation, search_type=_markers._Marker
        )
        return PrimitiveTypeInfo(
            type=cast(TypeForm, typ),
            type_origin=get_origin(typ),
            markers=parent_markers | set(extra_markers),
            _primitive_spec=primitive_spec,
        )


@dataclasses.dataclass(frozen=True)
class PrimitiveConstructorSpec(Generic[T]):
    """Specification for constructing a primitive type from a string.

    There are two ways to use this class:

    First, we can include it in a type signature via :class:`typing.Annotated`.
    This is the simplest for making local modifications to parsing behavior for
    individual fields.

    Alternatively, it can be returned by a rule in a :class:`ConstructorRegistry`.
    """

    nargs: int | Literal["*"]
    """Number of arguments required to construct an instance. If nargs is "*", then
    the number of arguments is variable."""
    metavar: str
    """Metavar to display in help messages."""
    instance_from_str: Callable[[list[str]], T]
    """Given a list of string arguments, construct an instance of the type. The
    length of the list will match the value of nargs."""
    is_instance: Callable[[Any], bool | Literal["~"]]
    """Given an object instance, does it match this primitive type? This is
    used for specific help messages when both a union type is present and a
    default is provided.

    Can return "~" to signify that an instance is a "fuzzy" match, and should
    only be used if there are no other matches. This is used for numeric tower
    support.
    """
    str_from_instance: Callable[[T], list[str]]
    """Convert an instance to a list of string arguments that would construct
    the instance. This is used for help messages when a default is provided."""
    choices: tuple[str, ...] | None = None
    """Finite set of choices for arguments."""

    _action: Literal["append"] | None = None
    """Internal action to use. Not part of the public API."""


def apply_default_primitive_rules(registry: ConstructorRegistry) -> None:
    """Apply default rules to the registry."""

    from ._registry import ConstructorRegistry

    @registry._default_primitive_rule
    def any_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type is not Any:
            return None
        raise UnsupportedTypeAnnotationError("`Any` is not a parsable type.")

    # HACK (json.loads): this is for code that uses
    # `tyro.conf.arg(constructor=json.loads)`. We're going to deprecate this
    # syntax (the constructor= argument in tyro.conf.arg), but there is code
    # that lives in the wild that relies on the behavior so we'll do our best
    # not to break it.
    vanilla_types = (int, str, float, complex, bytes, bytearray, json.loads)

    @registry._default_primitive_rule
    def basics_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type not in vanilla_types:
            return None
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar=type_info.type.__name__.upper(),
            instance_from_str=lambda args: (
                bytes(args[0], encoding="ascii")
                if type_info.type is bytes
                else type_info.type(args[0])
            ),
            # issubclass(type(x), y) here is preferable over isinstance(x, y)
            # due to quirks in the numeric tower.
            is_instance=lambda x: _resolver.isinstance_with_fuzzy_numeric_tower(
                x, type_info.type
            ),
            str_from_instance=lambda instance: [str(instance)],
        )

    if "torch" in sys.modules.keys():
        import torch

        @registry._default_primitive_rule
        def torch_device_rule(
            type_info: PrimitiveTypeInfo,
        ) -> PrimitiveConstructorSpec | None:
            if type_info.type is not torch.device:
                return None
            return PrimitiveConstructorSpec(
                nargs=1,
                metavar=type_info.type.__name__.upper(),
                instance_from_str=lambda args: torch.device(args[0]),
                is_instance=lambda x: isinstance(x, type_info.type),
                str_from_instance=lambda instance: [str(instance)],
            )

    @registry._default_primitive_rule
    def bool_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type is not bool:
            return None
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar="{True,False}",
            instance_from_str=lambda args: args[0] == "True",
            choices=("True", "False"),
            is_instance=lambda x: isinstance(x, bool),
            str_from_instance=lambda instance: ["True" if instance else "False"],
        )

    @registry._default_primitive_rule
    def nonetype_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type is not type(None):
            return None
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar="{None}",
            choices=("None",),
            instance_from_str=lambda args: None,
            is_instance=lambda x: x is None,
            str_from_instance=lambda instance: ["None"],
        )

    @registry._default_primitive_rule
    def path_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if not (
            type_info.type in (os.PathLike, pathlib.Path)
            or (
                inspect.isclass(type_info.type)
                and issubclass(type_info.type, pathlib.PurePath)
            )
        ):
            return None
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar=type_info.type.__name__.upper(),
            instance_from_str=lambda args: pathlib.Path(args[0]),
            is_instance=lambda x: hasattr(x, "__fspath__"),
            str_from_instance=lambda instance: [str(instance)],
        )

    @registry._default_primitive_rule
    def enum_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if not (
            inspect.isclass(type_info.type) and issubclass(type_info.type, enum.Enum)
        ):
            return None
        cast_type = cast(Type[enum.Enum], type_info.type)
        if _markers.EnumChoicesFromValues in type_info.markers:
            choices = tuple(str(m.value) for m in cast_type)
        else:
            choices = tuple(type_info.type.__members__.keys())

        return PrimitiveConstructorSpec(
            nargs=1,
            metavar="{" + ",".join(choices) + "}",
            instance_from_str=lambda args: (
                next(
                    iter(member for member in cast_type if str(member.value) == args[0])
                )
                if _markers.EnumChoicesFromValues in type_info.markers
                else cast_type[args[0]]
            ),
            is_instance=lambda x: isinstance(x, cast_type),
            str_from_instance=lambda instance: [
                (
                    str(instance.value)
                    if _markers.EnumChoicesFromValues in type_info.markers
                    else instance.name
                )
            ],
            choices=choices,
        )

    @registry._default_primitive_rule
    def datetime_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type not in (datetime.datetime, datetime.date, datetime.time):
            return None
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar={
                datetime.datetime: "YYYY-MM-DD[THH:MM:[SS[…]]]",
                datetime.date: "YYYY-MM-DD",
                datetime.time: "HH:MM[:SS[…]]",
            }[type_info.type],
            instance_from_str=lambda args: cast(
                Union[
                    Type[datetime.datetime], Type[datetime.date], Type[datetime.time]
                ],
                type_info.type,
            ).fromisoformat(args[0]),
            is_instance=lambda x: isinstance(x, type_info.type),
            str_from_instance=lambda instance: [instance.isoformat()],
        )

    @registry._default_primitive_rule
    def vague_container_rule(
        type_info: PrimitiveTypeInfo,
    ) -> PrimitiveConstructorSpec | None:
        if type_info.type not in (
            dict,
            Dict,
            tuple,
            Tuple,
            list,
            List,
            collections.abc.Sequence,
            Sequence,
            set,
            Set,
        ):
            return None
        typ = type_info.type
        if typ in (dict, Dict):
            typ = Dict[str, str]
        elif typ in (tuple, Tuple):
            typ = Tuple[str, ...]  # type: ignore
        elif typ in (list, List, collections.abc.Sequence, Sequence):
            typ = List[str]
        elif typ in (set, Set):
            typ = Set[str]

        registry = ConstructorRegistry._get_active_registry()
        return registry.get_primitive_spec(
            PrimitiveTypeInfo.make(
                typ,
                parent_markers=type_info.markers,
            )
        )

    @registry._default_primitive_rule
    def sequence_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type_origin not in (
            collections.abc.Sequence,
            frozenset,
            list,
            set,
            collections.deque,
            tuple,
        ):
            return None
        container_type = type_info.type_origin
        assert container_type is not None
        if container_type is collections.abc.Sequence:
            container_type = list

        if container_type is tuple:
            (contained_type, ell) = get_args(type_info.type)
            assert ell == Ellipsis
        else:
            (contained_type,) = get_args(type_info.type)

        registry = ConstructorRegistry._get_active_registry()
        inner_spec = registry.get_primitive_spec(
            PrimitiveTypeInfo.make(
                raw_annotation=contained_type,
                parent_markers=type_info.markers - {_markers.UseAppendAction},
            )
        )

        if _markers.UseAppendAction not in type_info.markers and not isinstance(
            inner_spec.nargs, int
        ):
            raise UnsupportedTypeAnnotationError(
                f"{container_type} and {contained_type} are both variable-length sequences."
                " This causes ambiguity."
                " For nesting variable-length sequences (example: List[List[int]]),"
                " `tyro.conf.UseAppendAction` can help resolve ambiguities."
            )

        def instance_from_str(args: list[str]) -> Any:
            # Validate nargs.
            assert isinstance(inner_spec.nargs, int)
            if isinstance(inner_spec.nargs, int) and len(args) % inner_spec.nargs != 0:
                raise ValueError(
                    f"input {args} is of length {len(args)}, which is not"
                    f" divisible by {inner_spec.nargs}."
                )

            # Instantiate.
            out = []
            step = inner_spec.nargs if isinstance(inner_spec.nargs, int) else 1
            for i in range(0, len(args), step):
                out.append(inner_spec.instance_from_str(args[i : i + inner_spec.nargs]))
            assert container_type is not None
            return cast(Callable, container_type)(out)

        def str_from_instance(instance: Sequence) -> list[str]:
            out = []
            for i in instance:
                out.extend(inner_spec.str_from_instance(i))
            return out

        if _markers.UseAppendAction in type_info.markers:
            return PrimitiveConstructorSpec(
                nargs=inner_spec.nargs,
                metavar=inner_spec.metavar,
                instance_from_str=inner_spec.instance_from_str,
                is_instance=lambda x: isinstance(x, container_type)
                and all(inner_spec.is_instance(i) for i in x),
                str_from_instance=str_from_instance,
                choices=inner_spec.choices,
                _action="append",
            )
        else:
            return PrimitiveConstructorSpec(
                nargs="*",
                metavar=_strings.multi_metavar_from_single(inner_spec.metavar),
                instance_from_str=instance_from_str,
                is_instance=lambda x: isinstance(x, container_type)
                and all(inner_spec.is_instance(i) for i in x),
                str_from_instance=str_from_instance,
                choices=inner_spec.choices,
            )

    @registry._default_primitive_rule
    def tuple_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type_origin is not tuple:
            return None
        types = get_args(type_info.type)
        typeset = set(types)  # Sets are unordered.
        typeset_no_ellipsis = typeset - {Ellipsis}  # type: ignore

        if typeset_no_ellipsis != typeset:
            # Ellipsis: variable argument counts. When an ellipsis is used, tuples must
            # contain only one type.
            assert len(typeset_no_ellipsis) == 1
            return sequence_rule(type_info)

        registry = ConstructorRegistry._get_active_registry()

        inner_specs = []
        total_nargs = 0
        for contained_type in types:
            spec = registry.get_primitive_spec(
                PrimitiveTypeInfo.make(contained_type, type_info.markers)
            )
            if isinstance(spec.nargs, int):
                total_nargs += spec.nargs
            else:
                raise UnsupportedTypeAnnotationError(
                    f"Tuples containing a variable-length sequences ({contained_type}) are not supported."
                )

            inner_specs.append(spec)

        def instance_from_str(args: list[str]) -> tuple:
            assert len(args) == total_nargs

            out = []
            i = 0
            for member_spec in inner_specs:
                assert isinstance(member_spec.nargs, int)
                member_strings = args[i : i + member_spec.nargs]
                if member_spec.choices is not None and any(
                    s not in member_spec.choices for s in member_strings
                ):
                    raise ValueError(
                        f"invalid choice: {member_strings} (choose from {member_spec.choices}))"
                    )
                out.append(member_spec.instance_from_str(member_strings))
                i += member_spec.nargs
            return tuple(out)

        def str_from_instance(instance: tuple) -> list[str]:
            out = []
            for member, spec in zip(instance, inner_specs):
                out.extend(spec.str_from_instance(member))
            return out

        return PrimitiveConstructorSpec(
            nargs=total_nargs,
            metavar=" ".join(spec.metavar for spec in inner_specs),
            instance_from_str=instance_from_str,
            str_from_instance=str_from_instance,
            is_instance=lambda x: isinstance(x, tuple)
            and len(x) == total_nargs
            and all(spec.is_instance(member) for member, spec in zip(x, inner_specs)),
        )

    @registry._default_primitive_rule
    def dict_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type_origin not in (dict, collections.abc.Mapping):
            return None

        registry = ConstructorRegistry._get_active_registry()

        key_type, val_type = get_args(type_info.type)
        key_spec = registry.get_primitive_spec(
            PrimitiveTypeInfo.make(
                raw_annotation=key_type,
                parent_markers=type_info.markers,
            )
        )
        val_spec = registry.get_primitive_spec(
            PrimitiveTypeInfo.make(
                raw_annotation=val_type,
                parent_markers=type_info.markers - {_markers.UseAppendAction},
            )
        )
        pair_metavar = f"{key_spec.metavar} {val_spec.metavar}"

        if not isinstance(key_spec.nargs, int):
            raise UnsupportedTypeAnnotationError(
                "Dictionary keys must have a fixed number of arguments."
            )

        if _markers.UseAppendAction not in type_info.markers and not isinstance(
            val_spec.nargs, int
        ):
            raise UnsupportedTypeAnnotationError(
                "Dictionary values must have a fixed number of arguments."
            )

        def instance_from_str(args: list[str]) -> dict:
            out = {}
            key_nargs = key_spec.nargs
            assert isinstance(key_nargs, int)
            val_nargs = (
                val_spec.nargs
                if _markers.UseAppendAction not in type_info.markers
                else len(args) - key_nargs
            )
            assert isinstance(val_nargs, int)

            pair_nargs = key_nargs + val_nargs
            if len(args) % pair_nargs != 0:
                raise ValueError("Incomplete set of key-value pairs!")

            for i in range(0, len(args), pair_nargs):
                key = key_spec.instance_from_str(args[i : i + key_nargs])
                value = val_spec.instance_from_str(args[i + key_nargs : i + pair_nargs])
                out[key] = value
            return out

        def str_from_instance(instance: dict) -> list[str]:
            # TODO: this may be strange right now for the append action.
            out: list[str] = []
            for key, value in instance.items():
                out.extend(key_spec.str_from_instance(key))
                out.extend(val_spec.str_from_instance(value))
            return out

        if _markers.UseAppendAction in type_info.markers:
            return PrimitiveConstructorSpec(
                nargs=(
                    key_spec.nargs + val_spec.nargs
                    if isinstance(val_spec.nargs, int)
                    else "*"
                ),
                metavar=pair_metavar,
                instance_from_str=instance_from_str,
                is_instance=lambda x: isinstance(x, dict)
                and all(
                    key_spec.is_instance(k) and val_spec.is_instance(v)
                    for k, v in x.items()
                ),
                str_from_instance=str_from_instance,
                _action="append",
            )
        else:
            return PrimitiveConstructorSpec(
                nargs="*",
                metavar=_strings.multi_metavar_from_single(pair_metavar),
                instance_from_str=instance_from_str,
                is_instance=lambda x: isinstance(x, dict)
                and all(
                    key_spec.is_instance(k) and val_spec.is_instance(v)
                    for k, v in x.items()
                ),
                str_from_instance=str_from_instance,
            )

    @registry._default_primitive_rule
    def literal_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type_origin not in (Literal, LiteralAlternate):
            return None
        choices = get_args(type_info.type)
        str_choices = tuple(
            (
                (
                    x.value
                    if _markers.EnumChoicesFromValues in type_info.markers
                    else x.name
                )
                if isinstance(x, enum.Enum)
                else str(x)
            )
            for x in choices
        )
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar="{" + ",".join(str_choices) + "}",
            instance_from_str=lambda args: choices[str_choices.index(args[0])],
            is_instance=lambda x: x in choices,
            str_from_instance=lambda instance: [str(instance)],
            choices=str_choices,
        )

    @registry._default_primitive_rule
    def union_rule(type_info: PrimitiveTypeInfo) -> PrimitiveConstructorSpec | None:
        if type_info.type_origin not in (Union, _resolver.UnionType):
            return None
        options = list(get_args(type_info.type))
        if type(None) in options:
            # Move `None` types to the beginning.
            # If we have `Optional[str]`, we want this to be parsed as
            # `Union[NoneType, str]`.
            options.remove(type(None))
            options.insert(0, type(None))

        # General unions, eg Union[int, bool]. We'll try to convert these from left to
        # right.
        option_specs: list[PrimitiveConstructorSpec] = []
        choices: tuple[str, ...] | None = ()
        nargs: int | Literal["*"] = 1
        first = True
        registry = ConstructorRegistry._get_active_registry()
        for t in options:
            option_spec = registry.get_primitive_spec(
                PrimitiveTypeInfo.make(
                    raw_annotation=t,
                    parent_markers=type_info.markers,
                )
            )
            if option_spec.choices is None:
                choices = None
            elif choices is not None:
                choices = choices + option_spec.choices

            option_specs.append(option_spec)

            if t is not type(None):
                # Enforce that `nargs` is the same for all child types, except for
                # NoneType.
                if first:
                    nargs = option_spec.nargs
                    first = False
                elif nargs != option_spec.nargs:
                    # Just be as general as possible if we see inconsistencies.
                    nargs = "*"

        metavar: str
        metavar = _strings.join_union_metavars(
            [option_spec.metavar for option_spec in option_specs],
        )

        def union_instantiator(strings: List[str]) -> Any:
            errors = []
            for i, option_spec in enumerate(option_specs):
                # Check choices.
                if option_spec.choices is not None and any(
                    x not in option_spec.choices for x in strings
                ):
                    errors.append(
                        f"{options[i]}: {strings} does not match choices {option_spec.choices}"
                    )
                    continue

                # Try passing input into instantiator.
                if len(strings) == option_spec.nargs or option_spec.nargs == "*":
                    try:
                        return option_spec.instance_from_str(strings)
                    except ValueError as e:
                        # Failed, try next instantiator.
                        errors.append(f"{options[i]}: {e.args[0]}")
                else:
                    errors.append(
                        f"{options[i]}: input length {len(strings)} did not match expected"
                        f" argument count {option_spec.nargs}"
                    )
            raise ValueError(
                f"no type in {options} could be instantiated from"
                f" {strings}.\n\nGot errors:  \n- " + "\n- ".join(errors)
            )

        def str_from_instance(instance: Any) -> List[str]:
            fuzzy_match = None
            for option_spec in option_specs:
                is_instance = option_spec.is_instance(instance)
                if is_instance is True:
                    return option_spec.str_from_instance(instance)
                elif is_instance == "~":
                    fuzzy_match = option_spec

            # If we get here, we have a fuzzy match.
            if fuzzy_match is not None:
                return fuzzy_match.str_from_instance(instance)

            assert False, f"could not match default value {instance} with any types in union {options}"

        return PrimitiveConstructorSpec(
            nargs=nargs,
            metavar=metavar,
            instance_from_str=union_instantiator,
            is_instance=lambda x: any(spec.is_instance(x) for spec in option_specs),
            str_from_instance=str_from_instance,
            choices=None if choices is None else tuple(set(choices)),
        )
