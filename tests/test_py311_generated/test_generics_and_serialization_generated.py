import contextlib
import dataclasses
import enum
import io
from typing import (
    Annotated,
    Callable,
    Generic,
    List,
    NewType,
    Tuple,
    Type,
    TypeVar,
)

import pytest
import yaml
from helptext_utils import get_helptext_with_checks

import tyro

T = TypeVar("T")


def _check_serialization_identity(cls: Type[T], instance: T) -> None:
    assert tyro.extras.from_yaml(cls, tyro.extras.to_yaml(instance)) == instance


ScalarType = TypeVar("ScalarType")


@dataclasses.dataclass
class AGenericCallable(Generic[T]):
    x: Callable[..., T] = lambda: None  # type: ignore


def test_generic_callable() -> None:
    assert tyro.cli(AGenericCallable, args=[]) == AGenericCallable()


def test_tuple_generic_variable() -> None:
    @dataclasses.dataclass
    class TupleGenericVariable(Generic[ScalarType]):
        xyz: Tuple[ScalarType, ...]

    assert tyro.cli(
        TupleGenericVariable[int], args=["--xyz", "1", "2", "3"]
    ) == TupleGenericVariable((1, 2, 3))


def test_tuple_generic_variable_newtype() -> None:
    @dataclasses.dataclass
    class TupleGenericVariable(Generic[ScalarType]):
        xyz: Tuple[ScalarType, ...]

    SpecialInt = NewType("SpecialInt", int)
    assert tyro.cli(
        TupleGenericVariable[SpecialInt], args=["--xyz", "1", "2", "3"]
    ) == TupleGenericVariable((SpecialInt(1), SpecialInt(2), SpecialInt(3)))


def test_tuple_generic_variable_newtype_container() -> None:
    @dataclasses.dataclass
    class TupleGenericVariable(Generic[ScalarType]):
        xyz: Tuple[ScalarType, ...]

    SpecialInt = NewType("SpecialInt", Tuple[int])
    assert tyro.cli(
        TupleGenericVariable[SpecialInt], args=["--xyz", "1", "2", "3"]
    ) == TupleGenericVariable((SpecialInt((1,)), SpecialInt((2,)), SpecialInt((3,))))


def test_tuple_generic_variable_more_newtype() -> None:
    @dataclasses.dataclass
    class TupleGenericVariable(Generic[ScalarType]):
        xyz: Tuple[ScalarType, ...]

    SpecialInt = NewType("SpecialInt", int)
    SpecialTuple = NewType("SpecialTuple", TupleGenericVariable[SpecialInt])
    assert tyro.cli(SpecialTuple, args=["--xyz", "1", "2", "3"]) == SpecialTuple(
        TupleGenericVariable((SpecialInt(1), SpecialInt(2), SpecialInt(3)))
    )


def test_tuple_generic_helptext() -> None:
    @dataclasses.dataclass
    class TupleGenericVariableHelptext(Generic[ScalarType]):
        """Helptext!"""

        xyz: Tuple[ScalarType, ...]

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(TupleGenericVariableHelptext[int], args=["--help"])
    helptext = f.getvalue()
    assert "Helptext!" in helptext


def test_tuple_generic_no_helptext() -> None:
    @dataclasses.dataclass
    class TupleGenericVariableNoHelptext(Generic[ScalarType]):
        xyz: Tuple[ScalarType, ...]

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(TupleGenericVariableNoHelptext[int], args=["--help"])
    helptext = f.getvalue()
    assert "Helptext!" not in helptext

    # Check that we don't accidentally grab docstrings from the generic alias!
    assert "The central part of internal API" not in helptext


def test_tuple_generic_fixed() -> None:
    @dataclasses.dataclass
    class TupleGenericFixed(Generic[ScalarType]):
        xyz: Tuple[ScalarType, ScalarType, ScalarType]

    assert tyro.cli(
        TupleGenericFixed[int], args=["--xyz", "1", "2", "3"]
    ) == TupleGenericFixed((1, 2, 3))


class CoordinateFrame(enum.Enum):
    WORLD = enum.auto()
    CAMERA = enum.auto()


@dataclasses.dataclass
class Point3(Generic[ScalarType]):
    x: ScalarType
    y: ScalarType
    z: ScalarType
    frame: CoordinateFrame


def test_simple_generic() -> None:
    @dataclasses.dataclass
    class SimpleGeneric:
        point_continuous: Point3[float]
        point_discrete: Point3[int]

    parsed_instance = tyro.cli(
        SimpleGeneric,
        args=[
            "--point-continuous.x",
            "1.2",
            "--point-continuous.y",
            "2.2",
            "--point-continuous.z",
            "3.2",
            "--point-continuous.frame",
            "WORLD",
            "--point-discrete.x",
            "1",
            "--point-discrete.y",
            "2",
            "--point-discrete.z",
            "3",
            "--point-discrete.frame",
            "WORLD",
        ],
    )
    assert parsed_instance == SimpleGeneric(
        Point3(1.2, 2.2, 3.2, CoordinateFrame.WORLD),
        Point3(1, 2, 3, CoordinateFrame.WORLD),
    )
    _check_serialization_identity(SimpleGeneric, parsed_instance)

    with pytest.raises(SystemExit):
        # Accidentally pass in floats instead of ints for discrete
        tyro.cli(
            SimpleGeneric,
            args=[
                "--point-continuous.x",
                "1.2",
                "--point-continuous.y",
                "2.2",
                "--point-continuous.z",
                "3.2",
                "--point-continuous.frame",
                "WORLD",
                "--point-discrete.x",
                "1.5",
                "--point-discrete.y",
                "2.5",
                "--point-discrete.z",
                "3.5",
                "--point-discrete.frame",
                "WORLD",
            ],
        )


def test_multilevel_generic() -> None:
    @dataclasses.dataclass
    class Triangle(Generic[ScalarType]):
        a: Point3[ScalarType]
        b: Point3[ScalarType]
        c: Point3[ScalarType]

    parsed_instance = tyro.cli(
        Triangle[float],
        args=[
            "--a.x",
            "1.0",
            "--a.y",
            "1.2",
            "--a.z",
            "1.3",
            "--a.frame",
            "WORLD",
            "--b.x",
            "1.0",
            "--b.y",
            "1.2",
            "--b.z",
            "1.3",
            "--b.frame",
            "WORLD",
            "--c.x",
            "1.0",
            "--c.y",
            "1.2",
            "--c.z",
            "1.3",
            "--c.frame",
            "WORLD",
        ],
    )
    assert parsed_instance == Triangle(
        Point3(1.0, 1.2, 1.3, CoordinateFrame.WORLD),
        Point3(1.0, 1.2, 1.3, CoordinateFrame.WORLD),
        Point3(1.0, 1.2, 1.3, CoordinateFrame.WORLD),
    )
    _check_serialization_identity(Triangle[float], parsed_instance)


def test_multilevel_generic_no_helptext() -> None:
    @dataclasses.dataclass
    class LineSegment(Generic[ScalarType]):
        a: Point3[ScalarType]
        b: Point3[ScalarType]

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(LineSegment[int], args=["--help"])
    helptext = f.getvalue()

    # Check that we don't accidentally grab docstrings from the generic alias!
    assert "The central part of internal API" not in helptext


def test_generic_nested_dataclass() -> None:
    @dataclasses.dataclass
    class Child:
        a: int
        b: int

    T = TypeVar("T")

    @dataclasses.dataclass
    class DataclassGeneric(Generic[T]):
        child: T

    parsed_instance = tyro.cli(
        DataclassGeneric[Child], args=["--child.a", "5", "--child.b", "7"]
    )
    assert parsed_instance == DataclassGeneric(Child(5, 7))

    # Local generics will break.
    with pytest.raises(yaml.constructor.ConstructorError):
        _check_serialization_identity(DataclassGeneric[Child], parsed_instance)


def test_generic_nested_dataclass_helptext() -> None:
    @dataclasses.dataclass
    class Child:
        a: int
        b: int

    T = TypeVar("T")

    @dataclasses.dataclass
    class DataclassGeneric(Generic[T]):
        child: T

    f = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(f):
            tyro.cli(DataclassGeneric[Child], args=["--help"])
    helptext = f.getvalue()

    # Check that we don't accidentally grab docstrings from the generic alias!
    assert "The central part of internal API" not in helptext


def test_generic_subparsers() -> None:
    @dataclasses.dataclass
    class CommandOne:
        a: int

    @dataclasses.dataclass
    class CommandTwo:
        b: int

    T1 = TypeVar("T1")
    T2 = TypeVar("T2")

    @dataclasses.dataclass
    class Subparser(Generic[T1, T2]):
        command: T1 | T2

    parsed_instance = tyro.cli(
        Subparser[CommandOne, CommandTwo],
        args="command:command-one --command.a 5".split(" "),
    )
    # Not supported in mypy.
    assert parsed_instance == Subparser(CommandOne(5))  # type: ignore
    # Local generics will break.
    with pytest.raises(yaml.constructor.ConstructorError):
        _check_serialization_identity(
            Subparser[CommandOne, CommandTwo], parsed_instance
        )

    parsed_instance = tyro.cli(
        Subparser[CommandOne, CommandTwo],
        args="command:command-two --command.b 7".split(" "),
    )
    # Not supported in mypy.
    assert parsed_instance == Subparser(CommandTwo(7))  # type: ignore
    # Local generics will break.
    with pytest.raises(yaml.constructor.ConstructorError):
        _check_serialization_identity(
            Subparser[CommandOne, CommandTwo], parsed_instance
        )


def test_generic_subparsers_in_container() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass
    class Command(Generic[T]):
        a: List[T]

    T1 = TypeVar("T1")
    T2 = TypeVar("T2")

    @dataclasses.dataclass
    class Subparser(Generic[T1, T2]):
        command: T1 | T2

    parsed_instance = tyro.cli(
        Subparser[Command[int], Command[float]],
        args="command:command-int --command.a 5 3".split(" "),
    )
    # Not supported in mypy.
    assert parsed_instance == Subparser(Command([5, 3])) and isinstance(  # type: ignore
        parsed_instance.command.a[0], int
    )
    # Local generics will break.
    with pytest.raises(yaml.constructor.ConstructorError):
        _check_serialization_identity(
            Subparser[Command[int], Command[float]], parsed_instance
        )

    parsed_instance = tyro.cli(
        Subparser[Command[int], Command[float]],
        args="command:command-float --command.a 7 2".split(" "),
    )
    # Not supported in mypy.
    assert parsed_instance == Subparser(Command([7.0, 2.0])) and isinstance(  # type: ignore
        parsed_instance.command.a[0], float
    )
    # Local generics will break.
    with pytest.raises(yaml.constructor.ConstructorError):
        _check_serialization_identity(
            Subparser[Command[int], Command[float]], parsed_instance
        )


def test_serialize_missing() -> None:
    @dataclasses.dataclass
    class TupleGenericVariableMissing(Generic[ScalarType]):
        xyz: Tuple[ScalarType, ...]

    x = TupleGenericVariableMissing[int](xyz=(tyro.MISSING, tyro.MISSING))
    assert tyro.extras.to_yaml(x).count("!missing") == 2
    _check_serialization_identity(TupleGenericVariableMissing[int], x)
    assert (
        tyro.extras.from_yaml(
            TupleGenericVariableMissing[int], tyro.extras.to_yaml(x)
        ).xyz[0]
        is tyro.MISSING
    )


def test_generic_inherited_type_narrowing() -> None:
    T = TypeVar("T")

    @dataclasses.dataclass
    class ActualParentClass(Generic[T]):
        x: T  # Documentation 1

        # Documentation 2
        y: T

        z: T = 3  # type: ignore
        """Documentation 3"""

    @dataclasses.dataclass
    class ChildClass(ActualParentClass[int]):
        a: int = 7

    def main(x: ActualParentClass[int] = ChildClass(5, 5)) -> ActualParentClass:
        return x

    assert tyro.cli(main, args="--x.x 3".split(" ")) == ChildClass(3, 5, 3)


def test_pculbertson() -> None:
    # https://github.com/brentyi/tyro/issues/7

    @dataclasses.dataclass(frozen=True)
    class TypeA:
        data: int

    @dataclasses.dataclass
    class TypeB:
        data: int

    @dataclasses.dataclass
    class Wrapper:
        subclass: TypeA | TypeB = TypeA(1)

    wrapper1 = Wrapper()  # Create Wrapper object.
    assert wrapper1 == tyro.extras.from_yaml(Wrapper, tyro.extras.to_yaml(wrapper1))


def test_annotated() -> None:
    # https://github.com/brentyi/tyro/issues/7

    @dataclasses.dataclass(frozen=True)
    class TypeA:
        data: int

    @dataclasses.dataclass
    class Wrapper:
        subclass: Annotated[TypeA, int] = TypeA(1)

    wrapper1 = Wrapper()  # Create Wrapper object.
    assert wrapper1 == tyro.extras.from_yaml(Wrapper, tyro.extras.to_yaml(wrapper1))


@dataclasses.dataclass
class TypeA:
    data: int


@dataclasses.dataclass
class TypeASubclass(TypeA):
    pass


@dataclasses.dataclass
class Wrapper:
    subclass: TypeA


def test_superclass() -> None:
    # https://github.com/brentyi/tyro/issues/7

    wrapper1 = Wrapper(TypeASubclass(3))  # Create Wrapper object.
    assert wrapper1 == tyro.extras.from_yaml(Wrapper, tyro.extras.to_yaml(wrapper1))


@dataclasses.dataclass(frozen=True)
class A(Generic[T]):
    x: T


@dataclasses.dataclass(frozen=True)
class B(A[int], Generic[T]):
    y: T


def test_inheritance_with_same_typevar() -> None:
    """In this example, the same TypeVar should resolve to a different type depending on context."""
    assert "INT" in get_helptext_with_checks(B[int])
    assert "STR" not in get_helptext_with_checks(B[int])
    assert "STR" in get_helptext_with_checks(B[str])
    assert "INT" in get_helptext_with_checks(B[str])

    assert tyro.cli(B[str], args=["--x", "1", "--y", "2"]) == B(1, "2")
    assert tyro.cli(B[int], args=["--x", "1", "--y", "2"]) == B(1, 2)


def test_deeply_inherited_init() -> None:
    @dataclasses.dataclass
    class AConfig:
        a: int

    TContainsAConfig = TypeVar("TContainsAConfig", bound=AConfig)

    class AModel(Generic[TContainsAConfig]):
        def __init__(self, config: TContainsAConfig):
            self.config = config

    @dataclasses.dataclass
    class ABConfig(AConfig):
        b: int

    TContainsABConfig = TypeVar("TContainsABConfig", bound=ABConfig)

    class ABModel(AModel[TContainsABConfig], Generic[TContainsABConfig]):
        pass

    @dataclasses.dataclass
    class ABCConfig(ABConfig):
        c: int

    class Dummy: ...

    class ABCModel(Dummy, ABModel[ABCConfig]):
        pass

    def a(model: ABCModel):
        print(model.config)

    def b(model: ABModel[ABConfig]):
        print(model.config)

    def c(model: ABModel[ABCConfig]):
        print(model.config)

    assert "--model.config.a" in get_helptext_with_checks(a)
    assert "--model.config.b" in get_helptext_with_checks(a)
    assert "--model.config.c" in get_helptext_with_checks(a)

    assert "--model.config.a" in get_helptext_with_checks(b)
    assert "--model.config.b" in get_helptext_with_checks(b)
    assert "--model.config.c" not in get_helptext_with_checks(b)

    assert "--model.config.a" in get_helptext_with_checks(c)
    assert "--model.config.b" in get_helptext_with_checks(c)
    assert "--model.config.c" in get_helptext_with_checks(c)


def test_simple_bound_method() -> None:
    T = TypeVar("T")

    class Config(Generic[T]):
        def __init__(self, a: T) -> None: ...
        def method(self, a: T) -> T:
            return a

    assert tyro.cli(Config[int], args="--a 5".split(" ")).method(3) == 3
    assert tyro.cli(Config[int](3).method, args="--a 5".split(" ")) == 5
    with pytest.raises(tyro.constructors.UnsupportedTypeAnnotationError):
        tyro.cli(Config(3).method, args="--a 5".split(" "))


def test_inherited_bound_method() -> None:
    """From @deeptoaster: https://github.com/brentyi/tyro/issues/233"""

    @dataclasses.dataclass
    class AConfig:
        a: int

    TContainsAConfig = TypeVar("TContainsAConfig", bound=AConfig)

    class AModel(Generic[TContainsAConfig]):
        def __init__(self, config: TContainsAConfig):
            self.config = config

    TContainsAModel = TypeVar("TContainsAModel", bound=AModel)

    @dataclasses.dataclass
    class ABConfig(AConfig):
        b: int

    class ABModel(AModel[ABConfig]):
        pass

    class AHelper(Generic[TContainsAModel]):
        def spam(self, model: TContainsAModel) -> TContainsAModel:
            self.model = model
            return model

    class ABHelper(AHelper[ABModel]):
        def print_model(self) -> None:
            print(self.model.config)

    assert tyro.cli(
        ABHelper().spam, args="--model.config.a 5 --model.config.b 7".split(" ")
    ).config == ABConfig(5, 7)


def test_inherited_class_method() -> None:
    @dataclasses.dataclass
    class AConfig:
        a: int

    TContainsAConfig = TypeVar("TContainsAConfig", bound=AConfig)

    class AModel(Generic[TContainsAConfig]):
        def __init__(self, config: TContainsAConfig):
            self.config = config

    TContainsAModel = TypeVar("TContainsAModel", bound=AModel)

    @dataclasses.dataclass
    class ABConfig(AConfig):
        b: int

    class ABModel(AModel[ABConfig]):
        pass

    class AHelper(Generic[TContainsAModel]):
        model: TContainsAModel

        @classmethod
        def spam(cls, model: TContainsAModel):
            cls.model = model

    class ABHelper(AHelper[ABModel]):
        @classmethod
        def print_model(cls):
            print(cls.model)

    tyro.cli(ABHelper.spam, args="--model.config.a 5 --model.config.b 7".split(" "))
    assert ABHelper.model.config == ABConfig(5, 7)  # type: ignore
