"""Self-contained Python completion logic for embedding in shell scripts.

This module provides the completion code that will be embedded in bash/zsh scripts.
"""

from __future__ import annotations

import ast
import pathlib


def get_embedded_code() -> str:
    """Get the Python completion code for embedding in shell scripts.

    Reads the completion script from _completion_script.py and returns
    the source code ready to embed in a heredoc, with type annotations removed.

    Returns:
        Python code as a string, ready to embed in a heredoc.
    """
    script_path = pathlib.Path(__file__).parent / "_completion_script.py"
    source = script_path.read_text()

    # Parse and strip type annotations using AST.
    source = _strip_type_annotations(source)

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

        # Skip typing imports - not needed without type annotations.
        if "from typing import" in line or "from __future__ import annotations" in line:
            continue

        output_lines.append(line)

    return "\n".join(output_lines).strip()


def _strip_type_annotations(source: str) -> str:
    """Remove type annotations from Python source code using AST.

    Args:
        source: Python source code.

    Returns:
        Source with type annotations removed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # If we can't parse it, return as-is.
        return source

    # Remove annotations from function definitions.
    class AnnotationStripper(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
            # Remove return annotation.
            node.returns = None

            # Remove parameter annotations.
            for arg in node.args.args:
                arg.annotation = None
            for arg in node.args.posonlyargs:
                arg.annotation = None
            for arg in node.args.kwonlyargs:
                arg.annotation = None
            if node.args.vararg:
                node.args.vararg.annotation = None
            if node.args.kwarg:
                node.args.kwarg.annotation = None

            # Continue visiting child nodes.
            self.generic_visit(node)
            return node

        def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.Assign | ast.AnnAssign:
            # Convert annotated assignments to regular assignments if they have a value.
            if node.value is not None:
                return ast.Assign(targets=[node.target], value=node.value)
            # If no value, keep as annotated assignment (shouldn't happen in functions).
            return node

    stripper = AnnotationStripper()
    tree = stripper.visit(tree)

    # Convert back to source code.
    return ast.unparse(tree)
