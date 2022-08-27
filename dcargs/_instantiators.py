"""Helper for using type annotations to recursively generate instantiator functions,
which map sequences of strings to the annotated type.

Some examples of type annotations and the desired instantiators:
```
    int

        lambda strings: int(str[0])

    List[int]

        lambda strings: list(
            [int(x) for x in strings]
        )

    List[Color], where Color is an enum

        lambda strings: list(
            [Color[x] for x in strings]
        )

    Tuple[int, float]

        lambda strings: tuple(
            [
                typ(x)
                for typ, x in zip(
                    (int, float),
                    strings,
                )
            ]
        )
```
"""
import collections.abc
import dataclasses
import enum
import inspect
from collections import deque
from typing import (
    Any,
    Callable,
    Dict,
    Hashable,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import Annotated, Final, Literal, get_args, get_origin

from . import _strings

_StandardInstantiator = Callable[[List[str]], Any]
# Special case: the only time that argparse doesn't give us a string is when the
# argument action is set to `store_true` or `store_false`. In this case, we get
# a bool directly, and the field action can be a no-op.
_FlagInstantiator = Callable[[bool], bool]

Instantiator = Union[_StandardInstantiator, _FlagInstantiator]

NoneType = type(None)


@dataclasses.dataclass
class InstantiatorMetadata:
    # Unlike in vanilla argparse, we never set nargs to None. To make things simpler, we
    # instead use nargs=1.
    nargs: Union[int, Literal["+"]]
    # Unlike in vanilla argparse, our metavar is always a string. We handle
    # sequences, multiple arguments, etc, manually.
    metavar: str
    choices: Optional[Tuple[str, ...]]

    def check_choices(self, strings: List[str]) -> None:
        if self.choices is not None and any(s not in self.choices for s in strings):
            raise ValueError(f"invalid choice: {strings} (choose from {self.choices}))")


class UnsupportedTypeAnnotationError(Exception):
    """Exception raised when an unsupported type annotation is detected."""


_builtin_set = set(
    filter(
        lambda x: isinstance(x, Hashable),  # type: ignore
        __builtins__.values(),  # type: ignore
    )
)


def instantiator_from_type(
    typ: Type, type_from_typevar: Dict[TypeVar, Type]
) -> Tuple[Instantiator, InstantiatorMetadata]:
    """Recursive helper for parsing type annotations.

    Returns two things:
    - An instantiator function, for instantiating the type from a string or list of
      strings. The latter applies when argparse's `nargs` parameter is set.
    - A metadata structure, which specifies parameters for argparse.
    """

    # Resolve typevars.
    if typ in type_from_typevar:
        return instantiator_from_type(
            type_from_typevar[typ],  # type: ignore
            type_from_typevar,
        )

    # Handle Any.
    if typ is Any:
        raise UnsupportedTypeAnnotationError("`Any` is not a parsable type.")

    # Handle NoneType.
    if typ is NoneType:

        def instantiator(strings: List[str]) -> None:
            # Note that other inputs should be caught by `choices` before the
            # instantiator runs.
            assert strings == ["None"]
            return None

        return instantiator, InstantiatorMetadata(
            nargs=1,
            metavar="{" + _strings.format_metavar("None") + "}",
            choices=("None",),
        )

    # Address container types. If a matching container is found, this will recursively
    # call instantiator_from_type().
    container_out = _instantiator_from_container_type(typ, type_from_typevar)
    if container_out is not None:
        return container_out

    # Validate that typ is a `(arg: str) -> T` type converter, as expected by argparse.
    if typ in _builtin_set:
        pass
    elif not callable(typ):
        raise UnsupportedTypeAnnotationError(
            f"Expected {typ} to be an `(arg: str) -> T` type converter, but is not"
            " callable."
        )
    else:
        param_count = 0
        has_var_positional = False
        try:
            signature = inspect.signature(typ)
        except ValueError:
            # No signature, this is often the case with pybind, etc.
            signature = None

        if signature is not None:
            # Some checks we can do if the signature is available!
            for i, param in enumerate(signature.parameters.values()):
                if i == 0 and param.annotation not in (str, inspect.Parameter.empty):
                    raise UnsupportedTypeAnnotationError(
                        f"Expected {typ} to be an `(arg: str) -> T` type converter, but"
                        f" got {signature}. You may have a nested type in a container,"
                        " which is unsupported."
                    )
                if param.kind is inspect.Parameter.VAR_POSITIONAL:
                    has_var_positional = True
                elif param.default is inspect.Parameter.empty and param.kind is not (
                    inspect.Parameter.VAR_KEYWORD
                ):
                    param_count += 1

            # Raise an error if parameters look wrong.
            if not (param_count == 1 or (param_count == 0 and has_var_positional)):
                raise UnsupportedTypeAnnotationError(
                    f"Expected {typ} to be an `(arg: str) -> T` type converter, but got"
                    f" {signature}. You may have a nested type in a container, which is"
                    " unsupported."
                )

    # Special case `choices` for some types, as implemented in `instance_from_string()`.
    auto_choices: Optional[Tuple[str, ...]] = None
    if typ is bool:
        auto_choices = ("True", "False")
    elif isinstance(typ, type) and issubclass(typ, enum.Enum):
        auto_choices = tuple(x.name for x in typ)

    def instantiator_base_case(strings: List[str]) -> Any:
        """Given a type and and a string from the command-line, reconstruct an object. Not
        intended to deal with containers.

        This is intended to replace all calls to `type(string)`, which can cause unexpected
        behavior. As an example, note that the following argparse code will always print
        `True`, because `bool("True") == bool("False") == bool("0") == True`.
        ```
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--flag", type=bool)

        print(parser.parse_args().flag)
        ```
        """
        assert len(get_args(typ)) == 0, f"Type {typ} cannot be instantiated."
        (string,) = strings
        if typ is bool:
            return {"True": True, "False": False}[string]  # type: ignore
        elif isinstance(typ, type) and issubclass(typ, enum.Enum):
            return typ[string]  # type: ignore
        elif typ is bytes:
            return bytes(string, encoding="ascii")  # type: ignore
        else:
            return typ(string)  # type: ignore

    return instantiator_base_case, InstantiatorMetadata(
        nargs=1,
        metavar=_strings.format_metavar(typ.__name__.upper())
        if auto_choices is None
        else "{" + ",".join(map(_strings.format_metavar, map(str, auto_choices))) + "}",
        choices=auto_choices,
    )


@overload
def _instantiator_from_type_inner(
    typ: Type,
    type_from_typevar: Dict[TypeVar, Type],
    allow_sequences: Literal["fixed_length"],
) -> Tuple[Instantiator, InstantiatorMetadata]:
    ...


@overload
def _instantiator_from_type_inner(
    typ: Type,
    type_from_typevar: Dict[TypeVar, Type],
    allow_sequences: Literal[False],
) -> Tuple[_StandardInstantiator, InstantiatorMetadata]:
    ...


@overload
def _instantiator_from_type_inner(
    typ: Type,
    type_from_typevar: Dict[TypeVar, Type],
    allow_sequences: Literal[True],
) -> Tuple[Instantiator, InstantiatorMetadata]:
    ...


def _instantiator_from_type_inner(
    typ: Type,
    type_from_typevar: Dict[TypeVar, Type],
    allow_sequences: Literal["fixed_length", True, False],
) -> Tuple[Instantiator, InstantiatorMetadata]:
    """Thin wrapper over instantiator_from_type, with some extra asserts for catching
    errors."""
    out = instantiator_from_type(typ, type_from_typevar)
    if out[1].nargs is not None:
        # We currently only use allow_sequences=False for options in Literal types,
        # which are evaluated using `type()`. It should not be possible to hit this
        # condition from polling a runtime type.
        assert allow_sequences
        if allow_sequences == "fixed_length" and not isinstance(out[1].nargs, int):
            raise UnsupportedTypeAnnotationError(
                f"Found an unsupported (variable-length) nested sequence of type {typ}."
            )
    return out


def _instantiator_from_container_type(
    typ: Type, type_from_typevar: Dict[TypeVar, Type]
) -> Optional[Tuple[Instantiator, InstantiatorMetadata]]:
    """Attempt to create an instantiator from a container type. Returns `None` is no
    container type is found."""

    type_origin = get_origin(typ)
    if type_origin is None:
        return None

    # Unwrap Annotated and Final types.
    if type_origin in (Annotated, Final):
        contained_type = get_args(typ)[0]
        return instantiator_from_type(contained_type, type_from_typevar)

    for make, matched_origins in {
        _instantiator_from_sequence: (
            collections.abc.Sequence,
            frozenset,
            list,
            set,
            deque,
        ),
        _instantiator_from_tuple: (tuple,),
        _instantiator_from_dict: (dict, collections.abc.Mapping),
        _instantiator_from_union: (Union,),
        _instantiator_from_literal: (Literal,),
    }.items():
        if type_origin in matched_origins:
            return make(typ, type_from_typevar)

    raise UnsupportedTypeAnnotationError(  # pragma: no cover
        f"Unsupported type {typ} with origin {type_origin}"
    )


def _instantiator_from_tuple(
    typ: Type, type_from_typevar: Dict[TypeVar, Type]
) -> Tuple[Instantiator, InstantiatorMetadata]:
    types = get_args(typ)
    typeset = set(types)  # Note that sets are unordered.
    typeset_no_ellipsis = typeset - {Ellipsis}  # type: ignore

    if typeset_no_ellipsis != typeset:
        # Ellipsis: variable argument counts. When an ellipsis is used, tuples must
        # contain only one type.
        assert len(typeset_no_ellipsis) == 1
        return _instantiator_from_sequence(typ, type_from_typevar)

    else:
        instantiators: List[_StandardInstantiator] = []
        metas: List[InstantiatorMetadata] = []
        nargs = 0
        for t in types:
            a, b = _instantiator_from_type_inner(
                t,
                type_from_typevar,
                allow_sequences="fixed_length",
            )
            instantiators.append(a)  # type: ignore
            metas.append(b)
            assert isinstance(b.nargs, int)
            nargs += b.nargs

        def fixed_length_tuple_instantiator(strings: List[str]) -> Any:
            assert len(strings) == nargs

            # Make tuple.
            out = []
            i = 0
            for make, meta in zip(instantiators, metas):
                assert isinstance(meta.nargs, int)
                meta.check_choices(strings[i : i + meta.nargs])
                out.append(make(strings[i : i + meta.nargs]))
                i += meta.nargs
            return tuple(out)

        return fixed_length_tuple_instantiator, InstantiatorMetadata(
            nargs=nargs,
            metavar=" ".join(m.metavar for m in metas),
            choices=None,
        )


def _join_union_metavars(metavars: Iterable[str]) -> str:
    """Metavar generation helper for unions. Could be revisited.

    Examples:
        None, INT => NONE|INT
        {0,1,2}, {3,4} => {0,1,2,3,4}
        {0,1,2}, {3,4}, STR => {0,1,2,3,4}|STR
        {None}, INT [INT ...] => {None}|{INT [INT ...]}
        STR, INT [INT ...] => STR|{INT [INT ...]}
        STR, INT INT => STR|{INT INT}

    The curly brackets are unfortunately overloaded but alternatives all interfere with
    argparse internals.
    """
    metavars = tuple(metavars)
    merged_metavars = [metavars[0]]
    for i in range(1, len(metavars)):
        prev = merged_metavars[-1]
        curr = metavars[i]
        if (
            prev.startswith("{")
            and prev.endswith("}")
            and curr.startswith("{")
            and curr.endswith("}")
        ):
            merged_metavars[-1] = prev[:-1] + "," + curr[1:]
        else:
            merged_metavars.append(curr)

    for i, m in enumerate(merged_metavars):
        if " " in m:
            merged_metavars[i] = "{" + m + "}"

    return "|".join(merged_metavars)


def _instantiator_from_union(
    typ: Type, type_from_typevar: Dict[TypeVar, Type]
) -> Tuple[Instantiator, InstantiatorMetadata]:
    options = list(get_args(typ))
    if NoneType in options:
        # Move `None` types to the beginning.
        # If we have `Optional[str]`, we want this to be parsed as
        # `Union[NoneType, str]`.
        options.remove(NoneType)
        options.insert(0, NoneType)

    # General unions, eg Union[int, bool]. We'll try to convert these from left to
    # right.
    instantiators = []
    metas = []
    nargs: Union[int, Literal["+"]] = 1
    first = True
    for t in options:
        a, b = _instantiator_from_type_inner(
            t,
            type_from_typevar,
            allow_sequences=True,
        )
        instantiators.append(a)
        metas.append(b)

        if t is not NoneType:
            # Enforce that `nargs` is the same for all child types, except for
            # NoneType.
            if first:
                nargs = b.nargs
                first = False
            elif nargs != b.nargs:
                # Just be as general as possible if we see inconsistencies.
                nargs = "+"

    metavar: str
    metavar = _join_union_metavars(map(lambda x: cast(str, x.metavar), metas))

    def union_instantiator(strings: List[str]) -> Any:
        metadata: InstantiatorMetadata
        errors = []
        for i, (instantiator, metadata) in enumerate(zip(instantiators, metas)):
            # Check choices.
            if metadata.choices is not None and any(
                x not in metadata.choices for x in strings
            ):
                errors.append(
                    f"{options[i]}: {strings} does not match choices {metadata.choices}"
                )
                continue

            # Try passing input into instantiator.
            if len(strings) == metadata.nargs or (metadata.nargs == "+"):
                try:
                    return instantiator(strings)  # type: ignore
                except ValueError as e:
                    # Failed, try next instantiator.
                    errors.append(f"{options[i]}: {e.args[0]}")
            else:
                errors.append(
                    f"{options[i]}: input length {len(strings)} did not match expected"
                    f" argument count {metadata.nargs}"
                )
        raise ValueError(
            f"no type in {options} could be instantiated from"
            f" {strings}.\n\nGot errors:  \n- " + "\n- ".join(errors)
        )

    return union_instantiator, InstantiatorMetadata(
        nargs=nargs,
        metavar=metavar,
        choices=None,
    )


def _instantiator_from_dict(
    typ: Type, type_from_typevar: Dict[TypeVar, Type]
) -> Tuple[Instantiator, InstantiatorMetadata]:
    key_type, val_type = get_args(typ)
    key_instantiator, key_meta = _instantiator_from_type_inner(
        key_type,
        type_from_typevar,
        allow_sequences="fixed_length",
    )
    val_instantiator, val_meta = _instantiator_from_type_inner(
        val_type,
        type_from_typevar,
        allow_sequences="fixed_length",
    )

    key_nargs = cast(int, key_meta.nargs)  # Casts needed for mypy but not pyright!
    val_nargs = cast(int, val_meta.nargs)
    assert isinstance(key_nargs, int)
    assert isinstance(val_nargs, int)
    pair_nargs = key_nargs + val_nargs

    def dict_instantiator(strings: List[str]) -> Any:
        out = {}
        if len(strings) % pair_nargs != 0:
            raise ValueError("incomplete set of key value pairs!")

        index = 0
        for _ in range(len(strings) // pair_nargs):
            k = strings[index : index + key_nargs]
            index += key_nargs
            v = strings[index : index + val_nargs]
            index += val_nargs

            if key_meta.choices is not None and any(
                kj not in key_meta.choices for kj in k
            ):
                raise ValueError(
                    f"invalid choice: {k} (choose from {key_meta.choices}))"
                )
            if val_meta.choices is not None and any(
                vj not in val_meta.choices for vj in v
            ):
                raise ValueError(
                    f"invalid choice: {v} (choose from {val_meta.choices}))"
                )
            out[key_instantiator(k)] = val_instantiator(v)  # type: ignore
        return out

    pair_metavar = f"{key_meta.metavar} {val_meta.metavar}"
    return dict_instantiator, InstantiatorMetadata(
        nargs="+",
        metavar=_strings.multi_metavar_from_single(pair_metavar),
        choices=None,
    )


def _instantiator_from_sequence(
    typ: Type, type_from_typevar: Dict[TypeVar, Type]
) -> Tuple[Instantiator, InstantiatorMetadata]:
    """Instantiator for variable-length sequences: list, sets, Tuple[T, ...], etc."""
    container_type = get_origin(typ)
    if container_type is collections.abc.Sequence:
        container_type = list

    if container_type is tuple:
        (contained_type, ell) = get_args(typ)
        assert ell == Ellipsis
    else:
        (contained_type,) = get_args(typ)

    make, inner_meta = _instantiator_from_type_inner(
        contained_type,
        type_from_typevar,
        allow_sequences="fixed_length",
    )

    def sequence_instantiator(strings: List[str]) -> Any:
        # Validate nargs.
        assert type(inner_meta.nargs) in (int, NoneType)
        if isinstance(inner_meta.nargs, int) and len(strings) % inner_meta.nargs != 0:
            raise ValueError(
                f"input {strings} is of length {len(strings)}, which is not divisible"
                f" by {inner_meta.nargs}."
            )

        # Make tuple.
        out = []
        step = inner_meta.nargs if isinstance(inner_meta.nargs, int) else 1
        for i in range(0, len(strings), step):
            out.append(make(strings[i : i + inner_meta.nargs]))  # type: ignore
        assert container_type is not None
        return container_type(out)

    return sequence_instantiator, InstantiatorMetadata(
        nargs="+",
        metavar=_strings.multi_metavar_from_single(inner_meta.metavar),
        choices=inner_meta.choices,
    )


def _instantiator_from_literal(
    typ: Type, type_from_typevar: Dict[TypeVar, Type]
) -> Tuple[Instantiator, InstantiatorMetadata]:
    choices = get_args(typ)
    str_choices = tuple(x.name if isinstance(x, enum.Enum) else str(x) for x in choices)
    return (
        # Note that if string is not in str_choices, it will be caught from setting
        # `choices` below.
        lambda strings: choices[str_choices.index(strings[0])],
        InstantiatorMetadata(
            nargs=1,
            metavar="{" + ",".join(map(_strings.format_metavar, str_choices)) + "}",
            choices=str_choices,
        ),
    )
