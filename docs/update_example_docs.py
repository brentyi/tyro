# mypy: ignore-errors
"""Helper script for updating the auto-generated examples pages in the documentation."""

from __future__ import annotations

import dataclasses
import io
import os
import pathlib
import pty
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union

from tqdm import tqdm

import tyro


def command_to_rst(
    command: list[str],
    cwd: Optional[Union[str, Path]] = None,
    shell: bool = False,
) -> Tuple[str, int]:
    """
    Run a command and format its output (including ANSI codes) as RST with HTML colors.
    Uses a pseudo-terminal to ensure ANSI color codes are output.

    Args:
        command: The command to run (string or list of strings)
        cwd: Working directory to run the command in (str or Path)
        shell: Whether to run the command through the shell

    Returns:
        Tuple of (formatted RST string, return code)
    """
    # Convert cwd to Path if provided
    if cwd is not None:
        cwd = Path(cwd).expanduser().resolve()
        if not cwd.exists():
            raise FileNotFoundError(f"Working directory does not exist: {cwd}")
        if not cwd.is_dir():
            raise NotADirectoryError(
                f"Working directory path is not a directory: {cwd}"
            )

    # Create a pseudo-terminal to capture colored output
    m, s = pty.openpty()

    # Set terminal type to ensure color support
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    process = subprocess.Popen(
        command,
        stdout=s,
        stderr=s,
        cwd=cwd,
        shell=shell,
        env=env,
        close_fds=True,
    )

    os.close(s)

    # Read output from the master end of the pseudo-terminal
    output = io.BytesIO()
    while True:
        try:
            data = os.read(m, 1024)
            if not data:
                break
            output.write(data)
        except OSError:
            break

    os.close(m)
    process.wait()

    # Decode the captured output
    output_str = output.getvalue().decode("utf-8", errors="replace")

    from ansi2html import Ansi2HTMLConverter

    # Create an Ansi2HTMLConverter instance
    converter = Ansi2HTMLConverter(inline=True, scheme="osx-basic")

    # Convert ANSI codes to HTML
    html_output = converter.convert(output_str, full=False)

    # Clean up any remaining ANSI codes (just in case)
    output_str = re.sub("\x1b\\[[0-9;]*[mGKH]", "", html_output)

    # Format as RST code block with HTML
    rst_output = ".. raw:: html\n\n"
    rst_output += '    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">\n'
    rst_output += f'    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>{shlex.join(command)}</strong>\n'

    # Indent and HTML-escape the content
    for line in output_str.splitlines():
        # We don't escape < and > because we want to preserve HTML tags
        # but we do escape & to prevent XML entities from being interpreted
        rst_output += f"    {line}\n"

    rst_output += "    </pre>\n"

    return rst_output, process.returncode


@dataclasses.dataclass
class ExampleMetadata:
    index: str
    index_with_zero: str
    source: str
    title: str
    usages: tuple[tuple[str, str]]  # (comment, command)
    description: str

    @staticmethod
    def from_path(path: pathlib.Path) -> ExampleMetadata:
        # 01_functions -> 01, _, functions.
        index, _, _ = path.stem.partition("_")

        # 01 -> 1.
        index_with_zero = index
        index = str(int(index))

        source = path.read_text().strip()

        docstring = source.split('"""')[1].strip()
        assert "Usage:" in docstring

        title, _, description = docstring.partition("\n")
        description, _, usage_text = description.partition("Usage:")

        example_usages: list[tuple[str, str]] = []
        comment = ""
        for usage_line in usage_text.splitlines():
            usage_line = usage_line.strip()
            if usage_line.startswith("#"):
                comment += usage_line.strip().lstrip("#").strip() + "\n"
            elif usage_line.startswith("python"):
                example_usages.append((comment.strip(), usage_line))
                comment = ""
            # else:
            #     assert len(usage_line) == 0, usage_line

        return ExampleMetadata(
            index=index,
            index_with_zero=index_with_zero,
            source=source.partition('"""')[2].partition('"""')[2].strip(),
            title=title,
            usages=tuple(example_usages),
            description=description.strip(),
        )


def get_example_paths(examples_dir: pathlib.Path) -> Iterable[pathlib.Path]:
    return filter(
        lambda p: not p.name.startswith("_"), sorted(examples_dir.glob("**/*.py"))
    )


REPO_ROOT = pathlib.Path(__file__).absolute().parent.parent


def main(
    examples_dir: pathlib.Path = REPO_ROOT / "examples",
    sphinx_source_dir: pathlib.Path = REPO_ROOT / "docs" / "source",
) -> None:
    print("\nStarting documentation update...")
    print(f"Examples directory: {examples_dir}")
    print(f"Sphinx source directory: {sphinx_source_dir}")

    example_doc_dir = sphinx_source_dir / "examples"
    print(f"Cleaning up old docs directory: {example_doc_dir}")
    shutil.rmtree(example_doc_dir)
    example_doc_dir.mkdir()

    category_set: set[str] = set()

    from concurrent.futures import ThreadPoolExecutor

    def process_example(path, examples_dir, REPO_ROOT):
        print(f"Processing example: {path.name}")
        ex = ExampleMetadata.from_path(path)
        usage_lines = []
        for comment, usage in ex.usages:
            usage_lines += [
                "",
                f"{comment}",
                "",
            ] + command_to_rst(shlex.split(usage), cwd=path.parent)[0].splitlines()

        category = path.parent.name

        example_content = "\n".join(
            [
                f".. _example-{path.stem}:",
                "",
                f"{ex.title}",
                "-" * len(ex.title),
                "",
                ex.description,
                "",
                "",
                ".. code-block:: python",
                "    :linenos:",
                "",
                f"    # {path.name}",
                "\n".join(
                    f"    {line}".rstrip()
                    for line in ex.source.replace("\n\n\n", "\n\n").splitlines()
                ),
                "",
            ]
            + usage_lines
        )
        return category, example_content

    with ThreadPoolExecutor() as executor:
        futures = []
        for path in get_example_paths(examples_dir):
            futures.append(
                executor.submit(process_example, path, examples_dir, REPO_ROOT)
            )

        category_set = set()
        example_contents: dict[str, str] = {}
        for future in tqdm(futures, total=len(futures)):
            category, content = future.result()
            category_set.add(category)
            if category not in example_contents:
                example_contents[category] = []
            example_contents[category].append(content)

    print(f"\nProcessing {len(category_set)} categories...")
    for category in category_set:
        print(f"\nProcessing category: {category}")

        example_category_dir = examples_dir / category
        readme_path = example_category_dir / "README.rst"
        if readme_path.exists():
            print("Found", readme_path)
            readme_content = readme_path.read_text()
        else:
            category_title = " ".join(category.split("_")[1:]).title()
            readme_content = "\n".join(
                [
                    f"{category_title}",
                    "=" * len(category_title),
                ]
            )

        # 0_basics => basics
        number, _, category_clean = category.partition("_")
        int(number)

        output_file = example_doc_dir / f"{category_clean}.rst"
        print(f"Writing documentation to: {output_file}")
        output_file.write_text(
            "\n".join(
                [
                    (
                        ".. Comment: this file is automatically generated by"
                        " `update_example_docs.py`."
                    ),
                    "   It should not be modified manually.",
                    "",
                    f".. _example-category-{category_clean}:",
                    "",
                    readme_content,
                    "",
                ]
                + example_contents[category]
            ),
            encoding="utf-8",
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print("Starting example documentation generator...")
    tyro.cli(main, description=__doc__)
    print("\nDocumentation generation complete!")
