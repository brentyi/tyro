"""Generate a Python 3.11 version of tests. This will use imports from `typing` instead
of `typing_extensions`, and replace Union[A, B] types with A | B."""

import pathlib
import subprocess
from concurrent.futures import ThreadPoolExecutor


def generate_from_path(test_path: pathlib.Path) -> None:
    content = test_path.read_text()
    content = content.replace("typing_extensions", "typing")

    for typx_only_import in ("Doc", "ReadOnly"):
        if typx_only_import not in content:
            continue
        content = content.replace(f"{typx_only_import},", "", 1)
        content = content.replace(f", {typx_only_import}\n", "", 1)
        content = content.replace(
            "\nfrom typing import ",
            f"\nfrom typing_extensions import {typx_only_import}\nfrom typing import ",
        )

    while "Union[" in content:
        new_content, _, b = content.partition("Union[")

        if b.strip()[0] == '"':
            break  # Don't bother with forward references!

        new_content_parts = [new_content]

        bracket_count = 0
        for i, char in enumerate(b):
            if char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1

            if char == "," and bracket_count == 0:
                new_content_parts.append("|")
            elif bracket_count == -1:
                while new_content_parts[-1] in (" ", "|"):
                    new_content_parts.pop(-1)
                new_content_parts.append(b[i + 1 :])
                break
            elif char != "\n":
                new_content_parts.append(char)

        content = "".join(new_content_parts)

    out_path = pathlib.Path(__file__).absolute().parent / (
        test_path.stem + "_generated.py"
    )
    out_path.write_text(content)

    subprocess.run(["ruff", "format", str(out_path)], check=True)
    subprocess.run(["ruff", "check", "--fix", str(out_path)], check=True)


with ThreadPoolExecutor(max_workers=8) as executor:
    list(
        executor.map(
            generate_from_path,
            pathlib.Path(__file__).absolute().parent.parent.glob("test_*.py"),
        )
    )
