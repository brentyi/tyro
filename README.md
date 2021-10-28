# dcargs

![build](https://github.com/brentyi/dcargs/workflows/build/badge.svg)
![mypy](https://github.com/brentyi/dcargs/workflows/mypy/badge.svg?branch=master)
![lint](https://github.com/brentyi/dcargs/workflows/lint/badge.svg)

<!-- vim-markdown-toc GFM -->

* [Feature list](#feature-list)
* [Comparisons to alternative tools](#comparisons-to-alternative-tools)
* [Example usage](#example-usage)

<!-- vim-markdown-toc -->

`dcargs` is a tool for generating portable, reusable, and strongly typed CLI
interfaces from dataclass definitions.

We expose one function, `parse()`, which takes a dataclass type and instantiates
it via an argparse-style CLI interface. If we create a script called
`simple.py`:

```python
import dataclasses

import dcargs


@dataclasses.dataclass
class Args:
    field1: str  # A string field.
    field2: int  # A numeric field.


if __name__ == "__main__":
    args = dcargs.parse(Args)
    print(args)
```

Running `python simple.py --help` would print:

```
usage: simple.py [-h] --field1 STR --field2 INT

optional arguments:
  -h, --help    show this help message and exit

required arguments:
  --field1 STR  A string field.
  --field2 INT  A numeric field.
```

And, from `python simple.py --field1 string --field2 4`:

```
Args(field1='string', field2=4)
```

### Feature list

The parse function supports a wide range of dataclass definitions, while
automatically generating helptext from comments/docstrings. Some of the basic
features are shown in the [example below](#example-usage).

Our unit tests cover many more complex type annotations, including classes
containing:

- Types natively accepted by `argparse`: str, int, float, pathlib.Path, etc
- Default values for optional parameters
- Booleans, which are automatically converted to flags when provided a default
  value (eg `action="store_true"` or `action="store_false"`; in the latter case,
  we prefix names with `no-`)
- Enums (via `enum.Enum`; argparse's `choices` is populated and arguments are
  converted automatically)
- Various container types. Some examples:
  - `typing.ClassVar` types (omitted from parser)
  - `typing.Optional` types
  - `typing.Literal` types (populates argparse's `choices`)
  - `typing.Sequence` types (populates argparse's `nargs`)
  - `typing.List` types (populates argparse's `nargs`)
  - `typing.Tuple` types, such as `typing.Tuple[T1, T2, T3]` or
    `typing.Tuple[T, ...]` (populates argparse's `nargs`, and converts
    automatically)
  - `typing.Set` types (populates argparse's `nargs`, and converts
    automatically)
  - `typing.Final` types and `typing.Annotated` (for parsing, these are
    effectively no-ops)
  - Nested combinations of the above: `Optional[Literal[T]]`,
    `Final[Optional[Sequence[T]]]`, etc
- Nested dataclasses
  - Simple nesting (see `OptimizerConfig` example below)
  - Unions over nested dataclasses (subparsers)
  - Optional unions over nested dataclasses (optional subparsers)
- Generic dataclasses (including nested generics, see
  [./examples/generics.py](./examples/generics.py))

A usage example is available below. Examples of additional features can be found
in the [tests](./tests/).

### Comparisons to alternative tools

There are several alternative libraries to `dcargs`; here's a rough summary of
some of them:

|                                                                                                 | dataclasses | attrs | Nesting | Subparsers | Containers | Choices from literals                                    | Docstrings as helptext | Generics |
| ----------------------------------------------------------------------------------------------- | ----------- | ----- | ------- | ---------- | ---------- | -------------------------------------------------------- | ---------------------- | -------- |
| **dcargs**                                                                                      | ✓           |       | ✓       | ✓          | ✓          | ✓                                                        | ✓                      | ✓        |
| **[datargs](https://github.com/roee30/datargs)**                                                | ✓           | ✓     |         | ✓          | ✓          | ✓                                                        |                        |          |
| **[typed-argument-parser](https://github.com/swansonk14/typed-argument-parser)**                |             |       |         | ✓          | ✓          | ✓                                                        | ✓                      |          |
| **[simple-parsing](https://github.com/lebrice/SimpleParsing)**                                  | ✓           |       | ✓       | ✓          | ✓          | [soon](https://github.com/lebrice/SimpleParsing/pull/86) | ✓                      |          |
| **[argparse-dataclass](https://pypi.org/project/argparse-dataclass/)**                          | ✓           |       |         |            |            |                                                          |                        |          |
| **[argparse-dataclasses](https://pypi.org/project/argparse-dataclasses/)**                      | ✓           |       |         |            |            |                                                          |                        |          |
| **[dataclass-cli](https://github.com/malte-soe/dataclass-cli)**                                 | ✓           |       |         |            |            |                                                          |                        |          |
| **[clout](https://github.com/python-clout/clout)**                                              |             | ✓     | ✓       |            |            |                                                          |                        |          |
| **[hf_argparser](https://huggingface.co/transformers/_modules/transformers/hf_argparser.html)** | ✓           |       |         |            | ✓          |                                                          |                        |          |

Some other distinguishing factors that `dcargs` has put effort into:

- Robust handling of forward references
- Support for nested containers and generics
- Strong typing: we actively avoid relying on strings or dynamic namespace
  objects (eg `argparse.Namespace`)
- Simplicity + strict abstractions: we're focused on a single function API, and
  don't leak any argparse implementation details to the user level. We also
  intentionally don't offer any way to add argument parsing-specific logic to
  dataclass definitions. (in contrast, some of the libaries above rely heavily
  on dataclass field metadata, or on the more extreme end inheritance+decorators
  to make parsing-specific dataclasses)

### Example usage

This code:

```python
"""An argument parsing example.

Note that there are multiple possible ways to document dataclass attributes, all
of which are supported by the automatic helptext generator.
"""

import dataclasses
import enum

import dcargs


class OptimizerType(enum.Enum):
    ADAM = enum.auto()
    SGD = enum.auto()


@dataclasses.dataclass
class OptimizerConfig:
    # Variant of SGD to use.
    type: OptimizerType

    # Learning rate to use.
    learning_rate: float = 3e-4

    # Coefficient for L2 regularization.
    weight_decay: float = 1e-2


@dataclasses.dataclass
class ExperimentConfig:
    experiment_name: str  # Experiment name to use.

    optimizer: OptimizerConfig

    seed: int = 0
    """Random seed. This is helpful for making sure that our experiments are
    all reproducible!"""


if __name__ == "__main__":
  config = dcargs.parse(ExperimentConfig, description=__doc__)
  print(config)
```

Generates the following argument parser:

```
$ python example.py --help
usage: example.py [-h] --experiment-name STR --optimizer.type {ADAM,SGD} [--optimizer.learning-rate FLOAT]
                  [--optimizer.weight-decay FLOAT] [--seed INT]

An argument parsing example.

Note that there are multiple possible ways to document dataclass attributes, all
of which are supported by the automatic helptext generator.

optional arguments:
  -h, --help            show this help message and exit
  --optimizer.learning-rate FLOAT
                        Learning rate to use. (default: 0.0003)
  --optimizer.weight-decay FLOAT
                        Coefficient for L2 regularization. (default: 0.01)
  --seed INT            Random seed. This is helpful for making sure that our experiments are
                        all reproducible! (default: 0)

required arguments:
  --experiment-name STR
                        Experiment name to use.
  --optimizer.type {ADAM,SGD}
                        Variant of SGD to use.
```
