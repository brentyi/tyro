# Installation

## Standard Installation

Tyro supports Python 3.7 through 3.13 and can be installed via pip:

```bash
pip install tyro
```

This will install the minimal dependencies required for tyro to function properly.

## Optional Dependencies

Tyro has optional integrations with several popular libraries. To install tyro with
all optional dependencies for full functionality:

```bash
pip install "tyro[dev]"
```

## Development Installation

If you'd like to contribute to tyro, here's how to set up a development environment:

```bash
# Clone repository
git clone git@github.com:brentyi/tyro.git
cd tyro

# Install in development mode with all dependencies
python -m pip install -e ".[dev]"

# Run tests
pytest

# Check types
pyright .

# Run linters
ruff check
ruff format
```

The development installation includes additional tools for testing, type checking, and code quality.
