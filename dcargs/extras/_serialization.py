"""Type-safe, human-readable serialization helpers for dataclasses."""

import dataclasses
import enum
import functools
from typing import IO, Any, Optional, Set, Type, TypeVar, Union

import yaml
from typing_extensions import get_args, get_origin

from .. import _fields, _resolver

ENUM_YAML_TAG_PREFIX = "!enum:"
DATACLASS_YAML_TAG_PREFIX = "!dataclass:"
MISSING_YAML_TAG_PREFIX = "!missing"

DataclassType = TypeVar("DataclassType")


def _get_contained_special_types_from_type(
    cls: Type,
    _parent_contained_dataclasses: Optional[Set[Type]] = None,
) -> Set[Type]:
    """Takes a dataclass type, and recursively searches its fields for dataclass or enum
    types."""
    assert _resolver.is_dataclass(cls)
    parent_contained_dataclasses = (
        set()
        if _parent_contained_dataclasses is None
        else _parent_contained_dataclasses
    )

    cls, _ = _resolver.unwrap_annotated(cls)
    cls, type_from_typevar = _resolver.resolve_generic_types(cls)

    contained_special_types = {cls}

    def handle_type(typ: Type) -> Set[Type]:
        # Handle dataclasses.
        if _resolver.is_dataclass(typ) and typ not in parent_contained_dataclasses:
            return _get_contained_special_types_from_type(
                typ,
                _parent_contained_dataclasses=contained_special_types
                | parent_contained_dataclasses,
            )

        # Handle enums.
        elif type(typ) is enum.EnumMeta:
            return {typ}

        # Handle Union, Annotated, List, etc. No-op when there are no args.
        return functools.reduce(set.union, map(handle_type, get_args(typ)), set())

    # Handle generics.
    for typ in type_from_typevar.values():
        contained_special_types |= handle_type(typ)

    if cls in parent_contained_dataclasses:
        return contained_special_types

    # Handle fields.
    for field in _resolver.resolved_fields(cls):  # type: ignore
        contained_special_types |= handle_type(field.type)

    # Handle subclasses.
    for subclass in cls.__subclasses__():
        contained_special_types |= handle_type(subclass)

    return contained_special_types


def _make_loader(cls: Type) -> Type[yaml.Loader]:
    class DataclassLoader(yaml.Loader):
        pass

    # Design Q: do we want to support multiple dataclass types with the same name?
    # - Why yes: rudimentary support for this is easy.
    # - Why no: might cause confusing error messages? Using all possible context cues
    # for this is also hard.
    #
    # => let's just keep things simple, assert uniqueness for now. Easier to add new
    # features later than remove them.

    contained_types = list(_get_contained_special_types_from_type(cls))
    contained_type_names = list(map(lambda cls: cls.__name__, contained_types))
    assert len(set(contained_type_names)) == len(contained_type_names), (
        "Contained dataclass type names must all be unique, but got"
        f" {contained_type_names}"
    )

    loader: yaml.Loader
    node: yaml.Node

    def make_dataclass_constructor(typ: Type):
        return lambda loader, node: typ(**loader.construct_mapping(node))

    def make_enum_constructor(typ: Type):
        return lambda loader, node: typ[loader.construct_python_str(node)]

    for typ, name in zip(contained_types, contained_type_names):
        if dataclasses.is_dataclass(typ):
            DataclassLoader.add_constructor(
                tag=DATACLASS_YAML_TAG_PREFIX + name,
                constructor=make_dataclass_constructor(typ),
            )
        elif issubclass(typ, enum.Enum):
            DataclassLoader.add_constructor(
                tag=ENUM_YAML_TAG_PREFIX + name,
                constructor=make_enum_constructor(typ),
            )
        else:
            assert False

    DataclassLoader.add_constructor(
        tag=MISSING_YAML_TAG_PREFIX,
        constructor=lambda *_unused: _fields.MISSING_PROP,  # type: ignore
    )

    return DataclassLoader


def _make_dumper(instance: Any) -> Type[yaml.Dumper]:
    class DataclassDumper(yaml.Dumper):
        def ignore_aliases(self, data):
            return super().ignore_aliases(data) or data is _fields.MISSING_PROP

    contained_types = list(_get_contained_special_types_from_type(type(instance)))
    contained_type_names = list(map(lambda cls: cls.__name__, contained_types))

    # Note: this is currently a stricter than necessary assert.
    assert len(set(contained_type_names)) == len(contained_type_names), (
        "Contained dataclass/enum names must all be unique, but got"
        f" {contained_type_names}"
    )

    dumper: yaml.Dumper
    data: Any
    field: dataclasses.Field

    def make_representer(name: str):
        def representer(dumper: DataclassDumper, data: Any) -> yaml.Node:
            if dataclasses.is_dataclass(data):
                return dumper.represent_mapping(
                    tag=DATACLASS_YAML_TAG_PREFIX + name,
                    mapping={
                        field.name: getattr(data, field.name)
                        for field in dataclasses.fields(data)
                        if field.init
                    },
                )
            elif isinstance(data, enum.Enum):
                return dumper.represent_scalar(
                    tag=ENUM_YAML_TAG_PREFIX + name, value=data.name
                )
            assert False

        return representer

    for typ, name in zip(contained_types, contained_type_names):
        DataclassDumper.add_representer(typ, make_representer(name))

    DataclassDumper.add_representer(
        type(_fields.MISSING_PROP),
        lambda dumper, data: dumper.represent_scalar(
            tag=MISSING_YAML_TAG_PREFIX, value=""
        ),
    )
    return DataclassDumper


def from_yaml(
    cls: Type[DataclassType],
    stream: Union[str, IO[str], bytes, IO[bytes]],
) -> DataclassType:
    """Re-construct a dataclass instance from a yaml-compatible string, which should be
    generated from `dcargs.extras.to_yaml()`.

    As a secondary feature aimed at enabling the use of :func:`dcargs.cli` for general
    configuration use cases, we also introduce functions for human-readable dataclass
    serialization: :func:`dcargs.conf.from_yaml` and :func:`dcargs.conf.to_yaml` attempt
    to strike a balance between flexibility and robustness — in contrast to naively
    dumping or loading dataclass instances (via pickle, PyYAML, etc), explicit type
    references enable custom tags that are robust against code reorganization and
    refactor, while a PyYAML backend enables serialization of arbitrary Python objects.

    .. warning::
        Serialization functionality is stable but deprecated. It may be removed in a
        future version of :code:`dcargs`.

    Args:
        cls: Type to reconstruct.
        stream: YAML to read from.

    Returns:
        Instantiated dataclass.
    """
    out = yaml.load(stream, Loader=_make_loader(cls))
    origin_cls = get_origin(cls)
    assert isinstance(out, origin_cls if origin_cls is not None else cls)
    return out


def to_yaml(instance: Any) -> str:
    """Serialize a dataclass; returns a yaml-compatible string that can be deserialized
    via `dcargs.extras.from_yaml()`.

    As a secondary feature aimed at enabling the use of :func:`dcargs.cli` for general
    configuration use cases, we also introduce functions for human-readable dataclass
    serialization: :func:`dcargs.conf.from_yaml` and :func:`dcargs.conf.to_yaml` attempt
    to strike a balance between flexibility and robustness — in contrast to naively
    dumping or loading dataclass instances (via pickle, PyYAML, etc), explicit type
    references enable custom tags that are robust against code reorganization and
    refactor, while a PyYAML backend enables serialization of arbitrary Python objects.

    .. warning::
        Serialization functionality is stable but deprecated. It may be removed in a
        future version of :code:`dcargs`.

    Args:
        instance: Dataclass instance to serialize.

    Returns:
        YAML string.
    """
    return "# dcargs YAML.\n" + yaml.dump(instance, Dumper=_make_dumper(instance))
