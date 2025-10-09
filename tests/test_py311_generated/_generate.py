"""Generate a Python 3.11 version of tests. This will use imports from `typing` instead
of `typing_extensions`, and replace Union[A, B] types with A | B."""

import pathlib
import subprocess
from concurrent.futures import ThreadPoolExecutor


def generate_from_path(test_path: pathlib.Path) -> None:
    # Skip tests that require Python 3.13+.
    if "min_py313" in test_path.name:
        return

    content = test_path.read_text()

    # Special handling for TypeVar with defaults - keep using typing_extensions.
    # TypeVar defaults are only available in typing module from Python 3.13+.
    if "TypeVar" in content and "default=" in content:
        # This test uses TypeVar with defaults, so we need to keep typing_extensions.
        # We'll only replace typing_extensions for non-TypeVar imports.
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if "from typing_extensions import" in line and "TypeVar" not in line:
                # Replace typing_extensions with typing for non-TypeVar imports.
                line = line.replace("typing_extensions", "typing")
            elif "import typing_extensions" in line:
                # Keep the import but we might need to handle it specially.
                pass
            new_lines.append(line)
        content = "\n".join(new_lines)
    else:
        # No TypeVar with defaults, safe to replace all typing_extensions.
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
        has_comma = False
        for i, char in enumerate(b):
            if char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1

            if char == "," and bracket_count == 0:
                new_content_parts.append("|")
                has_comma = True
            elif bracket_count == -1:
                if has_comma:
                    # Multiple types - convert to |.
                    while new_content_parts[-1] in (" ", "|"):
                        new_content_parts.pop(-1)
                    new_content_parts.append(b[i + 1 :])
                else:
                    # Single type Union - keep as-is with temporary marker.
                    new_content_parts = [
                        new_content,
                        "<<<UNION_SKIP>>>[",
                        b[: i + 1],
                        b[i + 1 :],
                    ]
                break
            elif char != "\n":
                new_content_parts.append(char)

        content = "".join(new_content_parts)

    # Restore any single-type Unions we skipped.
    content = content.replace("<<<UNION_SKIP>>>", "Union")

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
