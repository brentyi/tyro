from __future__ import annotations

import collections
import collections.abc
import dataclasses
import datetime
import enum
import inspect
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

from typing_extensions import Literal, get_args, get_origin

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

current_registry: PrimitiveConstructorRegistry | None = None


def get_active_primitive_registry() -> PrimitiveConstructorRegistry:
    global current_registry
    if current_registry is None:
        current_registry = PrimitiveConstructorRegistry()
    return current_registry


@dataclasses.dataclass(frozen=True)
class TypeInfo:
    static_type: TypeForm
    """Field type, with all runtime annotations (typing.Annotated) stripped."""
    static_type_origin: TypeForm | None
    """The output of get_origin() on the static type."""
    markers: set[_markers.Marker]
    """Set of tyro markers used to configure this field."""
    annotations: tuple[Any, ...]
    """All runtime annotations not included in `markers`."""
    source_registry: PrimitiveConstructorRegistry
    """The registry used to look up constructor specifications for this type."""

    @staticmethod
    def make(
        raw_annotation: TypeForm,
        parent_markers: set[_markers.Marker],
        source_registry: PrimitiveConstructorRegistry,
    ) -> TypeInfo:
        static_type, all_annotations = _resolver.unwrap_annotated(
            raw_annotation, search_type="all"
        )
        markers = set(a for a in all_annotations if isinstance(a, _markers._Marker))
        annotations = tuple(
            a for a in all_annotations if not isinstance(a, _markers._Marker)
        )
        return TypeInfo(
            static_type=static_type,
            static_type_origin=get_origin(static_type),
            markers=markers | parent_markers,
            annotations=annotations,
            source_registry=source_registry,
        )


@dataclasses.dataclass(frozen=True)
class PrimitiveConstructorSpec(Generic[T]):
    nargs: int | Literal["*"]
    metavar: str
    instance_from_str: Callable[[list[str]], T]
    is_instance: Callable[[Any], bool]
    str_from_instance: Callable[[T], list[str]]
    choices: tuple[str, ...] | None = None
    _action: Literal["append"] | None = None


SpecFactory = Callable[[TypeInfo], PrimitiveConstructorSpec]


class PrimitiveConstructorRegistry:
    def __init__(self):
        self._old_registry: PrimitiveConstructorRegistry | None = None
        self._rules: list[
            tuple[
                # Matching function.
                Callable[[TypeInfo], bool],
                # Spec factory.
                SpecFactory,
            ]
        ] = []

        # Apply the default primitive-handling rules.
        _apply_default_rules(self)

    def define_rule(
        self, matcher_fn: Callable[[TypeInfo], bool]
    ) -> Callable[[SpecFactory], SpecFactory]:
        def decorator(spec_factory: SpecFactory) -> SpecFactory:
            self._rules.append((matcher_fn, spec_factory))
            return spec_factory

        return decorator

    def get_spec(self, type_info: TypeInfo) -> PrimitiveConstructorSpec:
        """Get a constructor specification for a given type."""
        for matcher_fn, spec_factory in self._rules:
            if matcher_fn(type_info):
                return spec_factory(type_info)

        raise UnsupportedTypeAnnotationError(
            f"Unsupported type annotation: {type_info.static_type}"
        )

    def __enter__(self) -> PrimitiveConstructorRegistry:
        global current_registry
        self._old_registry = current_registry
        current_registry = self
        return self

    def __exit__(self, *args) -> None:
        global current_registry
        current_registry = self._old_registry


def _apply_default_rules(registry: PrimitiveConstructorRegistry) -> None:
    """Apply default rules to the registry."""

    @registry.define_rule(lambda type_info: type_info.static_type is Any)
    def any_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        raise UnsupportedTypeAnnotationError("`Any` is not a parsable type.")

    if "json" in sys.modules.keys():
        # HACK: this is for code that uses `tyro.conf.arg(constructor=json.loads)`.
        # We're going to deprecate this syntax (the constructor= argument in
        # tyro.conf.arg), but there is code that lives in the wild that relies
        # on the behavior so we'll do our best not to break it.
        import json

        vanilla_types = (int, str, float, bytes, json.loads)
    else:
        vanilla_types = (int, str, float, bytes)

    @registry.define_rule(lambda type_info: type_info.static_type in vanilla_types)
    def basics_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar=type_info.static_type.__name__.upper(),
            instance_from_str=lambda args: bytes(args[0], encoding="ascii")
            if type_info.static_type is bytes
            else type_info.static_type(args[0]),
            is_instance=lambda x: isinstance(x, type_info.static_type),
            str_from_instance=lambda instance: [str(instance)],
        )

    if "torch" in sys.modules.keys():
        import torch

        @registry.define_rule(lambda type_info: type_info.static_type is torch.device)
        def basics_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
            return PrimitiveConstructorSpec(
                nargs=1,
                metavar=type_info.static_type.__name__.upper(),
                instance_from_str=lambda args: torch.device(args[0]),
                is_instance=lambda x: isinstance(x, type_info.static_type),
                str_from_instance=lambda instance: [str(instance)],
            )

    @registry.define_rule(lambda type_info: type_info.static_type is bool)
    def bool_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        del type_info
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar="{True,False}",
            instance_from_str=lambda args: args[0] == "True",
            choices=("True", "False"),
            is_instance=lambda x: isinstance(x, bool),
            str_from_instance=lambda instance: ["True" if instance else "False"],
        )

    @registry.define_rule(lambda type_info: type_info.static_type is type(None))
    def nonetype_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        del type_info
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar="{None}",
            choices=("None",),
            instance_from_str=lambda args: None,
            is_instance=lambda x: x is None,
            str_from_instance=lambda instance: ["None"],
        )

    @registry.define_rule(
        lambda type_info: type_info.static_type in (os.PathLike, pathlib.Path)
        or (
            inspect.isclass(type_info.static_type)
            and issubclass(type_info.static_type, pathlib.PurePath)
        )
    )
    def path_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar=type_info.static_type.__name__.upper(),
            instance_from_str=lambda args: pathlib.Path(args[0]),
            is_instance=lambda x: hasattr(x, "__fspath__"),
            str_from_instance=lambda instance: [str(instance)],
        )

    @registry.define_rule(
        lambda type_info: inspect.isclass(type_info.static_type)
        and issubclass(type_info.static_type, enum.Enum)
    )
    def enum_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        cast_type = cast(Type[enum.Enum], type_info.static_type)
        if _markers.EnumChoicesFromValues in type_info.markers:
            choices = tuple(str(m.value) for m in cast_type)
        else:
            choices = tuple(type_info.static_type.__members__.keys())

        return PrimitiveConstructorSpec(
            nargs=1,
            metavar="{" + ",".join(choices) + "}",
            instance_from_str=lambda args: next(
                iter(member for member in cast_type if str(member.value) == args[0])
            )
            if _markers.EnumChoicesFromValues in type_info.markers
            else cast_type[args[0]],
            is_instance=lambda x: isinstance(x, cast_type),
            str_from_instance=lambda instance: [
                str(instance.value)
                if _markers.EnumChoicesFromValues in type_info.markers
                else instance.name
            ],
            choices=choices,
        )

    @registry.define_rule(
        lambda type_info: type_info.static_type
        in (datetime.datetime, datetime.date, datetime.time)
    )
    def datetime_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        return PrimitiveConstructorSpec(
            nargs=1,
            metavar={
                datetime.datetime: "YYYY-MM-DD[THH:MM:[SS[…]]]",
                datetime.date: "YYYY-MM-DD",
                datetime.time: "HH:MM[:SS[…]]",
            }[type_info.static_type],
            instance_from_str=lambda args: cast(
                Union[
                    Type[datetime.datetime], Type[datetime.date], Type[datetime.time]
                ],
                type_info.static_type,
            ).fromisoformat(args[0]),
            is_instance=lambda x: isinstance(x, type_info.static_type),
            str_from_instance=lambda instance: [instance.isoformat()],
        )

    @registry.define_rule(lambda type_info: type_info.static_type_origin is tuple)
    def tuple_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        types = get_args(type_info.static_type)
        typeset = set(types)  # Note that sets are unordered.
        typeset_no_ellipsis = typeset - {Ellipsis}  # type: ignore

        if typeset_no_ellipsis != typeset:
            # Ellipsis: variable argument counts. When an ellipsis is used, tuples must
            # contain only one type.
            assert len(typeset_no_ellipsis) == 1
            return sequence_rule(type_info)

        inner_specs = []
        total_nargs = 0
        for contained_type in types:
            spec = type_info.source_registry.get_spec(
                TypeInfo.make(
                    contained_type, type_info.markers, type_info.source_registry
                )
            )
            if isinstance(spec.nargs, int):
                total_nargs += spec.nargs
            else:
                raise UnsupportedTypeAnnotationError(
                    f"Tuple contains a variable-length sequence {contained_type}, which causes ambiguity when nested."
                    " For nesting variable-length sequences (example: List[List[int]]),"
                    " `tyro.conf.UseAppendAction` can help resolve ambiguities."
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

    @registry.define_rule(
        lambda type_info: type_info.static_type
        in (
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
        )
    )
    def vague_container_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        typ = type_info.static_type
        if typ in (dict, Dict):
            typ = Dict[str, str]
        elif typ in (tuple, Tuple):
            typ = Tuple[str, ...]  # type: ignore
        elif typ in (list, List, collections.abc.Sequence, Sequence):
            typ = List[str]
        elif typ in (set, Set):
            typ = Set[str]
        return type_info.source_registry.get_spec(
            TypeInfo.make(
                typ,
                parent_markers=type_info.markers,
                source_registry=type_info.source_registry,
            )
        )

    @registry.define_rule(
        lambda type_info: type_info.static_type_origin
        in (
            collections.abc.Sequence,
            frozenset,
            list,
            set,
            collections.deque,
        )
    )
    def sequence_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        container_type = type_info.static_type_origin
        assert container_type is not None
        if container_type is collections.abc.Sequence:
            container_type = list

        if container_type is tuple:
            (contained_type, ell) = get_args(type_info.static_type)
            assert ell == Ellipsis
        else:
            (contained_type,) = get_args(type_info.static_type)

        inner_spec = type_info.source_registry.get_spec(
            TypeInfo.make(
                raw_annotation=contained_type,
                parent_markers=type_info.markers - {_markers.UseAppendAction},
                source_registry=type_info.source_registry,
            )
        )
        if _markers.UseAppendAction in type_info.markers:

            def str_from_instance(instance: Sequence) -> list[str]:
                # TODO: this is not quite right.
                out = []
                for i in instance:
                    out.extend(inner_spec.str_from_instance(i))
                return out

            return PrimitiveConstructorSpec(
                nargs=inner_spec.nargs,
                metavar=inner_spec.metavar,
                choices=inner_spec.choices,
                instance_from_str=lambda args: cast(
                    Callable, type_info.static_type_origin
                )(inner_spec.instance_from_str(a) for a in cast(List[List[str]], args)),
                is_instance=lambda x: isinstance(x, container_type)
                and all(inner_spec.is_instance(i) for i in x),
                str_from_instance=str_from_instance,
                _action="append",
            )

        if not isinstance(inner_spec.nargs, int):
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
            return container_type(out)

        def str_from_instance(instance: Sequence) -> list[str]:
            out = []
            for i in instance:
                out.extend(inner_spec.str_from_instance(i))
            return out

        return PrimitiveConstructorSpec(
            nargs="*",
            metavar=_strings.multi_metavar_from_single(inner_spec.metavar),
            instance_from_str=instance_from_str,
            is_instance=lambda x: isinstance(x, container_type)
            and all(inner_spec.is_instance(i) for i in x),
            str_from_instance=str_from_instance,
            choices=inner_spec.choices,
        )

    @registry.define_rule(
        lambda type_info: type_info.static_type_origin
        in (dict, collections.abc.Mapping)
    )
    def dict_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        key_type, val_type = get_args(type_info.static_type)
        key_spec = type_info.source_registry.get_spec(
            TypeInfo.make(
                raw_annotation=key_type,
                parent_markers=type_info.markers,
                source_registry=type_info.source_registry,
            )
        )
        val_spec = type_info.source_registry.get_spec(
            TypeInfo.make(
                raw_annotation=val_type,
                parent_markers=type_info.markers - {_markers.UseAppendAction},
                source_registry=type_info.source_registry,
            )
        )
        pair_metavar = f"{key_spec.metavar} {val_spec.metavar}"

        if not isinstance(key_spec.nargs, int):
            raise UnsupportedTypeAnnotationError(
                "Dictionary keys must have a fixed number of arguments."
            )

        if _markers.UseAppendAction in type_info.markers:

            def instance_from_str(args: list[str]) -> dict:
                # Our types are currently broken for the append actions.
                args_cast = cast(List[List[str]], args)

                key_nargs = key_spec.nargs
                out = {}
                for s in args_cast:
                    out[key_spec.instance_from_str(s[:key_nargs])] = (
                        val_spec.instance_from_str(s[key_nargs:])
                    )
                return out

            def str_from_instance(instance: dict) -> list[str]:
                out = []
                for key, value in instance.items():
                    out.extend(key_spec.str_from_instance(key))
                    out.extend(val_spec.str_from_instance(value))
                return out

            return PrimitiveConstructorSpec(
                nargs=key_spec.nargs + val_spec.nargs
                if isinstance(val_spec.nargs, int)
                else "*",
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
            if not isinstance(val_spec.nargs, int):
                raise UnsupportedTypeAnnotationError(
                    "Dictionary values must have a fixed number of arguments."
                )

            def instance_from_str(args: list[str]) -> dict:
                out = {}
                key_nargs = key_spec.nargs
                val_nargs = val_spec.nargs
                assert isinstance(key_nargs, int)
                assert isinstance(val_nargs, int)

                pair_nargs = key_nargs + val_nargs
                if len(args) % pair_nargs != 0:
                    raise ValueError("Incomplete set of key-value pairs!")

                for i in range(0, len(args), pair_nargs):
                    key = key_spec.instance_from_str(args[i : i + key_nargs])
                    value = val_spec.instance_from_str(
                        args[i + key_nargs : i + pair_nargs]
                    )
                    out[key] = value
                return out

            def str_from_instance(instance: dict) -> list[str]:
                out = []
                for key, value in instance.items():
                    out.extend(key_spec.str_from_instance(key))
                    out.extend(val_spec.str_from_instance(value))
                return out

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

    @registry.define_rule(
        lambda type_info: type_info.static_type_origin in (Literal, LiteralAlternate)
    )
    def literal_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        choices = get_args(type_info.static_type)
        str_choices = tuple(
            (x.value if _markers.EnumChoicesFromValues in type_info.markers else x.name)
            if isinstance(x, enum.Enum)
            else str(x)
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

    @registry.define_rule(
        lambda type_info: type_info.static_type_origin in (Union, _resolver.UnionType)
    )
    def union_rule(type_info: TypeInfo) -> PrimitiveConstructorSpec:
        options = list(get_args(type_info.static_type))
        if type(None) in options:
            # Move `None` types to the beginning.
            # If we have `Optional[str]`, we want this to be parsed as
            # `Union[NoneType, str]`.
            options.remove(type(None))
            options.insert(0, type(None))

        # General unions, eg Union[int, bool]. We'll try to convert these from left to
        # right.
        option_specs = []
        choices: tuple[str, ...] | None = ()
        nargs: None | int | Literal["*"] = 1
        first = True
        for t in options:
            option_spec = type_info.source_registry.get_spec(
                TypeInfo.make(
                    raw_annotation=t,
                    parent_markers=type_info.markers,
                    source_registry=type_info.source_registry,
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
            for option_spec in option_specs:
                if option_spec.is_instance(instance):
                    return option_spec.str_from_instance(instance)
            raise ValueError(f"instance {instance} is not in {options}")

        return PrimitiveConstructorSpec(
            nargs=nargs,
            metavar=metavar,
            instance_from_str=union_instantiator,
            is_instance=lambda x: any(spec.is_instance(x) for spec in option_specs),
            str_from_instance=str_from_instance,
            choices=None if choices is None else tuple(set(choices)),
        )


# @registry.define_rule(lambda type_info: type_info.static_type is tuple)
# def tuple_spec_factory(type_info: TypeInfo[T]) -> PrimitiveConstructorSpec[T]:
#     return PrimitiveConstructorSpec[T](
#         nargs=len(type_form),
#         metavar=" ".join(type_form),
#         instance_from_str=lambda args: tuple(args),
#         str_from_instance=lambda instance: list(instance),
#     )


#
#     def __init_subclass__(cls, metavar: str, nargs: int | Literal["*"]):
#         cls.metavar = metavar
#         cls.nargs = nargs
#         return super().__init_subclass__()
#
#     @abc.abstractmethod
#     def instance_from_str(self, anno: type[T], args: list[str]) -> T:
#         """Convert a list of strings to an instance. The length of the list will
#         match the value of `nargs`."""
#
#     @abc.abstractmethod
#     def str_from_instance(self, anno: type[T], instance: T) -> list[str]:
#         """Convert an instance to a list of strings. This is used for generating
#         usage messages when a default value is provided."""


# class StructConstructorSpec(Generic[T]):
#     def __init__(
#         self,
#         constructor_factory: Callable[
#             [TypeForm[T], T], tuple[Callable[..., T], list[FieldSpec]]
#         ],
#     ):
#         """Specification for instantiating struct types. Struct types are
#         unpacked into fields; each field can then be either a nested struct
#         type or a primitive type."""
#         self._constructor_factory = constructor_factory
#
#
# @dataclasses.dataclass(frozen=True)
# class FieldSpec:
#     name: str
#     type_or_callable: TypeForm[Any] | Callable
#     default: Any
#     default_source: Literal["field", "overridden"]
#     """Whether the default value was provided by the field or overridden by the parent."""
#
#     helptext: str | None
