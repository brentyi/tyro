from dataclasses import dataclass


@dataclass(frozen=True, eq=False)
class _MutexGroupConfig:
    required: bool = False


def create_mutex_group(*, required: bool) -> object:
    """Create a mutually exclusive group for command-line arguments.

    When multiple arguments are annotated with the same mutex group, they become
    mutually exclusive - only one can be specified at a time via the CLI.

    Args:
        required: If True, exactly one argument from the group must be specified.
                  If False, at most one argument from the group can be specified.

    Returns:
        A configuration object to be used with :py:data:`typing.Annotated`.

    Example::

        import tyro
        from typing import Annotated

        # Create mutex groups.
        RequiredGroup = tyro.conf.create_mutex_group(required=True)
        OptionalGroup = tyro.conf.create_mutex_group(required=False)

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
    """
    return _MutexGroupConfig(required=required)
