from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, eq=False)
class _MutexGroupConfig:
    required: bool = False
    title: str | None = None


def create_mutex_group(*, required: bool, title: str | None = None) -> object:
    """Create a mutually exclusive group for command-line arguments.

    When multiple arguments are annotated with the same mutex group, they become
    mutually exclusive: only one can be specified at a time via the CLI.

    .. warning::
        Mutex groups are currently only supported for individual arguments (primitive
        types, enums, etc.), not for composite types like dataclasses or structs. To
        make fields within a dataclass mutually exclusive, annotate each field
        individually rather than the dataclass itself.

        For example, the annotation on ``Config`` will have no effect::

            @dataclass
            class Config:
                foo: int
                bar: str

            MutexGroup = tyro.conf.create_mutex_group(required=True)

            def main(
                config: Annotated[Config, MutexGroup],  # Has no effect!
                other: Annotated[int, MutexGroup],
            ): ...

        Instead, annotate individual fields within the dataclass.

    Args:
        required: If True, exactly one argument from the group must be specified.
                  If False, at most one argument from the group can be specified.
        title: Optional custom title for the argument group in the help text.
               If not provided, defaults to "mutually exclusive".

    Returns:
        A configuration object to be used with :py:data:`typing.Annotated`.

    Example::

        import tyro
        from typing import Annotated

        # Create mutex groups with optional custom titles.
        RequiredGroup = tyro.conf.create_mutex_group(
            required=True, title="output options"
        )
        OptionalGroup = tyro.conf.create_mutex_group(
            required=False, title="verbosity level"
        )

        def main(
            # Exactly one of these must be specified.
            option_a: Annotated[str | None, RequiredGroup] = None,
            option_b: Annotated[int | None, RequiredGroup] = None,
            # At most one of these can be specified.
            verbose: Annotated[bool, OptionalGroup] = False,
            quiet: Annotated[bool, OptionalGroup] = False,
        ) -> None:
            print(f"{option_a=}, {option_b=}, {verbose=}, {quiet=}")

        # DisallowNone prevents None from being a valid CLI choice.
        tyro.cli(main, config=(tyro.conf.DisallowNone,))

    In this example:
    - The user must specify either ``--option-a`` or ``--option-b``, but not both.
    - The user can optionally specify either ``--verbose`` or ``--quiet``, but not both.
    - Using :data:`DisallowNone` ensures that ``--option-a None`` is not accepted.
    - Custom titles appear in the help text instead of the default "mutually exclusive".
    """
    return _MutexGroupConfig(required=required, title=title)
