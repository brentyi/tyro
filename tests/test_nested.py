import dataclasses
from typing import Any, Generic, NewType, Optional, Tuple, TypeVar, Union

import pytest
from helptext_utils import get_helptext_with_checks
from typing_extensions import Annotated, Final, Literal

import tyro


def test_nested() -> None:
    @dataclasses.dataclass
    class B:
        y: int

    @dataclasses.dataclass
    class Nested:
        x: int
        b: B
        """Helptext for b"""

    assert tyro.cli(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(x=1, b=B(y=3))
    with pytest.raises(SystemExit):
        tyro.cli(Nested, args=["--x", "1"])

    def main(x: Nested):
        return x

    assert "Helptext for b" in get_helptext_with_checks(main)


def test_nested_annotated() -> None:
    @dataclasses.dataclass
    class B:
        y: int

    @dataclasses.dataclass
    class Nested:
        x: int
        b: Annotated[B, "this should be ignored"]

    assert tyro.cli(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(x=1, b=B(y=3))
    with pytest.raises(SystemExit):
        tyro.cli(Nested, args=["--x", "1"])


def test_nested_final() -> None:
    @dataclasses.dataclass
    class B:
        y: int

    @dataclasses.dataclass
    class Nested:
        x: int
        b: Final[B]  # type: ignore

    assert tyro.cli(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(x=1, b=B(y=3))
    with pytest.raises(SystemExit):
        tyro.cli(Nested, args=["--x", "1"])


def test_nested_accidental_underscores() -> None:
    @dataclasses.dataclass
    class B:
        arg_name: str

    @dataclasses.dataclass
    class Nested:
        x: int
        child_struct: B

    assert (
        tyro.cli(Nested, args=["--x", "1", "--child-struct.arg-name", "three_five"])
        == tyro.cli(Nested, args=["--x", "1", "--child_struct.arg_name", "three_five"])
        == tyro.cli(Nested, args=["--x", "1", "--child_struct.arg-name", "three_five"])
        == tyro.cli(Nested, args=["--x", "1", "--child_struct.arg_name=three_five"])
        == Nested(x=1, child_struct=B(arg_name="three_five"))
    )
    with pytest.raises(SystemExit):
        tyro.cli(Nested, args=["--x", "1"])


def test_nested_default() -> None:
    @dataclasses.dataclass(frozen=True)
    class B:
        y: int = 1

    @dataclasses.dataclass
    class Nested:
        x: int = 2
        b: B = B()

    assert tyro.cli(Nested, args=[], default=Nested(x=1, b=B(y=2))) == Nested(
        x=1, b=B(y=2)
    )


def test_nested_default_alternate() -> None:
    @dataclasses.dataclass
    class B:
        y: int = 3

    @dataclasses.dataclass
    class Nested:
        x: int
        b: B

    assert (
        Nested(x=1, b=B(y=3))
        == tyro.cli(Nested, args=["--x", "1", "--b.y", "3"])
        == tyro.cli(Nested, args=[], default=Nested(x=1, b=B(y=3)))
    )
    assert tyro.cli(Nested, args=["--x", "1"]) == Nested(x=1, b=B(y=3))


def test_default_nested() -> None:
    @dataclasses.dataclass(frozen=True)
    class B:
        y: int = 3

    @dataclasses.dataclass(frozen=True)
    class Nested:
        x: int
        b: B = B(y=5)

    assert tyro.cli(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(x=1, b=B(y=3))
    assert tyro.cli(Nested, args=["--x", "1"]) == Nested(x=1, b=B(y=5))


def test_double_default_nested() -> None:
    @dataclasses.dataclass(frozen=True)
    class Child:
        y: int

    @dataclasses.dataclass(frozen=True)
    class Parent:
        c: Child

    @dataclasses.dataclass(frozen=True)
    class Grandparent:
        x: int
        b: Parent = Parent(Child(y=5))

    assert tyro.cli(Grandparent, args=["--x", "1", "--b.c.y", "3"]) == Grandparent(
        x=1, b=Parent(Child(y=3))
    )
    assert tyro.cli(Grandparent, args=["--x", "1"]) == Grandparent(
        x=1, b=Parent(Child(y=5))
    )


def test_default_factory_nested() -> None:
    @dataclasses.dataclass
    class B:
        y: int = 3

    @dataclasses.dataclass
    class Nested:
        x: int
        b: B = dataclasses.field(default_factory=lambda: B(y=5))

    assert tyro.cli(Nested, args=["--x", "1", "--b.y", "3"]) == Nested(x=1, b=B(y=3))
    assert tyro.cli(Nested, args=["--x", "1"]) == Nested(x=1, b=B(y=5))


def test_optional_nested() -> None:
    @dataclasses.dataclass
    class OptionalNestedChild:
        y: int
        z: int

    @dataclasses.dataclass
    class OptionalNested:
        x: int
        b: Optional[OptionalNestedChild] = None

    assert tyro.cli(OptionalNested, args=["--x", "1"]) == OptionalNested(x=1, b=None)
    with pytest.raises(SystemExit):
        tyro.cli(
            OptionalNested, args=["--x", "1", "b:optional-nested-child", "--b.y", "3"]
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            OptionalNested, args=["--x", "1", "b:optional-nested-child", "--b.z", "3"]
        )

    assert tyro.cli(
        OptionalNested,
        args=["--x", "1", "b:optional-nested-child", "--b.y", "2", "--b.z", "3"],
    ) == OptionalNested(x=1, b=OptionalNestedChild(y=2, z=3))


def test_optional_nested_newtype() -> None:
    @dataclasses.dataclass
    class OptionalNestedChild:
        y: int
        z: int

    SpecialOptionalNestedChild = NewType(
        "SpecialOptionalNestedChild", OptionalNestedChild
    )

    @dataclasses.dataclass
    class OptionalNested:
        x: int
        b: Optional[SpecialOptionalNestedChild] = None

    assert tyro.cli(OptionalNested, args=["--x", "1"]) == OptionalNested(x=1, b=None)
    with pytest.raises(SystemExit):
        tyro.cli(
            OptionalNested,
            args=["--x", "1", "b:special-optional-nested-child", "--b.y", "3"],
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            OptionalNested,
            args=["--x", "1", "b:special-optional-nested-child", "--b.z", "3"],
        )

    assert tyro.cli(
        OptionalNested,
        args=[
            "--x",
            "1",
            "b:special-optional-nested-child",
            "--b.y",
            "2",
            "--b.z",
            "3",
        ],
    ) == OptionalNested(
        x=1, b=SpecialOptionalNestedChild(OptionalNestedChild(y=2, z=3))
    )


def test_optional_nested_multiple() -> None:
    """Adapted from: https://github.com/brentyi/tyro/issues/60"""

    @dataclasses.dataclass(frozen=True)
    class OutputHeadSettings:
        number_of_outputs: int = 1

    @dataclasses.dataclass(frozen=True)
    class OptimizerSettings:
        name: str = "adam"

    @dataclasses.dataclass(frozen=True)
    class ModelSettings:
        output_head_settings: Optional[OutputHeadSettings] = None
        optimizer_settings: Optional[OptimizerSettings] = None

    assert tyro.cli(
        ModelSettings,
        args="output-head-settings:None optimizer-settings:None".split(" "),
    ) == ModelSettings(None, None)

    with pytest.raises(SystemExit):
        # Order cannot be flipped, unfortunately.
        tyro.cli(
            ModelSettings,
            args="optimizer-settings:None output-head-settings:None".split(" "),
        )

    assert tyro.cli(
        ModelSettings,
        args="output-head-settings:output-head-settings optimizer-settings:None".split(
            " "
        ),
    ) == ModelSettings(OutputHeadSettings(1), None)

    assert tyro.cli(
        ModelSettings,
        args=(
            "output-head-settings:output-head-settings"
            " --output-head-settings.number-of-outputs 5 optimizer-settings:None".split(
                " "
            )
        ),
    ) == ModelSettings(OutputHeadSettings(5), None)

    assert tyro.cli(
        tyro.conf.OmitSubcommandPrefixes[
            tyro.conf.ConsolidateSubcommandArgs[ModelSettings]
        ],
        args=("output-head-settings None --number-of-outputs 5".split(" ")),
    ) == ModelSettings(OutputHeadSettings(5), None)

    assert tyro.cli(
        tyro.conf.OmitSubcommandPrefixes[
            tyro.conf.ConsolidateSubcommandArgs[ModelSettings]
        ],
        args=(
            "output-head-settings"
            " optimizer-settings --name sgd --number-of-outputs 5".split(" ")
        ),
    ) == ModelSettings(OutputHeadSettings(5), OptimizerSettings("sgd"))


def test_subparser() -> None:
    @dataclasses.dataclass
    class HTTPServer:
        y: int

    @dataclasses.dataclass
    class SMTPServer:
        z: int

    @dataclasses.dataclass
    class Subparser:
        x: int
        bc: Union[HTTPServer, SMTPServer]

    assert tyro.cli(
        Subparser, args=["--x", "1", "bc:http-server", "--bc.y", "3"]
    ) == Subparser(x=1, bc=HTTPServer(y=3))
    assert tyro.cli(
        Subparser, args=["--x", "1", "bc:smtp-server", "--bc.z", "3"]
    ) == Subparser(x=1, bc=SMTPServer(z=3))

    with pytest.raises(SystemExit):
        # Missing subcommand.
        tyro.cli(Subparser, args=["--x", "1"])
    with pytest.raises(SystemExit):
        # Wrong field.
        tyro.cli(Subparser, args=["--x", "1", "bc:http-server", "--bc.z", "3"])
    with pytest.raises(SystemExit):
        # Wrong field.
        tyro.cli(Subparser, args=["--x", "1", "bc:smtp-server", "--bc.y", "3"])


def test_subparser_newtype() -> None:
    @dataclasses.dataclass
    class HTTPServer:
        y: int

    @dataclasses.dataclass
    class SMTPServer:
        z: int

    HTTPServer1 = NewType("HTTPServer1", HTTPServer)
    HTTPServer2 = NewType("HTTPServer2", HTTPServer)

    @dataclasses.dataclass
    class Subparser:
        x: int
        bc: Union[HTTPServer1, HTTPServer2, SMTPServer]

    assert tyro.cli(
        Subparser, args=["--x", "1", "bc:http-server1", "--bc.y", "3"]
    ) == Subparser(x=1, bc=HTTPServer1(HTTPServer(y=3)))
    assert tyro.cli(
        Subparser, args=["--x", "1", "bc:http-server2", "--bc.y", "3"]
    ) == Subparser(x=1, bc=HTTPServer2(HTTPServer(y=3)))
    assert tyro.cli(
        Subparser, args=["--x", "1", "bc:smtp-server", "--bc.z", "3"]
    ) == Subparser(x=1, bc=SMTPServer(z=3))

    with pytest.raises(SystemExit):
        # Missing subcommand.
        tyro.cli(Subparser, args=["--x", "1"])
    with pytest.raises(SystemExit):
        # Wrong field.
        tyro.cli(Subparser, args=["--x", "1", "bc:http-server1", "--bc.z", "3"])
    with pytest.raises(SystemExit):
        # Wrong field.
        tyro.cli(Subparser, args=["--x", "1", "bc:smtp-server", "--bc.y", "3"])


def test_subparser_root() -> None:
    @dataclasses.dataclass
    class HTTPServer:
        y: int

    @dataclasses.dataclass
    class SMTPServer:
        z: int

    @dataclasses.dataclass
    class Subparser:
        x: int
        bc: Union[HTTPServer, SMTPServer]

    assert tyro.cli(
        Union[HTTPServer, SMTPServer],
        args=["http-server", "--y", "3"],  # type: ignore
    ) == HTTPServer(y=3)


def test_subparser_with_default() -> None:
    @dataclasses.dataclass
    class DefaultHTTPServer:
        y: int

    @dataclasses.dataclass
    class DefaultSMTPServer:
        z: int

    @dataclasses.dataclass
    class DefaultSubparser:
        x: int
        bc: Union[DefaultHTTPServer, DefaultSMTPServer] = dataclasses.field(
            default_factory=lambda: DefaultHTTPServer(5)
        )

    assert (
        tyro.cli(
            DefaultSubparser, args=["--x", "1", "bc:default-http-server", "--bc.y", "5"]
        )
        == tyro.cli(DefaultSubparser, args=["--x", "1"])
        == DefaultSubparser(x=1, bc=DefaultHTTPServer(y=5))
    )
    assert tyro.cli(
        DefaultSubparser, args=["--x", "1", "bc:default-smtp-server", "--bc.z", "3"]
    ) == DefaultSubparser(x=1, bc=DefaultSMTPServer(z=3))
    assert (
        tyro.cli(
            DefaultSubparser, args=["--x", "1", "bc:default-http-server", "--bc.y", "8"]
        )
        == tyro.cli(
            DefaultSubparser,
            args=[],
            default=DefaultSubparser(x=1, bc=DefaultHTTPServer(y=8)),
        )
        == DefaultSubparser(x=1, bc=DefaultHTTPServer(y=8))
    )

    with pytest.raises(SystemExit):
        tyro.cli(DefaultSubparser, args=["--x", "1", "b", "--bc.z", "3"])
    with pytest.raises(SystemExit):
        tyro.cli(DefaultSubparser, args=["--x", "1", "c", "--bc.y", "3"])


def test_subparser_with_default_and_newtype() -> None:
    @dataclasses.dataclass
    class DefaultHTTPServer_:
        y: int

    DefaultHTTPServer__ = NewType("DefaultHTTPServer__", DefaultHTTPServer_)
    DefaultHTTPServer = NewType("DefaultHTTPServer", DefaultHTTPServer__)  # type: ignore
    # ^nesting NewType is not technically allowed and pyright will complain,
    # but we should try to be robust to it anyways.

    def make_http_server(y: int) -> DefaultHTTPServer:
        return DefaultHTTPServer(DefaultHTTPServer__(DefaultHTTPServer_(y)))

    @dataclasses.dataclass
    class DefaultSMTPServer:
        z: int

    @dataclasses.dataclass
    class DefaultSubparser:
        x: int
        bc: Union[DefaultHTTPServer, DefaultSMTPServer] = dataclasses.field(
            default_factory=lambda: make_http_server(5)
        )

    assert (
        tyro.cli(
            DefaultSubparser, args=["--x", "1", "bc:default-http-server", "--bc.y", "5"]
        )
        == tyro.cli(DefaultSubparser, args=["--x", "1"])
        == DefaultSubparser(x=1, bc=make_http_server(y=5))
    )
    assert tyro.cli(
        DefaultSubparser, args=["--x", "1", "bc:default-smtp-server", "--bc.z", "3"]
    ) == DefaultSubparser(x=1, bc=DefaultSMTPServer(z=3))
    assert (
        tyro.cli(
            DefaultSubparser, args=["--x", "1", "bc:default-http-server", "--bc.y", "8"]
        )
        == tyro.cli(
            DefaultSubparser,
            args=[],
            default=DefaultSubparser(x=1, bc=make_http_server(y=8)),
        )
        == DefaultSubparser(x=1, bc=make_http_server(y=8))
    )

    with pytest.raises(SystemExit):
        tyro.cli(DefaultSubparser, args=["--x", "1", "b", "--bc.z", "3"])
    with pytest.raises(SystemExit):
        tyro.cli(DefaultSubparser, args=["--x", "1", "c", "--bc.y", "3"])


def test_subparser_with_default_alternate() -> None:
    @dataclasses.dataclass
    class DefaultInstanceHTTPServer:
        y: int = 0

    @dataclasses.dataclass
    class DefaultInstanceSMTPServer:
        z: int = 0

    @dataclasses.dataclass
    class DefaultInstanceSubparser:
        x: int
        bc: Union[DefaultInstanceHTTPServer, DefaultInstanceSMTPServer]

    assert (
        tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "5"],
        )
        == tyro.cli(
            DefaultInstanceSubparser,
            args=[],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5)),
        )
        == tyro.cli(
            DefaultInstanceSubparser,
            args=["bc:default-instance-http-server"],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5))
    )
    assert tyro.cli(
        DefaultInstanceSubparser,
        args=["bc:default-instance-smtp-server", "--bc.z", "3"],
        default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=5)),
    ) == DefaultInstanceSubparser(x=1, bc=DefaultInstanceSMTPServer(z=3))
    assert (
        tyro.cli(
            DefaultInstanceSubparser,
            args=["--x", "1", "bc:default-instance-http-server", "--bc.y", "8"],
        )
        == tyro.cli(
            DefaultInstanceSubparser,
            args=[],
            default=DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=8)),
        )
        == DefaultInstanceSubparser(x=1, bc=DefaultInstanceHTTPServer(y=8))
    )

    with pytest.raises(SystemExit):
        tyro.cli(DefaultInstanceSubparser, args=["--x", "1", "b", "--bc.z", "3"])
    with pytest.raises(SystemExit):
        tyro.cli(DefaultInstanceSubparser, args=["--x", "1", "c", "--bc.y", "3"])


def test_subparser_with_default_bad() -> None:
    @dataclasses.dataclass
    class DefaultHTTPServer:
        y: int

    @dataclasses.dataclass
    class DefaultSMTPServer:
        z: int

    @dataclasses.dataclass
    class DefaultSubparser:
        x: int
        bc: Union[DefaultHTTPServer, DefaultSMTPServer] = dataclasses.field(
            default_factory=lambda: 5  # type: ignore
        )

    # Tolerate bad static types: https://github.com/brentyi/tyro/issues/20
    # Should give us a bunch of warnings!
    with pytest.warns(UserWarning):
        assert tyro.cli(DefaultSubparser, args=["--x", "1"]) == DefaultSubparser(
            1,
            5,  # type: ignore
        )


def test_subparser_with_default_bad_alt() -> None:
    @dataclasses.dataclass
    class A:
        a: int

    @tyro.conf.configure(tyro.conf.subcommand(name="bbbb"))
    @dataclasses.dataclass
    class B:
        b: int

    @dataclasses.dataclass
    class C:
        c: int

    with pytest.warns(UserWarning):
        assert tyro.cli(
            Union[A, Annotated[B, None]],  # type: ignore
            default=C(3),
            args=["c", "--c", "2"],
        ) == C(2)


def test_optional_subparser() -> None:
    @dataclasses.dataclass
    class OptionalHTTPServer:
        y: int

    @dataclasses.dataclass
    class OptionalSMTPServer:
        z: int

    @dataclasses.dataclass
    class OptionalSubparser:
        x: int
        bc: Optional[Union[OptionalHTTPServer, OptionalSMTPServer]]

    assert tyro.cli(
        OptionalSubparser, args=["--x", "1", "bc:optional-http-server", "--bc.y", "3"]
    ) == OptionalSubparser(x=1, bc=OptionalHTTPServer(y=3))
    assert tyro.cli(
        OptionalSubparser, args=["--x", "1", "bc:optional-smtp-server", "--bc.z", "3"]
    ) == OptionalSubparser(x=1, bc=OptionalSMTPServer(z=3))
    assert tyro.cli(
        OptionalSubparser, args=["--x", "1", "bc:None"]
    ) == OptionalSubparser(x=1, bc=None)

    with pytest.raises(SystemExit):
        # Wrong field.
        tyro.cli(
            OptionalSubparser,
            args=["--x", "1", "bc:optional-http-server", "--bc.z", "3"],
        )
    with pytest.raises(SystemExit):
        # Wrong field.
        tyro.cli(
            OptionalSubparser,
            args=["--x", "1", "bc:optional-smtp-server", "--bc.y", "3"],
        )


def test_post_init_default() -> None:
    @dataclasses.dataclass
    class DataclassWithDynamicDefault:
        x: int = 3
        y: Optional[int] = None

        def __post_init__(self):
            # If unspecified, set y = x.
            if self.y is None:
                self.y = self.x

    @dataclasses.dataclass
    class NoDefaultPostInitArgs:
        inner: DataclassWithDynamicDefault

    @dataclasses.dataclass
    class DefaultFactoryPostInitArgs:
        inner: DataclassWithDynamicDefault = dataclasses.field(
            default_factory=DataclassWithDynamicDefault
        )

    assert (
        tyro.cli(NoDefaultPostInitArgs, args=["--inner.x", "5"]).inner
        == tyro.cli(DefaultFactoryPostInitArgs, args=["--inner.x", "5"]).inner
        == DataclassWithDynamicDefault(x=5, y=5)
    )


def test_multiple_subparsers() -> None:
    @dataclasses.dataclass
    class Subcommand1:
        x: int = 0

    @dataclasses.dataclass
    class Subcommand2:
        y: int = 1

    @dataclasses.dataclass
    class Subcommand3:
        z: int = 2

    @dataclasses.dataclass
    class MultipleSubparsers:
        a: Union[Subcommand1, Subcommand2, Subcommand3]
        b: Union[Subcommand1, Subcommand2, Subcommand3]
        c: Union[Subcommand1, Subcommand2, Subcommand3]

    with pytest.raises(SystemExit):
        tyro.cli(MultipleSubparsers, args=[])

    assert tyro.cli(
        MultipleSubparsers, args="a:subcommand1 b:subcommand2 c:subcommand3".split(" ")
    ) == MultipleSubparsers(Subcommand1(), Subcommand2(), Subcommand3())

    assert tyro.cli(
        MultipleSubparsers,
        args="a:subcommand1 --a.x 5 b:subcommand2 --b.y 7 c:subcommand3 --c.z 3".split(
            " "
        ),
    ) == MultipleSubparsers(Subcommand1(x=5), Subcommand2(y=7), Subcommand3(z=3))

    assert tyro.cli(
        MultipleSubparsers,
        args="a:subcommand2 --a.y 5 b:subcommand1 --b.x 7 c:subcommand3 --c.z 3".split(
            " "
        ),
    ) == MultipleSubparsers(Subcommand2(y=5), Subcommand1(x=7), Subcommand3(z=3))

    assert tyro.cli(
        MultipleSubparsers,
        args="a:subcommand3 --a.z 5 b:subcommand1 --b.x 7 c:subcommand3 --c.z 3".split(
            " "
        ),
    ) == MultipleSubparsers(Subcommand3(z=5), Subcommand1(x=7), Subcommand3(z=3))


def test_multiple_subparsers_with_default() -> None:
    @dataclasses.dataclass(frozen=True)
    class Subcommand1:
        x: int = 0

    @dataclasses.dataclass(frozen=True)
    class Subcommand2:
        y: int = 1

    @dataclasses.dataclass(frozen=True)
    class Subcommand3:
        z: int = 2

    @dataclasses.dataclass
    class MultipleSubparsers:
        a: Union[Subcommand1, Subcommand2, Subcommand3] = Subcommand1(tyro.MISSING)
        b: Union[Subcommand1, Subcommand2, Subcommand3] = Subcommand2(7)
        c: Union[Subcommand1, Subcommand2, Subcommand3] = Subcommand3(3)

    with pytest.raises(SystemExit):
        tyro.cli(
            MultipleSubparsers,
            args=[],
        )

    assert tyro.cli(
        MultipleSubparsers,
        args=["a:subcommand1", "--a.x", "5"],
    ) == MultipleSubparsers(Subcommand1(x=5), Subcommand2(y=7), Subcommand3(z=3))

    assert tyro.cli(
        MultipleSubparsers,
        args="a:subcommand1 --a.x 3".split(" "),
    ) == MultipleSubparsers(Subcommand1(x=3), Subcommand2(y=7), Subcommand3(z=3))

    with pytest.raises(SystemExit):
        tyro.cli(
            MultipleSubparsers,
            args=[],
            default=MultipleSubparsers(
                Subcommand1(),
                Subcommand2(),
                Subcommand3(tyro.MISSING),
            ),
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            MultipleSubparsers,
            args=[
                "a:subcommand1",
            ],
            default=MultipleSubparsers(
                Subcommand1(),
                Subcommand2(),
                Subcommand3(tyro.MISSING),
            ),
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            MultipleSubparsers,
            args=["a:subcommand1", "b:subcommand2"],
            default=MultipleSubparsers(
                Subcommand1(),
                Subcommand2(),
                Subcommand3(tyro.MISSING),
            ),
        )
    with pytest.raises(SystemExit):
        tyro.cli(
            MultipleSubparsers,
            args=["a:subcommand1", "b:subcommand2", "c:subcommand3"],
            default=MultipleSubparsers(
                Subcommand1(),
                Subcommand2(),
                Subcommand3(tyro.MISSING),
            ),
        )
    assert tyro.cli(
        MultipleSubparsers,
        args=["a:subcommand1", "b:subcommand2", "c:subcommand3", "--c.z", "3"],
        default=MultipleSubparsers(
            Subcommand1(),
            Subcommand2(),
            Subcommand3(tyro.MISSING),
        ),
    ) == MultipleSubparsers(Subcommand1(x=0), Subcommand2(y=1), Subcommand3(z=3))
    assert tyro.cli(
        MultipleSubparsers,
        args=["a:subcommand1", "b:subcommand2", "c:subcommand2"],
        default=MultipleSubparsers(
            Subcommand1(),
            Subcommand2(),
            Subcommand3(tyro.MISSING),
        ),
    ) == MultipleSubparsers(Subcommand1(x=0), Subcommand2(y=1), Subcommand2(y=1))


def test_nested_subparsers_with_default() -> None:
    @dataclasses.dataclass(frozen=True)
    class Subcommand1:
        x: int = 0

    @dataclasses.dataclass(frozen=True)
    class Subcommand3:
        z: int = 2

    @dataclasses.dataclass(frozen=True)
    class Subcommand2:
        y: Union[Subcommand1, Subcommand3]

    @dataclasses.dataclass(frozen=True)
    class MultipleSubparsers:
        a: Union[Subcommand1, Subcommand2] = Subcommand2(Subcommand1(tyro.MISSING))

    with pytest.raises(SystemExit):
        tyro.cli(MultipleSubparsers, args=[])
    with pytest.raises(SystemExit):
        tyro.cli(MultipleSubparsers, args=["a:subcommand2"])

    assert tyro.cli(
        MultipleSubparsers, args="a:subcommand1 --a.x 3".split(" ")
    ) == MultipleSubparsers(Subcommand1(3))
    assert tyro.cli(
        MultipleSubparsers, args="a:subcommand2 a.y:subcommand3 --a.y.z 2".split(" ")
    ) == MultipleSubparsers(Subcommand2(Subcommand3()))
    assert tyro.cli(
        MultipleSubparsers, args="a:subcommand2 a.y:subcommand3 --a.y.z 7".split(" ")
    ) == MultipleSubparsers(Subcommand2(Subcommand3(7)))
    assert tyro.cli(
        MultipleSubparsers, args="a:subcommand2 a.y:subcommand1 --a.y.x 7".split(" ")
    ) == MultipleSubparsers(Subcommand2(Subcommand1(7)))


def test_nested_subparsers_multiple() -> None:
    @dataclasses.dataclass(frozen=True)
    class Subcommand1:
        x: int = 0

    @dataclasses.dataclass(frozen=True)
    class Subcommand3:
        z: int = 2

    @dataclasses.dataclass(frozen=True)
    class Subcommand2:
        y: Union[Subcommand1, Subcommand3]

    @dataclasses.dataclass(frozen=True)
    class MultipleSubparsers:
        a: Union[Subcommand1, Subcommand2]
        b: Union[Subcommand1, Subcommand2]

    with pytest.raises(SystemExit):
        tyro.cli(MultipleSubparsers, args=[])
    assert tyro.cli(
        MultipleSubparsers, args="a:subcommand1 b:subcommand1".split(" ")
    ) == MultipleSubparsers(Subcommand1(), Subcommand1())
    assert tyro.cli(
        MultipleSubparsers,
        args="a:subcommand1 b:subcommand2 b.y:subcommand1".split(" "),
    ) == MultipleSubparsers(Subcommand1(), Subcommand2(Subcommand1()))
    assert tyro.cli(
        MultipleSubparsers,
        args="a:subcommand2 a.y:subcommand1 b:subcommand2 b.y:subcommand1".split(" "),
    ) == MultipleSubparsers(Subcommand2(Subcommand1()), Subcommand2(Subcommand1()))
    assert tyro.cli(
        MultipleSubparsers,
        args=(
            "a:subcommand2 a.y:subcommand1 --a.y.x 3 b:subcommand2 b.y:subcommand1"
            " --b.y.x 7".split(" ")
        ),
    ) == MultipleSubparsers(Subcommand2(Subcommand1(3)), Subcommand2(Subcommand1(7)))


def test_nested_subparsers_multiple_in_container() -> None:
    @dataclasses.dataclass(frozen=True)
    class Subcommand1:
        x: int = 0

    @dataclasses.dataclass(frozen=True)
    class Subcommand3:
        z: int = 2

    @dataclasses.dataclass(frozen=True)
    class Subcommand2:
        y: Union[Subcommand1, Subcommand3]

    @dataclasses.dataclass(frozen=True)
    class MultipleSubparsers:
        a: Union[Subcommand1, Subcommand2]
        b: Union[Subcommand1, Subcommand2]

    @dataclasses.dataclass(frozen=True)
    class Root:
        inner: MultipleSubparsers

    with pytest.raises(SystemExit):
        tyro.cli(Root, args=[])
    assert tyro.cli(
        Root, args="inner.a:subcommand1 inner.b:subcommand1".split(" ")
    ) == Root(MultipleSubparsers(Subcommand1(), Subcommand1()))
    assert tyro.cli(
        Root,
        args="inner.a:subcommand1 inner.b:subcommand2 inner.b.y:subcommand1".split(" "),
    ) == Root(MultipleSubparsers(Subcommand1(), Subcommand2(Subcommand1())))
    assert tyro.cli(
        Root,
        args=(
            "inner.a:subcommand2 inner.a.y:subcommand1 inner.b:subcommand2"
            " inner.b.y:subcommand1".split(" ")
        ),
    ) == Root(
        MultipleSubparsers(Subcommand2(Subcommand1()), Subcommand2(Subcommand1()))
    )
    assert tyro.cli(
        Root,
        args=(
            "inner.a:subcommand2 inner.a.y:subcommand1 --inner.a.y.x 3"
            " inner.b:subcommand2 inner.b.y:subcommand1 --inner.b.y.x 7".split(" ")
        ),
    ) == Root(
        MultipleSubparsers(Subcommand2(Subcommand1(3)), Subcommand2(Subcommand1(7)))
    )


def test_tuple_nesting() -> None:
    @dataclasses.dataclass(frozen=True)
    class Color:
        r: int
        g: int
        b: int

    @dataclasses.dataclass(frozen=True)
    class Location:
        x: float
        y: float
        z: float

    def main(x: Tuple[Tuple[Color], Location, float]):
        return x

    assert tyro.cli(
        main,
        args=(
            "--x.0.0.r 255 --x.0.0.g 0 --x.0.0.b 0 --x.1.x 5.0 --x.1.y 0.0"
            " --x.1.z 2.0 --x.2 4.0".split(" ")
        ),
    ) == ((Color(255, 0, 0),), Location(5.0, 0.0, 2.0), 4.0)


def test_tuple_nesting_union() -> None:
    @dataclasses.dataclass(frozen=True)
    class Color:
        r: int
        g: int
        b: int

    @dataclasses.dataclass(frozen=True)
    class Location:
        x: float
        y: float
        z: float

    def main(x: Union[Tuple[Tuple[Color], Location, float], Tuple[Color, Color]]):
        return x

    assert tyro.cli(
        main,
        args=(
            "x:tuple-tuple-color-location-float --x.0.0.r 255 --x.0.0.g 0 --x.0.0.b 0"
            " --x.1.x 5.0 --x.1.y 0.0 --x.1.z 2.0 --x.2 4.0".split(" ")
        ),
    ) == ((Color(255, 0, 0),), Location(5.0, 0.0, 2.0), 4.0)


def test_generic_subparsers() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass
    class A(Generic[T]):
        x: T

    def main(x: Union[A[int], A[float]]) -> Any:
        return x

    assert tyro.cli(main, args="x:a-float --x.x 3.2".split(" ")) == A(3.2)
    assert tyro.cli(main, args="x:a-int --x.x 3".split(" ")) == A(3)

    def main_with_default(x: Union[A[str], A[int]] = A(5)) -> Any:
        return x

    assert tyro.cli(main_with_default, args=[]) == A(5)
    assert tyro.cli(main_with_default, args=["x:a-str", "--x.x", "3"]) == A("3")


def test_generic_inherited() -> None:
    class UnrelatedParentClass:
        pass

    T = TypeVar("T")

    @dataclasses.dataclass
    class ActualParentClass(Generic[T]):
        x: T  # Documentation 1

        # Documentation 2
        y: T

        z: T = 3  # type: ignore
        """Documentation 3"""

    @dataclasses.dataclass
    class ChildClass(UnrelatedParentClass, ActualParentClass[int]):
        pass

    assert tyro.cli(
        ChildClass, args=["--x", "1", "--y", "2", "--z", "3"]
    ) == ChildClass(x=1, y=2, z=3)


def test_subparser_in_nested() -> None:
    @dataclasses.dataclass
    class A:
        a: int

    @dataclasses.dataclass
    class B:
        b: int

    @dataclasses.dataclass
    class Nested2:
        subcommand: Union[A, B]

    @dataclasses.dataclass
    class Nested1:
        nested2: Nested2

    @dataclasses.dataclass
    class Parent:
        nested1: Nested1

    assert tyro.cli(
        Parent,
        args="nested1.nested2.subcommand:a --nested1.nested2.subcommand.a 3".split(" "),
    ) == Parent(Nested1(Nested2(A(3))))
    assert tyro.cli(
        Parent,
        args="nested1.nested2.subcommand:b --nested1.nested2.subcommand.b 7".split(" "),
    ) == Parent(Nested1(Nested2(B(7))))


# def test_frozen_dict() -> None:
#     def main(
#         x: Mapping[str, float] = frozendict(  # type: ignore
#             {
#                 "num_epochs": 20,
#                 "batch_size": 64,
#             }
#         ),
#     ):
#         return x
#
#     assert hash(tyro.cli(main, args="--x.num-epochs 10".split(" "))) == hash(
#         frozendict({"num_epochs": 10, "batch_size": 64})  # type: ignore
#     )


def test_nested_in_subparser() -> None:
    # https://github.com/brentyi/tyro/issues/9
    @dataclasses.dataclass(frozen=True)
    class Subtype:
        data: int = 1

    @dataclasses.dataclass(frozen=True)
    class TypeA:
        subtype: Subtype = Subtype(1)

    @dataclasses.dataclass(frozen=True)
    class TypeB:
        subtype: Subtype = Subtype(2)

    @dataclasses.dataclass(frozen=True)
    class Wrapper:
        supertype: Union[TypeA, TypeB] = TypeA()

    assert tyro.cli(Wrapper, args=[]) == Wrapper()
    assert (
        tyro.cli(Wrapper, args="supertype:type-a --supertype.subtype.data 1".split(" "))
        == Wrapper()
    )


def test_nested_in_subparser_override_with_default() -> None:
    @dataclasses.dataclass(frozen=True)
    class Mnist:
        binary: bool = False
        """Set to load binary version of MNIST dataset."""

    @dataclasses.dataclass
    class ImageNet:
        subset: Literal[50, 100, 1000]
        """Choose between ImageNet-50, ImageNet-100, ImageNet-1000, etc."""

    # Possible optimizer configurations.

    Selector = tyro.extras.subcommand_type_from_defaults(
        {
            "m": Mnist(),
            "i": ImageNet(50),
        }
    )

    @dataclasses.dataclass(frozen=True)
    class DatasetContainer:
        dataset: Selector = Mnist()  # type: ignore

    @dataclasses.dataclass
    class Adam:
        learning_rate: float = 1e-3
        betas: Tuple[float, float] = (0.9, 0.999)
        container: DatasetContainer = DatasetContainer()

    @dataclasses.dataclass
    class Sgd:
        learning_rate: float = 3e-4
        container: DatasetContainer = DatasetContainer()

    # Train script.

    Optimizers = tyro.extras.subcommand_type_from_defaults(
        {"adam": Adam(container=DatasetContainer(ImageNet(50))), "sgd": Sgd()},
        prefix_names=False,
    )

    @tyro.conf.configure(tyro.conf.OmitSubcommandPrefixes)
    def train(
        optimizer: Optimizers = Adam(container=DatasetContainer(ImageNet(50))),  # type: ignore
    ) -> Union[Adam, Sgd]:
        return optimizer

    assert tyro.cli(train, args=[]) == Adam(container=DatasetContainer(ImageNet(50)))
    assert tyro.cli(train, args=["adam"]) == Adam(
        container=DatasetContainer(ImageNet(50))
    )
    assert tyro.cli(train, args=["sgd"]) == Sgd(container=DatasetContainer(Mnist()))


def test_underscore_prefix() -> None:
    """https://github.com/brentyi/tyro/issues/77"""

    @dataclasses.dataclass
    class PrivateConfig:
        pass

    @dataclasses.dataclass
    class BaseConfig:
        _private: PrivateConfig = dataclasses.field(
            default_factory=lambda: PrivateConfig()
        )

    @dataclasses.dataclass
    class Level1(BaseConfig):
        pass

    @dataclasses.dataclass
    class Level2(BaseConfig):
        child: Level1 = dataclasses.field(default_factory=lambda: Level1())

    @dataclasses.dataclass
    class Level3(BaseConfig):
        child: Level2 = dataclasses.field(default_factory=lambda: Level2())

    tyro.cli(Level3, args=[])


def test_subcommand_dict_helper() -> None:
    def checkout(branch: str) -> str:
        """Check out a branch."""
        return branch

    def commit(message: str, all: bool = False) -> Tuple[str, bool]:
        """Make a commit."""
        return (message, all)

    assert tyro.extras.subcommand_cli_from_dict(
        {
            "commit": commit,
        },
        args="commit --message hello --all".split(" "),
    ) == ("hello", True)
    assert (
        tyro.extras.subcommand_cli_from_dict(
            {
                "checkout": checkout,
                "commit": commit,
            },
            args="checkout --branch main".split(" "),
        )
        == "main"
    )
    assert tyro.extras.subcommand_cli_from_dict(
        {
            "checkout": checkout,
            "commit": commit,
        },
        args="commit --message hello".split(" "),
    ) == ("hello", False)
    assert tyro.extras.subcommand_cli_from_dict(
        {
            "checkout": checkout,
            "commit": commit,
        },
        args="commit --message hello --all".split(" "),
    ) == ("hello", True)


def test_subcommand_by_type_tree() -> None:
    @dataclasses.dataclass(frozen=True)
    class A:
        a: Union[int, str]

    @dataclasses.dataclass
    class Args:
        inner: Union[
            Annotated[A, tyro.conf.subcommand(name="alt", default=A(5))], A
        ] = A("hello")

    assert tyro.cli(Args, args=[]) == Args(A("hello"))
    assert "default: inner:alt" in get_helptext_with_checks(Args)


def test_annotated_narrow_0() -> None:
    @dataclasses.dataclass
    class A: ...

    @dataclasses.dataclass
    class B(A):
        x: int

    def main(x: Annotated[A, tyro.conf.OmitArgPrefixes] = B(x=3)) -> Any:
        return x

    assert tyro.cli(main, args=[]) == B(x=3)
    assert tyro.cli(main, args="--x 5".split(" ")) == B(x=5)


def test_annotated_narrow_1() -> None:
    @dataclasses.dataclass
    class A: ...

    @dataclasses.dataclass
    class B(A):
        x: int

    from tyro._resolver import narrow_subtypes

    assert narrow_subtypes(Annotated[A, False], B(3)) == Annotated[B, False]  # type: ignore


def test_union_with_dict() -> None:
    @dataclasses.dataclass(frozen=True)
    class Config:
        name: str
        age: int

    def main(config: Union[Config, dict] = {"name": "hello", "age": 25}) -> Any:
        return config

    assert tyro.cli(main, args=[]) == {"name": "hello", "age": 25}
    assert tyro.cli(main, args="config:dict".split(" ")) == {"name": "hello", "age": 25}
    assert tyro.cli(main, args="config:dict --config.age 27".split(" ")) == {
        "name": "hello",
        "age": 27,
    }
    assert tyro.cli(
        main, args="config:config --config.name world --config.age 27".split(" ")
    ) == Config(name="world", age=27)


def test_union_with_tuple() -> None:
    @dataclasses.dataclass(frozen=True)
    class Config:
        name: str
        age: int

    def main(config: Union[Config, tuple] = ("hello", 5)) -> Any:
        return config

    assert tyro.cli(main, args=[]) == ("hello", 5)
    assert tyro.cli(main, args="config:tuple".split(" ")) == ("hello", 5)
    assert tyro.cli(main, args="config:tuple hello 27".split(" ")) == ("hello", 27)
    assert tyro.cli(
        main, args="config:config --config.name world --config.age 27".split(" ")
    ) == Config(name="world", age=27)


def test_union_with_tuple_subscripted() -> None:
    @dataclasses.dataclass(frozen=True)
    class Config:
        name: str
        age: int

    def main(config: Union[Config, Tuple[str, int]] = ("hello", 5)) -> Any:
        return config

    assert tyro.cli(main, args=[]) == ("hello", 5)
    assert tyro.cli(main, args="config:tuple-str-int".split(" ")) == ("hello", 5)
    assert tyro.cli(main, args="config:tuple-str-int hello 27".split(" ")) == (
        "hello",
        27,
    )
    assert tyro.cli(
        main, args="config:config --config.name world --config.age 27".split(" ")
    ) == Config(name="world", age=27)


def test_union_with_tuple_autoexpand() -> None:
    @dataclasses.dataclass(frozen=True)
    class Config:
        name: str
        age: int

    # tyro should automatically expand this `Config` type to `Config | tuple`.
    def main(config: Config = ("hello", 5)) -> Any:  # type: ignore
        return config

    assert tyro.cli(main, args=[]) == ("hello", 5)
    assert tyro.cli(main, args="config:tuple".split(" ")) == ("hello", 5)
    assert tyro.cli(main, args="config:tuple hello 27".split(" ")) == ("hello", 27)
    assert tyro.cli(
        main, args="config:config --config.name world --config.age 27".split(" ")
    ) == Config(name="world", age=27)


def test_subcommand_default_with_conf_annotation() -> None:
    """Adapted from @mirceamironenco.

    https://github.com/brentyi/tyro/issues/221#issuecomment-2572850582
    """

    @dataclasses.dataclass(frozen=True)
    class OptimizerConfig:
        lr: float = 1e-1

    @dataclasses.dataclass(frozen=True)
    class AdamConfig(OptimizerConfig):
        adam_foo: float = 1.0

    @dataclasses.dataclass(frozen=True)
    class SGDConfig(OptimizerConfig):
        sgd_foo: float = 1.0

    def _constructor() -> Any:
        cfgs = [
            Annotated[SGDConfig, tyro.conf.subcommand(name="sgd")],
            Annotated[AdamConfig, tyro.conf.subcommand(name="adam")],
        ]
        return Union.__getitem__(tuple(cfgs))  # type: ignore

    @dataclasses.dataclass(frozen=True)
    class Config1:
        optimizer: Annotated[
            OptimizerConfig, tyro.conf.arg(constructor_factory=_constructor)
        ] = AdamConfig()
        foo: int = 1
        bar: str = "abc"

    assert "(default: optimizer:adam)" in get_helptext_with_checks(Config1)

    @dataclasses.dataclass(frozen=True)
    class Config2:
        optimizer: Annotated[
            OptimizerConfig, tyro.conf.arg(constructor_factory=_constructor)
        ] = SGDConfig()
        foo: int = 1
        bar: str = "abc"

    assert "(default: optimizer:sgd)" in get_helptext_with_checks(Config2)
