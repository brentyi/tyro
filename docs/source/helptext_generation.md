# Helptext generation
In addition to type annotations, :func:`tyro.cli()` will also parse docstrings
and comments. These are used to automatically generate helptext; see examples
for how these end up being formatted.

## General callables
For general callables, field helptext is extracted from the corresponding field
docstring. Our examples use Google-style docstrings, but ReST, Numpydoc-style
and Epydoc docstrings are supported as well. Under the hood, all of these
options use [docstring_parser](https://github.com/rr-/docstring_parser).

```python
def main(field1: str, field2: int = 3) -> None:
    """Function, whose arguments will be populated from a CLI interface.
    Args:
        field1: A string field.
        field2: A numeric field, with a default value.
    """
    print(field1, field2)
```

## Dataclasses, TypedDict, NamedTuple
For types defined using class attributes, enumerating each argument list in the
class docstring can be cumbersome. If they are unavailable, :func:`tyro.cli`
will generate helptext from docstrings and comments on attributes. These are
parsed via source code inspection.

**(1) Attribute docstrings**

As per [PEP 257](https://peps.python.org/pep-0257/#what-is-a-docstring).

```python
@dataclasses.dataclass
class Args:
    field1: str
    """A string field."""
    field2: int = 3
    """A numeric field, with a default value."""
```

**(2) Inline comments**

Inline comments can be more succinct than true attribute docstrings.

```python
@dataclasses.dataclass
class Args:
    field1: str  # A string field.
    field2: int = 3  # A numeric field, with a default value.
```

This can be turned off using :data:`tyro.conf.HelptextFromCommentsOff`.

**(3) Preceding comments**

These can also be handy for semantically grouping fields, such as the two string
fields below.

```python
@dataclasses.dataclass
class Args:
    # String fields.
    field1: str
    field2: str
    # An integer field.
    # Multi-line comments are supported.
    field3: int
```

This can be turned off using :data:`tyro.conf.HelptextFromCommentsOff`.

## Support for [PEP 727](https://peps.python.org/pep-0727/) `Doc` objects

> ⚠️  As of this writing (2025-03-23), PEP 727 is in *draft* status and its
> future is far from certain. Please be advised that support for this could
> [disappear](https://github.com/python/typing_extensions/issues/443) from
> `typing_extensions` at some point, although the PEP sponsor and
> `typing_extensions` co-maintainer has expressed support for maintaining it
> [indefinitely](https://discuss.python.org/t/pep-727-documentation-metadata-in-typing/32566/183).

If you provide a PEP 727 `Doc` object in an `Annotated` type annotation,
then it will be the source of helptext for the corresponding attribute,
rather than docstrings or comments.

```python
@dataclasses.dataclass
class Config:
    input_file: Annotated[str, Doc("Path to the input file")]
    # The Doc string will become helptext for input_file
```

Note: the current evaluation method may not work on Pydantic objects
with these annotations.
