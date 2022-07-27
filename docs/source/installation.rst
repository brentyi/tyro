Installation
==========================================

Standard
------------------------------------------

Installation is supported on Python >=3.7 via pip. This is typically all that's
required.


.. code-block::

      pip install dcargs


Development
------------------------------------------

If you're interested in development, the recommended way to install :code:`dcargs` is via `poetry`:

.. code-block::

      # Clone repository and install.
      git clone git@github.com:brentyi/dcargs.git
      cd dcargs
      poetry install

      # Run tests.
      pytest

      # Check types.
      mypy --install-types .

