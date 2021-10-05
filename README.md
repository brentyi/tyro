# dcargs

`dcargs` is argparse + datclasses, with the goal of generating portable,
reusable, and strongly typed CLI interfaces.

We expose only one function, which takes a dataclass type and instantiates it
via CLI flags:

```python
# Importable via dcargs.parse
def parse(cls: Type[DataclassType], description: str = "") -> DataclassType:
    ...
```

The parse function supports dataclasses containing:

- [x] Native types: str, int, float
- [x] Boolean flags
- [x] Enums (via `enum.Enum`)
- [x] Optional types
- [x] Literal types (by populating `choices`)
- [ ] Sequence and list types (by populating `nargs`)
- [x] Forward references (including in unions)
- [x] Automatic helptext generation
- [x] Nested dataclasses
  - [x] Simple nesting
  - [x] Unions over child structures (subparsers)

Very similar to [datargs](https://github.com/roee30/datargs) and
[simple-parsing](https://github.com/lebrice/SimpleParsing). Comparison coming
soon!

### Example

The following code:

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


config = dcargs.parse(ExperimentConfig)
print(config)
```

Generates the following argument parser:

```
$ python example.py --help
usage: example.py [-h] --experiment-name EXPERIMENT_NAME --optimizer-type {ADAM,SGD} [--optimizer-learning-rate OPTIMIZER_LEARNING_RATE]
                  [--optimizer-weight-decay OPTIMIZER_WEIGHT_DECAY] [--seed SEED]

An argument parsing example.

Note that there are multiple possible ways to document dataclass attributes, all
of which are supported by the automatic helptext generator.

optional arguments:
  -h, --help            show this help message and exit
  --optimizer-learning-rate OPTIMIZER_LEARNING_RATE
                        Learning rate to use. (float, default: 0.0003)
  --optimizer-weight-decay OPTIMIZER_WEIGHT_DECAY
                        Coefficient for L2 regularization. (float, default: 0.01)
  --seed SEED           Random seed. This is helpful for making sure that our experiments are
                        all reproducible! (int, default: 0)

required arguments:
  --experiment-name EXPERIMENT_NAME
                        Experiment name to use. (str)
  --optimizer-type {ADAM,SGD}
                        Variant of SGD to use. (str)
```
