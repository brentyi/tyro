"""Interface for generating `argparse.ArgumentParser()` definitions from callables."""

from __future__ import annotations

import warnings
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from typing_extensions import Annotated, get_args, get_origin

from tyro.constructors._registry import ConstructorRegistry
from tyro.constructors._struct_spec import (
    InvalidDefaultInstanceError,
    UnsupportedStructTypeMessage,
)

from . import (
    _arguments,
    _docstrings,
    _fields,
    _resolver,
    _singleton,
    _strings,
    _subcommand_matching,
    _unsafe_cache,
)
from . import _fmtlib as fmt
from ._record import Record
from ._typing_compat import is_typing_union
from .conf import _confstruct, _markers
from .constructors._primitive_spec import (
    PrimitiveConstructorSpec,
    UnsupportedTypeAnnotationError,
)

T = TypeVar("T")


class LazyParserSpecification:
    """Lazy wrapper that defers full ParserSpecification creation until needed.

    Computes lightweight metadata (description) for fast help text generation,
    while deferring expensive parser construction until actually needed.
    """

    def __init__(
        self,
        description_factory: Callable[[], str],
        factory: Callable[[], ParserSpecification],
    ) -> None:
        self._description_factory = description_factory
        self._description: str | None = None

        # Factory for creating the full parser when needed.
        self._factory = factory
        self._cached: ParserSpecification | None = None

    @property
    def description(self) -> str:
        """Lightweight field needed for tyro help formatting."""
        if self._description is None:
            self._description = self._description_factory()
        return self._description

    def evaluate(self) -> ParserSpecification:
        """Get the full ParserSpecification, creating it if needed."""
        if self._cached is None:
            self._cached = self._factory()
        return self._cached


class ArgWithContext(Record):
    _fields = ("arg", "source_parser", "local_root_parser")

    def __init__(
        self,
        arg: _arguments.ArgumentDefinition,
        source_parser: ParserSpecification,
        local_root_parser: ParserSpecification,
    ) -> None:
        self.arg = arg
        self.source_parser = source_parser
        """ParserSpecification that directly contains this argument."""
        self.local_root_parser = local_root_parser
        """Furthest ancestor of `source_parser` within the same (sub)command."""


class ParserSpecification(Record):
    """Each parser contains a list of arguments and optionally some subparsers."""

    _description: str | None = None

    _fields = (
        "f",
        "markers",
        "_lazy_description",
        "args",
        "field_list",
        "child_from_prefix",
        "helptext_from_intern_prefixed_field_name",
        "subparsers_from_intern_prefix",
        "intern_prefix",
        "extern_prefix",
        "has_required_args",
        "subparser_parent",
        "prog_suffix",
    )

    def __init__(
        self,
        f: Callable,
        markers: frozenset[_markers._Marker],
        description: str | Callable[[], str | None] | None,
        args: List[_arguments.ArgumentDefinition],
        field_list: List[_fields.FieldDefinition],
        child_from_prefix: Dict[str, ParserSpecification],
        helptext_from_intern_prefixed_field_name: Dict[
            str, str | Callable[[], str | None] | None
        ],
        subparsers_from_intern_prefix: Dict[str, SubparsersSpecification],
        intern_prefix: str,
        extern_prefix: str,
        has_required_args: bool,
        subparser_parent: ParserSpecification | None,
        prog_suffix: str,
    ) -> None:
        self.f = f
        self.markers = markers
        self._lazy_description = description
        self.args = args
        self.field_list = field_list
        self.child_from_prefix = child_from_prefix
        self.helptext_from_intern_prefixed_field_name = (
            helptext_from_intern_prefixed_field_name
        )
        # Subparser groups that are direct children of this parser. The actual tree
        # structure for argparse is built on-demand in apply().
        self.subparsers_from_intern_prefix = subparsers_from_intern_prefix
        self.intern_prefix = intern_prefix
        self.extern_prefix = extern_prefix
        self.has_required_args = has_required_args
        self.subparser_parent = subparser_parent
        self.prog_suffix = prog_suffix

    @property
    def description(self) -> str:
        """Description of this parser. Docstring parsing is expensive, so we only
        evaluate this when it's needed for helptext."""
        if self._description is None:
            desc = self._lazy_description
            if callable(desc):
                desc = desc()
            # A lazy description can evaluate to None, for example when a nested
            # field has no attribute docstring. Fall back to the docstring of the
            # type itself. An explicit empty string suppresses this fallback.
            if desc is None:
                desc = _docstrings.get_callable_description(self.f)
            self._description = _strings.remove_single_line_breaks(desc)
        return self._description

    @staticmethod
    def from_callable_or_type(
        f: Callable[..., T],
        markers: Iterable[_markers.Marker],
        description: str | Callable[[], str | None] | None,
        parent_classes: Set[Any],
        default_instance: Union[
            T, _singleton.PropagatingMissingType, _singleton.NonpropagatingMissingType
        ],
        intern_prefix: str,
        extern_prefix: str,
        subcommand_prefix: str,
        support_single_arg_types: bool,
        prog_suffix: str,
    ) -> ParserSpecification:
        """Create a parser definition from a callable or type."""

        # Consolidate subcommand types.
        f_unwrapped, new_markers = _resolver.unwrap_annotated(f, _markers._Marker)
        markers = frozenset(markers).union(new_markers)

        # Cycle detection.
        #
        # - `parent` here refers to in the nesting hierarchy, not the superclass.
        # - We threshold by `max_nesting_depth` to suppress false positives,
        #   for example from custom constructors that behave differently
        #   depending the default value. (example: ml_collections.ConfigDict)
        max_nesting_depth = 128
        if (
            intern_prefix.count(".") > max_nesting_depth
            and _unsafe_cache._make_key(f) in parent_classes
            and f is not dict
        ):
            raise UnsupportedTypeAnnotationError(
                (
                    fmt.text(
                        "Found a cyclic dependency with type ",
                        fmt.text["cyan"](str(f)),
                    ),
                )
            )

        # TODO: we are abusing the (minor) distinctions between types, classes, and
        # callables throughout the code. This is mostly for legacy reasons, could be
        # cleaned up.
        parent_classes = parent_classes | {_unsafe_cache._make_key(f)}

        # Wrap our type with a dummy dataclass if it can't be treated as a
        # nested type. For example: passing in f=int will result in a dataclass
        # with a single field typed as int.
        #
        # Why don't we always use a dummy dataclass?
        # => Docstrings for inner structs are currently lost when we nest struct types.
        # Resolve the type of `f`, generate a field list.
        # Try once first to avoid calling field_list_from_type_or_callable twice.
        f_for_field_list = f
        default_instance_for_field_list = default_instance

        # Check if we need DummyWrapper by trying to get fields first.
        with _fields.FieldDefinition.marker_context(tuple(markers)):
            out = _fields.field_list_from_type_or_callable(
                f=f_for_field_list,
                default_instance=default_instance_for_field_list,
                support_single_arg_types=support_single_arg_types,
                in_union_context=False,
            )

            # If not a struct type and not None, wrap in DummyWrapper and try again.
            if isinstance(
                out, UnsupportedStructTypeMessage
            ) and f_unwrapped is not type(None):
                from ._dummy_wrapper import DummyWrapper

                try:
                    f_for_field_list = DummyWrapper[f]  # type: ignore
                    default_instance_for_field_list = DummyWrapper(default_instance)  # type: ignore
                    out = _fields.field_list_from_type_or_callable(
                        f=f_for_field_list,
                        default_instance=default_instance_for_field_list,
                        support_single_arg_types=support_single_arg_types,
                        in_union_context=False,
                    )
                except TypeError as e:  # pragma: no cover
                    # In Python 3.8, DummyWrapper[f] raises TypeError if f is not a valid type.
                    # (e.g., "Parameters to generic types must be types. Got 5.")
                    raise UnsupportedTypeAnnotationError(
                        (
                            fmt.text(
                                "Expected a type, class, or callable, but got ",
                                fmt.text["cyan"](repr(f)),
                                ".",
                            ),
                        )
                    ) from e

            assert not isinstance(out, UnsupportedStructTypeMessage), out.message
            assert not isinstance(out, InvalidDefaultInstanceError), "\n".join(
                repr(fmt.rows(*out.message))
            )
            f, field_list = out

        has_required_args = False
        args: list[_arguments.ArgumentDefinition] = []
        helptext_from_intern_prefixed_field_name: Dict[
            str, str | Callable[[], str | None] | None
        ] = {}

        child_from_prefix: Dict[str, ParserSpecification] = {}

        subparsers_from_prefix = {}

        for field in field_list:
            field_out = handle_field(
                field,
                parent_classes=parent_classes,
                intern_prefix=intern_prefix,
                extern_prefix=extern_prefix,
                subcommand_prefix=subcommand_prefix,
                prog_suffix=prog_suffix,
            )
            if isinstance(field_out, _arguments.ArgumentDefinition):
                # Handle single arguments.
                args.append(field_out)
                if field_out.lowered.required:
                    has_required_args = True
            elif isinstance(field_out, SubparsersSpecification):
                # Handle subparsers.
                subparsers_from_prefix[field_out.intern_prefix] = field_out
            elif isinstance(field_out, ParserSpecification):
                # Handle nested parsers.
                nested_parser = field_out
                child_from_prefix[field_out.intern_prefix] = nested_parser

                # Flatten subparsers from nested parser into current parser.
                # This handles the case where a field's type has subcommands that need
                # to be accessible at the parent level.
                for (
                    prefix,
                    subparser_spec,
                ) in nested_parser.subparsers_from_intern_prefix.items():
                    subparsers_from_prefix[prefix] = subparser_spec

                if nested_parser.has_required_args:
                    has_required_args = True

                # Helptext for this field; used as description for grouping arguments.
                class_field_name = _strings.make_field_name(
                    [intern_prefix, field.intern_name]
                )

                # `field.helptext` can be a callable that returns `None` (for
                # example, lazy docstring parsing when a field has no attribute
                # docstring), so the docstring fallback needs to happen after
                # evaluation. We keep this lazy - don't evaluate yet.
                def evaluate_group_helptext(
                    helptext: str | Callable[[], str | None] | None = field.helptext,
                    f: Callable = nested_parser.f,
                ) -> str | None:
                    out = helptext() if callable(helptext) else helptext
                    if out is None:
                        # Fall back to the docstring of the nested type. An
                        # explicit empty string (`tyro.conf.arg(help="")`)
                        # suppresses this fallback.
                        out = _docstrings.get_callable_description(f)
                    return out

                helptext_from_intern_prefixed_field_name[class_field_name] = (
                    evaluate_group_helptext
                )

                # If arguments are in an optional group, it indicates that the default_instance
                # will be used if none of the arguments are passed in.
                if (
                    len(nested_parser.args) >= 1
                    and _markers._OPTIONAL_GROUP in nested_parser.args[0].field.markers
                ):

                    def evaluate_optional_group_helptext(
                        evaluate_group_helptext: Callable[
                            [], str | None
                        ] = evaluate_group_helptext,
                        default: Any = field.default,
                    ) -> str:
                        helptext = evaluate_group_helptext()
                        return (
                            ("" if helptext is None else helptext + "\n\n")
                            + "Default: "
                            + str(default)
                        )

                    helptext_from_intern_prefixed_field_name[class_field_name] = (
                        evaluate_optional_group_helptext
                    )

        parser_spec = ParserSpecification(
            f=f,
            markers=markers,
            description=description,
            args=args,
            field_list=field_list,
            child_from_prefix=child_from_prefix,
            helptext_from_intern_prefixed_field_name=helptext_from_intern_prefixed_field_name,
            subparsers_from_intern_prefix=subparsers_from_prefix,
            intern_prefix=intern_prefix,
            extern_prefix=extern_prefix,
            has_required_args=has_required_args,
            subparser_parent=None,
            prog_suffix=prog_suffix,
        )

        return parser_spec

    def get_args_including_children(
        self,
        local_root: ParserSpecification | None = None,
    ) -> list[ArgWithContext]:
        """Get all arguments in this parser and its children.

        Does not include arguments in subparsers.
        """
        if local_root is None:
            local_root = self
        args = [ArgWithContext(arg, self, local_root) for arg in self.args]
        for child in self.child_from_prefix.values():
            args.extend(child.get_args_including_children(local_root))
        return args


def _is_number(value: Any) -> bool:
    # We avoid importing this unless it's needed.
    import numbers

    return isinstance(value, numbers.Number)


def handle_field(
    field: _fields.FieldDefinition,
    parent_classes: Set[Any],
    intern_prefix: str,
    extern_prefix: str,
    subcommand_prefix: str,
    prog_suffix: str,
) -> Union[
    _arguments.ArgumentDefinition,
    ParserSpecification,
    SubparsersSpecification,
]:
    """Determine what to do with a single field definition."""

    # Check that the default value matches the final resolved type.
    # There's some similar Union-specific logic for this in narrow_union_type(). We
    # may be able to consolidate this.
    if (
        not _singleton.is_sentinel(field.default)
        # If a custom constructor is set, static_type may not be
        # matched to the annotated type.
        and field.argconf.constructor_factory is None
        # The numeric tower in Python is wacky. This logic is non-critical, so
        # we'll just skip it (+the complexity) for numbers.
        and type(field.default) not in (int, float, bool)
        and not _resolver.is_instance(field.type_stripped, field.default)
        and not _is_number(field.default)
    ):
        # If the default value doesn't match the resolved type, we expand the
        # type. This is inspired by https://github.com/brentyi/tyro/issues/88.
        field_name = _strings.make_field_name([extern_prefix, field.extern_name])
        message = (
            f"The field `{field_name}` is annotated with type `{field.type}`, "
            f"but the default value `{field.default}` has type `{type(field.default)}`. "
            f"We'll try to handle this gracefully, but it may cause unexpected behavior."
        )
        warnings.warn(message)
        field = field.with_new_type_stripped(
            Union[field.type_stripped, type(field.default)]  # type: ignore
        )

    # Force primitive if (1) the field is annotated with a primitive constructor spec, or (2) if
    # a custom primitive exists for the type.
    if type(field.type) is type and not ConstructorRegistry._has_custom_rules():
        force_primitive = False
    else:
        force_primitive = (
            len(_resolver.unwrap_annotated(field.type, PrimitiveConstructorSpec)[1]) > 0
        ) or ConstructorRegistry._is_primitive_type(
            field.type, field.markers, nondefault_only=True
        )

    if not force_primitive:
        # (1) Handle Unions over callables; these result in subparsers.
        if _markers.Suppress not in field.markers and _is_union(field.type_stripped):
            subparsers_attempt = SubparsersSpecification.from_field(
                field,
                parent_classes=parent_classes,
                intern_prefix=_strings.make_field_name(
                    [intern_prefix, field.intern_name]
                ),
                extern_prefix=(
                    extern_prefix
                    if _markers.OmitArgPrefixes in field.markers
                    else field.extern_name
                    if field.argconf.prefix_name is False
                    else _strings.make_field_name([extern_prefix, field.extern_name])
                ),
                prog_suffix=prog_suffix,
            )
            if subparsers_attempt is not None:
                return subparsers_attempt

        # (2) Handle nested callables.
        if _fields.is_struct_type(field.type, field.default, in_union_context=False):
            # Keep description lazy - don't evaluate yet.
            return ParserSpecification.from_callable_or_type(
                field.type_stripped,
                markers=field.markers,
                description=field.helptext,
                parent_classes=parent_classes,
                default_instance=field.default,
                intern_prefix=_strings.make_field_name(
                    [intern_prefix, field.intern_name]
                ),
                extern_prefix=(
                    _strings.make_field_name([extern_prefix, field.extern_name])
                    if field.argconf.prefix_name in (True, None)
                    else field.extern_name
                ),
                subcommand_prefix=subcommand_prefix,
                support_single_arg_types=False,
                prog_suffix=prog_suffix,
            )

    # (3) Handle primitive or fixed types. These produce a single argument!
    arg = _arguments.ArgumentDefinition(
        intern_prefix=intern_prefix,
        extern_prefix=extern_prefix,
        subcommand_prefix=subcommand_prefix,
        field=field,
    )

    # Validate that Fixed/Suppress fields have defaults.
    if (
        _markers.Fixed in field.markers or _markers.Suppress in field.markers
    ) and _singleton.is_missing(field.default):
        raise UnsupportedTypeAnnotationError(
            (
                fmt.text(
                    "Field ",
                    fmt.text["magenta", "bold"](field.intern_name),
                    " is marked as Fixed or Suppress but is missing a default value",
                ),
            )
        )

    return arg


def _is_union(typ: Any) -> bool:
    if type(typ) is type:
        return False
    return is_typing_union(get_origin(_resolver.unwrap_annotated(typ)))


def _validated_aliases(
    aliases_from_name: Dict[str, Tuple[str, ...]],
    parser_from_name: Dict[str, Any],
) -> Dict[str, Tuple[str, ...]]:
    """Filter alias entries to those whose canonical is in `parser_from_name`
    (suppressed branches drop out), and assert no alias collides with a
    canonical name or with another alias in the same Union."""
    out: Dict[str, Tuple[str, ...]] = {}
    seen: Dict[str, str] = {}  # alias -> canonical-it-belongs-to
    for canonical, aliases in aliases_from_name.items():
        if canonical not in parser_from_name:
            continue
        for alias in aliases:
            # An alias only genuinely collides with a canonical name when it is
            # *exactly* that canonical name. At parse time a token resolves by
            # exact match first (then by a delimiter swap), so a registered
            # alias is always reachable as itself -- even when its swapped form
            # (`_`<->`-`) happens to match another subcommand's canonical. We
            # must NOT reject the swapped form: doing so wrongly forbids natural
            # aliases like `run_server` for a `run-server` subcommand (its own
            # canonical), and aliases that are still distinctly reachable.
            assert alias not in parser_from_name, (
                f"Alias {alias!r} on subcommand {canonical!r} collides with "
                f"the canonical name of another subcommand in the same Union."
            )
            assert alias not in seen, (
                f"Alias {alias!r} is registered on both {seen[alias]!r} and "
                f"{canonical!r} in the same Union."
            )
            seen[alias] = canonical
        out[canonical] = aliases
    return out


_DEFAULT_SUBCOMMAND_CONFIG = _confstruct._SubcommandConfig(
    "unused",
    description=None,
    default=_singleton.MISSING_NONPROP,
    prefix_name=True,
    constructor_factory=None,
)


_struct_free_unions: Dict[Any, bool] = _unsafe_cache.make_cache()
"""Annotations that we know don't result in any subcommands."""


def _get_subcommand_config(
    annotations: Iterable[Any],
) -> _confstruct._SubcommandConfig | None:
    """Get the first subcommand config in a sequence of annotations."""
    for x in annotations:
        if isinstance(x, _confstruct._SubcommandConfig):
            return x
    return None


def _swap_constructor(option: Any, config: _confstruct._SubcommandConfig) -> Any:
    """Swap a subcommand type using `tyro.conf.subcommand(constructor=...)`."""
    assert config.constructor_factory is not None
    return Annotated[  # type: ignore
        (
            config.constructor_factory(),
            *_resolver.unwrap_annotated(option, "all")[1],
        )
    ]


def _get_full_name(typ: Any) -> str:
    """Get a name for a type, for use in warnings."""
    typ = _resolver.unwrap_annotated(typ)
    if typ is None:
        return "none"
    name = getattr(typ, "__name__", None)
    return f"{typ.__module__}.{name}" if name is not None else str(typ)


class SubparsersSpecification(Record):
    """Structure for defining subparsers. Each subparser is a parser with a name."""

    _canonical_from_alias: Dict[str, str] | None = None

    _fields = (
        "description",
        "parser_from_name",
        "default_name",
        "intern_prefix",
        "extern_prefix",
        "required",
        "default_instance",
        "option_from_name",
        "prog_suffix",
        "aliases_from_name",
    )

    def __init__(
        self,
        description: str | Callable[[], str | None] | None,
        parser_from_name: Dict[str, LazyParserSpecification],
        default_name: str | None,
        intern_prefix: str,
        extern_prefix: str,
        required: bool,
        default_instance: Any,
        option_from_name: Dict[str, Any],
        prog_suffix: str,
        aliases_from_name: Dict[str, Tuple[str, ...]],
    ) -> None:
        self.description = description
        self.parser_from_name = parser_from_name
        self.default_name = default_name
        self.intern_prefix = intern_prefix
        self.extern_prefix = extern_prefix
        self.required = required
        self.default_instance = default_instance
        self.option_from_name = option_from_name
        self.prog_suffix = prog_suffix
        self.aliases_from_name = aliases_from_name

    def display_name(self, canonical: str) -> str:
        """Render a subcommand name with its aliases for help output:
        ``"add (sum, +)"`` when aliases exist, otherwise just ``"add"``."""
        aliases = self.aliases_from_name.get(canonical)
        if not aliases:
            return canonical
        return canonical + " (" + ", ".join(aliases) + ")"

    def canonical_from_alias(self) -> Dict[str, str]:
        """Inverted alias map for fast lookup. Includes the identity mapping
        for each canonical name, so a single dict lookup resolves any
        user-typed subcommand name (canonical or alias) to its canonical
        form. Cached on the spec instance."""
        if self._canonical_from_alias is not None:
            return self._canonical_from_alias
        out = {name: name for name in self.parser_from_name}
        for canonical, aliases in self.aliases_from_name.items():
            for alias in aliases:
                out[alias] = canonical
        self._canonical_from_alias = out
        return out

    @staticmethod
    def from_field(
        field: _fields.FieldDefinition,
        parent_classes: Set[Any],
        intern_prefix: str,
        extern_prefix: str,
        prog_suffix: str,
    ) -> SubparsersSpecification | ParserSpecification | None:
        """From a field: return either a subparser specification, a parser
        specification for subcommands when `tyro.conf.AvoidSubcommands` is used
        and a default is set, or `None` if the field does not create a
        subparser."""
        # Union of classes should create subparsers.
        typ = _resolver.unwrap_annotated(field.type_stripped)
        if not is_typing_union(get_origin(typ)):
            return None

        # Share work between fields with the same annotation.
        union_key = _unsafe_cache.type_key(typ)
        if (
            union_key in _struct_free_unions
            and not ConstructorRegistry._has_custom_rules()
        ):
            return None

        # We don't use sets here to retain order of subcommands.
        options: List[Union[type, Callable]] = []

        # Flatten nested unions wrapped in Annotated (e.g.,
        # Annotated[Union[A, B], some_metadata]). We flatten unless the
        # metadata contains a _SubcommandConfig, which signals an
        # intentional hierarchical subparser group.
        # Annotations from the wrapper are propagated to each child.
        found_subcommand_conf = False
        for option in get_args(typ):
            unwrapped, all_annotations = _resolver.unwrap_annotated(option, "all")
            subcommand_config = _get_subcommand_config(all_annotations)
            if subcommand_config is None and is_typing_union(get_origin(unwrapped)):
                for child in get_args(unwrapped):
                    if len(all_annotations) > 0:
                        child = Annotated[(child,) + tuple(all_annotations)]  # type: ignore
                    # Children can also be annotated.
                    child_config = _get_subcommand_config(
                        _resolver.unwrap_annotated(child, "all")[1]
                    )
                    if (
                        child_config is not None
                        and child_config.constructor_factory is not None
                    ):
                        found_subcommand_conf = True
                        child = _swap_constructor(child, child_config)
                    options.append(child)  # type: ignore
            elif (
                # If specified, swap types using tyro.conf.subcommand(constructor=...).
                subcommand_config is not None
                and subcommand_config.constructor_factory is not None
            ):
                found_subcommand_conf = True
                options.append(_swap_constructor(option, subcommand_config))
            else:
                options.append(option)

        # Exit if we don't contain any struct types.
        def recursive_contains_struct_type(options: list[Any]) -> bool:
            for o in options:
                if _fields.is_struct_type(
                    o, _singleton.MISSING_NONPROP, in_union_context=True
                ):
                    return True
                if is_typing_union(get_origin(_resolver.unwrap_annotated(o))):
                    if recursive_contains_struct_type(get_args(o)):  # type: ignore
                        return True
            return False

        if not found_subcommand_conf and not recursive_contains_struct_type(options):
            _struct_free_unions[union_key] = True
            return None

        # Get subcommand configurations from `tyro.conf.subcommand()`.
        subcommand_config_from_name: Dict[str, _confstruct._SubcommandConfig] = {}
        subcommand_type_from_name: Dict[str, type] = {}
        subcommand_names: list[str] = []
        aliases_from_name: Dict[str, Tuple[str, ...]] = {}
        is_default_subcommand_name: str | None = None

        # Filter out suppressed subcommands upfront — they should not
        # participate in default matching or appear in error messages.
        filtered_options: List[Union[type, Callable]] = []
        subcommand_name_prefix = (
            "" if _markers.OmitSubcommandPrefixes in field.markers else extern_prefix
        )
        for option in options:
            option_unwrapped, all_annotations = _resolver.unwrap_annotated(
                option, "all"
            )
            if _markers.Suppress in all_annotations:
                continue
            filtered_options.append(option)

            subcommand_name = _strings.subparser_name_from_type(
                subcommand_name_prefix, cast(type, option)
            )
            subcommand_names.append(subcommand_name)
            if subcommand_name in subcommand_type_from_name:
                # Raise a warning that the subcommand already exists
                original_type_full_name = _get_full_name(
                    subcommand_type_from_name[subcommand_name]
                )
                new_type_full_name = _get_full_name(option_unwrapped)

                warnings.warn(
                    f"Duplicate subcommand name detected: '{subcommand_name}' is already used for "
                    f"{original_type_full_name} but will be overwritten by {new_type_full_name}. "
                    f"Only the last type ({new_type_full_name}) will be accessible via this subcommand. "
                    f"Consider using distinct class names or use tyro.conf.subcommand() to specify "
                    f"explicit subcommand names."
                )
            found_subcommand_configs = [
                x
                for x in all_annotations
                if isinstance(x, _confstruct._SubcommandConfig)
            ]
            if len(found_subcommand_configs) != 0:
                # Explicitly annotated default.
                assert len(found_subcommand_configs) == 1, (
                    f"Expected only one subcommand config, but {subcommand_name} has"
                    f" {len(found_subcommand_configs)}."
                )
                cfg = found_subcommand_configs[0]
                subcommand_config_from_name[subcommand_name] = cfg
                if cfg.aliases:
                    aliases_from_name[subcommand_name] = cfg.aliases
                if cfg.is_default:
                    assert is_default_subcommand_name is None, (
                        "Multiple subcommands marked with is_default=True: "
                        f"{is_default_subcommand_name!r} and {subcommand_name!r}."
                    )
                    is_default_subcommand_name = subcommand_name
            subcommand_type_from_name[subcommand_name] = cast(type, option)
        options = filtered_options

        # If a field default is provided, try to find a matching subcommand name.
        # Note: EXCLUDE_FROM_CALL (from TypedDict total=False or NotRequired[]) is
        # a sentinel that means no default was provided, so we skip matching.
        default_name = (
            _subcommand_matching.match_subcommand(
                field.default,
                subcommand_config_from_name,
                subcommand_type_from_name,
                extern_prefix,
            )
            if not _singleton.is_sentinel(field.default)
            else None
        )

        # If a branch was annotated with is_default=True, use it as the
        # default subcommand. We require that the field default (if any)
        # matches this branch -- silently letting the field default override
        # is_default would be confusing.
        if is_default_subcommand_name is not None:
            if default_name is None:
                default_name = is_default_subcommand_name
            else:
                assert default_name == is_default_subcommand_name, (
                    f"Subcommand {is_default_subcommand_name!r} is annotated "
                    f"with is_default=True, but the field default matches a "
                    f"different subcommand {default_name!r}. Either remove "
                    f"is_default=True or make the field default consistent "
                    f"with it."
                )

        if (
            default_name is not None
            and _markers.NewSubcommandForDefaults in field.markers
        ):
            # Create a new "default" subcommand instead of matching to an
            # existing one. This preserves original subcommand defaults.
            default_subcommand_name = (
                "default"
                if _markers.OmitSubcommandPrefixes in field.markers
                else f"{extern_prefix}:default"
            )
            assert default_subcommand_name not in subcommand_type_from_name, (
                f"Cannot create new default subcommand '{default_subcommand_name}' "
                f"because it already exists."
            )

            # Add to tracking structures. We inherit type from matched default
            # subcommand.
            default_config = _confstruct._SubcommandConfig(
                name="default",
                description="",
                default=field.default,
                prefix_name=True,
                constructor_factory=None,
            )
            default_type = subcommand_type_from_name[default_name]
            subcommand_config_from_name[default_subcommand_name] = default_config
            subcommand_type_from_name[default_subcommand_name] = default_type

            # Add matching pair of subcommand name and type.
            subcommand_names.append(default_subcommand_name)
            options.append(default_type)

            default_name = default_subcommand_name

        # Handle `tyro.conf.AvoidSubcommands` with a default value.
        if default_name is not None and _markers.AvoidSubcommands in field.markers:
            return ParserSpecification.from_callable_or_type(
                subcommand_type_from_name[default_name],
                markers=field.markers,
                description=None,
                parent_classes=parent_classes,
                default_instance=field.default,
                intern_prefix=intern_prefix,
                extern_prefix=extern_prefix,
                subcommand_prefix=extern_prefix,
                support_single_arg_types=True,
                prog_suffix=prog_suffix,
            )

        # Add subcommands for each option.
        parser_from_name: Dict[str, LazyParserSpecification] = {}
        option_from_name: Dict[str, Any] = {}
        for option, subcommand_name in zip(options, subcommand_names):
            # Get a subcommand config: either pulled from the type annotations or the
            # field default.
            subcommand_config = subcommand_config_from_name.get(
                subcommand_name, _DEFAULT_SUBCOMMAND_CONFIG
            )

            # If names match, borrow subcommand default from field default.
            if default_name == subcommand_name and not _singleton.is_missing(
                field.default
            ):
                subcommand_config = subcommand_config.replace(default=field.default)

            # Skip None options when DisallowNone is present.
            # This follows the same pattern as regular field DisallowNone handling.
            if _markers.DisallowNone in field.markers and _resolver.unwrap_annotated(
                option
            ) is type(None):
                continue

            # Create lazy description, for fast help text generation.
            # If no explicit description, get it from the callable's docstring.
            def description_factory(
                description: str | None = subcommand_config.description,
                option: Any = option,
            ) -> str:
                option_unwrapped = _resolver.unwrap_annotated(option)
                if option_unwrapped is type(None):
                    description = ""
                elif description is None:
                    description = _docstrings.get_callable_description(option_unwrapped)
                return _strings.remove_single_line_breaks(description)

            # Create lazy parser: defer expensive parsing until actually needed.
            def parser_factory(
                option: Any = option,
                subcommand_config: _confstruct._SubcommandConfig = subcommand_config,
                subcommand_name: str = subcommand_name,
            ) -> ParserSpecification:
                # Strip the subcommand config from the option type.
                # Relevant: https://github.com/brentyi/tyro/pull/117
                option, annotations = _resolver.unwrap_annotated(option, "all")
                annotations = tuple(
                    a
                    for a in annotations
                    if not isinstance(a, _confstruct._SubcommandConfig)
                )
                if len(annotations) > 0:
                    option = Annotated[(option,) + annotations]  # type: ignore

                with _fields.FieldDefinition.marker_context(tuple(field.markers)):
                    subparser = ParserSpecification.from_callable_or_type(
                        option,  # type: ignore
                        markers=field.markers,
                        description=subcommand_config.description,
                        parent_classes=parent_classes,
                        default_instance=subcommand_config.default,
                        intern_prefix=intern_prefix,
                        extern_prefix=extern_prefix,
                        subcommand_prefix=extern_prefix,
                        support_single_arg_types=True,
                        prog_suffix=subcommand_name
                        if prog_suffix == ""
                        else prog_suffix + " " + subcommand_name,
                    )
                # Apply prefix to helptext in nested classes in subparsers.
                return subparser.replace(
                    helptext_from_intern_prefixed_field_name={
                        _strings.make_field_name([intern_prefix, k]): v
                        for k, v in subparser.helptext_from_intern_prefixed_field_name.items()
                    },
                )

            option_from_name[subcommand_name] = option
            parser_from_name[subcommand_name] = LazyParserSpecification(
                description_factory=description_factory,
                factory=parser_factory,
            )

        # Default parser was suppressed!
        if default_name not in parser_from_name:
            default_name = None

        # Required if a default is passed in, but the default value has missing
        # parameters.
        if default_name is None:
            # Special case for DisallowNone: if the default would be None but we
            # suppressed the None subcommand due to DisallowNone, keep it optional.
            if field.default is None and _markers.DisallowNone in field.markers:
                required = False
            else:
                # If the default is EXCLUDE_FROM_CALL (from TypedDict total=False or
                # NotRequired[Union[...]]), the subparser is optional. When no subcommand
                # is selected, the field will be excluded from the result (see _calling.py).
                required = field.default is not _singleton.EXCLUDE_FROM_CALL
        else:
            required = False
            # Evaluate the lazy parser to check for required args/subparsers.
            default_parser_evaluated = parser_from_name[default_name].evaluate()
            # Error should have been caught earlier.
            assert not isinstance(
                default_parser_evaluated, UnsupportedTypeAnnotationError
            ), "Unexpected UnsupportedTypeAnnotationError in backend"

            # If there are any required arguments.
            if any(
                map(lambda arg: arg.lowered.required, default_parser_evaluated.args)
            ):
                required = True
            # If there are any required subparsers.
            elif any(
                subparser_spec.required
                for subparser_spec in default_parser_evaluated.subparsers_from_intern_prefix.values()
            ):
                required = True

        return SubparsersSpecification(
            # If we wanted, we could add information about the default instance
            # automatically, as is done for normal fields. But for now we just rely on
            # the user to include it in the docstring.
            # Keep description lazy - don't evaluate yet.
            description=field.helptext,
            parser_from_name=parser_from_name,
            default_name=default_name,
            intern_prefix=intern_prefix,
            extern_prefix=extern_prefix,
            required=required,
            default_instance=field.default,
            option_from_name=option_from_name,
            prog_suffix=prog_suffix,
            aliases_from_name=_validated_aliases(aliases_from_name, parser_from_name),
        )
