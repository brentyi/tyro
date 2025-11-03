"""Self-contained Python completion logic for embedding in shell scripts.

This module provides the completion code that will be embedded in bash/zsh scripts.
"""

from __future__ import annotations

import pathlib


def get_embedded_code() -> str:
    """Get the Python completion code for embedding in shell scripts.

    Reads the completion script from _completion_script.py and returns
    the source code ready to embed in a heredoc.

    Returns:
        Python code as a string, ready to embed in a heredoc.
    """
    script_path = pathlib.Path(__file__).parent / "_completion_script.py"
    source = script_path.read_text()

    # Extract only the necessary parts (skip module docstring at top).
    lines = source.split("\n")
    output_lines = []
    skip_until_import = True

    for line in lines:
        # Skip until we hit the first import or def.
        if skip_until_import:
            if line.startswith("import ") or line.startswith("def "):
                skip_until_import = False
            else:
                continue

        output_lines.append(line)

    return "\n".join(output_lines).strip()
