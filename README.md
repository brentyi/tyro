# dcargs

![build](https://github.com/brentyi/dcargs/workflows/build/badge.svg)
![mypy](https://github.com/brentyi/dcargs/workflows/mypy/badge.svg?branch=master)
![lint](https://github.com/brentyi/dcargs/workflows/lint/badge.svg)

`dcargs` is a tool for generating portable, reusable, and strongly typed CLI
interfaces from dataclass definitions.

We expose one function, `parse(Type[T]) -> T`, which takes a dataclass type and
instantiates it via an argparse-style CLI interface:

```python
import dataclasses

import dcargs

@dataclasses.dataclass
class Args:
    field1: str
    field2: int

args = dcargs.parse(Args)
```

The parse function supports dataclasses containing a wide range of types. Our
unit tests currently cover:

- Types natively accepted by `argparse`: str, int, float, pathlib.Path, etc
- Booleans, which can have different behaviors based on default values (eg
  `action="store_true"` or `action="store_false"`)
- Enums (via `enum.Enum`)
- Various generic and container types:
  - `typing.Optional` types
  - `typing.Literal` types (populates `choices`)
  - `typing.Sequence` types (populates `nargs`)
  - `typing.List` types (populates `nargs`)
  - `typing.Tuple` types (populates `nargs`; must contain just one child type)
  - `typing.Optional[typing.Literal]` types
  - `typing.Optional[typing.Sequence]` types
  - `typing.Optional[typing.List]` types
  - `typing.Optional[typing.Tuple]` types
- Nested dataclasses
  - Simple nesting (see `OptimizerConfig` example below)
  - Unions over nested dataclasses (subparsers)
  - Optional unions over nested dataclasses (optional subparsers)

`dcargs.parse` will also:

- Generate helptext from field comments/docstrings
- Resolve forward references in type hints

A usage example is available below. Examples of additional features can be found
in the [unit tests](./tests/).

### Comparisons to alternative tools

There are several alternative libraries to `dcargs`; here's a rough summary of
some of them:

|                                                                                                 | Parsers from dataclasses | Parsers from attrs | Nested dataclasses | Subparsers (via Unions) | Containers | Choices from literals                                    | Docstrings as helptext |
| ----------------------------------------------------------------------------------------------- | ------------------------ | ------------------ | ------------------ | ----------------------- | ---------- | -------------------------------------------------------- | ---------------------- |
| **dcargs**                                                                                      | ✓                        |                    | ✓                  | ✓                       | ✓          | ✓                                                        | ✓                      |
| **[datargs](https://github.com/roee30/datargs)**                                                | ✓                        | ✓                  |                    | ✓                       | ✓          | ✓                                                        |                        |
| **[simple-parsing](https://github.com/lebrice/SimpleParsing)**                                  | ✓                        |                    | ✓                  | ✓                       | ✓          | [soon](https://github.com/lebrice/SimpleParsing/pull/86) | ✓                      |
| **[argparse-dataclass](https://pypi.org/project/argparse-dataclass/)**                          | ✓                        |                    |                    |                         |            |                                                          |                        |
| **[argparse-dataclasses](https://pypi.org/project/argparse-dataclasses/)**                      | ✓                        |                    |                    |                         |            |                                                          |                        |
| **[dataclass-cli](https://github.com/malte-soe/dataclass-cli)**                                 | ✓                        |                    |                    |                         |            |                                                          |                        |
| **[hf_argparser](https://huggingface.co/transformers/_modules/transformers/hf_argparser.html)** | ✓                        |                    |                    |                         | ✓          |                                                          |                        |

Aside from the raw feature list, `dcargs` also has robust handling of forward
references and more generic types, as well as some more philosphical design and
usage distinctions.

We choose strong typing and abstraction over configurability: we don't expose
any argparse implementation details, rely on any dynamic namespace objects (eg
`argparse.Namespace`) or string-based keys, and don't offer any way to add
argument parsing-specific code or logic to dataclass definitions (these should
be separate!). In contrast, many of the libraries above rely on field metadata
to specify helptext or argument choices, or otherwise focused on inheritance-
and decorator-based syntax for defining argument parsing-specific dataclasses.

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
