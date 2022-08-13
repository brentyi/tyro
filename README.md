<h1 align="">dcargs</h1>

<p align="">
    <em><a href="https://brentyi.github.io/dcargs">Documentation</a></em>
    &nbsp;&nbsp;&bull;&nbsp;&nbsp;
    <em><code>pip install dcargs</code></em>
</p>
<p align="">
    <img alt="build" src="https://github.com/brentyi/dcargs/workflows/build/badge.svg" />
    <img alt="mypy" src="https://github.com/brentyi/dcargs/workflows/mypy/badge.svg?branch=master" />
    <img alt="lint" src="https://github.com/brentyi/dcargs/workflows/lint/badge.svg" />
    <a href="https://codecov.io/gh/brentyi/dcargs">
        <img alt="codecov" src="https://codecov.io/gh/brentyi/dcargs/branch/master/graph/badge.svg" />
    </a>
    <a href="https://pypi.org/project/dcargs/">
        <img alt="codecov" src="https://img.shields.io/pypi/pyversions/dcargs" />
    </a>
</p>

<p align="">
    <strong><code>dcargs</code></strong> is a library for typed CLI interfaces
    and configuration objects.
</p>

<p align="">
    Our core interface, <code>dcargs.cli()</code>, generates argument parsers from type-annotated
    <br />callables: functions, dataclasses, classes, and <em>nested</em> dataclasses and classes.
</p>

<p align="">
    This can be used as a replacement for <code>argparse</code>:
</p>

<table align="">
<tr>
    <td><strong>with argparse</strong></td>
    <td><strong>with dcargs</strong></td>
</tr>
<tr>
<td>

```python
"""Sum two numbers from argparse."""

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
"""Sum two numbers by calling a
function with dcargs."""

import dcargs

def main(a: int, b: int = 3) -> None:
    print(a + b)

dcargs.cli(main)
```

---

```python
"""Sum two numbers by instantiating
a dataclass with dcargs."""

from dataclasses import dataclass

import dcargs

@dataclass
class Args:
    a: int
    b: int = 3

args = dcargs.cli(Args)
print(args.a + args.b)
```

</td>
</tr>
</table>

<p align="">
    For more sophisticated examples, see
    <a href="https://brentyi.github.io/dcargs">our documentation</a>.
</p>
