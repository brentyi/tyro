import dcargs


class Args:
    def __init__(
        self,
        field1: str,
        field2: int,
        flag: bool = False,
    ):
        """Arguments.

        Args:
            field1: A string field.
            field2: A numeric field.
            flag: A boolean flag.
        """
        self.data = [field1, field2, flag]


if __name__ == "__main__":
    args = dcargs.cli(Args)
    print(args.data)
