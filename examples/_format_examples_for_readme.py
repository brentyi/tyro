"""Helper script for generating the examples list in the README.

Generally, invoked as:
`python examples/_format_examples_for_readme.py --readme-path ./README.md`
"""

import concurrent.futures
import pathlib
import re
import subprocess
from typing import Optional

import dcargs

README_MARKER_START = "<!-- START EXAMPLES -->"
README_MARKER_END = "<!-- END EXAMPLES -->"
SCRIPT_FORMAT_TEMPLATE = """
<details>
<summary>
<strong>{index}. {title}</strong>
</summary>

[{path}]({path})

<table><tr><td>

```python
{source}
```

---

```console
$ python {path} --help
```
```
{helptext}
```

</td></tr></table>
</details>
"""


def update_readme(readme_path: pathlib.Path, inner: str) -> None:
    """Puts `inner` in between {README_MARKER_START} and {README_MARKER_END}."""
    readme_contents = readme_path.read_text()
    assert README_MARKER_START in readme_contents
    assert README_MARKER_END in readme_contents
    before, _, after = readme_contents.partition(README_MARKER_START)
    _, _, after = readme_contents.rpartition(README_MARKER_END)
    readme_path.write_text(
        "".join([before, README_MARKER_START, inner, README_MARKER_END, after])
    )
    print(f"Wrote update examples to {readme_path}!")
    try:
        subprocess.run(args=["prettier", "-w", readme_path.as_posix()])
        print("Successfully formatted with `prettier`!")
    except FileNotFoundError:
        print("Tried to format README with `prettier`, but not in PATH.")


def format_script_for_readme(index: int, path: pathlib.Path) -> str:
    title = " ".join(
        map(
            # Capitalize first letter of each word.
            lambda lower: lower[0:1].upper() + lower[1:],
            # Remove integer prefix.
            path.stem.split("_")[1:],
        )
    )

    source = path.read_text().strip()

    helptext = subprocess.run(
        args=["python", str(path), "--help"], stdout=subprocess.PIPE, encoding="utf8"
    ).stdout
    helptext = re.sub(  # Strip colorcodes.
        r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", helptext
    ).strip()

    return SCRIPT_FORMAT_TEMPLATE.format(
        index=index, title=title, path=path, source=source, helptext=helptext
    )


def main(readme_path: pathlib.Path) -> None:
    """Helper script for generating the examples list in the README.

    Args:
        readme_path: README file to write to; we replace the contents between
            the start and end markers. If not specified, output is printed.
    """
    script_paths = sorted(
        filter(
            lambda p: not p.name.startswith("_"),
            pathlib.Path(__file__).parent.glob("*.py"),
        )
    )

    with concurrent.futures.ThreadPoolExecutor() as executor:
        out_str = "\n".join(
            executor.map(
                format_script_for_readme,
                range(1, len(script_paths) + 1),
                script_paths,
            )
        )
    update_readme(readme_path, out_str)


if __name__ == "__main__":
    dcargs.cli(main)
