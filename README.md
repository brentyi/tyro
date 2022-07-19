# dcargs

![build](https://github.com/brentyi/dcargs/workflows/build/badge.svg)
![mypy](https://github.com/brentyi/dcargs/workflows/mypy/badge.svg?branch=master)
![lint](https://github.com/brentyi/dcargs/workflows/lint/badge.svg)
[![codecov](https://codecov.io/gh/brentyi/dcargs/branch/master/graph/badge.svg)](https://codecov.io/gh/brentyi/dcargs)
[![PyPI Python Version][pypi-versions-badge]][pypi]

[pypi-versions-badge]: https://img.shields.io/pypi/pyversions/dcargs
[pypi-badge]: https://badge.fury.io/py/dcargs.svg
[pypi]: https://pypi.org/project/dcargs/

**`dcargs`** is a library for typed CLI interfaces and configuration objects.

```
pip install dcargs
```

Our core interface generates argument parsers from type-annotated callables. In
the simplest case, this can be used as a drop-in replacement for `argparse`:

<table>
<tr>
<td><strong>with argparse</strong></td>
<td><strong>with dcargs</strong></td>
</tr>
<tr>
<td>

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "--a",
    type=int,
    required=True,
)
parser.add_argument(
    "--b",
    type=int,
    default=3,
)
args = parser.parse_args()

print(args.a + args.b)
```

</td>
<td>

```python
import dcargs

def main(a: int, b: int = 3) -> None:
    print(a + b)

dcargs.cli(main)
```

</td>
</tr>
</table>

The broader goal is to enable replacing configuration frameworks like `hydra`,
`gin-config`, and `ml_collections` with hierarchical structures built using
standard Python dataclasses and type annotations.

For a full list of features and usage examples, see
[**our documentation**](https://brentyi.github.io/dcargs).
