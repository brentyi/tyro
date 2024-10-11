"""Decorator-based Subcommands

:func:`tyro.extras.SubcommandApp()` provides a decorator-based API for
subcommands, which is inspired by `click <https://click.palletsprojects.com/>`_.

Usage:
`python my_script.py --help`
`python my_script.py greet --help`
`python my_script.py greet --name Alice`
`python my_script.py greet --name Bob --loud`
`python my_script.py addition --help`
`python my_script.py addition --a 5 --b 3`
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
