# tyro

<p align="left">
    <a href="https://codecov.io/gh/brentyi/tyro">
        <img alt="codecov" src="https://codecov.io/gh/brentyi/tyro/branch/main/graph/badge.svg" />
    </a>
    <a href="https://pypi.org/project/tyro/">
        <img src="https://static.pepy.tech/personalized-badge/tyro?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=GREEN&left_text=downloads" alt="PyPI Downloads">
    </a>
    <a href="https://pypi.org/project/tyro/">
        <img alt="codecov" src="https://img.shields.io/pypi/pyversions/tyro" />
    </a>
</p>

<p align="left">
    <em><a href="https://brentyi.github.io/tyro">Documentation</a></em>
    &nbsp;&nbsp;&bull;&nbsp;&nbsp;
    <em><code>pip install tyro</code></em>
</p>

<strong><code>tyro.cli()</code></strong> is a tool for generating CLI
interfaces from type-annotated Python.

We can define configurable scripts using functions:

https://github.com/user-attachments/assets/6f884313-6111-40a1-b9c7-7cd83d737296

Or instantiate configs defined using tools like `dataclasses`, `pydantic`, and `attrs`:

https://github.com/user-attachments/assets/edec520d-0c05-4547-8dc5-c2e211aadfb2

Other features include helptext generation, nested structures, subcommands, and
shell completion. For examples and the API reference, see our
[documentation](https://brentyi.github.io/tyro).

### Why `tyro`?

1. **Define things once.** Standard Python type annotations, docstrings, and default values are parsed to automatically generate command-line interfaces with nice helptext.

2. **Static types.** Unlike tools dependent on dictionaries, YAML, or dynamic
   namespaces, arguments populated by `tyro` are better undestood by IDEs and
   language servers, as well as static checking tools like `pyright` and `mypy`.

3. **Modularity.** `tyro` supports hierarchical configurations, which make it
   easy to decentralize definitions, defaults, and documentation.

### In the wild

`tyro` is designed to be lightweight for throwaway scripts, while
improving maintainability for larger projects. Examples:

<table>
  <tr>
    <td>
      <a href="https://github.com/nerfstudio-project/nerfstudio/">
        nerfstudio-project/nerfstudio
        <br /><img
          alt="GitHub stars"
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
          alt="GitHub stars"
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
          alt="GitHub stars"
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
          alt="GitHub stars"
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
          alt="GitHub stars"
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
          alt="GitHub stars"
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
          alt="GitHub stars"
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
          alt="GitHub stars"
          src="https://img.shields.io/github/stars/vwxyzjn/cleanrl?style=social"
        />
      </a>
    </td>
    <td>Single-file implementation of deep RL algorithms.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/pytorch-labs/LeanRL/">
        pytorch-labs/LeanRL
        <br /><img
          alt="GitHub stars"
          src="https://img.shields.io/github/stars/pytorch-labs/LeanRL?style=social"
        />
      </a>
    </td>
    <td>Fork of CleanRL, optimized using PyTorch 2 features.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/pytorch/torchtitan">
        pytorch/torchtitan
        <br /><img
          alt="GitHub stars"
          src="https://img.shields.io/github/stars/pytorch/torchtitan?style=social"
        />
      </a>
    </td>
    <td>PyTorch-native platform for training generative AI models.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/KwaiVGI/LivePortrait">
        KwaiVGI/LivePortrait
        <br /><img
          alt="GitHub stars"
          src="https://img.shields.io/github/stars/KwaiVGI/LivePortrait?style=social"
        />
      </a>
    </td>
    <td>Stitching and retargeting for portraits.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/Physical-Intelligence/openpi/">
        Physical-Intelligence/openpi
        <br /><img
          alt="GitHub stars"
          src="https://img.shields.io/github/stars/Physical-Intelligence/openpi?style=social"
        />
      </a>
    </td>
    <td>Open-source models for robotics.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/mujocolab/mjlab">
        mujocolab/mjlab
        <br /><img
          alt="GitHub stars"
          src="https://img.shields.io/github/stars/mujocolab/mjlab?style=social"
        />
      </a>
    </td>
    <td>Lightweight, modular abstractions for RL and sim-to-real robotics.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/amazon-far/holosoma">
        amazon-far/holosoma
        <br /><img
          alt="GitHub stars"
          src="https://img.shields.io/github/stars/amazon-far/holosoma?style=social"
        />
      </a>
    </td>
    <td>Humanoid robotics framework for RL training and deployment.</td>
  </tr>
  <tr>
    <td>
      <a href="https://github.com/MalcolmMielle/bark_monitor">
        MalcolmMielle/bark_monitor
        <br /><img
          alt="GitHub stars"
          src="https://img.shields.io/github/stars/MalcolmMielle/bark_monitor?style=social"
        />
      </a>
    </td>
    <td>Show your neighbor that your dog doesn't bark!</td>
  </tr>
</table>

### Alternatives

`tyro` is opinionated. If any design decisions don't make sense, feel free to
file an issue!

You might also consider one of many alternative libraries. Some that we
like:

- [cappa](https://github.com/dancardin/cappa) offers a similar core feature
  set but with very different ergonomics. It looks polished and well-maintained!
- [cyclopts](https://github.com/BrianPugh/cyclopts) and
  [defopt](https://defopt.readthedocs.io/) has very comprehensive type
  annotation support and a heavier emphasis on subcommand generation.
- [simple-parsing](https://github.com/lebrice/SimpleParsing) and
  [jsonargparse](https://github.com/omni-us/jsonargparse) provide deeper
  integration with configuration file formats like YAML and JSON.
- [clipstick](https://github.com/sander76/clipstick), which focuses on
  simplicity + generating CLIs from Pydantic models.
- [datargs](https://github.com/roee30/datargs) provides a minimal API for
  dataclasses.
- [fire](https://github.com/google/python-fire) and
  [clize](https://github.com/epsy/clize) support arguments without type
  annotations.

There are also some options that directly extend `tyro`:

- [mininterface](https://github.com/CZ-NIC/mininterface) simultaneously generates
  GUI, TUI, web, CLI, and file-based program configuration.
- [manuscript](https://github.com/stllfe/manuscript) generates CLI interfaces from
  a simple block of configuration variables.

We also have some notes on `tyro`'s design goals and other alternatives in the
docs [here](https://brentyi.github.io/tyro/goals_and_alternatives/).
