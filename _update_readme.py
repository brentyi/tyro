"""Helper script for updating the auto-generated parts of the README. (docstring,
examples list)"""

import concurrent.futures
import dataclasses
import inspect
import pathlib
import re
import subprocess

import dcargs


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
    helptext = subprocess.run(
        args=["python", str(path), "--help"], stdout=subprocess.PIPE, encoding="utf8"
    ).stdout
    helptext = re.sub(  # Strip colorcodes.
        r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", helptext
    ).strip()

    return f"""
<details>
<summary>
<strong>{index}. {title}</strong>
</summary>
<table><tr><td>

[{path}]({path})

```python
{source}
```

---

<pre>
<samp>$ <kbd>python {path} --help</kbd>
{helptext}</samp>
</pre>

</td></tr></table>
</details>
    """.strip()


def get_examples_str(examples_dir: pathlib.Path, constants: Constants) -> str:
    script_paths = sorted(examples_dir.glob("*.py"))
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
