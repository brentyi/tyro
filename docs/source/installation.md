# Installation

## Standard

Installation is supported on Python >=3.7 via pip. This is typically all that's
required.

```bash
pip install tyro
```

## Development

If you're interested in development, the recommended way to install `tyro` is
via `pip`.

```bash
# Clone repository and install.
git clone git@github.com:brentyi/tyro.git
cd tyro
python -m pip install -e ".[dev]"

# Run tests.
pytest

# Check types.
mypy --install-types .
```
