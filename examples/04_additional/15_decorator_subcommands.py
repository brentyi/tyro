"""Decorator-based Subcommands

:func:`tyro.extras.app.command()` and :func:`tyro.extras.app.cli()` provide a
decorator-based API for subcommands, which is inspired by `click
<https://click.palletsprojects.com/>`_.

Usage:
`python my_script.py greet Alice`
`python my_script.py greet Bob --loud`
`python my_script.py add 5 3`
"""

from tyro.extras import app


@app.command()
def greet(name: str, loud: bool = False):
    """Greet someone."""
    greeting = f"Hello, {name}!"
    if loud:
        greeting = greeting.upper()
    print(greeting)


@app.command()
def add(a: int, b: int):
    """Add two numbers."""
    print(f"{a} + {b} = {a + b}")


if __name__ == "__main__":
    app.cli()
