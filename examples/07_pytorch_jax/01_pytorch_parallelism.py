"""PyTorch Parallelism

The :code:`console_outputs=` argument can be set to :code:`False` to suppress helptext and
error message printing.

This is useful in PyTorch for distributed training scripts, where you only want
to print helptext from the main process:


.. code-block:: python

    # HuggingFace Accelerate.
    args = tyro.cli(Args, console_outputs=accelerator.is_main_process)

    # PyTorch DDP.
    args = tyro.cli(Args, console_outputs=(rank == 0))

    # PyTorch Lightning.
    args = tyro.cli(Args, console_outputs=trainer.is_global_zero)


Usage:

    python ./01_pytorch_parallelism.py --help
"""

import tyro


def train(foo: int, bar: str) -> None:
    """Description. This should show up in the helptext!"""


if __name__ == "__main__":
    args = tyro.cli(train, console_outputs=False)
    print(args)
