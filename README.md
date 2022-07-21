<h1 align="center">dcargs</h1>

<p align="center">
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

<p align="center">
    <emph><code>pip install dcargs</code></emph>
    &nbsp;&nbsp;&bull;&nbsp;&nbsp;
    <emph><a href="https://brentyi.github.io/dcargs">Documentation</a></emph>
</p>

<br />

<p align="center">
    <strong><code>dcargs</code></strong> is a library for typed CLI interfaces
    and configuration objects.
</p>

<p align="center">
    Our core interface, <code>dcargs.cli()</code>, generates argument parsers from type-annotated
    <br />callables: functions, classes, dataclasses, and <em>nested</em> dataclasses and classes.
</p>

<p align="center">
    This can be used as a drop-in replacement for <code>argparse</code>:
</p>

<table align="center">
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

<p align="center">
    For more sophisticated examples, see
    <a href="https://brentyi.github.io/dcargs">our documentation</a>.
</p>
