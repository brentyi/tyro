# tyro

|coverage| |nbsp| |downloads| |nbsp| |versions|

:func:`tyro.cli()` generates CLI interfaces from type-annotated Python.

We can define configurable scripts using functions:

<div class="tyro-demo">
  <div class="panel">
    <div class="panel-header">
      <div class="panel-dots">
        <div class="panel-dot red"></div>
        <div class="panel-dot yellow"></div>
        <div class="panel-dot green"></div>
      </div>
      <div class="panel-title">script.py</div>
    </div>
    <div class="panel-content">
<pre><code><span class="highlight-comment"><span class="comment"># Write standard Python</span></span>
<span class="keyword">from</span> typing <span class="keyword">import</span> Literal

<span class="keyword">def</span> <span class="function">main</span>(
    name: <span class="builtin">str</span>,
    greet: Literal[<span class="string">"Hello"</span>, <span class="string">"Hi"</span>] = <span class="string">"Hi"</span>,
) -> <span class="builtin">None</span>:
    <span class="string">"""Print a greeting."""</span>
    <span class="builtin">print</span>(<span class="string">f"</span>{greet}, {name}!<span class="string">"</span>)

<span class="highlight-comment"><span class="comment"># Call tyro.cli()</span></span>
<span class="keyword">if</span> __name__ == <span class="string">"__main__"</span>:
    <span class="keyword">import</span> tyro
    tyro.cli(main)</code></pre>
    </div>
  </div>
  <div class="arrow">→</div>
  <div class="panel">
    <div class="panel-header">
      <div class="panel-dots">
        <div class="panel-dot red"></div>
        <div class="panel-dot yellow"></div>
        <div class="panel-dot green"></div>
      </div>
      <div class="panel-title">Terminal</div>
    </div>
    <div class="panel-content">
<pre><span class="highlight-comment"><span class="comment"># tyro CLI</span></span>
<span class="prompt">$ </span><span class="command">python script.py --help</span>
usage: script.py [-h] [OPTIONS]

Print a greeting.

<span class="h-dim">╭─ options ──────────────────────────────╮
│</span> -h, --help         <span class="h-dim">show help message</span>   <span class="h-dim">│
│</span> --name <span class="h-bold">STR</span>         <span class="h-red">(required)</span>          <span class="h-dim">│
│</span> --greet <span class="h-bold">{Hello,Hi}</span> <span class="h-cyan">(default: Hi)</span>       <span class="h-dim">│
╰────────────────────────────────────────╯</span>

<span class="prompt">$ </span><span class="command">python script.py --name World</span>
Hi, World!</pre>
    </div>
  </div>
</div>

Or using structures like dataclasses:

<div class="tyro-demo">
  <div class="panel">
    <div class="panel-header">
      <div class="panel-dots">
        <div class="panel-dot red"></div>
        <div class="panel-dot yellow"></div>
        <div class="panel-dot green"></div>
      </div>
      <div class="panel-title">script.py</div>
    </div>
    <div class="panel-content">
<pre><code><span class="highlight-comment"><span class="comment"># Write standard Python</span></span>
<span class="keyword">from</span> dataclasses <span class="keyword">import</span> dataclass
<span class="keyword">from</span> typing <span class="keyword">import</span> Literal

<span class="decorator">@dataclass</span>
<span class="keyword">class</span> <span class="function">Args</span>:
    <span class="string">"""Configure a greeting."""</span>
    name: <span class="builtin">str</span>
    greet: Literal[<span class="string">"Hello"</span>, <span class="string">"Hi"</span>] = <span class="string">"Hi"</span>

<span class="highlight-comment"><span class="comment"># Call tyro.cli()</span></span>
<span class="keyword">if</span> __name__ == <span class="string">"__main__"</span>:
    <span class="keyword">import</span> tyro
    args = tyro.cli(Args)
    <span class="builtin">print</span>(<span class="string">f"</span>{args.greet}, {args.name}!<span class="string">"</span>)</code></pre>
    </div>
  </div>
  <div class="arrow">→</div>
  <div class="panel">
    <div class="panel-header">
      <div class="panel-dots">
        <div class="panel-dot red"></div>
        <div class="panel-dot yellow"></div>
        <div class="panel-dot green"></div>
      </div>
      <div class="panel-title">Terminal</div>
    </div>
    <div class="panel-content">
<pre><span class="highlight-comment"><span class="comment"># tyro CLI</span></span>
<span class="prompt">$ </span><span class="command">python script.py --help</span>
usage: script.py [-h] [OPTIONS]

Configure a greeting.

<span class="h-dim">╭─ options ──────────────────────────────╮
│</span> -h, --help         <span class="h-dim">show help message</span>   <span class="h-dim">│
│</span> --name <span class="h-bold">STR</span>         <span class="h-red">(required)</span>          <span class="h-dim">│
│</span> --greet <span class="h-bold">{Hello,Hi}</span> <span class="h-cyan">(default: Hi)</span>       <span class="h-dim">│
╰────────────────────────────────────────╯</span>

<span class="prompt">$ </span><span class="command">python script.py --name World</span>
Hi, World!</pre>
    </div>
  </div>
</div>

Other features include helptext generation, nested structures, subcommands, and
shell completion.

#### Why `tyro`?

1. **Define things once.** Standard Python type annotations, docstrings, and default values are parsed to automatically generate command-line interfaces with nice helptext.

2. **Static types.** Unlike tools dependent on dictionaries, YAML, or dynamic
   namespaces, arguments populated by `tyro` are better undestood by IDEs and
   language servers, as well as static checking tools like `pyright` and `mypy`.

3. **Modularity.** `tyro` supports hierarchical configurations, which make it
   easy to decentralize definitions, defaults, and documentation.

<!-- prettier-ignore-start -->

.. toctree::
   :caption: Getting started
   :hidden:
   :maxdepth: 1
   :titlesonly:

   installation
   your_first_cli
   whats_supported

.. toctree::
   :caption: Examples
   :hidden:
   :titlesonly:

   ./examples/basics.rst
   ./examples/hierarchical_structures.rst
   ./examples/subcommands.rst
   ./examples/overriding_configs.rst
   ./examples/generics.rst
   ./examples/custom_constructors.rst
   ./examples/pytorch_jax.rst


.. toctree::
   :caption: Notes
   :hidden:
   :maxdepth: 5
   :glob:

   goals_and_alternatives
   helptext_generation
   tab_completion
   wandb_sweeps


.. toctree::
   :caption: API Reference
   :hidden:
   :maxdepth: 5
   :titlesonly:

   api/tyro/index



.. |downloads| image:: https://static.pepy.tech/personalized-badge/tyro?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=GREEN&left_text=downloads
   :alt: Download count icon
   :target: https://pypi.org/project/tyro/
.. |coverage| image:: https://codecov.io/gh/brentyi/tyro/branch/main/graph/badge.svg
   :alt: Test coverage status icon
   :target: https://codecov.io/gh/brentyi/tyro
.. |versions| image:: https://img.shields.io/pypi/pyversions/tyro
   :alt: Version icon
   :target: https://pypi.org/project/tyro/
.. |nbsp| unicode:: 0xA0
   :trim:

<!-- prettier-ignore-end -->
