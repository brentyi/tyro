"""Helper module for test_docstring_field_not_found_warning.

This module provides a dataclass whose source code can be read by
inspect.getsource(), which is needed to trigger the docstring-parsing warning
in get_class_tokenization_with_field().
"""

import dataclasses


@dataclasses.dataclass
class SimpleConfig:
    """A simple config with known fields."""

    x: int = 1
    """X parameter."""
