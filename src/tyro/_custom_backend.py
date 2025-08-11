import sys
from dataclasses import dataclass
from typing import Annotated

import tyro
import tyro._fmtlib as fmt
from tyro._arguments import (
    BooleanOptionalAction,
    flag_to_inverse,
    generate_argument_helptext,
)
from tyro._parsers import ParserSpecification


def print_help(parser: ParserSpecification, prog: str = "script.py") -> None:
    # print(parser.description)
    # for arg in parser.args:
    #     print(arg.lowered.name_or_flags)
    #
    usage_strings = []
    group_description: dict[str, str] = {}
    groups: dict[str, list[tuple[str | fmt._Text, fmt._Text]]] = {
        "positional arguments": [],
        "options": [("-h, --help", fmt.text["dim"]("show this help message and exit"))],
    }

    def recurse_args(parser: ParserSpecification) -> None:
        # Note: multiple parsers can have the same extern_prefix. This might overwrite some groups.
        group_label = (parser.extern_prefix + " options").strip()
        groups.setdefault(group_label, [])
        if parser.extern_prefix != "":
            # Ignore root, since we'll show description above.
            group_description[group_label] = parser.description
        for arg in parser.args:
            # Update usage.
            if arg.field.is_positional():
                assert arg.lowered.metavar is not None
                invocation_short = fmt.text["bold"](arg.lowered.metavar)
                invocation_long_parts = [arg.lowered.metavar]
            else:
                name_or_flags = arg.lowered.name_or_flags
                if arg.lowered.action is BooleanOptionalAction:
                    name_or_flags = []
                    for name_or_flag in arg.lowered.name_or_flags:
                        name_or_flags.append(name_or_flag)
                        name_or_flags.append(flag_to_inverse(name_or_flag))
                    invocation_short = (
                        arg.lowered.name_or_flags[0]
                        + " | "
                        + flag_to_inverse(arg.lowered.name_or_flags[0])
                    )
                elif arg.lowered.metavar is not None:
                    invocation_short = fmt.text(
                        arg.lowered.name_or_flags[0],
                        " ",
                        fmt.text["bold"](arg.lowered.metavar),
                    )
                else:
                    invocation_short = arg.lowered.name_or_flags[0]

                if arg.lowered.required is False:
                    invocation_short = fmt.text("[", invocation_short, "]")

                invocation_long_parts = []
                for i, name in enumerate(name_or_flags):
                    if i > 0:
                        invocation_long_parts.append(", ")

                    invocation_long_parts.append(name)
                    if arg.lowered.metavar is not None:
                        invocation_long_parts.append(" ")
                        invocation_long_parts.append(
                            fmt.text["bold"](arg.lowered.metavar)
                        )

            # Populate help window.
            usage_strings.append(invocation_short)
            helptext = generate_argument_helptext(arg, arg.lowered)
            groups[
                group_label if not arg.field.is_positional() else "positional arguments"
            ].append((fmt.text(*invocation_long_parts), helptext))
        for child in parser.child_from_prefix.values():
            recurse_args(child)

    recurse_args(parser)

    # Put arguments in boxes.
    group_boxes = []
    max_invocation_width = 0
    max_helptext_width = 0
    for g in groups.values():
        for invocation, helptext in g:
            max_invocation_width = min(24, max(max_invocation_width, len(invocation)))
            max_helptext_width = max(max_helptext_width, len(helptext))

    for group_name, g in groups.items():
        if len(g) == 0:
            continue
        rows = []
        if group_description.get(group_name, "") != "":
            rows.append(group_description[group_name])
            rows.append(fmt.hr["dim"]())
        for invocation, helptext in g:
            if len(invocation) > max_invocation_width:
                # Invocation and helptext on separate lines.
                rows.append(invocation)
                rows.append(fmt.columns(("", max_invocation_width + 2), helptext))
            else:
                # Invocation and helptext on the same line.
                rows.append(
                    fmt.columns((invocation, max_invocation_width + 2), helptext)
                )
        group_boxes.append(
            fmt.box["dim"](
                fmt.text["dim"](group_name),
                fmt.rows(*rows),
            )
        )

    usage_args = fmt.text(*usage_strings, delimeter=" ")
    header = fmt.text(
        fmt.text["bold"]("usage: "),
        prog,
        " [-h] ",
        usage_args if len(usage_args) < 80 else "[OPTIONS]",
        fmt.text("\n\n", parser.description, "\n")
        if parser.description != ""
        else "\n",
    )
    helptext = fmt.rows(*group_boxes)
    print("\n".join(header.render()))
    print("\n".join(helptext.render(min(160, helptext.max_width()))))


if __name__ == "__main__":

    def instantiate(parser: ParserSpecification, args: list[str]) -> None:
        # print(parser.f)
        # print(parser.field_list)

        positional_args = []
        kwargs = {}

        if "--help" in args:
            print_help(parser)

        # for arg in parser.args:
        #     ...

        # arg_from_flag = {}
        # for arg in parser.args:
        #     ...

        # for arg in parser.args:
        #     if not arg.field.is_positional():
        #         assert arg.lowered.nargs is not None
        #         print(arg.lowered.nargs)

        # for arg in parser.child:
        #     print(arg.field.intern_name)
        #     ...
        # print(arg.lowered.name_or_flags)
        # print(arg.field.is_positional())

    @dataclass
    class Child:
        z: bool

    @dataclass
    class Parent:
        """Arguments description."""

        child: Child
        x: int
        y: Annotated[str, tyro.conf.arg(aliases=("--yep",))] = "hello"
        """Second field."""

    parser = ParserSpecification.from_callable_or_type(
        Parent,
        markers=set(),
        description=None,
        parent_classes=set(),
        default_instance=tyro.constructors.MISSING_NONPROP,
        intern_prefix="",
        extern_prefix="",
    )

    out = instantiate(parser, sys.argv[1:])
    tyro.cli(Parent, args=["--help"])
    print(out)
