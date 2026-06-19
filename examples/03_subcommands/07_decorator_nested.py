"""Nested decorator-based subcommands

A :class:`tyro.extras.SubcommandApp` can be registered as a subcommand on
another :class:`tyro.extras.SubcommandApp`, producing a hierarchical CLI. Use
``aliases=`` for short names and ``is_default=True`` to pick which subcommand
runs when none is named.

Usage:

    python 07_decorator_nested.py --help
    python 07_decorator_nested.py db --help
    python 07_decorator_nested.py db migrate --version 7
    python 07_decorator_nested.py db seed --rows 5
    python 07_decorator_nested.py greet --name Alice
"""

from tyro.extras import SubcommandApp

# Nested app for database commands.
db = SubcommandApp()


@db.command(aliases=["m"])
def migrate(version: int = 1) -> None:
    """Apply schema migrations."""
    print(f"migrating to version {version}")


@db.command
def seed(rows: int = 10) -> None:
    """Populate with seed data."""
    print(f"seeding {rows} rows")


# Top-level app.
app = SubcommandApp()
app.command(db, name="db")


@app.command(is_default=True)
def greet(name: str = "world") -> None:
    """Default action when no subcommand is given."""
    print(f"hello {name}")


if __name__ == "__main__":
    app.cli()
