import sys

from tyro import _fmtlib as fmt


def test_nested_box() -> None:
    box = fmt.box["red"](
        fmt.text["red", "bold"]("Unrecognized argument"),
        fmt.rows(
            fmt.cols(
                (
                    fmt.box(
                        "title",
                        fmt.text["green"]("Unrecognized options: --hello"),
                    ),
                    0.15,
                ),
                (
                    fmt.box(
                        "title",
                        fmt.text["green"]("Unrecognized options: --hello"),
                    ),
                    20,
                ),
                fmt.box["green"](
                    fmt.text["magenta"]("title"),
                    fmt.text["bold"]("Unrecognized options: ", "--hello"),
                ),
            ),
            fmt.hr["red"](),
            fmt.text(
                "For full helptext, run [...]",
            ),
        ),
    )

    _backup = sys.stdout.isatty
    sys.stdout.isatty = lambda: True  # type: ignore
    fmt._FORCE_UTF8_BOXES = True
    fmt._FORCE_ANSI = True
    lines = box.render(width=80)
    fmt._FORCE_UTF8_BOXES = False
    fmt._FORCE_ANSI = False
    sys.stdout.isatty = _backup  # type: ignore
    expected = [
        "\x1b[31m╭\x1b[0m\x1b[31m─\x1b[0m\x1b[m\x1b[0m\x1b[m \x1b[0m\x1b[31;1mUnrecognized\x1b[0m\x1b[31;1m argument\x1b[0m\x1b[m\x1b[0m\x1b[m \x1b[0m\x1b[31m──────────────────────────────────────────────────────╮\x1b[0m",
        "\x1b[31m│\x1b[0m \x1b[m╭\x1b[0m\x1b[m─\x1b[0m\x1b[m\x1b[0m\x1b[m \x1b[0m\x1b[mtitle\x1b[0m\x1b[m\x1b[0m\x1b[m \x1b[0m\x1b[m─╮\x1b[0m\x1b[m╭\x1b[0m\x1b[m─\x1b[0m\x1b[m\x1b[0m\x1b[m \x1b[0m\x1b[mtitle\x1b[0m\x1b[m\x1b[0m\x1b[m \x1b[0m\x1b[m──────────╮\x1b[0m\x1b[32m╭\x1b[0m\x1b[32m─\x1b[0m\x1b[m\x1b[0m\x1b[m \x1b[0m\x1b[35mtitle\x1b[0m\x1b[m\x1b[0m\x1b[m \x1b[0m\x1b[32m───────────────────────────────────╮\x1b[0m \x1b[31m│\x1b[0m",
        "\x1b[31m│\x1b[0m \x1b[m│\x1b[0m \x1b[32mUnrecog\x1b[0m \x1b[m│\x1b[0m\x1b[m│\x1b[0m \x1b[32mUnrecognized    \x1b[0m \x1b[m│\x1b[0m\x1b[32m│\x1b[0m \x1b[1mUnrecognized\x1b[0m\x1b[1m options:\x1b[0m\x1b[1m \x1b[0m\x1b[1m--hello            \x1b[0m \x1b[32m│\x1b[0m \x1b[31m│\x1b[0m",
        "\x1b[31m│\x1b[0m \x1b[m│\x1b[0m \x1b[32mnized\x1b[0m\x1b[32m o\x1b[0m \x1b[m│\x1b[0m\x1b[m│\x1b[0m \x1b[32moptions:\x1b[0m\x1b[32m --hello\x1b[0m \x1b[m│\x1b[0m\x1b[32m╰\x1b[0m\x1b[32m───────────────────────────────────────────\x1b[0m\x1b[32m╯\x1b[0m \x1b[31m│\x1b[0m",
        "\x1b[31m│\x1b[0m \x1b[m│\x1b[0m \x1b[32mptions:\x1b[0m \x1b[m│\x1b[0m\x1b[m╰\x1b[0m\x1b[m──────────────────\x1b[0m\x1b[m╯\x1b[0m                                              \x1b[31m│\x1b[0m",
        "\x1b[31m│\x1b[0m \x1b[m│\x1b[0m \x1b[32m--hello\x1b[0m \x1b[m│\x1b[0m                                                                  \x1b[31m│\x1b[0m",
        "\x1b[31m│\x1b[0m \x1b[m╰\x1b[0m\x1b[m─────────\x1b[0m\x1b[m╯\x1b[0m                                                                  \x1b[31m│\x1b[0m",
        "\x1b[31m│\x1b[0m \x1b[31m────────────────────────────────────────────────────────────────────────────\x1b[0m \x1b[31m│\x1b[0m",
        "\x1b[31m│\x1b[0m \x1b[mFor\x1b[0m\x1b[m full\x1b[0m\x1b[m helptext,\x1b[0m\x1b[m run\x1b[0m\x1b[m [...]                                                \x1b[0m \x1b[31m│\x1b[0m",
        "\x1b[31m╰\x1b[0m\x1b[31m──────────────────────────────────────────────────────────────────────────────\x1b[0m\x1b[31m╯\x1b[0m",
    ]
    assert lines == expected

    # Can run with `pytest -s` to check qualitatively.
    print()
    print(*lines, sep="\n")


def test_empty() -> None:
    assert fmt.rows().render(width=10) == []
    assert fmt.cols().render(width=10) == []


def test_scale_cols() -> None:
    assert fmt.cols(
        ("", 3),
        ("", 3),
        ("", 3),
    ).render(width=10) == [" " * 10]
    assert fmt.cols(
        ("", 3),
        ("", 3),
        ("", 3),
    ).render(width=8) == [" " * 8]


if __name__ == "__main__":
    test_nested_box()
