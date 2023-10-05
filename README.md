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
    <img alt="build" src="https://github.com/brentyi/tyro/workflows/build/badge.svg" />
    <img alt="mypy" src="https://github.com/brentyi/tyro/workflows/mypy/badge.svg?branch=main" />
    <img alt="lint" src="https://github.com/brentyi/tyro/workflows/lint/badge.svg" />
    <a href="https://codecov.io/gh/brentyi/tyro">
        <img alt="codecov" src="https://codecov.io/gh/brentyi/tyro/branch/main/graph/badge.svg" />
    </a>
    <a href="https://pypi.org/project/tyro/">
        <img alt="codecov" src="https://img.shields.io/pypi/pyversions/tyro" />
    </a>
</p>

<br />

<strong><code>tyro</code></strong> is a tool for generating command-line
interfaces and configuration objects from type-annotated Python.

Our single-function core API, `tyro.cli()`,

- Generates CLI interfaces from a comprehensive set of Python type constructs.
- Generates helptext automatically from defaults, annotations, and docstrings.
- Understands hierarchy, nesting, and tools you may already use, like
  `dataclasses`, `pydantic`, and `attrs`.
- Provides flexible support for subcommands, as well as choosing between and
  overriding values in configuration objects.
- Enables tab completion in both your IDE and terminal.
- Supports fine-grained configuration via PEP 529 runtime annotations
  (`tyro.conf.*`).

For examples and the API reference, see our
[documentation](https://brentyi.github.io/tyro).

### In the wild

`tyro` has been stress-tested in several projects, including:

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
    <td>Library for distributed training of large language models in JAX.</td>
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
    <td>Interface for processing composite Wavefront OBJ files for Mujoco.</td>
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
</table>
