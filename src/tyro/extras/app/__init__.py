"""This module provides a decorator-based API for subcommands in `tyro`, inspired by click.

Example:

```python
from tyro.extras import app

@app.command
def greet(name: str, loud: bool = False):
    '''Greet someone.'''
    greeting = f"Hello, {name}!"
    if loud:
        greeting = greeting.upper()
    print(greeting)

@app.command
def add(a: int, b: int):
    '''Add two numbers.'''
    print(f"{a} + {b} = {a + b}")

if __name__ == "__main__":
    app.cli()
```

Usage:
`python my_script.py greet Alice`
`python my_script.py greet Bob --loud`
`python my_script.py add 5 3`
"""

from ._tyro_app import cli as cli
from ._tyro_app import command as command
