"""Decorator-based Subcommands

:func:`tyro.extras.SubcommandApp()` provides a decorator-based API for
subcommands, which is inspired by `click <https://click.palletsprojects.com/>`_.

Usage:

    python 04_decorator_subcommands.py --help
    python 04_decorator_subcommands.py greet --help
    python 04_decorator_subcommands.py greet --name Alice
    python 04_decorator_subcommands.py greet --name Bob --loud
    python 04_decorator_subcommands.py addition --help
    python 04_decorator_subcommands.py addition --a 5 --b 3
"""

from tyro.extras import SubcommandApp

app = SubcommandApp()


@app.command
def greet(name: str, loud: bool = False) -> None:
    """Greet someone."""
    greeting = f"Hello, {name}!"
    if loud:
        greeting = greeting.upper()
    print(greeting)


@app.command(name="addition")
def add(a: int, b: int) -> None:
    """Add two numbers."""
    print(f"{a} + {b} = {a + b}")


if __name__ == "__main__":
    app.cli()
