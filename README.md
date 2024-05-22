<br />
<p align="center">
    <!--
    Note that this README will be used for both GitHub and PyPI.
    We therefore:
    - Keep all image URLs absolute.
    - In the GitHub action we use for publishing, strip some HTML tags that aren't supported by PyPI.
    -->
    <!-- pypi-strip -->
    <picture>
        <source media="(prefers-color-scheme: dark)" srcset="https://brentyi.github.io/tyro/_static/logo-dark.svg" />
    <!-- /pypi-strip -->
        <img alt="tyro logo" src="https://brentyi.github.io/tyro/_static/logo-light.svg" width="200px" />
    <!-- pypi-strip -->
    </picture>
    <!-- /pypi-strip -->

</p>

<p align="center">
    <em><a href="https://brentyi.github.io/tyro">Documentation</a></em>
    &nbsp;&nbsp;&bull;&nbsp;&nbsp;
    <em><code>pip install tyro</code></em>
</p>

<p align="center">
    <img alt="build" src="https://github.com/brentyi/tyro/actions/workflows/build.yml/badge.svg" />
    <img alt="mypy" src="https://github.com/brentyi/tyro/actions/workflows/mypy.yml/badge.svg" />
    <img alt="pyright" src="https://github.com/brentyi/tyro/actions/workflows/pyright.yml/badge.svg" />
    <img alt="ruff" src="https://github.com/brentyi/tyro/actions/workflows/ruff.yml/badge.svg" />
    <a href="https://codecov.io/gh/brentyi/tyro">
        <img alt="codecov" src="https://codecov.io/gh/brentyi/tyro/branch/main/graph/badge.svg" />
    </a>
    <a href="https://pypi.org/project/tyro/">
        <img alt="codecov" src="https://img.shields.io/pypi/pyversions/tyro" />
    </a>
</p>

<br />

<strong><code>tyro</code></strong> is a tool for generating command-line
interfaces and configuration objects in Python.

Our core API, `tyro.cli()`,

- **Generates CLI interfaces** from Python type signatures.
- **Populates helptext automatically** from defaults, annotations, and
  docstrings.
- **Understands nesting** of `dataclasses`, `pydantic`, and `attrs` structures.
- **Prioritizes static analysis** for type checking and autocompletion with
  tools like
  [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance),
  [Pyright](https://github.com/microsoft/pyright), and
  [mypy](https://github.com/python/mypy).

For advanced users, it also supports:

- **Subcommands**, as well as choosing between and overriding values in
  configuration objects.
- **Shell completion** for `bash`, `zsh`, and `tcsh`.
- **Fine-grained configuration** via [PEP
  593](https://peps.python.org/pep-0593/) annotations (`tyro.conf.*`).

For examples and the API reference, see our
[documentation](https://brentyi.github.io/tyro).

### In the wild

`tyro` is designed to be lightweight enough for throwaway scripts, while
facilitating type safety and modularity for larger projects. Examples:

<table>
  <tr>
    <td>
      <a href="https://github.com/nerfstudio-project/nerfstudio/">
        nerfstudio-project/nerfstudio
        <br /><img
          alt="GitHub star count"
          src="https://img.shields.io/github/stars/nerfstudio-project/nerfstudio?style=social"
        />
      </a>
    </td>
    <td>
      Open-source tools for neural radiance fields.
    </td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/Sea-Snell/JAXSeq/">
        Sea-Snell/JAXSeq
        <br /><img
          alt="GitHub star count"
          src="https://img.shields.io/github/stars/Sea-Snell/JAXSeq?style=social"
        />
      </a>
    </td>
    <td>Train very large language models in Jax.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/kevinzakka/obj2mjcf">
        kevinzakka/obj2mjcf
        <br /><img
          alt="GitHub star count"
          src="https://img.shields.io/github/stars/kevinzakka/obj2mjcf?style=social"
        />
      </a>
    </td>
    <td>Interface for processing OBJ files for Mujoco.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/blurgyy/jaxngp">
        blurgyy/jaxngp
        <br /><img
          alt="GitHub star count"
          src="https://img.shields.io/github/stars/blurgyy/jaxngp?style=social"
        />
      </a>
    </td>
    <td>
      CUDA-accelerated implementation of
      <a href="https://nvlabs.github.io/instant-ngp/">instant-ngp</a>, in JAX.
    </td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/NVIDIAGameWorks/kaolin-wisp">
        NVIDIAGameWorks/kaolin-wisp
        <br /><img
          alt="GitHub star count"
          src="https://img.shields.io/github/stars/NVIDIAGameWorks/kaolin-wisp?style=social"
        />
      </a>
    </td>
    <td>PyTorch library for neural fields.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/autonomousvision/sdfstudio">
        autonomousvision/sdfstudio
        <br /><img
          alt="GitHub star count"
          src="https://img.shields.io/github/stars/autonomousvision/sdfstudio?style=social"
        />
      </a>
    </td>
    <td>Unified framework for surface reconstruction.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/openrlbenchmark/openrlbenchmark">
        openrlbenchmark/openrlbenchmark
        <br /><img
          alt="GitHub star count"
          src="https://img.shields.io/github/stars/openrlbenchmark/openrlbenchmark?style=social"
        />
      </a>
    </td>
    <td>Collection of tracked experiments for reinforcement learning.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/vwxyzjn/cleanrl">
        vwxyzjn/cleanrl
        <br /><img
          alt="GitHub star count"
          src="https://img.shields.io/github/stars/vwxyzjn/cleanrl?style=social"
        />
      </a>
    </td>
    <td>Single-file implementation of deep RL algorithms.</td>
  </tr>
</table>

### Alternatives

`tyro` is an opinionated library. If any design decisions don't make sense,
feel free to file an issue!

You might also consider one of many alternative libraries. Some that we
particularly like:

- [simple-parsing](https://github.com/lebrice/SimpleParsing) and
  [jsonargparse](https://github.com/omni-us/jsonargparse), which provide deeper
  integration with configuration file formats like YAML and JSON.
- [clipstick](https://github.com/sander76/clipstick), which focuses on
  generating CLIs from Pydantic models.
- [datargs](https://github.com/roee30/datargs), which provides a minimal API for
  dataclasses.
- [fire](https://github.com/google/python-fire) and
  [clize](https://github.com/epsy/clize), which support arguments without type
  annotations.

We also have some notes on `tyro`'s design goals and other alternatives in the
docs [here](https://brentyi.github.io/tyro/goals_and_alternatives/).
