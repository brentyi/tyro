# Tyro Development Guide

## Build & Test Commands
- Install dev dependencies: `pip install -e ".[dev]"`
- Run all tests: `pytest`
- Run specific test: `pytest tests/test_file.py -v` or `pytest tests/test_file.py::test_name -v`
- Prefer pyright for type checking: `pyright .`
- Run linting: `ruff check`
- Fix linting issues: `ruff check --fix` (some fixes require `--unsafe-fixes` option)
- Format code: `ruff format` (check changes first with `ruff format --diff`)

## Style Guidelines
- Use type annotations for all functions and variables
- Follow PEP 8 conventions 
- Use descriptive variable/function names in snake_case
- Classes should use CamelCase
- Prefer dataclasses for configuration objects
- Use docstrings for public functions/classes
- Import ordering: stdlib > third-party > local modules
- Pass exceptions up where appropriate (don't suppress silently)
- Prefer composition over inheritance

## Architecture
Tyro focuses on generating CLI interfaces from type-annotated Python. The codebase supports Python 3.7-3.13 with conditional imports and version-specific features.