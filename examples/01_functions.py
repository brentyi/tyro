"""CLI generation example from a simple annotated function. `dcargs.cli()` will call
`main()`, with arguments populated from the CLI."""

import dcargs


def main(
    field1: str,
    field2: int = 3,
    flag: bool = False,
) -> None:
    """Function, whose arguments will be populated from a CLI interface.

    Args:
        field1: A string field.
        field2: A numeric field, with a default value.
        flag: A boolean flag.
    """
    print(field1, field2, flag)


if __name__ == "__main__":
    dcargs.cli(main)
