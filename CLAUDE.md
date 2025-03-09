# Tyro Development Guide

## Build & Test Commands
- Install dev dependencies: `pip install -e ".[dev]"`
- Run all tests: `pytest -n auto` (parallel execution)
- Run all tests: `pytest` (sequential execution)
- Run specific test: `pytest tests/test_file.py -v` or `pytest tests/test_file.py::test_name -v`
- When modifying tests, regenerate the Py311 test variants: `python tests/test_py311_generated/_generate.py`
- Prefer pyright for type checking: `pyright .`
- Run linting: `ruff check`
- Fix linting issues: `ruff check --fix` (some fixes require `--unsafe-fixes` option)
- Format code: `ruff format` (check changes first with `ruff format --diff`)

## Style Guidelines
- Use type annotations for all functions and variables.
- Follow PEP 8 conventions.
- Use descriptive variable/function names in snake_case.
- Classes should use CamelCase.
- Prefer dataclasses for configuration objects.
- Use docstrings for public functions/classes.
- Use full sentences with periods in docstrings and comments.
- Import ordering: stdlib > third-party > local modules.
- Pass exceptions up where appropriate (don't suppress silently).
- Prefer composition over inheritance.

## Architecture
Tyro focuses on generating CLI interfaces from type-annotated Python. The codebase supports Python 3.7-3.13 with conditional imports and version-specific features.

## Documentation
- Document all public functions, classes, and methods.
- Use consistent docstring style with full sentences ending in periods.
- Include examples in docstrings for complex functionality.
- For markers and config options, show both the feature and its effect on CLI usage.
- Update the docstrings when changing any public API.

## Architecture
Tyro focuses on generating CLI interfaces from type-annotated Python. The codebase supports Python 3.7-3.13 with conditional imports and version-specific features.