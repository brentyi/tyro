import dataclasses
import datetime
import enum
from typing import IO, Any, Optional, Set, Type, TypeVar, Union

import yaml
from typing_extensions import get_origin

from . import _resolver

ENUM_YAML_TAG_PREFIX = "!enum:"
DATACLASS_YAML_TAG_PREFIX = "!dataclass:"

DataclassType = TypeVar("DataclassType")


def _get_contained_special_types_from_instance(instance: Any) -> Set[Type]:
    """Takes an object and recursively searches its cihldren for dataclass or enum
    types."""
    if issubclass(type(instance), enum.Enum):
        return {type(instance)}
    elif not dataclasses.is_dataclass(instance):
        return set()

    out = {type(instance)}
    for v in vars(instance).values():
        out |= _get_contained_special_types_from_instance(v)
    return out


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

    cls, type_from_typevar = _resolver.resolve_generic_classes(cls)

    contained_dataclasses = {cls}

    def handle_type(typ) -> Set[Type]:
        if _resolver.is_dataclass(typ) and typ not in parent_contained_dataclasses:
            return _get_contained_special_types_from_type(
                typ,
                _parent_contained_dataclasses=contained_dataclasses
                | parent_contained_dataclasses,
            )
        elif type(typ) is enum.EnumMeta:
            return {typ}
        return set()

    # Handle generics.
    for typ in type_from_typevar.values():
        contained_dataclasses |= handle_type(typ)

    if cls in parent_contained_dataclasses:
        return contained_dataclasses

    # Handle fields.
    for field in _resolver.resolved_fields(cls):  # type: ignore
        contained_dataclasses |= handle_type(field.type)

    return contained_dataclasses


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
    assert len(set(contained_type_names)) == len(
        contained_type_names
    ), f"Contained dataclass type names must all be unique, but got {contained_type_names}"

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

    return DataclassLoader


def _make_dumper(instance: Any) -> Type[yaml.Dumper]:
    class DataclassDumper(yaml.Dumper):
        pass

    contained_types = list(_get_contained_special_types_from_instance(instance))
    contained_type_names = list(map(lambda cls: cls.__name__, contained_types))

    # Note: this is currently a stricter than necessary assert.
    assert len(set(contained_type_names)) == len(
        contained_type_names
    ), f"Contained dataclass/enum names must all be unique, but got {contained_type_names}"

    dumper: yaml.Dumper
    data: Any
    field: dataclasses.Field

    def make_representer(name: str):
        def representer(dumper, data):
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

        return representer

    for typ, name in zip(contained_types, contained_type_names):
        DataclassDumper.add_representer(typ, make_representer(name))
    return DataclassDumper


def from_yaml(
    cls: Type[DataclassType],
    stream: Union[str, IO[str], bytes, IO[bytes]],
) -> DataclassType:
    """Re-construct a dataclass instance from a yaml-compatible string, which should be
    generated from `dcargs.to_yaml()`."""
    out = yaml.load(stream, Loader=_make_loader(cls))
    origin_cls = get_origin(cls)
    assert isinstance(out, origin_cls if origin_cls is not None else cls)
    return out


def _timestamp() -> str:
    """Get a current timestamp as a string. Example format: `2021-11-05-15:46:32`."""
    return datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")


def to_yaml(instance: Any) -> str:
    """Serialize a dataclass; returns a yaml-compatible string that can be deserialized
    via `dcargs.from_yaml()`."""
    return f"# YAML generated via dcargs, at {_timestamp()}.\n" + yaml.dump(
        instance, Dumper=_make_dumper(instance)
    )
