from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, Sequence, TypeVar, Union, overload

from typing_extensions import Annotated

import tyro
from tyro._strings import delimiter_context, swap_delimiters
from tyro.conf import subcommand as _subcommand_marker
from tyro.conf._markers import Suppress
from tyro.constructors import ConstructorRegistry

CallableT = TypeVar("CallableT", bound=Callable)


@dataclasses.dataclass
class _CommandSpec:
    """Internal record for a registered subcommand."""

    target: Union[Callable, "SubcommandApp"]
    help: str | None = None
    aliases: tuple[str, ...] = ()
    is_default: bool = False


def _make_nested_factory(union_type: Any) -> Callable[[], Any]:
    """Return a constructor_factory that yields the nested Union. We
    capture by argument (not closure) to avoid late-binding bugs in
    ``_build_union``'s loop."""
    return lambda: union_type


class SubcommandApp:
    """This class provides a decorator-based API for subcommands in
    :mod:`tyro`, inspired by `Typer <https://typer.tiangolo.com/>`_ and
    `cyclopts <https://cyclopts.readthedocs.io/>`_. Under-the-hood, this is a light wrapper
    over :func:`tyro.cli`.

    Example:

    .. code-block:: python

        from tyro.extras import SubcommandApp

        app = SubcommandApp()

        @app.command
        def greet(name: str, loud: bool = False):
            '''Greet someone.'''
            greeting = f"Hello, {name}!"
            if loud:
                greeting = greeting.upper()
            print(greeting)

        @app.command(name="addition", aliases=["sum"])
        def add(a: int, b: int):
            '''Add two numbers.'''
            print(f"{a} + {b} = {a + b}")

        if __name__ == "__main__":
            app.cli()

    Subcommand groups can be nested by registering one
    :class:`SubcommandApp` as a subcommand on another:

    .. code-block:: python

        db = SubcommandApp()

        @db.command
        def migrate(): ...

        @db.command
        def seed(): ...

        app = SubcommandApp()
        app.command(db, name="db")  # `mycli db migrate`, `mycli db seed`

    To make one subcommand the default when no subcommand is given, pass
    ``is_default=True``:

    .. code-block:: python

        @app.command(is_default=True)
        def run(name: str = "world"):
            print(f"hello {name}")

        # `mycli` runs `run("world")`; `mycli --name alice` runs `run("alice")`;
        # `mycli run --name alice` also works.

    Usage:

    .. code-block:: bash

        python my_script.py greet Alice
        python my_script.py greet Bob --loud
        python my_script.py addition 5 3
        python my_script.py sum 5 3        # via alias

    """

    def __init__(self) -> None:
        self._subcommands: Dict[str, _CommandSpec] = {}

    @overload
    def command(self, func: CallableT) -> CallableT: ...

    @overload
    def command(
        self,
        func: None = None,
        *,
        name: str | None = None,
        aliases: Sequence[str] | None = None,
        help: str | None = None,
        is_default: bool = False,
    ) -> Callable[[CallableT], CallableT]: ...

    @overload
    def command(
        self,
        func: "SubcommandApp",
        *,
        name: str | None = None,
        aliases: Sequence[str] | None = None,
        help: str | None = None,
        is_default: bool = False,
    ) -> "SubcommandApp": ...

    def command(
        self,
        func: CallableT | "SubcommandApp" | None = None,
        *,
        name: str | None = None,
        aliases: Sequence[str] | None = None,
        help: str | None = None,
        is_default: bool = False,
    ) -> Any:
        """Register a function or nested :class:`SubcommandApp` as a subcommand.

        This method is inspired by Typer's ``@app.command()`` and cyclopts's
        ``@app.command()`` decorators.

        Args:
            func: The function (or :class:`SubcommandApp` instance) to
                register. If ``None``, returns a decorator.
            name: Name of the subcommand. Defaults to the function's
                ``__name__``. Required when registering a
                :class:`SubcommandApp` (since the app has no name of its own).
            aliases: Alternative names that resolve to the same subcommand.
                For example, ``aliases=["sum"]`` lets users invoke ``add`` as
                either ``add`` or ``sum``.
            help: Override the helptext for this subcommand. If not set, the
                function's docstring (or nested app's description) is used.
            is_default: If ``True``, this subcommand becomes the implicit
                choice when the user invokes the CLI without naming a
                subcommand. At most one command per :class:`SubcommandApp`
                may set this.
        """

        def inner(target: CallableT | "SubcommandApp") -> CallableT | "SubcommandApp":
            nonlocal name
            if isinstance(target, SubcommandApp):
                assert name is not None, (
                    "When registering a nested SubcommandApp, `name=` is required."
                )
            elif name is None:
                name = target.__name__

            if is_default:
                for existing_name, existing_spec in self._subcommands.items():
                    assert not existing_spec.is_default, (
                        f"Cannot set is_default=True on {name!r}: "
                        f"{existing_name!r} is already the default."
                    )

            self._subcommands[name] = _CommandSpec(
                target=target,
                help=help,
                aliases=tuple(aliases) if aliases else (),
                is_default=is_default,
            )
            return target

        if func is not None:
            return inner(func)
        return inner

    def _build_union(
        self,
        *,
        use_underscores: bool,
        sort_subcommands: bool = False,
    ) -> Any:
        """Build the Annotated Union type that tyro.cli consumes.

        Recurses into nested SubcommandApp instances.
        """
        items = list(self._subcommands.items())
        if sort_subcommands:
            items.sort(key=lambda kv: kv[0])

        annotated_options: list[Any] = []
        for orig_name, spec in items:
            sub_name = swap_delimiters(orig_name)
            target = spec.target
            if isinstance(target, SubcommandApp):
                nested_union = target._build_union(use_underscores=use_underscores)
                annotated_options.append(
                    Annotated[
                        Any,
                        _subcommand_marker(
                            name=sub_name,
                            constructor_factory=_make_nested_factory(nested_union),
                            aliases=spec.aliases or None,
                            # Only use a docstring assigned directly to the
                            # instance; `target.__doc__` would fall back to the
                            # docstring of the SubcommandApp class itself. The
                            # final fallback is "" rather than None: None means
                            # "infer", which would pick up `typing.Union`'s
                            # docstring from the synthesized union type.
                            description=spec.help or vars(target).get("__doc__") or "",
                            is_default=spec.is_default,
                        ),
                    ]
                )
            else:
                annotated_options.append(
                    Annotated[
                        Any,
                        _subcommand_marker(
                            name=sub_name,
                            constructor=target,
                            aliases=spec.aliases or None,
                            description=spec.help,
                            is_default=spec.is_default,
                        ),
                    ]
                )

        # tyro.cli requires Union to have at least two arms; pad with
        # suppressed None when needed.
        if len(annotated_options) < 2:
            annotated_options.append(Annotated[None, Suppress])

        return Union[tuple(annotated_options)]  # type: ignore

    def cli(
        self,
        *,
        prog: str | None = None,
        description: str | None = None,
        args: Sequence[str] | None = None,
        use_underscores: bool = False,
        console_outputs: bool = True,
        add_help: bool = True,
        config: Sequence[Any] | None = None,
        sort_subcommands: bool = False,
        registry: ConstructorRegistry | None = None,
    ) -> Any:
        """Run the command-line interface.

        This method creates a CLI using tyro, with all subcommands registered using
        :func:`command()`.

        Args:
            prog: The name of the program printed in helptext. Mirrors argument from
                `argparse.ArgumentParser()`.
            description: Description text for the parser, displayed when the --help flag is
                passed in. If not specified, the class docstring is used. Mirrors argument from
                `argparse.ArgumentParser()`.
            args: If set, parse arguments from a sequence of strings instead of the
                commandline. Mirrors argument from `argparse.ArgumentParser.parse_args()`.
            use_underscores: If True, use underscores as a word delimiter instead of hyphens.
                This primarily impacts helptext; underscores and hyphens are treated equivalently
                when parsing happens. We default helptext to hyphens to follow the GNU style guide.
                https://www.gnu.org/software/libc/manual/html_node/Argument-Syntax.html
            console_outputs: If set to `False`, parsing errors and help messages will be
                suppressed.
            add_help: Add a -h/--help option to the parser. This mirrors the argument from
                `argparse.ArgumentParser()`.
            config: Sequence of config marker objects, from `tyro.conf`.
            sort_subcommands: If True, sort the subcommands alphabetically by name.
            registry: A :class:`tyro.constructors.ConstructorRegistry` instance containing custom
                constructor rules.
        """
        assert self._subcommands, "SubcommandApp has no commands registered."

        with delimiter_context("_" if use_underscores else "-"):
            union_type = self._build_union(
                use_underscores=use_underscores,
                sort_subcommands=sort_subcommands,
            )

        return tyro.cli(
            union_type,
            prog=prog,
            description=description,
            args=args,
            use_underscores=use_underscores,
            console_outputs=console_outputs,
            add_help=add_help,
            config=config,
            registry=registry,
        )
