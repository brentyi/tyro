"""Legacy, argparse-based backend for parsing command-line arguments."""

from __future__ import annotations

import dataclasses
from typing import Any, Container, Dict, List, Sequence, Tuple, cast

from .. import _fmtlib as fmt
from .. import _parsers, _strings
from .._singleton import NonpropagatingMissingType
from ..conf import _markers
from ..conf._mutex_group import _MutexGroupConfig
from ..constructors._primitive_spec import UnsupportedTypeAnnotationError
from . import _argparse as argparse
from . import _argparse_formatter
from ._base import ParserBackend


def _spec_has_is_default(spec: _parsers.ParserSpecification) -> bool:
    """Quick check: any subparser group at this level *or nested below it*
    uses is_default (signaled by default_name being set with no field
    default instance)? Recurses into nested subparsers so that a default
    set only on a deeper branch is still detected."""
    for subparser_spec in spec.subparsers_from_intern_prefix.values():
        if subparser_spec.default_name is not None and isinstance(
            subparser_spec.default_instance, NonpropagatingMissingType
        ):
            return True
        for parser in subparser_spec.parser_from_name.values():
            evaluated = parser.evaluate()
            # Error should have been caught earlier.
            assert not isinstance(evaluated, UnsupportedTypeAnnotationError), (
                "Unexpected UnsupportedTypeAnnotationError in argparse backend"
            )
            if _spec_has_is_default(evaluated):
                return True
    return False


def _find_subcommand_token(
    args: List[str], cursor: int, choices: Container[str]
) -> int | None:
    """Scan args from cursor for a non-flag token in `choices`. Skips flags
    and the token immediately following each flag (likely the flag's
    value), since a value that happens to equal a subcommand name must not
    be mistaken for explicit selection."""
    i = cursor
    while i < len(args):
        tok = args[i]
        if tok == "--":
            i += 1
            continue
        if tok.startswith("-") and len(tok) > 1:
            i += 1
            if i < len(args) and not args[i].startswith("-"):
                i += 1
            continue
        if tok in choices:
            return i
        i += 1
    return None


def _inject_is_default_subcommands(
    parser_spec: _parsers.ParserSpecification,
    args: List[str],
) -> List[str]:
    """Argparse-specific shim: argparse has no concept of an implicit
    default subparser. When ``tyro.conf.subcommand(is_default=True)`` is
    set on a branch and the user omits the subcommand, we prepend the
    default subcommand name so argparse can route correctly. The tyro
    backend handles this case natively in its parsing loop.
    """
    # Hot-path early exit: if no level uses is_default, don't walk.
    if not _spec_has_is_default(parser_spec):
        return args

    args = list(args)

    def walk(
        spec: _parsers.ParserSpecification, cursor: int
    ) -> int:
        """Recursively inject default subcommand names, returning the updated
        cursor position. A single parser level can contain multiple sibling
        subparser groups (e.g. two ``Union`` fields), and each chosen branch
        may itself contain nested subparser groups. We must descend into *each*
        chosen branch independently rather than tracking a single ``next_spec``,
        otherwise a default in one branch's nested subparser is dropped when a
        later sibling subcommand is also present at this level. See BUG 1."""
        for subparser_spec in spec.subparsers_from_intern_prefix.values():
            canonical_lookup = subparser_spec.canonical_from_alias()
            chosen_idx = _find_subcommand_token(args, cursor, canonical_lookup)

            if (
                chosen_idx is None
                and subparser_spec.default_name is not None
                and isinstance(
                    subparser_spec.default_instance, NonpropagatingMissingType
                )
            ):
                args.insert(cursor, subparser_spec.default_name)
                chosen_idx = cursor

            if chosen_idx is None:
                # No selection and no injectable default for this group; we
                # can't reliably descend further into this branch.
                continue

            cursor = chosen_idx + 1
            chosen = canonical_lookup.get(args[chosen_idx], args[chosen_idx])
            evaluated = subparser_spec.parser_from_name[chosen].evaluate()
            # Error should have been caught earlier.
            assert not isinstance(evaluated, UnsupportedTypeAnnotationError), (
                "Unexpected UnsupportedTypeAnnotationError in argparse backend"
            )
            # Descend into the chosen branch, which may have its own nested
            # subparser groups (including default branches to inject).
            cursor = walk(evaluated, cursor)
        return cursor

    walk(parser_spec, 0)
    return args


def _check_mutex_groups_within_subcommand_boundaries(
    parser_spec: _parsers.ParserSpecification,
) -> None:
    """Raise a clear error if any mutex group spans a subcommand boundary.

    argparse builds one ``_MutuallyExclusiveGroup`` per parser object and
    cannot share a mutex group across subparsers: the parent parser and each
    subparser are independent ``ArgumentParser`` instances. So if a single
    ``tyro.conf.create_mutex_group`` has members on both sides of a subcommand
    boundary (e.g. a top-level field and a subcommand-arm field, or two
    different subcommand arms), argparse would silently build a *separate*
    group on each parser. This destroys mutual exclusion (both members get
    accepted) and, for required groups, wrongly demands a member on every
    parser level.

    The tyro backend enforces such groups globally and is correct. Since
    argparse cannot replicate this without rearchitecting, we detect the
    situation at parser-construction time and raise an explicit error rather
    than silently mis-parsing. See BUG 3.

    Detection mirrors how the argparse parser is constructed: a single argparse
    parser "node" owns a ``ParserSpecification``'s own ``args`` plus all args
    reachable through ``child_from_prefix`` (which do *not* cross subparsers).
    Each subparser arm is a distinct node. A mutex config that appears in more
    than one node spans a subcommand boundary.
    """
    # Map each mutex config to the set of distinct parser-node ids that
    # reference it. A node id is the integer id() of the ParserSpecification at
    # the root of an argparse-parser group (the spec passed to apply_parser).
    nodes_from_mutex_config: Dict[_MutexGroupConfig, set] = {}

    def visit_node(spec: _parsers.ParserSpecification, node_id: int) -> None:
        # Collect mutex configs from this spec's own args and from all
        # non-subparser descendants (these share the same argparse parser).
        for arg in spec.args:
            group_conf = arg.field.mutex_group
            if group_conf is not None and not arg.is_suppressed():
                nodes_from_mutex_config.setdefault(group_conf, set()).add(node_id)
        for child in spec.child_from_prefix.values():
            visit_node(child, node_id)

        # Each subparser arm is a fresh argparse parser node.
        for subparser_spec in spec.subparsers_from_intern_prefix.values():
            for parser_lazy in subparser_spec.parser_from_name.values():
                evaluated = parser_lazy.evaluate()
                assert not isinstance(evaluated, UnsupportedTypeAnnotationError), (
                    "Unexpected UnsupportedTypeAnnotationError in argparse backend"
                )
                visit_node(evaluated, id(evaluated))

    visit_node(parser_spec, id(parser_spec))

    for group_conf, node_ids in nodes_from_mutex_config.items():
        if len(node_ids) > 1:
            title = group_conf.title or "mutually exclusive"
            raise UnsupportedTypeAnnotationError(
                (
                    fmt.text(
                        "The mutex group ",
                        fmt.text["cyan"](repr(title)),
                        " has members that span a subcommand (subparser) "
                        "boundary, which the argparse backend cannot enforce: "
                        "argparse builds an independent mutually-exclusive group "
                        "for each parser level, so mutual exclusion would be "
                        "silently lost. Keep all members of a mutex group within "
                        "a single (sub)command, or use the default 'tyro' backend, "
                        "which enforces mutex groups globally.",
                    ),
                )
            )


def _reorder_subparsers_action_last(parser: argparse.ArgumentParser) -> None:
    """Move any ``_SubParsersAction`` to the end of ``parser._actions``.

    argparse matches positional actions in ``parser._actions`` order. The
    subparsers action has ``nargs=PARSER`` (``A...``), which greedily consumes
    every remaining positional token. When a parent-level positional is
    declared *before* a subcommand union (e.g. ``name: Positional[str]`` then
    ``sub: Union[A, B]``), tyro's documented usage is ``STR [{sub:a,sub:b}]``
    -- the plain positional first, then the subcommand. But the subparsers
    action is registered before the plain positional's store action, so
    argparse routes the leading positional into the subparsers action and
    reports an "invalid choice" error.

    Ensuring the subparsers action is matched *after* all other positionals
    lets argparse consume fixed-arity positionals first, then route the
    remaining tokens into the subparser. This mirrors the tyro backend, which
    handles this ordering natively. See BUG 2.
    """
    actions = parser._actions
    subparser_actions = [a for a in actions if isinstance(a, argparse._SubParsersAction)]
    if not subparser_actions:
        return
    # Stable reorder: keep relative order of everything else, move subparser
    # actions to the very end.
    others = [a for a in actions if not isinstance(a, argparse._SubParsersAction)]
    actions[:] = others + subparser_actions


class ArgparseBackend(ParserBackend):
    """Backend that uses argparse for parsing command-line arguments.

    This is the original implementation, which constructs an argparse.ArgumentParser
    from the ParserSpecification and uses it to parse arguments. While robust and
    well-tested, it can be slow for complex command structures with many subcommands.
    """

    def parse_args(
        self,
        parser_spec: _parsers.ParserSpecification,
        args: Sequence[str],
        prog: str,
        return_unknown_args: bool,
        console_outputs: bool,
        add_help: bool,
        compact_help: bool = False,
    ) -> tuple[dict[str | None, Any], list[str] | None]:
        """Parse command-line arguments using argparse."""
        # compact_help is not supported for ArgparseBackend.
        assert not compact_help, "compact_help is only supported with TyroBackend"

        # Create and configure the argparse parser.
        parser = self.get_parser_for_completion(
            parser_spec,
            prog=prog,
            add_help=add_help,
            console_outputs=console_outputs,
        )
        args = _inject_is_default_subcommands(parser_spec, list(args))
        parser._args = args

        # Parse the arguments.
        if return_unknown_args:
            namespace, unknown_args = parser.parse_known_args(args=args)
        else:
            namespace = parser.parse_args(args=args)
            unknown_args = None

        # Convert namespace to dictionary.
        value_from_prefixed_field_name = vars(namespace)

        return value_from_prefixed_field_name, unknown_args

    def get_parser_for_completion(
        self,
        parser_spec: _parsers.ParserSpecification,
        prog: str | None,
        add_help: bool,
        console_outputs: bool = True,
    ) -> _argparse_formatter.TyroArgumentParser:
        """Get an argparse parser for shell completion generation."""

        parser = _argparse_formatter.TyroArgumentParser(
            prog=prog,
            allow_abbrev=False,
            add_help=add_help,
        )
        parser._parser_specification = parser_spec
        parser._parsing_known_args = False
        parser._console_outputs = console_outputs
        parser._args = []

        # argparse cannot share a mutually-exclusive group across subparsers.
        # Detect and clearly reject this case before constructing the parser,
        # so we never silently mis-parse. See BUG 3.
        _check_mutex_groups_within_subcommand_boundaries(parser_spec)

        # Populate the argparse parser.
        apply_parser(
            parser_spec, parser, force_required_subparsers=False, add_help=add_help
        )

        return parser


def apply_parser(
    parser_spec: _parsers.ParserSpecification,
    parser: argparse.ArgumentParser,
    force_required_subparsers: bool,
    add_help: bool,
) -> Tuple[argparse.ArgumentParser, ...]:
    """Create defined arguments and subparsers."""

    # Generate helptext.
    parser.description = parser_spec.description

    # `force_required_subparsers`: if we have required arguments and we're
    # consolidating all arguments into the leaves of the subparser trees, a
    # required argument in one node of this tree means that all of its
    # descendants are required.
    if (
        _markers.CascadeSubcommandArgs in parser_spec.markers
    ) and parser_spec.has_required_args:
        force_required_subparsers = True

    # Create subparser tree.
    # Build materialized tree from direct subparsers on-demand for argparse.
    subparser_group = None
    root_subparsers = build_parser_subparsers(parser_spec)

    if root_subparsers is not None:
        leaves = apply_materialized_subparsers(
            parser_spec,
            root_subparsers,
            parser,
            force_required_subparsers,
            force_consolidate_args=_markers.CascadeSubcommandArgs
            in parser_spec.markers,
            add_help=add_help,
        )
        subparser_group = parser._action_groups.pop()
    else:
        leaves = (parser,)

    # Depending on whether we want to cascade subcommand args, we can either
    # apply arguments to the intermediate parser or only on the leaves.
    if _markers.CascadeSubcommandArgs in parser_spec.markers:
        for leaf in leaves:
            apply_parser_args(parser_spec, leaf)
    else:
        apply_parser_args(parser_spec, parser)

    if subparser_group is not None:
        parser._action_groups.append(subparser_group)

    # Ensure plain positionals are matched before the subparsers action (which
    # greedily consumes all remaining tokens). See BUG 2.
    _reorder_subparsers_action_last(parser)

    # Break some API boundaries to rename the "optional arguments" => "options".
    assert parser._action_groups[1].title in (
        # python <= 3.9
        "optional arguments",
        # python >= 3.10
        "options",
    )
    parser._action_groups[1].title = "options"

    return leaves


def apply_parser_args(
    parser_spec: _parsers.ParserSpecification,
    parser: argparse.ArgumentParser,
    parent: _parsers.ParserSpecification | None = None,
    exclusive_group_from_group_conf: Dict[
        _MutexGroupConfig, argparse._MutuallyExclusiveGroup
    ]
    | None = None,
) -> None:
    """Create defined arguments and subparsers."""

    # Make argument groups.
    def format_group_name(group_name: str) -> str:
        return (group_name + " options").strip()

    group_from_group_name: Dict[str, argparse._ArgumentGroup] = {
        "": parser._action_groups[1],
        **{
            cast(str, group.title).partition(" ")[0]: group
            for group in parser._action_groups[2:]
        },
    }
    positional_group = parser._action_groups[0]
    assert positional_group.title == "positional arguments"

    # Inherit mutex groups from parent or create new dict
    if exclusive_group_from_group_conf is None:
        exclusive_group_from_group_conf = {}

    # Add each argument group. Groups with only suppressed arguments won't
    # be added.
    for arg in parser_spec.args:
        # Only reject if it's NOT also at parser level (which would be wrapper usage).
        if (
            _markers.CascadeSubcommandArgs in arg.field.markers
            and _markers.CascadeSubcommandArgs not in parser_spec.markers
        ):
            raise ValueError(
                f"Per-argument CascadeSubcommandArgs is not supported with the argparse backend. "
                f"Argument '{arg.field.intern_name}' has per-argument CascadeSubcommandArgs marker. "
                f"Please use backend='tyro' instead: tyro.cli(..., config=(tyro.conf.UseTypoBackend,))"
            )

        # Don't add suppressed arguments to the parser.
        if arg.is_suppressed():
            continue
        elif arg.is_positional():
            arg.add_argument(positional_group)
            continue
        elif arg.field.mutex_group is not None:
            group_conf = arg.field.mutex_group
            if group_conf not in exclusive_group_from_group_conf:
                exclusive_group_from_group_conf[group_conf] = (
                    parser.add_mutually_exclusive_group(required=group_conf.required)
                )
            arg.add_argument(exclusive_group_from_group_conf[group_conf])
        else:
            group_name = (
                arg.extern_prefix
                if arg.field.argconf.name != ""
                # If the field name is "erased", we'll place the argument in
                # the parent's group.
                #
                # This is to avoid "issue 1" in:
                # https://github.com/brentyi/tyro/issues/183
                #
                # Setting `tyro.conf.arg(name="")` should generally be
                # discouraged, so this will rarely matter.
                else arg.extern_prefix.rpartition(".")[0]
            )
            if group_name not in group_from_group_name:
                description = (
                    parent.helptext_from_intern_prefixed_field_name.get(
                        arg.intern_prefix
                    )
                    if parent is not None
                    else None
                )
                # Evaluate lazy description if callable.
                if callable(description):
                    description = description()
                group_from_group_name[group_name] = parser.add_argument_group(
                    format_group_name(group_name),
                    description=description,
                )
            arg.add_argument(group_from_group_name[group_name])

    for child in parser_spec.child_from_prefix.values():
        apply_parser_args(
            child,
            parser,
            parent=parser_spec,
            exclusive_group_from_group_conf=exclusive_group_from_group_conf,
        )


@dataclasses.dataclass(frozen=True)
class MaterializedParserTree:
    """Argparse-specific materialized tree structure.

    This wraps a ParserSpecification and adds the materialized subparser tree
    structure needed for argparse. The tyro backend doesn't need this.
    """

    parser_spec: _parsers.ParserSpecification
    subparsers: MaterializedSubparsersTree | None


@dataclasses.dataclass(frozen=True)
class MaterializedSubparsersTree:
    """Argparse-specific materialized subparser tree structure.

    This wraps a SubparsersSpecification and contains the fully materialized
    tree of parser options.
    """

    subparser_spec: _parsers.SubparsersSpecification
    parser_tree_from_name: Dict[str, MaterializedParserTree]


def build_parser_subparsers(
    parser_spec: _parsers.ParserSpecification,
) -> MaterializedSubparsersTree | None:
    """Build the materialized subparser tree for a single parser's direct subparsers."""
    root_subparsers: MaterializedSubparsersTree | None = None
    for subparser_spec in parser_spec.subparsers_from_intern_prefix.values():
        root_subparsers = add_subparsers_to_leaves(root_subparsers, subparser_spec)
    return root_subparsers


def add_subparsers_to_leaves(
    root: MaterializedSubparsersTree | None,
    leaf: _parsers.SubparsersSpecification,
) -> MaterializedSubparsersTree:
    """Build materialized subparser tree for argparse.

    This creates the nested tree structure that argparse needs, where each level
    of subparsers is materialized. Multiple Union fields at the same level get
    nested (e.g., mode: Union[A,B] and dataset: Union[X,Y] becomes: choose mode,
    then choose dataset).
    """
    if root is None:
        # Convert SubparsersSpecification to MaterializedSubparsersTree.
        # Recursively build subparsers for each parser option.
        parser_tree_from_name = {}
        for name, parser_spec_lazy in leaf.parser_from_name.items():
            parser_spec = parser_spec_lazy.evaluate()
            # Error should have been caught earlier in _cli.py.
            assert not isinstance(parser_spec, UnsupportedTypeAnnotationError), (
                "Unexpected UnsupportedTypeAnnotationError in backend"
            )
            parser_tree_from_name[name] = MaterializedParserTree(
                parser_spec=parser_spec,
                subparsers=build_parser_subparsers(parser_spec),
            )
        return MaterializedSubparsersTree(
            subparser_spec=leaf, parser_tree_from_name=parser_tree_from_name
        )

    # Recursively add leaf to all branches in the tree.
    new_parser_trees = {}
    for name, parser_tree in root.parser_tree_from_name.items():
        new_parser_trees[name] = MaterializedParserTree(
            parser_spec=parser_tree.parser_spec,
            subparsers=add_subparsers_to_leaves(parser_tree.subparsers, leaf),
        )
    return MaterializedSubparsersTree(
        subparser_spec=dataclasses.replace(
            root.subparser_spec,
            required=root.subparser_spec.required or leaf.required,
        ),
        parser_tree_from_name=new_parser_trees,
    )


def apply_materialized_subparsers(
    parser_spec: _parsers.ParserSpecification,
    materialized_tree: MaterializedSubparsersTree,
    parent_parser: argparse.ArgumentParser,
    force_required_subparsers: bool,
    force_consolidate_args: bool,
    add_help: bool,
) -> Tuple[argparse.ArgumentParser, ...]:
    """Apply a materialized subparser tree to an argparse parser.

    This is similar to SubparsersSpecification.apply() but works with the
    materialized tree structure.

    Args:
        parser_spec: The parser specification that owns this materialized tree.
        materialized_tree: The materialized subparser tree to apply.
        parent_parser: The argparse parser to add subparsers to.
        force_required_subparsers: Whether to force subparsers to be required.
        force_consolidate_args: If True, apply this parser's args to all leaves,
            regardless of this parser's cascading setting.
            This is used to propagate CascadeSubcommandArgs from ancestors.
    """
    subparser_spec = materialized_tree.subparser_spec
    title = "subcommands"
    metavar = "{" + ",".join(materialized_tree.parser_tree_from_name.keys()) + "}"

    required = subparser_spec.required or force_required_subparsers

    if not required:
        title = "optional " + title
        metavar = f"[{metavar}]"

    # Make description.
    description_parts = []
    if subparser_spec.description is not None:
        desc = subparser_spec.description
        # Evaluate lazy description if callable.
        if callable(desc):
            desc = desc()
        if desc is not None:
            description_parts.append(desc)
    if not required and subparser_spec.default_name is not None:
        description_parts.append(f"(default: {subparser_spec.default_name})")

    # If this subparser is required because of a required argument in a
    # parent (tyro.conf.CascadeSubcommandArgs).
    if not subparser_spec.required and force_required_subparsers:
        description_parts.append("(required to specify parent argument)")

    description = " ".join(description_parts) if len(description_parts) > 0 else None

    # Add subparsers to argparse.
    argparse_subparsers = parent_parser.add_subparsers(
        dest=_strings.make_subparser_dest(subparser_spec.intern_prefix),
        description=description,
        required=required,
        title=title,
        metavar=metavar,
    )

    subparser_tree_leaves: List[argparse.ArgumentParser] = []
    for name, parser_tree in materialized_tree.parser_tree_from_name.items():
        subparser_def = parser_tree.parser_spec
        helptext = subparser_def.description.replace("%", "%%")
        aliases = list(subparser_spec.aliases_from_name.get(name, ()))
        subparser = argparse_subparsers.add_parser(
            name,
            help=helptext,
            allow_abbrev=False,
            add_help=add_help,
            aliases=aliases,
        )

        # Set parent link for helptext traversal when CascadeSubcommandArgs is used.
        if force_consolidate_args or (
            _markers.CascadeSubcommandArgs in parser_spec.markers
        ):
            subparser_def = dataclasses.replace(
                subparser_def, subparser_parent=parser_spec
            )

        # Attributes used for error message generation.
        assert isinstance(subparser, _argparse_formatter.TyroArgumentParser)
        assert isinstance(parent_parser, _argparse_formatter.TyroArgumentParser)
        subparser._parsing_known_args = parent_parser._parsing_known_args
        subparser._parser_specification = subparser_def
        subparser._console_outputs = parent_parser._console_outputs
        subparser._args = parent_parser._args

        # Apply this parser, using its materialized subparsers if any.
        if parser_tree.subparsers is not None:
            # This parser has nested subparsers in the materialized tree.
            # Store the materialized subparser spec for help formatting.
            subparser._materialized_subparser_spec = (
                parser_tree.subparsers.subparser_spec
            )
            leaves = apply_parser_with_materialized_subparsers(
                subparser_def,
                parser_tree.subparsers,
                subparser,
                force_required_subparsers,
                force_consolidate_args,
                add_help=add_help,
            )
        else:
            # No nested subparsers, just apply normally.
            leaves = apply_parser(
                subparser_def, subparser, force_required_subparsers, add_help=add_help
            )

        subparser_tree_leaves.extend(leaves)

    return tuple(subparser_tree_leaves)


def apply_parser_with_materialized_subparsers(
    parser_spec: _parsers.ParserSpecification,
    materialized_subparsers: MaterializedSubparsersTree,
    parser: argparse.ArgumentParser,
    force_required_subparsers: bool,
    force_consolidate_args: bool,
    add_help: bool,
) -> Tuple[argparse.ArgumentParser, ...]:
    """Apply a parser that has pre-materialized subparsers.

    Args:
        parser_spec: The parser specification to apply.
        materialized_subparsers: The materialized subparser tree.
        parser: The argparse parser to apply to.
        force_required_subparsers: Whether to force subparsers to be required.
        force_consolidate_args: If True, indicates an ancestor has CascadeSubcommandArgs,
            so this parser should also cascade its args to descendants.
    """
    # Generate helptext.
    parser.description = parser_spec.description

    # Check if either the parent (via force_consolidate_args) or this parser wants to cascade.
    should_cascade = force_consolidate_args or (
        _markers.CascadeSubcommandArgs in parser_spec.markers
    )

    if should_cascade and parser_spec.has_required_args:
        force_required_subparsers = True

    # Apply the materialized subparsers, propagating cascade mode.
    leaves = apply_materialized_subparsers(
        parser_spec,
        materialized_subparsers,
        parser,
        force_required_subparsers,
        force_consolidate_args=should_cascade,
        add_help=add_help,
    )
    subparser_group = parser._action_groups.pop()

    # Apply arguments.
    if should_cascade:
        for leaf in leaves:
            # When cascading, apply this parser's args to leaves.
            apply_parser_args(parser_spec, leaf)
    else:
        apply_parser_args(parser_spec, parser)

    parser._action_groups.append(subparser_group)

    # Ensure plain positionals are matched before the subparsers action (which
    # greedily consumes all remaining tokens). See BUG 2.
    _reorder_subparsers_action_last(parser)

    # Rename "optional arguments" => "options".
    assert parser._action_groups[1].title in (
        "optional arguments",
        "options",
    )
    parser._action_groups[1].title = "options"

    return leaves
