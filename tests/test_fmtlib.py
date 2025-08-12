from tyro import _fmtlib as fmtlib


def test_nested_box() -> None:
    lines = fmtlib.box["red"](
        fmtlib.text["red", "bold"]("Unrecognized argument"),
        fmtlib.rows(
            fmtlib.columns(
                (
                    fmtlib.box(
                        "title",
                        fmtlib.text["green"]("Unrecognized options: --hello"),
                    ),
                    0.15,
                ),
                (
                    fmtlib.box(
                        "title",
                        fmtlib.text["green"]("Unrecognized options: --hello"),
                    ),
                    20,
                ),
                fmtlib.box["green"](
                    fmtlib.text["magenta"]("title"),
                    fmtlib.text["bold"]("Unrecognized options: ", "--hello"),
                ),
            ),
            fmtlib.hr["red"](),
            fmtlib.text(
                "For full helptext, run [...]",
            ),
        ),
    ).render(container_width=80)
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


if __name__ == "__main__":
    test_nested_box()
