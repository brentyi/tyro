"""Legacy, argparse-based backend for parsing command-line arguments."""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Sequence, Tuple, cast

from .. import _parsers, _strings
from ..conf import _markers
from ..conf._mutex_group import _MutexGroupConfig
from . import _argparse as argparse
from . import _argparse_formatter
from ._base import ParserBackend


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
    ) -> tuple[dict[str | None, Any], list[str] | None]:
        """Parse command-line arguments using argparse."""

        # Create and configure the argparse parser.
        parser = self.get_parser_for_completion(
            parser_spec,
            prog=prog,
            add_help=add_help,
            console_outputs=console_outputs,
        )
        parser._args = list(args)

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
        description_parts.append(subparser_spec.description)
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
        subparser = argparse_subparsers.add_parser(
            name,
            help=helptext,
            allow_abbrev=False,
            add_help=add_help,
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

    # Rename "optional arguments" => "options".
    assert parser._action_groups[1].title in (
        "optional arguments",
        "options",
    )
    parser._action_groups[1].title = "options"

    return leaves
