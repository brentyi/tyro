import textwrap

NESTED_DATACLASS_DELIMETER: str = "."
SUBPARSER_DEST_FMT: str = "{name} (positional)"


def dedent(text: str) -> str:
    """Same as textwrap.dedent, but ignores the first line."""
    first_line, line_break, rest = text.partition("\n")
    if line_break == "":
        return textwrap.dedent(text)
    return f"{first_line.strip()}\n{textwrap.dedent(rest)}"


def bool_from_string(text: str) -> bool:
    text = text.lower()
    if text in ("true", "1"):
        return True
    elif text in ("false", "0"):
        return False
    else:
        raise ValueError(f"Boolean value expected, but got {text}.")
