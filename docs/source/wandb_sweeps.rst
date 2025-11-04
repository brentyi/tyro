W&B Sweep Compatibility
========================

`Weights & Biases (wandb) <https://wandb.ai>`_ is a popular platform for experiment tracking and hyperparameter optimization. Its `sweep functionality <https://docs.wandb.ai/guides/sweeps>`_ allows you to define hyperparameter search spaces and automatically run experiments with different configurations.

Tyro works with wandb sweeps for most parameter types. There are some considerations when using sequence types like tuples or lists.

Sequence Arguments
~~~~~~~~~~~~~~~~~~

By default, sequence arguments like ``tuple[int, int, int]`` or ``list[int]`` are parsed from multiple command-line values: ``--hidden-dims 128 128 128``. However, wandb sweeps pass all parameter values as single strings.

For compatibility with wandb sweeps, use the :data:`tyro.conf.UsePythonSyntaxForLiteralCollections` marker. This makes tyro expect Python literal syntax for collections (lists, tuples, dicts, sets):

.. code-block:: python

    from dataclasses import dataclass
    import tyro

    @dataclass
    class Config:
        hidden_dims: tuple[int, int, int] = (128, 128, 128)
        learning_rate: float = 1e-3

    if __name__ == "__main__":
        config = tyro.cli(Config, config=(tyro.conf.UsePythonSyntaxForLiteralCollections,))
        # Your training code here...

In your wandb sweep configuration, specify collection values using Python literal syntax:

.. code-block:: yaml

    parameters:
      hidden_dims:
        values: ["(128, 128, 128)", "(256, 256, 256)", "(512, 512, 512)"]
      learning_rate:
        values: [1e-3, 1e-4, 1e-5]

The marker applies to all collection types:

- Tuples: ``"(1, 2, 3)"``
- Lists: ``"[1, 2, 3]"``
- Dicts: ``"{'a': 1, 'b': 2}"``
- Sets: ``"{1, 2, 3}"``

Collections can contain built-in types (``int``, ``str``, ``float``, ``bool``, etc.)
and nested structures:

.. code-block:: python

    @dataclass
    class Config:
        # Built-in types work.
        values: list[int] = [1, 2, 3]

        # Nested structures work.
        pairs: list[tuple[str, int]] = [("a", 1), ("b", 2)]

        # Dictionaries work.
        mapping: dict[str, list[int]] = {"x": [1, 2], "y": [3, 4]}

    config = tyro.cli(Config, config=(tyro.conf.UsePythonSyntaxForLiteralCollections,))
    # Usage: python script.py --values "[10, 20, 30]" --pairs "[('x', 5), ('y', 10)]"

Boolean Flags
~~~~~~~~~~~~~

Wandb sweeps work best with explicit ``--flag True/False`` syntax rather than tyro's default ``--flag/--no-flag`` pairs. Use :data:`tyro.conf.FlagConversionOff` in the ``config`` argument:

.. code-block:: python

    from dataclasses import dataclass
    import tyro

    @dataclass
    class Config:
        use_dropout: bool = False
        learning_rate: float = 1e-3

    if __name__ == "__main__":
        config = tyro.cli(Config, config=(tyro.conf.FlagConversionOff,))

In your sweep configuration:

.. code-block:: yaml

    parameters:
      use_dropout:
        values: [True, False]
      learning_rate:
        values: [1e-3, 1e-4, 1e-5]

Complete Example
~~~~~~~~~~~~~~~~

For a complete wandb sweeps setup with both sequence arguments and boolean flags, combine both markers:

.. code-block:: python

    from dataclasses import dataclass
    import tyro

    @dataclass
    class Config:
        hidden_dims: tuple[int, int, int] = (128, 128, 128)
        use_dropout: bool = False
        learning_rate: float = 1e-3

    if __name__ == "__main__":
        config = tyro.cli(
            Config,
            config=(
                tyro.conf.UsePythonSyntaxForLiteralCollections,
                tyro.conf.FlagConversionOff,
            ),
        )
        # Your training code here...

Corresponding sweep configuration:

.. code-block:: yaml

    parameters:
      hidden_dims:
        values: ["(128, 128, 128)", "(256, 256, 256)"]
      use_dropout:
        values: [True, False]
      learning_rate:
        values: [1e-3, 1e-4, 1e-5]

Additional Resources
~~~~~~~~~~~~~~~~~~~~

- `wandb Sweeps Documentation <https://docs.wandb.ai/guides/sweeps>`_
- `wandb GitHub Issue #2939 <https://github.com/wandb/wandb/issues/2939>`_ - Discussion about list/tuple parameter handling in sweeps
- :doc:`/examples/custom_constructors` - For advanced parameter parsing customization
