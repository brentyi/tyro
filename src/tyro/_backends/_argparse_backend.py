"""Argparse-based backend for parsing command-line arguments."""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Sequence, Tuple

from .. import _parsers, _strings
from ..conf import _markers
from . import _argparse as argparse
from . import _argparse_formatter
from ._base import ParserBackend

# Materialized tree structures for argparse backend.
# These are only needed for argparse, not for the tyro backend.


def _check_for_global_args(parser_spec: _parsers.ParserSpecification) -> None:
    """Check if GlobalArgs marker is used anywhere in the parser tree.

    Raises:
        ValueError: If GlobalArgs marker is found (not supported in argparse backend).
    """

    def check_recursive(parser: _parsers.ParserSpecification) -> None:
        # Check arguments for GlobalArgs marker.
        for arg in parser.args:
            if _markers.GlobalArgs in arg.field.markers:
                raise ValueError(
                    f"GlobalArgs marker is not supported with the argparse backend. "
                    f"Argument '{arg.field.intern_name}' has GlobalArgs marker. "
                    f"Please use backend='tyro' instead: tyro.cli(..., config=(tyro.conf.UseTypoBackend,))"
                )

        # Check nested children.
        for child in parser.child_from_prefix.values():
            check_recursive(child)

        # Check subparsers.
        for subparser_spec in parser.subparsers_from_intern_prefix.values():
            for child in subparser_spec.parser_from_name.values():
                check_recursive(child)

    check_recursive(parser_spec)


@dataclasses.dataclass(frozen=True)
class MaterializedParserTree:
    """Argparse-specific materialized tree structure.

    This wraps a ParserSpecification and adds the materialized subparser tree
    structure needed for argparse. The tyro backend doesn't need this.
    """

    parser_spec: _parsers.ParserSpecification
    subparsers: "MaterializedSubparsersTree | None"


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
        for name, parser_spec in leaf.parser_from_name.items():
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
    force_consolidate_args: bool = False,
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
            regardless of this parser's consolidate_subcommand_args setting.
            This is used to propagate ConsolidateSubcommandArgs from ancestors.
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
    # parent (tyro.conf.ConsolidateSubcommandArgs).
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
            add_help=parent_parser.add_help,
        )

        # Set parent link for helptext traversal when ConsolidateSubcommandArgs is used.
        if force_consolidate_args or (
            _markers.ConsolidateSubcommandArgs in parser_spec.markers
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
            )
        else:
            # No nested subparsers, just apply normally.
            leaves = subparser_def.apply(subparser, force_required_subparsers)

        subparser_tree_leaves.extend(leaves)

    return tuple(subparser_tree_leaves)


def apply_parser_with_materialized_subparsers(
    parser_spec: _parsers.ParserSpecification,
    materialized_subparsers: MaterializedSubparsersTree,
    parser: argparse.ArgumentParser,
    force_required_subparsers: bool,
    force_consolidate_args: bool = False,
) -> Tuple[argparse.ArgumentParser, ...]:
    """Apply a parser that has pre-materialized subparsers.

    Args:
        parser_spec: The parser specification to apply.
        materialized_subparsers: The materialized subparser tree.
        parser: The argparse parser to apply to.
        force_required_subparsers: Whether to force subparsers to be required.
        force_consolidate_args: If True, indicates an ancestor has ConsolidateSubcommandArgs,
            so this parser should also consolidate its args to leaves.
    """
    # Generate helptext.
    parser.description = parser_spec.description

    # Check if either the parent (via force_consolidate_args) or this parser wants to consolidate.
    should_consolidate = force_consolidate_args or (
        _markers.ConsolidateSubcommandArgs in parser_spec.markers
    )

    if should_consolidate and parser_spec.has_required_args:
        force_required_subparsers = True

    # Apply the materialized subparsers, propagating consolidate mode.
    leaves = apply_materialized_subparsers(
        parser_spec,
        materialized_subparsers,
        parser,
        force_required_subparsers,
        force_consolidate_args=should_consolidate,
    )
    subparser_group = parser._action_groups.pop()

    # Apply arguments.
    if should_consolidate:
        for leaf in leaves:
            # When consolidating, apply this parser's args to leaves.
            parser_spec.apply_args(leaf)
    else:
        parser_spec.apply_args(parser)

    parser._action_groups.append(subparser_group)

    # Rename "optional arguments" => "options".
    assert parser._action_groups[1].title in (
        "optional arguments",
        "options",
    )
    parser._action_groups[1].title = "options"

    return leaves


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
    ) -> tuple[dict[str | None, Any], list[str] | None]:
        """Parse command-line arguments using argparse."""

        # Check for GlobalArgs marker (not supported in argparse backend).
        _check_for_global_args(parser_spec)

        # Create and configure the argparse parser.
        parser = _argparse_formatter.TyroArgumentParser(
            prog=prog,
            allow_abbrev=False,
            add_help=parser_spec.add_help,
        )
        parser._parser_specification = parser_spec
        parser._parsing_known_args = return_unknown_args
        parser._console_outputs = console_outputs
        parser._args = list(args)

        # Apply the parser specification to populate the argparse parser.
        parser_spec.apply(parser, force_required_subparsers=False)

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
    ) -> _argparse_formatter.TyroArgumentParser:
        """Get an argparse parser for shell completion generation."""

        parser = _argparse_formatter.TyroArgumentParser(
            prog=prog,
            allow_abbrev=False,
            add_help=add_help,
        )
        parser._parser_specification = parser_spec
        parser._parsing_known_args = False
        parser._console_outputs = True
        parser._args = []

        # Apply the parser specification to populate the argparse parser.
        parser_spec.apply(parser, force_required_subparsers=False)

        return parser
