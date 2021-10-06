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
- Booleans, which are converted to flags (in argparse: `action="store_true"`)
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
  - Simple nesting
  - Unions over nested dataclasses (subparsers)
  - Optional unions over nested dataclasses (optional subparsers)

`dcargs.parse` will also:

- Generate helptext from field comments/docstrings
- Resolve forward references in type hints

A usage example is available below. Examples of additional features can be found
in the [unit tests](./tests/).

### Comparisons to existing tools

**[datargs](https://github.com/roee30/datargs)** was the largest inspiration for
`dcargs`. Use `datargs` if you need more fine-grained configurability, attrs
support, or automatic conversion from legacy argparse code to dataclass
definitions. Use `dcargs` if you'd prefer to keep argument parsing-specific code
out of your dataclasses, or want more simplicity, nested dataclasses, forward
references, or automatic helptext generation.

**[argparse-dataclass](https://pypi.org/project/argparse-dataclass/)** is also
similar and simple, but has fewer features and relies on field metadata for
specifying argparse options. In contrast, `dcargs` completely abstracts away the
underlying argparse interface, and has support for things like nested classes,
subparsers, and container types.

**[argparse-dataclasses](https://pypi.org/project/argparse-dataclasses/)** uses
an inheritance-based approach for building parsers from dataclasses. `dcargs` is
more functional, and has support for things like nested classes, subparsers, and
container types.

**[simple-parsing](https://github.com/lebrice/SimpleParsing)** is also a really
powerful library, with similar support for helptext generation, containers, and
nested dataclasses. Use `simple-parsing` if you don't mind a less minimalistic
design philosophy and are okay with slightly weaker typing (a la argparse
namespaces), or are willing to trade that off for more configurablity and
features. (for example, a single parser in simple-parsing can support multiple
dataclasses with different "destinations", and raw argparse-style arguments can
also be specified)

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
