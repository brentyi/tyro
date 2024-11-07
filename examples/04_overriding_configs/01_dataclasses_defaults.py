"""Dataclasses + Defaults

The :code:`default=` argument can be used to override default values in dataclass
types.


.. note::

    When ``default=`` is used, we advise against mutation of configuration
    objects from a dataclass's :code:`__post_init__` method [#f1]_. In the
    example below, :code:`__post_init__` would be called twice: once for the
    :code:`Args()` object provided as a default value and another time for the
    :code:`Args()` objected instantiated by :func:`tyro.cli()`. This can cause
    confusing behavior! Instead, we show below one example of how derived
    fields can be defined immutably.

    .. [#f1] Official Python docs for ``__post_init__`` can be found `here <https://docs.python.org/3/library/dataclasses.html#dataclasses.__post_init__>`_.


Usage:

    python ./01_dataclasses_defaults.py --help
    python ./01_dataclasses_defaults.py --reps 3
    python ./01_dataclasses_defaults.py --string hello --reps 5
"""

import dataclasses

import tyro


@dataclasses.dataclass
class Args:
    """Description.
    This should show up in the helptext!"""

    string: str
    """A string field."""

    reps: int = 3
    """A numeric field, with a default value."""

    @property
    def derived_field(self) -> str:
        return ", ".join([self.string] * self.reps)


if __name__ == "__main__":
    args = tyro.cli(
        Args,
        default=Args(
            string="default string",
            reps=tyro.MISSING,
        ),
    )
    print(args.derived_field)
