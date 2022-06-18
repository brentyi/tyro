import dcargs


def main(
    field1: str,
    field2: int,
    flag: bool = False,
) -> None:
    """Function, whose arguments will be populated from a CLI interface.

    Args:
        field1: First field.
        field2: Second field.
        flag: Boolean flag that we can set to true.
    """
    print(field1, field2, flag)


if __name__ == "__main__":
    dcargs.cli(main)
