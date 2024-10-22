# Supported types

For minimum-boilerplate CLIs, `tyro` aims to maximize support of
Python's standard [typing](https://docs.python.org/3/library/typing.html)
features.

As a partial list, inputs can be annotated with:

- Basic types like `int`, `str`, `float`, `bool`, `pathlib.Path`, `None`.
- `datetime.date`, `datetime.datetime`, and `datetime.time`.
- Container types like `list`, `dict`, `tuple`, and `set`.
- Union types, like `X | Y`, `Union[X, Y]`, and `Optional[T]`.
- `typing.Literal` and `enum.Enum` .
- Type aliases, for example using Python 3.12's [PEP 695](https://peps.python.org/pep-0695/) `type` statement.
- Generics, such as those annotated with `typing.TypeVar` or with the type parameter syntax introduced by Python 3.12's [PEP 695](https://peps.python.org/pep-0695/).
- etc

Compositions of the above types, like `tuple[int | str, ...] | None`, are also supported.

Types can also be placed and nested in various structures, such as:

- `dataclasses.dataclass`.
- `attrs`, `pydantic`, and `flax.linen` models.
- `typing.NamedTuple`.
- `typing.TypedDict`, flags like `total=`, and associated annotations like `typing.Required`, `typing.NotRequired`, `typing.ReadOnly`,

### What's not supported

There are some limitations. We currently _do not_ support:

- Variable-length sequences over nested structures, unless a default is
  provided. For types like `list[Dataclass]`, we require a default value to
  infer length from. The length of the corresponding field cannot be changed
  from the CLI interface.
- Nesting variable-length sequences in other sequences. `tuple[int, ...]` and
  `tuple[tuple[int, int, int], ...]` are supported, as the variable-length
  sequence is the outermost type. However, `tuple[tuple[int, ...], ...]` is
  ambiguous to parse and not supported.
- Self-referential types, like `type RecursiveList[T] = T | list[RecursiveList[T]]`.

In each of these cases, a [custom
constructor](https://brentyi.github.io/tyro/examples/04_additional/11_custom_constructors/)
can be defined as a workaround.
