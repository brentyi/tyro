"""Cleaner Console Outputs for Scripts with Multiple Workers

The `console_outputs=` argument can be set to `False` to suppress helptext and
error message printing.

This is useful in PyTorch for distributed training scripts, where you only want
to print the helptext from the main process:

```python
# Hugging Face Accelerate.
args = tyro.cli(Args, console_outputs=accelerator.is_main_process)

# PyTorch DDP.
args = tyro.cli(Args, console_outputs=(rank == 0))

# PyTorch Lightning.
args = tyro.cli(Args, console_outputs=trainer.is_global_zero)
```

Usage:
`python ./14_suppress_console_outputs.py --help`
"""

import dataclasses

import tyro


@dataclasses.dataclass
class Args:
    """Description.
    This should show up in the helptext!"""

    field1: int
    """A field."""

    field2: int = 3
    """A numeric field, with a default value."""


if __name__ == "__main__":
    args = tyro.cli(Args, console_outputs=False)
    print(args)
