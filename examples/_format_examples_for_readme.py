"""Helper script for generating the examples list in the README.

Generally, invoked as:
`python --readme-path ./README.md`
"""

import pathlib
import re
import subprocess
from typing import Optional

import dcargs


def _comment(x: str) -> str:
    return f"<!-- {x} -->"


README_MARKER_START = _comment("START EXAMPLES")
README_MARKER_END = _comment("END EXAMPLES")
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
    print(f"Wrote to {readme_path}!")


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


def main(readme_path: Optional[pathlib.Path] = None) -> None:
    """Helper script for generating the examples list in the README.

    Args:
        readme_path: README file to write to; we replace the contents between
            the start and end markers. If not specified, output is printed.
    """
    out_list = []
    for i, script_path in enumerate(sorted(pathlib.Path(__file__).parent.glob("*.py"))):
        print(script_path)
        if script_path.name.startswith("_"):
            continue

        out_list.append(format_script_for_readme(i + 1, script_path))

    out_str = "\n".join(out_list)

    if readme_path is None:
        print(out_str)
    else:
        update_readme(readme_path, out_str)


if __name__ == "__main__":
    dcargs.cli(main)
