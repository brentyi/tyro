.. Comment: this file is automatically generated by `update_example_docs.py`.
   It should not be modified manually.

.. _example-category-subcommands:

Subcommands
===========

In these examples, we show how :func:`tyro.cli` can be used to create CLI
interfaces with subcommands.


.. _example-01_subcommands:

Subcommands are Unions
----------------------

All of :mod:`tyro`'s subcommand features are built using unions over struct
types (typically dataclasses). Subcommands are used to choose between types in
the union; arguments are then populated from the chosen type.

.. note::

    For configuring subcommands beyond what can be expressed with type annotations, see
    :func:`tyro.conf.subcommand()`.


.. code-block:: python
    :linenos:

    # 01_subcommands.py
    from __future__ import annotations

    import dataclasses

    import tyro

    @dataclasses.dataclass
    class Checkout:
        """Checkout a branch."""

        branch: str

    @dataclasses.dataclass
    class Commit:
        """Commit changes."""

        message: str

    if __name__ == "__main__":
        cmd = tyro.cli(Checkout | Commit)
        print(cmd)


Print the helptext. This will show the available subcommands:

.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./01_subcommands.py --help</strong>
    <span style="font-weight: bold">usage</span>: 01_subcommands.py [-h] <span style="font-weight: bold">{checkout,commit}</span>
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">──────────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help              <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────────╯</span>
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> subcommands </span><span style="font-weight: lighter">──────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> {checkout,commit}                                       <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     checkout            <span style="font-weight: lighter">Checkout a branch.</span>              <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     commit              <span style="font-weight: lighter">Commit changes.</span>                 <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────────╯</span>
    </pre>

The `commit` subcommand:

.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./01_subcommands.py commit --help</strong>
    <span style="font-weight: bold">usage</span>: 01_subcommands.py commit [-h] --message <span style="font-weight: bold">STR</span>
    
    Commit changes.
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">───────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help           <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --message <span style="font-weight: bold">STR</span>        <span style="font-weight: bold; color: #e60000">(required)</span>                      <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰──────────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./01_subcommands.py commit --message hello</strong>
    Commit(message='hello')
    </pre>

The `checkout` subcommand:

.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./01_subcommands.py checkout --help</strong>
    <span style="font-weight: bold">usage</span>: 01_subcommands.py checkout [-h] --branch <span style="font-weight: bold">STR</span>
    
    Checkout a branch.
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">──────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help          <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --branch <span style="font-weight: bold">STR</span>        <span style="font-weight: bold; color: #e60000">(required)</span>                      <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./01_subcommands.py checkout --branch main</strong>
    Checkout(branch='main')
    </pre>
.. _example-02_subcommands_in_func:

Subcommands as Function Arguments
---------------------------------

A subcommand will be created for each input annotated with a union over
struct types.

.. note::

    To prevent :func:`tyro.cli()` from converting a Union type into a subcommand,
    use :class:`tyro.conf.AvoidSubcommands`.

.. note::

    Argument ordering for subcommands can be tricky. In the example below,
    ``--shared-arg`` must always come *before* the subcommand. As an option for
    alleviating this, see :class:`tyro.conf.ConsolidateSubcommandArgs`.


.. code-block:: python
    :linenos:

    # 02_subcommands_in_func.py
    from __future__ import annotations

    import dataclasses

    import tyro

    @dataclasses.dataclass
    class Checkout:
        """Checkout a branch."""

        branch: str

    @dataclasses.dataclass
    class Commit:
        """Commit changes."""

        message: str

    def main(
        shared_arg: int,
        cmd: Checkout | Commit = Checkout(branch="default"),
    ):
        print(f"{shared_arg=}")
        print(cmd)

    if __name__ == "__main__":
        tyro.cli(main)


Print the helptext. This will show the available subcommands:

.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./02_subcommands_in_func.py --help</strong>
    <span style="font-weight: bold">usage</span>: 02_subcommands_in_func.py [-h] --shared-arg <span style="font-weight: bold">INT</span>
                                     <span style="font-weight: bold">[{cmd:checkout,cmd:commit}]</span>
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">──────────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help              <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --shared-arg <span style="font-weight: bold">INT</span>        <span style="font-weight: bold; color: #e60000">(required)</span>                      <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────────╯</span>
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> optional subcommands </span><span style="font-weight: lighter">─────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> <span style="font-weight: bold">(default: cmd:checkout)                                </span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> <span style="font-weight: lighter">──────────────────────────────────────────             </span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> [{cmd:checkout,cmd:commit}]                             <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     cmd:checkout        <span style="font-weight: lighter">Checkout a branch.</span>              <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     cmd:commit          <span style="font-weight: lighter">Commit changes.</span>                 <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────────╯</span>
    </pre>

Using the default subcommand:

.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./02_subcommands_in_func.py --shared-arg 100</strong>
    shared_arg=100
    Checkout(branch='default')
    </pre>

Choosing a different subcommand:

.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./02_subcommands_in_func.py --shared-arg 100 cmd:commit --cmd.message 'Hello!'</strong>
    shared_arg=100
    Commit(message='Hello!')
    </pre>
.. _example-03_multiple_subcommands:

Sequenced Subcommands
---------------------

Multiple unions over struct types are populated using a series of subcommands.


.. code-block:: python
    :linenos:

    # 03_multiple_subcommands.py
    from __future__ import annotations

    import dataclasses
    from typing import Literal

    import tyro

    # Possible dataset configurations.

    @dataclasses.dataclass
    class Mnist:
        binary: bool = False
        """Set to load binary version of MNIST dataset."""

    @dataclasses.dataclass
    class ImageNet:
        subset: Literal[50, 100, 1000]
        """Choose between ImageNet-50, ImageNet-100, ImageNet-1000, etc."""

    # Possible optimizer configurations.

    @dataclasses.dataclass
    class Adam:
        learning_rate: float = 1e-3
        betas: tuple[float, float] = (0.9, 0.999)

    @dataclasses.dataclass
    class Sgd:
        learning_rate: float = 3e-4

    # Train script.

    def train(
        dataset: Mnist | ImageNet = Mnist(),
        optimizer: Adam | Sgd = Adam(),
    ) -> None:
        """Example training script.

        Args:
            dataset: Dataset to train on.
            optimizer: Optimizer to train with.

        Returns:
            None:
        """
        print(dataset)
        print(optimizer)

    if __name__ == "__main__":
        tyro.cli(train, config=(tyro.conf.ConsolidateSubcommandArgs,))


We apply the :class:`tyro.conf.ConsolidateSubcommandArgs` flag. This
pushes all arguments to the end of the command:

.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./03_multiple_subcommands.py --help</strong>
    <span style="font-weight: bold">usage</span>: 03_multiple_subcommands.py [-h] <span style="font-weight: bold">[{dataset:mnist,dataset:image-net}]</span>
    
    Example training script.
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help        <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰───────────────────────────────────────────────────╯</span>
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> optional subcommands </span><span style="font-weight: lighter">───────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> <span style="font-weight: bold">Dataset to train on. (default: dataset:mnist)    </span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> <span style="font-weight: lighter">─────────────────────────────────────────────    </span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> [{dataset:mnist,dataset:image-net}]               <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     dataset:mnist                                 <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     dataset:image-net                             <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰───────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./03_multiple_subcommands.py dataset:mnist --help</strong>
    <span style="font-weight: bold">usage</span>: 03_multiple_subcommands.py dataset:mnist [-h]
                                                    <span style="font-weight: bold">[{optimizer:adam,optimizer:sgd</span>
    <span style="font-weight: bold">}]</span>
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">─────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help        <span style="font-weight: lighter">show this help message and exit</span>  <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰────────────────────────────────────────────────────╯</span>
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> optional subcommands </span><span style="font-weight: lighter">────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> <span style="font-weight: bold">Optimizer to train with. (default: optimizer:adam)</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> <span style="font-weight: lighter">──────────────────────────────────────────────────</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> [{optimizer:adam,optimizer:sgd}]                   <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     optimizer:adam                                 <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     optimizer:sgd                                  <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰────────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./03_multiple_subcommands.py dataset:mnist optimizer:adam --help</strong>
    <span style="font-weight: bold">usage</span>: 03_multiple_subcommands.py dataset:mnist optimizer:adam
           [-h] [--optimizer.learning-rate <span style="font-weight: bold">FLOAT</span>] [--optimizer.betas <span style="font-weight: bold">FLOAT FLOAT</span>]
           [--dataset.binary | --dataset.no-binary]
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">────────────────────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help                                                        <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     <span style="font-weight: lighter">show this help message and exit</span>                               <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰───────────────────────────────────────────────────────────────────╯</span>
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> optimizer options </span><span style="font-weight: lighter">──────────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> --optimizer.learning-rate <span style="font-weight: bold">FLOAT</span>                                   <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     <span style="color: #008080">(default: 0.001)</span>                                              <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --optimizer.betas <span style="font-weight: bold">FLOAT FLOAT</span>                                     <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     <span style="color: #008080">(default: 0.9 0.999)</span>                                          <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰───────────────────────────────────────────────────────────────────╯</span>
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> dataset options </span><span style="font-weight: lighter">────────────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> --dataset.binary, --dataset.no-binary                             <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     <span style="font-weight: lighter">Set to load binary version of MNIST dataset.</span> <span style="color: #008080">(default: False)</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰───────────────────────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./03_multiple_subcommands.py dataset:mnist optimizer:adam --optimizer.learning-rate 3e-4 --dataset.binary</strong>
    Mnist(binary=True)
    Adam(learning_rate=0.0003, betas=(0.9, 0.999))
    </pre>
.. _example-04_decorator_subcommands:

Decorator-based Subcommands
---------------------------

:func:`tyro.extras.SubcommandApp()` provides a decorator-based API for
subcommands, which is inspired by `click <https://click.palletsprojects.com/>`_.


.. code-block:: python
    :linenos:

    # 04_decorator_subcommands.py
    from tyro.extras import SubcommandApp

    app = SubcommandApp()

    @app.command
    def greet(name: str, loud: bool = False) -> None:
        """Greet someone."""
        greeting = f"Hello, {name}!"
        if loud:
            greeting = greeting.upper()
        print(greeting)

    @app.command(name="addition")
    def add(a: int, b: int) -> None:
        """Add two numbers."""
        print(f"{a} + {b} = {a + b}")

    if __name__ == "__main__":
        app.cli()




.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python 04_decorator_subcommands.py --help</strong>
    <span style="font-weight: bold">usage</span>: 04_decorator_subcommands.py [-h] <span style="font-weight: bold">{greet,addition}</span>
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">──────────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help              <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────────╯</span>
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> subcommands </span><span style="font-weight: lighter">──────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> {greet,addition}                                        <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     greet               <span style="font-weight: lighter">Greet someone.</span>                  <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     addition            <span style="font-weight: lighter">Add two numbers.</span>                <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python 04_decorator_subcommands.py greet --help</strong>
    <span style="font-weight: bold">usage</span>: 04_decorator_subcommands.py greet [-h] --name <span style="font-weight: bold">STR</span> [--loud | --no-loud]
    
    Greet someone.
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">──────────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help              <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --name <span style="font-weight: bold">STR</span>              <span style="font-weight: bold; color: #e60000">(required)</span>                      <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --loud, --no-loud       <span style="color: #008080">(default: False)</span>                <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python 04_decorator_subcommands.py greet --name Alice</strong>
    Hello, Alice!
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python 04_decorator_subcommands.py greet --name Bob --loud</strong>
    HELLO, BOB!
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python 04_decorator_subcommands.py addition --help</strong>
    <span style="font-weight: bold">usage</span>: 04_decorator_subcommands.py addition [-h] --a <span style="font-weight: bold">INT</span> --b <span style="font-weight: bold">INT</span>
    
    Add two numbers.
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help        <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --a <span style="font-weight: bold">INT</span>           <span style="font-weight: bold; color: #e60000">(required)</span>                      <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --b <span style="font-weight: bold">INT</span>           <span style="font-weight: bold; color: #e60000">(required)</span>                      <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰───────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python 04_decorator_subcommands.py addition --a 5 --b 3</strong>
    5 + 3 = 8
    </pre>
.. _example-05_subcommands_func:

Subcommands from Functions
--------------------------

We provide a shorthand for generating a subcommand CLI from a dictionary. This
is a thin wrapper around :func:`tyro.cli()`'s more verbose, type-based API. If
more generality is needed, the internal working are explained in the docs for
:func:`tyro.extras.subcommand_cli_from_dict()`.


.. code-block:: python
    :linenos:

    # 05_subcommands_func.py
    import tyro

    def checkout(branch: str) -> None:
        """Check out a branch."""
        print(f"{branch=}")

    def commit(message: str, all: bool = False) -> None:
        """Make a commit."""
        print(f"{message=} {all=}")

    if __name__ == "__main__":
        tyro.extras.subcommand_cli_from_dict(
            {
                "checkout": checkout,
                "commit": commit,
            }
        )




.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./05_subcommands_func.py --help</strong>
    <span style="font-weight: bold">usage</span>: 05_subcommands_func.py [-h] <span style="font-weight: bold">{checkout,commit}</span>
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">──────────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help              <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────────╯</span>
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> subcommands </span><span style="font-weight: lighter">──────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> {checkout,commit}                                       <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     checkout            <span style="font-weight: lighter">Check out a branch.</span>             <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span>     commit              <span style="font-weight: lighter">Make a commit.</span>                  <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./05_subcommands_func.py commit --help</strong>
    <span style="font-weight: bold">usage</span>: 05_subcommands_func.py commit [-h] --message <span style="font-weight: bold">STR</span> [--all | --no-all]
    
    Make a commit.
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">─────────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help             <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --message <span style="font-weight: bold">STR</span>          <span style="font-weight: bold; color: #e60000">(required)</span>                      <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --all, --no-all        <span style="color: #008080">(default: False)</span>                <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰────────────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./05_subcommands_func.py commit --message hello --all</strong>
    message='hello' all=True
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./05_subcommands_func.py checkout --help</strong>
    <span style="font-weight: bold">usage</span>: 05_subcommands_func.py checkout [-h] --branch <span style="font-weight: bold">STR</span>
    
    Check out a branch.
    
    <span style="font-weight: lighter">╭─</span><span style="font-weight: lighter"> options </span><span style="font-weight: lighter">──────────────────────────────────────────</span><span style="font-weight: lighter">─╮</span>
    <span style="font-weight: lighter">│</span> -h, --help          <span style="font-weight: lighter">show this help message and exit</span> <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">│</span> --branch <span style="font-weight: bold">STR</span>        <span style="font-weight: bold; color: #e60000">(required)</span>                      <span style="font-weight: lighter">│</span>
    <span style="font-weight: lighter">╰─────────────────────────────────────────────────────╯</span>
    </pre>



.. raw:: html

    <pre class="highlight" style="padding: 1em; box-sizing: border-box; font-size: 0.85em; line-height: 1.2em;">
    <strong style="opacity: 0.7; padding-bottom: 0.5em; display: inline-block"><span style="user-select: none">$ </span>python ./05_subcommands_func.py checkout --branch main</strong>
    branch='main'
    </pre>