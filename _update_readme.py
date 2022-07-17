"""Helper script for updating the auto-generated parts of the README. (docstring,
examples list)"""
import concurrent.futures
import dataclasses
import html
import inspect
import os
import pathlib
import shlex
import subprocess

import dcargs
import dcargs._strings


@dataclasses.dataclass(frozen=True)
class Constants:
    docstring_start: str = "<!-- START DOCSTRING -->"
    docstring_marker_end: str = "<!-- END DOCSTRING -->"

    examples_marker_start: str = "<!-- START EXAMPLES -->"
    examples_marker_end: str = "<!-- END EXAMPLES -->"


def replace_between_markers(
    content: str, marker_start: str, marker_end: str, inner: str
) -> str:
    """Puts `inner` between `marker_start` and `marker_end`."""
    assert marker_start in content
    assert marker_end in content
    before, _, after = content.partition(marker_start)
    _, _, after = content.rpartition(marker_end)
    return "".join([before, marker_start, inner, marker_end, after])


def format_script_for_readme(path: pathlib.Path) -> str:
    print("Handling:", path)

    # 01_functions -> 01, _, functions.
    index, _, title = path.stem.partition("_")

    # 01 -> 1.
    index = str(int(index))

    # functions -> Functions.
    title = title.replace("_", " ").title()

    source = path.read_text().strip()
    example_output_lines = []

    docstring = source.split('"""')[1].strip()
    assert "Usage:" in docstring
    description_text, _, usage_text = docstring.partition("Usage:")
    example_usages = map(
        lambda x: x[1:-1],
        filter(
            lambda line: line.startswith("`") and line.endswith("`"),
            usage_text.split("\n"),
        ),
    )
    for usage in example_usages:
        # Example usage: `ENV=something python ./path --help`
        args = shlex.split(usage)
        python_index = args.index("python")

        env_vars = {}
        if python_index > 0:
            env_vars = {
                k: v for (k, v) in map(lambda x: x.split("="), args[:python_index])
            }
        process_output = subprocess.run(
            args=["python", str(path)] + args[python_index + 2 :],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf8",
            env=dict(os.environ, **env_vars),
        )
        if process_output.stderr != "":
            output = dcargs._strings.strip_color_codes(process_output.stderr).strip()
        elif process_output.stdout != "":
            output = dcargs._strings.strip_color_codes(process_output.stdout).strip()
        else:
            assert False
        example_output_lines.extend(
            [
                "",
                "<pre>",
                f"<samp>$ <kbd>{usage}</kbd>",
                f"{html.escape(output)}</samp>",
                "</pre>",
            ]
        )

    return "\n".join(
        [
            "",
            "<details>",
            "<summary>",
            f"<strong>{index}. {title}</strong>",
            "</summary>",
            "<blockquote>",
            "",
            description_text,
            "",
            "\n".join(example_usages),
            "",
            f"**Code ([link]({path})):**",
            "",
            "```python",
            source[3:].partition('"""')[2].strip(),
            "```",
            "",
            "<br />",
            "",
            "**Example usage:**",
            "",
        ]
        + example_output_lines
        + [
            "",
            "</blockquote>",
            "</details>",
        ]
    )


def get_examples_str(examples_dir: pathlib.Path, constants: Constants) -> str:
    script_paths = filter(
        lambda p: not p.name.startswith("_"), sorted(examples_dir.glob("*.py"))
    )
    with concurrent.futures.ThreadPoolExecutor() as executor:
        return "\n".join(
            executor.map(
                format_script_for_readme,
                script_paths,
            )
        )


REPO_ROOT = pathlib.Path(__file__).parent


def main(
    readme_path: pathlib.Path = REPO_ROOT / "README.md",
    examples_dir: pathlib.Path = REPO_ROOT / "examples",
    constants: Constants = Constants(),
) -> None:
    """Helper script for generating the examples list in the README."""

    # Read.
    content = readme_path.read_text(encoding="utf8")

    # Update examples.
    content = replace_between_markers(
        content,
        constants.examples_marker_start,
        constants.examples_marker_end,
        get_examples_str(examples_dir, constants),
    )

    # Update docstring.
    content = replace_between_markers(
        content,
        constants.docstring_start,
        constants.docstring_marker_end,
        f"\n\n```\n{inspect.getdoc(dcargs.cli)}\n```\n\n",
    )

    # Write.
    readme_path.write_text(content)

    # Format.
    try:
        subprocess.run(args=["prettier", "-w", readme_path.as_posix()])
        print("Successfully formatted with `prettier`!")
    except FileNotFoundError:
        print("Tried to format README with `prettier`, but not in PATH.")


if __name__ == "__main__":
    dcargs.cli(main)
