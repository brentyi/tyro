"""Helper script for updating the auto-generated examples pages in the documentation."""

from __future__ import annotations

import dataclasses
import pathlib
import shlex
from typing import Iterable

import dcargs


@dataclasses.dataclass
class ExampleMetadata:
    index: str
    index_with_zero: str
    source: str
    title: str
    usages: Iterable[str]
    description: str

    @staticmethod
    def from_path(path: pathlib.Path) -> ExampleMetadata:
        # 01_functions -> 01, _, functions.
        index, _, title = path.stem.partition("_")

        # 01 -> 1.
        index_with_zero = index
        index = str(int(index))

        # functions -> Functions.
        title = title.replace("_", " ").title()

        source = path.read_text().strip()

        docstring = source.split('"""')[1].strip()
        assert "Usage:" in docstring
        description, _, usage_text = docstring.partition("Usage:")
        example_usages = map(
            lambda x: x[1:-1],
            filter(
                lambda line: line.startswith("`") and line.endswith("`"),
                usage_text.split("\n"),
            ),
        )
        return ExampleMetadata(
            index=index,
            index_with_zero=index_with_zero,
            source=source[3:].partition('"""')[2].strip(),
            title=title,
            usages=example_usages,
            description=description,
        )


def get_example_paths(examples_dir: pathlib.Path) -> Iterable[pathlib.Path]:
    return filter(
        lambda p: not p.name.startswith("_"), sorted(examples_dir.glob("*.py"))
    )


REPO_ROOT = pathlib.Path(__file__).absolute().parent.parent


def main(
    examples_dir: pathlib.Path = REPO_ROOT / "examples",
    sphinx_source_dir: pathlib.Path = REPO_ROOT / "docs" / "source",
) -> None:
    for path in get_example_paths(examples_dir):
        ex = ExampleMetadata.from_path(path)
        path_for_sphinx = pathlib.Path("..") / ".." / path.relative_to(REPO_ROOT)

        usage_lines = []
        for usage in ex.usages:
            args = shlex.split(usage)
            python_index = args.index("python")
            sphinx_usage = shlex.join(
                args[:python_index]
                + ["python", path_for_sphinx.as_posix()]
                + args[python_index + 2 :]
            )

            usage_lines += [
                f".. command-output:: {sphinx_usage}",
                "",
            ]

        (sphinx_source_dir / f"example_{ex.index_with_zero}.rst").write_text(
            "\n".join(
                [
                    f"{ex.index}. {ex.title}",
                    "==========================================",
                    "",
                    ex.description,
                    "",
                    "",
                    "Example",
                    "------------------------------------------",
                    "",
                    "",
                    "",
                    ".. code-block:: python",
                    "       :linenos:",
                    "",
                    "       " + "\n       ".join(ex.source.split("\n")),
                    "",
                    "",
                    "",
                    "Usage",
                    "------------------------------------------",
                    "",
                ]
                + usage_lines
            )
        )


if __name__ == "__main__":
    dcargs.cli(main, description=__doc__)
