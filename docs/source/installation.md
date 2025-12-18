# Installation

## Standard installation

Tyro supports Python 3.8 through 3.14 and can be installed via pip:

```bash
pip install tyro
```

## Development installation

If you'd like to contribute to tyro, here's how to set up a development environment:

```bash
# Clone repository.
git clone git@github.com:brentyi/tyro.git
cd tyro

# Run tests.
uv run --extra dev pytest

# Check types.
uv run --extra dev pyright

# Run linters.
uvx ruff check --fix
uvx ruff format
```

The `uv run` command automatically handles creating a virtual environment and installing dependencies.

To run tests that include neural network library integrations (PyTorch, JAX, etc.), use the `dev-nn` extra:

```bash
uv run --extra dev-nn pytest
```
